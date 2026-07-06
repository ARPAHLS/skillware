import json
import os
import re
import requests
import glob
import yaml
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from skillware.core.base_skill import BaseSkill

_ETH_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
_ZERO_WIDTH_CHARS = "\u200b\u200c\u200d\ufeff"


class WalletScreeningSkill(BaseSkill):
    """
    A specific implementation of a compliance skill that screens Ethereum wallets
    against sanctions lists and malicious contract databases.
    """

    # Etherscan account.txlist pagination (see api.etherscan.io docs).
    ETHERSCAN_TX_PAGE_OFFSET = 1000
    ETHERSCAN_TX_MAX_PAGES = 10  # cap: 10_000 normal txs per screen

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.etherscan_api_key = os.environ.get("ETHERSCAN_API_KEY")
        if not self.etherscan_api_key and self.config:
            self.etherscan_api_key = self.config.get("ETHERSCAN_API_KEY")

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

        # 1. Fetch Data
        txs, fetch_warnings = self._get_eth_transactions(address)
        eth_balance = self._get_eth_balance(address)
        eth_usd = self._get_price(self.coingecko_url_usd, "usd")
        eth_eur = self._get_price(self.coingecko_url_eur, "eur")

        # 2. Sanctions Check (FTM + additional lists via index)
        sanctions_hits = self._lookup_sanctions_hits(address)

        # 3. Analyze Transactions
        analysis = self._analyze_transactions(txs, address)

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
        exclude = ["malicious_scs_2025.json", "entities.ftm.json"]
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

    def _get_price(self, url: str, currency: str) -> float:
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
            return data.get("ethereum", {}).get(currency, 0.0)
        except Exception:
            return 0.0

    def _get_eth_transactions(self, address: str) -> Tuple[List[Dict], List[str]]:
        """Fetch normal ETH txs from Etherscan with pagination and warning codes."""
        url = "https://api.etherscan.io/api"
        warnings: List[str] = []
        all_txs: List[Dict] = []
        page = 1

        while page <= self.ETHERSCAN_TX_MAX_PAGES:
            params = {
                "module": "account",
                "action": "txlist",
                "address": address,
                "startblock": 0,
                "endblock": 99999999,
                "page": page,
                "offset": self.ETHERSCAN_TX_PAGE_OFFSET,
                "sort": "asc",
                "apikey": self.etherscan_api_key,
            }
            try:
                resp = requests.get(url, params=params, timeout=15)
                data = resp.json()
            except Exception:
                warnings.append(
                    "etherscan_txlist_unavailable"
                    if page == 1
                    else "etherscan_txlist_partial"
                )
                break

            if data.get("status") != "1":
                message = str(data.get("message", "")).lower()
                if page == 1 and "no transactions found" in message:
                    return [], warnings
                warnings.append(
                    "etherscan_txlist_unavailable"
                    if page == 1
                    else "etherscan_txlist_partial"
                )
                break

            batch = data.get("result")
            if not isinstance(batch, list):
                warnings.append("etherscan_txlist_unavailable")
                break

            all_txs.extend(batch)
            if len(batch) < self.ETHERSCAN_TX_PAGE_OFFSET:
                break
            if page >= self.ETHERSCAN_TX_MAX_PAGES:
                warnings.append("etherscan_txlist_truncated")
                break
            page += 1

        return all_txs, warnings

    def _get_eth_balance(self, address: str) -> float:
        url = "https://api.etherscan.io/api"
        params = {
            "module": "account",
            "action": "balance",
            "address": address,
            "tag": "latest",
            "apikey": self.etherscan_api_key,
        }
        try:
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            if data.get("status") == "1":
                return int(data["result"]) / 1e18
        except Exception:
            pass
        return 0.0

    # --- Logic Helpers ---

    def _analyze_transactions(
        self, txs: List[Dict], wallet_addr: str
    ) -> Dict[str, Any]:
        wallet_addr = wallet_addr.lower()
        value_in = 0.0
        value_out = 0.0
        gas_paid = 0.0
        counterparty_counts = {}
        malicious_interactions = []

        for tx in txs:
            from_addr = tx.get("from", "").lower()
            to_addr = tx.get("to", "").lower() if tx.get("to") else ""

            try:
                value_eth = int(tx.get("value", "0")) / 1e18
            except Exception:
                value_eth = 0.0

            is_error = tx.get("isError", "0") == "1"
            if is_error:
                continue

            # Gas
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

            # Malicious Check
            other_party = None
            tx_risk_entries: List[Dict] = []
            if to_addr:
                tx_risk_entries = self._lookup_tx_risk_entries(to_addr)
                if tx_risk_entries:
                    other_party = to_addr
            if not tx_risk_entries and from_addr:
                tx_risk_entries = self._lookup_tx_risk_entries(from_addr)
                if tx_risk_entries:
                    other_party = from_addr

            if other_party and tx_risk_entries:
                primary = max(
                    tx_risk_entries,
                    key=lambda item: self._severity_rank(item.get("severity", "")),
                )
                sources = sorted(
                    {entry.get("source_file", "Unknown") for entry in tx_risk_entries}
                )
                malicious_interactions.append(
                    {
                        "tx_hash": tx.get("hash"),
                        "other_party": other_party,
                        "direction": "out" if from_addr == wallet_addr else "in",
                        "contract_name": primary.get("contract_name"),
                        "severity": primary.get("severity"),
                        "jurisdictions": primary.get("jurisdictions", []),
                        "source_file": primary.get("source_file"),
                        "sources": sources,
                        "value_eth": value_eth,
                    }
                )

            # Flow
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

        most_interacted = None
        if counterparty_counts:
            most_interacted = max(counterparty_counts.items(), key=lambda x: x[1])

        return {
            "total_txs": len(txs),
            "value_in": value_in,
            "value_out": value_out,
            "gas_paid": gas_paid,
            "malicious_interactions": malicious_interactions,
            "counterparty_counts": counterparty_counts,
            "most_interacted": most_interacted,
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
                    # 'entity': entity # simplified for AI token usage, normally full entity is heavy
                }
            )
        return summary

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

        # Create structured summaries
        sanctions_summary = self._summarize_sanctions(sanctions_hits)

        # Format Top Counterparties
        top_counterparties = sorted(
            [(k, v) for k, v in analysis.get("counterparty_counts", {}).items()],
            key=lambda x: -x[1],
        )[:10]

        metadata: Dict[str, Any] = {
            "screening_time": datetime.now().isoformat(),
            "wallet_address": address,
            "data_sources_count": len(self.additional_datasets) + 2,
        }
        if warnings:
            metadata["warnings"] = warnings

        return {
            "metadata": metadata,
            "summary": {
                "risk_flag": bool(sanctions_hits)
                or bool(analysis["malicious_interactions"]),
                "sanctioned_entity_match": bool(sanctions_hits),
                "malicious_interaction_count": len(analysis["malicious_interactions"]),
                "balance_eth": eth_balance,
                "balance_usd": eth_balance * eth_usd,
                "total_transactions": txs_count,
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
            },
            "risk_details": {
                "sanctions_hits": sanctions_summary,
                "malicious_interactions": analysis["malicious_interactions"],
            },
            "network_analysis": {
                "most_interacted_wallet": analysis["most_interacted"],
                "top_10_counterparties": top_counterparties,
            },
        }
