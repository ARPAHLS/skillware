import json
import os
import re
import requests
import glob
import yaml
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from skillware.core.base_skill import BaseSkill
from skillware.core.evm_config import load_merged_evm_config, resolve_chain

_ETH_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
_ZERO_WIDTH_CHARS = "\u200b\u200c\u200d\ufeff"
# Major tokens for volume reporting; addresses come from evm.tokens / chain.weth.
_MAJOR_TOKEN_SYMBOLS = ("usdt", "usdc", "dai", "weth")
_REPORT_SCHEMA_VERSION = "2.0"
_VERDICT_STATEMENTS = {
    "DIRECT_SANCTIONS_MATCH": (
        "Screened address matches a bundled sanctions or watchlist record."
    ),
    "MALICIOUS_OR_INDIRECT_EXPOSURE": (
        "Direct malicious-contract interaction or hop-1 sanctioned counterparty detected."
    ),
    "PHISHING_OR_SCAM_EXPOSURE": (
        "Interaction with a reported phishing or scam contract; no direct sanctions hit."
    ),
    "CLEAN_RECORD": (
        "No direct sanctions or malicious contract interactions detected."
    ),
}


class WalletScreeningSkill(BaseSkill):
    """
    A specific implementation of a compliance skill that screens Ethereum wallets
    against sanctions lists and malicious contract databases.
    """

    # Etherscan account.* pagination (see api.etherscan.io docs).
    ETHERSCAN_TX_PAGE_OFFSET = 1000
    ETHERSCAN_TX_MAX_PAGES = 10  # cap: 10_000 rows per action per screen
    ETHERSCAN_API_URL = "https://api.etherscan.io/api"
    SCREENING_CHAIN = "ethereum"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.etherscan_api_key = self.credential("ETHERSCAN_API_KEY")

        # Config
        self.data_dir = os.path.join(os.path.dirname(__file__), "data")
        self.coingecko_url_eur = "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=eur"
        self.coingecko_url_usd = "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd"

        # Load Core Datasets
        self.malicious_contracts = self._load_json_file("malicious_scs_2025.json") or []
        self.sanctions_entities = self._load_json_lines("entities.ftm.json") or []

        # Load Additional Datasets dynamically (normalized files, etc.)
        self.additional_datasets = self._load_additional_datasets()

        # ETH address -> sanctions records (built once; O(1) lookup per screen)
        self._sanctions_index: Dict[str, List[Dict]] = {}
        self._build_sanctions_index()
        # ETH address -> tx risk records (core malicious + normalized lists)
        self._tx_risk_index: Dict[str, List[Dict]] = {}
        self._build_tx_risk_index()
        # symbol -> {address, decimals} for ethereum major tokens (evm_config)
        self._major_tokens = self._load_major_tokens()

    @property
    def manifest(self) -> Dict[str, Any]:
        manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {}

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        address = self.normalize_eth_address(params.get("address") or "")
        if not address:
            return {"error": "Invalid Ethereum address provided."}

        if not self.etherscan_api_key:
            return {"error": "Missing ETHERSCAN_API_KEY environment variable."}

        # 1. Fetch Data (normal ETH, ERC-20, and internal)
        txs, eth_warnings = self._get_eth_transactions(address)
        token_txs, token_warnings = self._get_erc20_transactions(address)
        internal_txs, internal_warnings = self._get_internal_transactions(address)
        fetch_warnings = eth_warnings + token_warnings + internal_warnings

        eth_balance = self._get_eth_balance(address)
        eth_usd = self._get_price(self.coingecko_url_usd, "usd")
        eth_eur = self._get_price(self.coingecko_url_eur, "eur")

        # 2. Sanctions Check (FTM + additional lists via index)
        sanctions_hits = self._lookup_sanctions_hits(address)

        # 3. Analyze Transactions (ETH + ERC-20 + internal)
        analysis = self._analyze_transactions(
            txs, address, token_txs=token_txs, internal_txs=internal_txs
        )

        # 4. Construct Rich Report
        return self._generate_report_data(
            address=address,
            analysis=analysis,
            sanctions_hits=sanctions_hits,
            eth_balance=eth_balance,
            eth_usd=eth_usd,
            eth_eur=eth_eur,
            txs_count=len(txs),
            warnings=fetch_warnings,
        )

    # --- Loader Helpers ---

    def _load_json_file(self, filename: str) -> Any:
        path = os.path.join(self.data_dir, filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def _load_json_lines(self, filename: str) -> List[Any]:
        path = os.path.join(self.data_dir, filename)
        entities = []
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entities.append(json.loads(line))
                        except Exception:
                            pass
        return entities

    def _load_additional_datasets(self) -> List[Dict]:
        """Loads all other JSON files in data_dir not explicitly loaded."""
        all_entries = []
        exclude = [
            "malicious_scs_2025.json",
            "entities.ftm.json",
            # Snapshot metadata, not screenable wallet rows.
            "ofac_sdn_manifest.json",
            "ofac_sdn_quarantine.json",
        ]
        for fname in glob.glob(os.path.join(self.data_dir, "*.json")):
            if os.path.basename(fname) in exclude:
                continue

            try:
                base_name = os.path.basename(fname)
                with open(fname, "r", encoding="utf-8") as f:
                    first = f.read(1)
                    f.seek(0)
                    data = []
                    if first == "[":
                        data = json.load(f)
                    else:
                        for line in f:
                            if line.strip():
                                try:
                                    data.append(json.loads(line))
                                except Exception:
                                    pass

                    # Tag entries with source file
                    if isinstance(data, list):
                        for entry in data:
                            if isinstance(entry, dict):
                                entry["__source_file__"] = base_name
                                all_entries.append(entry)
            except Exception as e:
                print(f"Error loading {fname}: {e}")
        return all_entries

    # --- API Helpers ---

    @staticmethod
    def normalize_eth_address(address: str) -> Optional[str]:
        """Normalize and validate an Ethereum address (EIP-55 checksum not required)."""
        if not isinstance(address, str):
            return None
        cleaned = address.strip().translate({ord(c): None for c in _ZERO_WIDTH_CHARS})
        if not cleaned.lower().startswith("0x"):
            return None
        normalized = "0x" + cleaned[2:].lower()
        if _ETH_ADDRESS_RE.match(normalized):
            return normalized
        return None

    @staticmethod
    def _iter_property_values(properties: Dict, key: str):
        raw = properties.get(key)
        if raw is None:
            return
        if isinstance(raw, list):
            for item in raw:
                if item is not None:
                    yield str(item)
        else:
            yield str(raw)

    def _eth_addresses_from_record(self, record: Dict) -> List[str]:
        """Collect normalized Ethereum addresses from a sanctions or FTM record."""
        found: List[str] = []
        if "addresses" in record and isinstance(record["addresses"], list):
            for a in record["addresses"]:
                norm = self.normalize_eth_address(str(a))
                if norm:
                    found.append(norm)

        properties = record.get("properties") or {}
        if isinstance(properties, dict):
            for key in ("address", "publicKey"):
                for value in self._iter_property_values(properties, key):
                    for part in value.split(","):
                        norm = self.normalize_eth_address(part)
                        if norm:
                            found.append(norm)

        if "address" in record and not isinstance(record["address"], list):
            norm = self.normalize_eth_address(str(record["address"]))
            if norm:
                found.append(norm)

        return list(dict.fromkeys(found))

    def _build_sanctions_index(self) -> None:
        """Index normalized ETH addresses from FTM and additional datasets."""
        index: Dict[str, List[Dict]] = {}
        for entity in self.sanctions_entities:
            addrs = self._eth_addresses_from_record(entity)
            if not addrs:
                continue
            tagged = dict(entity)
            tagged["__source_file__"] = "entities.ftm.json"
            for addr in addrs:
                index.setdefault(addr, []).append(tagged)

        for entry in self.additional_datasets:
            addrs = self._eth_addresses_from_record(entry)
            if not addrs:
                continue
            tagged = dict(entry)
            for addr in addrs:
                index.setdefault(addr, []).append(tagged)

        self._sanctions_index = index

    def _lookup_sanctions_hits(self, address: str) -> List[Dict]:
        normalized = self.normalize_eth_address(address)
        if not normalized:
            return []
        return list(self._sanctions_index.get(normalized, []))

    @staticmethod
    def _severity_rank(value: str) -> int:
        order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        return order.get(str(value).lower(), 0)

    def _record_to_tx_risk_entry(self, record: Dict) -> Dict[str, Any]:
        return {
            "contract_name": record.get("name")
            or record.get("label")
            or record.get("caption")
            or "Unknown",
            "severity": (record.get("severity") or "high").lower(),
            "category": record.get("category") or record.get("reason") or "malicious",
            "source_file": record.get("__source_file__", "malicious_scs_2025.json"),
            "jurisdictions": record.get("jurisdictions_blocked", []),
        }

    def _build_tx_risk_index(self) -> None:
        """Index normalized ETH addresses used for tx-level risk screening."""
        index: Dict[str, List[Dict]] = {}
        for record in self.malicious_contracts:
            if not isinstance(record, dict):
                continue
            for addr in self._eth_addresses_from_record(record):
                index.setdefault(addr, []).append(self._record_to_tx_risk_entry(record))

        for record in self.additional_datasets:
            if not isinstance(record, dict):
                continue
            source = str(record.get("__source_file__", "")).lower()
            if (
                "uniswap_trm" not in source
                and "trm" not in source
                and "malicious" not in source
            ):
                continue
            for addr in self._eth_addresses_from_record(record):
                index.setdefault(addr, []).append(self._record_to_tx_risk_entry(record))

        self._tx_risk_index = index

    def _lookup_tx_risk_entries(self, address: str) -> List[Dict]:
        normalized = self.normalize_eth_address(address)
        if not normalized:
            return []
        return list(self._tx_risk_index.get(normalized, []))

    def _load_major_tokens(self) -> Dict[str, Dict[str, Any]]:
        """Resolve USDT/USDC/DAI/WETH from operator evm.tokens (ethereum)."""
        resolved: Dict[str, Dict[str, Any]] = {}
        try:
            merged = load_merged_evm_config()
            chain_tokens = merged.tokens.get(self.SCREENING_CHAIN, {})
            if isinstance(chain_tokens, dict):
                for symbol in _MAJOR_TOKEN_SYMBOLS:
                    meta = chain_tokens.get(symbol)
                    if not isinstance(meta, dict):
                        continue
                    addr = self.normalize_eth_address(str(meta.get("address") or ""))
                    if not addr:
                        continue
                    decimals = meta.get("decimals")
                    try:
                        decimals_i = int(decimals) if decimals is not None else 18
                    except (TypeError, ValueError):
                        decimals_i = 18
                    resolved[symbol] = {"address": addr, "decimals": decimals_i}
            if "weth" not in resolved:
                try:
                    chain = resolve_chain(self.SCREENING_CHAIN, require_enabled=False)
                    weth = self.normalize_eth_address(str(chain.get("weth") or ""))
                    if weth:
                        resolved["weth"] = {"address": weth, "decimals": 18}
                except ValueError:
                    pass
        except Exception:
            return resolved
        return resolved

    def _major_token_by_address(self) -> Dict[str, str]:
        return {meta["address"]: symbol for symbol, meta in self._major_tokens.items()}

    def _get_price(self, url: str, currency: str) -> float:
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
            return data.get("ethereum", {}).get(currency, 0.0)
        except Exception:
            return 0.0

    def _paginate_account_action(
        self, address: str, action: str, warning_prefix: str
    ) -> Tuple[List[Dict], List[str]]:
        """Paginate an Etherscan account.* list action with shared warning codes."""
        warnings: List[str] = []
        all_rows: List[Dict] = []
        page = 1

        while page <= self.ETHERSCAN_TX_MAX_PAGES:
            params = {
                "module": "account",
                "action": action,
                "address": address,
                "startblock": 0,
                "endblock": 99999999,
                "page": page,
                "offset": self.ETHERSCAN_TX_PAGE_OFFSET,
                "sort": "asc",
                "apikey": self.etherscan_api_key,
            }
            try:
                resp = requests.get(self.ETHERSCAN_API_URL, params=params, timeout=15)
                data = resp.json()
            except Exception:
                warnings.append(
                    f"{warning_prefix}_unavailable"
                    if page == 1
                    else f"{warning_prefix}_partial"
                )
                break

            if data.get("status") != "1":
                message = str(data.get("message", "")).lower()
                if page == 1 and "no transactions found" in message:
                    return [], warnings
                warnings.append(
                    f"{warning_prefix}_unavailable"
                    if page == 1
                    else f"{warning_prefix}_partial"
                )
                break

            batch = data.get("result")
            if not isinstance(batch, list):
                warnings.append(f"{warning_prefix}_unavailable")
                break

            all_rows.extend(batch)
            if len(batch) < self.ETHERSCAN_TX_PAGE_OFFSET:
                break
            if page >= self.ETHERSCAN_TX_MAX_PAGES:
                warnings.append(f"{warning_prefix}_truncated")
                break
            page += 1

        return all_rows, warnings

    def _get_eth_transactions(self, address: str) -> Tuple[List[Dict], List[str]]:
        """Fetch normal ETH txs from Etherscan with pagination and warning codes."""
        return self._paginate_account_action(address, "txlist", "etherscan_txlist")

    def _get_erc20_transactions(self, address: str) -> Tuple[List[Dict], List[str]]:
        """Fetch ERC-20 token transfers (account.tokentx)."""
        return self._paginate_account_action(address, "tokentx", "etherscan_tokentx")

    def _get_internal_transactions(self, address: str) -> Tuple[List[Dict], List[str]]:
        """Fetch internal ETH transfers (account.txlistinternal)."""
        return self._paginate_account_action(
            address, "txlistinternal", "etherscan_txlistinternal"
        )

    def _get_eth_balance(self, address: str) -> float:
        params = {
            "module": "account",
            "action": "balance",
            "address": address,
            "tag": "latest",
            "apikey": self.etherscan_api_key,
        }
        try:
            resp = requests.get(self.ETHERSCAN_API_URL, params=params, timeout=10)
            data = resp.json()
            if data.get("status") == "1":
                return int(data["result"]) / 1e18
        except Exception:
            pass
        return 0.0

    # --- Logic Helpers ---

    def _append_risk_interaction(
        self,
        bucket: List[Dict],
        *,
        tx: Dict,
        wallet_addr: str,
        from_addr: str,
        to_addr: str,
        transfer_kind: str,
        value_eth: Optional[float] = None,
        token_symbol: Optional[str] = None,
        token_amount: Optional[float] = None,
        contract_address: Optional[str] = None,
    ) -> None:
        candidates = [to_addr, from_addr]
        if contract_address:
            candidates.append(contract_address)
        other_party = None
        tx_risk_entries: List[Dict] = []
        for candidate in candidates:
            if not candidate:
                continue
            hits = self._lookup_tx_risk_entries(candidate)
            if hits:
                other_party = candidate
                tx_risk_entries = hits
                break
        if not other_party or not tx_risk_entries:
            return

        primary = max(
            tx_risk_entries,
            key=lambda item: self._severity_rank(item.get("severity", "")),
        )
        sources = sorted(
            {entry.get("source_file", "Unknown") for entry in tx_risk_entries}
        )
        entry: Dict[str, Any] = {
            "tx_hash": tx.get("hash"),
            "other_party": other_party,
            "direction": "out" if from_addr == wallet_addr else "in",
            "transfer_kind": transfer_kind,
            "contract_name": primary.get("contract_name"),
            "severity": primary.get("severity"),
            "jurisdictions": primary.get("jurisdictions", []),
            "source_file": primary.get("source_file"),
            "sources": sources,
        }
        if value_eth is not None:
            entry["value_eth"] = value_eth
        if token_symbol is not None:
            entry["token_symbol"] = token_symbol
        if token_amount is not None:
            entry["token_amount"] = token_amount
        if contract_address:
            entry["token_contract"] = contract_address
        bucket.append(entry)

    def _analyze_transactions(
        self,
        txs: List[Dict],
        wallet_addr: str,
        token_txs: Optional[List[Dict]] = None,
        internal_txs: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        wallet_addr = wallet_addr.lower()
        token_txs = token_txs or []
        internal_txs = internal_txs or []
        value_in = 0.0
        value_out = 0.0
        gas_paid = 0.0
        counterparty_counts: Dict[str, int] = {}
        malicious_interactions: List[Dict] = []
        major_by_addr = self._major_token_by_address()
        token_volumes: Dict[str, float] = {symbol: 0.0 for symbol in self._major_tokens}

        for tx in txs:
            from_addr = (tx.get("from") or "").lower()
            to_addr = (tx.get("to") or "").lower()

            try:
                value_eth = int(tx.get("value", "0")) / 1e18
            except Exception:
                value_eth = 0.0

            if tx.get("isError", "0") == "1":
                continue

            if from_addr == wallet_addr:
                try:
                    gas = (
                        int(tx.get("gasUsed", "0"))
                        * int(tx.get("gasPrice", "0"))
                        / 1e18
                    )
                    gas_paid += gas
                except Exception:
                    pass

            self._append_risk_interaction(
                malicious_interactions,
                tx=tx,
                wallet_addr=wallet_addr,
                from_addr=from_addr,
                to_addr=to_addr,
                transfer_kind="eth",
                value_eth=value_eth,
            )

            if to_addr == wallet_addr:
                value_in += value_eth
                counterparty = from_addr
            elif from_addr == wallet_addr:
                value_out += value_eth
                counterparty = to_addr
            else:
                counterparty = None

            if counterparty:
                counterparty_counts[counterparty] = (
                    counterparty_counts.get(counterparty, 0) + 1
                )

        for tx in internal_txs:
            from_addr = (tx.get("from") or "").lower()
            to_addr = (tx.get("to") or "").lower()
            if tx.get("isError", "0") == "1":
                continue
            try:
                value_eth = int(tx.get("value", "0")) / 1e18
            except Exception:
                value_eth = 0.0

            self._append_risk_interaction(
                malicious_interactions,
                tx=tx,
                wallet_addr=wallet_addr,
                from_addr=from_addr,
                to_addr=to_addr,
                transfer_kind="internal",
                value_eth=value_eth,
            )

            if to_addr == wallet_addr:
                value_in += value_eth
                counterparty = from_addr
            elif from_addr == wallet_addr:
                value_out += value_eth
                counterparty = to_addr
            else:
                counterparty = None
            if counterparty:
                counterparty_counts[counterparty] = (
                    counterparty_counts.get(counterparty, 0) + 1
                )

        for tx in token_txs:
            from_addr = (tx.get("from") or "").lower()
            to_addr = (tx.get("to") or "").lower()
            contract = self.normalize_eth_address(str(tx.get("contractAddress") or ""))
            symbol_key = major_by_addr.get(contract or "")
            try:
                decimals = int(tx.get("tokenDecimal") or "18")
            except Exception:
                decimals = 18
            if symbol_key and symbol_key in self._major_tokens:
                decimals = int(self._major_tokens[symbol_key]["decimals"])
            try:
                amount = int(tx.get("value", "0")) / (10**decimals)
            except Exception:
                amount = 0.0

            token_symbol = (
                symbol_key.upper()
                if symbol_key
                else (tx.get("tokenSymbol") or "UNKNOWN")
            )
            self._append_risk_interaction(
                malicious_interactions,
                tx=tx,
                wallet_addr=wallet_addr,
                from_addr=from_addr,
                to_addr=to_addr,
                transfer_kind="erc20",
                token_symbol=token_symbol,
                token_amount=amount,
                contract_address=contract,
            )

            if symbol_key and (from_addr == wallet_addr or to_addr == wallet_addr):
                token_volumes[symbol_key] = token_volumes.get(symbol_key, 0.0) + amount

            if to_addr == wallet_addr:
                counterparty = from_addr
            elif from_addr == wallet_addr:
                counterparty = to_addr
            else:
                counterparty = None
            if counterparty:
                counterparty_counts[counterparty] = (
                    counterparty_counts.get(counterparty, 0) + 1
                )

        most_interacted = None
        if counterparty_counts:
            most_interacted = max(counterparty_counts.items(), key=lambda x: x[1])

        return {
            "total_txs": len(txs),
            "total_token_txs": len(token_txs),
            "total_internal_txs": len(internal_txs),
            "value_in": value_in,
            "value_out": value_out,
            "gas_paid": gas_paid,
            "malicious_interactions": malicious_interactions,
            "counterparty_counts": counterparty_counts,
            "most_interacted": most_interacted,
            "token_volumes": token_volumes,
        }

    def _summarize_sanctions(self, hits: List[Dict]) -> List[Dict]:
        summary = []
        for entity in hits:
            label = entity.get("label") or entity.get("properties", {}).get(
                "name", "Unknown"
            )
            jurisdiction = entity.get("jurisdiction") or entity.get(
                "properties", {}
            ).get("country", "Unknown")
            reason = entity.get("reason") or entity.get("properties", {}).get(
                "reason", "N/A"
            )
            source_file = entity.get("__source_file__", "Unknown")
            summary.append(
                {
                    "label": label,
                    "jurisdiction": jurisdiction,
                    "reason": reason,
                    "source_file": source_file,
                }
            )
        return summary

    def _collect_indirect_exposures(
        self, counterparty_counts: Dict[str, int], wallet_addr: str
    ) -> List[Dict[str, Any]]:
        """Hop-1: screen direct counterparties against the sanctions index."""
        wallet = (wallet_addr or "").lower()
        exposures: List[Dict[str, Any]] = []
        for counterparty, tx_count in sorted(
            counterparty_counts.items(), key=lambda item: (-item[1], item[0])
        ):
            if not counterparty or counterparty == wallet:
                continue
            hits = self._lookup_sanctions_hits(counterparty)
            if not hits:
                continue
            summarized = self._summarize_sanctions(hits)
            primary = summarized[0] if summarized else {}
            exposures.append(
                {
                    "counterparty": counterparty,
                    "tx_count": tx_count,
                    "label": primary.get("label"),
                    "jurisdiction": primary.get("jurisdiction"),
                    "reason": primary.get("reason"),
                    "source_file": primary.get("source_file"),
                    "sanctions_hits": summarized,
                }
            )
        return exposures

    @staticmethod
    def compute_risk_level(
        sanctions_hits: List[Dict],
        malicious_interactions: List[Dict],
        indirect_exposures: List[Dict],
    ) -> Tuple[str, str, str]:
        """Return ``(risk_level, decision, reason_code)`` for schema v2 verdicts."""
        if sanctions_hits:
            return ("critical", "DENY", "DIRECT_SANCTIONS_MATCH")

        if indirect_exposures:
            return ("high", "DENY", "MALICIOUS_OR_INDIRECT_EXPOSURE")

        if malicious_interactions:
            ranks = [
                WalletScreeningSkill._severity_rank(item.get("severity", ""))
                for item in malicious_interactions
            ]
            if any(rank >= 3 for rank in ranks):
                return ("high", "DENY", "MALICIOUS_OR_INDIRECT_EXPOSURE")
            return ("medium", "REVIEW", "PHISHING_OR_SCAM_EXPOSURE")

        return ("low", "ALLOW", "CLEAN_RECORD")

    def _build_risk_factors(
        self,
        sanctions_summary: List[Dict],
        malicious_interactions: List[Dict],
        indirect_exposures: List[Dict],
    ) -> List[Dict[str, Any]]:
        factors: List[Dict[str, Any]] = []
        for hit in sanctions_summary:
            factors.append(
                {
                    "code": "DIRECT_SANCTIONS_MATCH",
                    "severity": "critical",
                    "evidence": {
                        "label": hit.get("label"),
                        "source_file": hit.get("source_file"),
                        "jurisdiction": hit.get("jurisdiction"),
                    },
                }
            )
        for exposure in indirect_exposures:
            factors.append(
                {
                    "code": "HOP1_SANCTIONS_COUNTERPARTY",
                    "severity": "high",
                    "evidence": {
                        "counterparty": exposure.get("counterparty"),
                        "tx_count": exposure.get("tx_count"),
                        "label": exposure.get("label"),
                        "source_file": exposure.get("source_file"),
                    },
                }
            )
        for interaction in malicious_interactions:
            severity = (interaction.get("severity") or "high").lower()
            factors.append(
                {
                    "code": "MALICIOUS_CONTRACT_INTERACTION",
                    "severity": severity,
                    "evidence": {
                        "other_party": interaction.get("other_party"),
                        "transfer_kind": interaction.get("transfer_kind"),
                        "contract_name": interaction.get("contract_name"),
                        "tx_hash": interaction.get("tx_hash"),
                        "source_file": interaction.get("source_file"),
                    },
                }
            )
        return factors

    def _generate_report_data(
        self,
        address,
        analysis,
        sanctions_hits,
        eth_balance,
        eth_usd,
        eth_eur,
        txs_count,
        warnings=None,
    ):
        warnings = warnings or []
        pnl = analysis["value_out"] - analysis["value_in"] - analysis["gas_paid"]
        pnl_pct = (
            ((pnl) / analysis["value_in"] * 100) if analysis["value_in"] > 0 else 0.0
        )

        sanctions_summary = self._summarize_sanctions(sanctions_hits)
        malicious = analysis["malicious_interactions"]
        indirect_exposures = self._collect_indirect_exposures(
            analysis.get("counterparty_counts") or {}, address
        )
        risk_level, decision, reason_code = self.compute_risk_level(
            sanctions_hits, malicious, indirect_exposures
        )
        risk_factors = self._build_risk_factors(
            sanctions_summary, malicious, indirect_exposures
        )

        top_counterparties = sorted(
            [(k, v) for k, v in analysis.get("counterparty_counts", {}).items()],
            key=lambda x: -x[1],
        )[:10]

        risky_counterparties = [
            {
                "address": row["counterparty"],
                "tx_count": row["tx_count"],
                "label": row.get("label"),
                "reason": row.get("reason"),
                "source_file": row.get("source_file"),
            }
            for row in indirect_exposures
        ]

        metadata: Dict[str, Any] = {
            "screening_time": datetime.now().isoformat(),
            "wallet_address": address,
            "chain": self.SCREENING_CHAIN,
            "mode": "full_forensics",
            "data_sources_count": len(self.additional_datasets) + 2,
        }
        if warnings:
            metadata["warnings"] = warnings

        token_volumes = analysis.get("token_volumes") or {}
        token_flow = {
            f"{symbol}_volume": round(float(volume), 8)
            for symbol, volume in sorted(token_volumes.items())
            if volume
        }

        risk_flag = risk_level in {"critical", "high", "medium"}

        return {
            "schema_version": _REPORT_SCHEMA_VERSION,
            "metadata": metadata,
            "verdict": {
                "decision": decision,
                "risk_level": risk_level,
                "reason_code": reason_code,
                "summary_statement": _VERDICT_STATEMENTS[reason_code],
            },
            "summary": {
                "risk_level": risk_level,
                # Backward-compatible alias for v1 hosts.
                "risk_flag": risk_flag,
                "sanctioned_entity_match": bool(sanctions_hits),
                "malicious_interaction_count": len(malicious),
                "indirect_exposure_count": len(indirect_exposures),
                "balance_eth": eth_balance,
                "balance_usd": eth_balance * eth_usd,
                # Backward-compatible: normal ETH txlist count only.
                "total_transactions": txs_count,
                "total_token_txs": analysis.get("total_token_txs", 0),
                "total_internal_txs": analysis.get("total_internal_txs", 0),
            },
            "financial_analysis": {
                "value_in_eth": analysis["value_in"],
                "value_in_usd": analysis["value_in"] * eth_usd,
                "value_out_eth": analysis["value_out"],
                "value_out_usd": analysis["value_out"] * eth_usd,
                "gas_paid_eth": analysis["gas_paid"],
                "pnl_eth": pnl,
                "pnl_usd": pnl * eth_usd,
                "pnl_percent": pnl_pct,
                "value_in_eur": analysis["value_in"] * eth_eur,
                "value_out_eur": analysis["value_out"] * eth_eur,
                "token_flow": token_flow,
            },
            "risk_details": {
                "sanctions_hits": sanctions_summary,
                "malicious_interactions": malicious,
                "indirect_exposures": indirect_exposures,
            },
            "risk_factors": risk_factors,
            "network_analysis": {
                "most_interacted_wallet": analysis["most_interacted"],
                "top_10_counterparties": top_counterparties,
                "risky_counterparties": risky_counterparties,
            },
        }
