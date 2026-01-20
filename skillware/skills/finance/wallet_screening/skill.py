import json
import os
import requests
import glob
from typing import Any, Dict, List, Optional
from datetime import datetime
from skillware.core.base_skill import BaseSkill

class WalletScreeningSkill(BaseSkill):
    """
    A specific implementation of a compliance skill that screens Ethereum wallets
    against sanctions lists and malicious contract databases.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.etherscan_api_key = os.environ.get("ETHERSCAN_API_KEY")
        if not self.etherscan_api_key and self.config:
             self.etherscan_api_key = self.config.get("ETHERSCAN_API_KEY")

        # Config
        self.data_dir = os.path.join(os.path.dirname(__file__), 'data')
        self.coingecko_url_eur = "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=eur"
        self.coingecko_url_usd = "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd"

        # Load Core Datasets
        self.malicious_contracts = self._load_json_file('malicious_scs_2025.json') or []
        self.sanctions_entities = self._load_json_lines('entities.ftm.json') or []
        
        # Load Additional Datasets dynamically (normalized files, etc.)
        self.additional_datasets = self._load_additional_datasets()

    @property
    def manifest(self) -> Dict[str, Any]:
        return {}

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        address = params.get('address')
        if not address or not self._validate_eth_address(address):
            return {"error": "Invalid Ethereum address provided."}
        
        if not self.etherscan_api_key:
            return {"error": "Missing ETHERSCAN_API_KEY environment variable."}

        # 1. Fetch Data
        txs = self._get_eth_transactions(address)
        eth_balance = self._get_eth_balance(address)
        eth_usd = self._get_price(self.coingecko_url_usd, "usd")
        eth_eur = self._get_price(self.coingecko_url_eur, "eur")

        # 2. Sanctions Check (Core + Additional)
        sanctions_hits = self._check_against_sanctions(address)
        sanctions_hits.extend(self._check_against_additional_sanctions(address))
        
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
            txs_count=len(txs)
        )

    # --- Loader Helpers ---

    def _load_json_file(self, filename: str) -> Any:
        path = os.path.join(self.data_dir, filename)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    def _load_json_lines(self, filename: str) -> List[Any]:
        path = os.path.join(self.data_dir, filename)
        entities = []
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entities.append(json.loads(line))
                        except:
                            pass
        return entities

    def _load_additional_datasets(self) -> List[Dict]:
        """Loads all other JSON files in data_dir not explicitly loaded."""
        all_entries = []
        exclude = ['malicious_scs_2025.json', 'entities.ftm.json']
        for fname in glob.glob(os.path.join(self.data_dir, '*.json')):
            if os.path.basename(fname) in exclude:
                continue
            
            try:
                base_name = os.path.basename(fname)
                with open(fname, 'r', encoding='utf-8') as f:
                    first = f.read(1)
                    f.seek(0)
                    data = []
                    if first == '[':
                        data = json.load(f)
                    else:
                        for line in f:
                            if line.strip():
                                try:
                                    data.append(json.loads(line))
                                except: pass
                    
                    # Tag entries with source file
                    if isinstance(data, list):
                        for entry in data:
                            if isinstance(entry, dict):
                                entry['__source_file__'] = base_name
                                all_entries.append(entry)
            except Exception as e:
                print(f"Error loading {fname}: {e}")
        return all_entries

    # --- API Helpers ---

    def _validate_eth_address(self, address: str) -> bool:
        return isinstance(address, str) and address.startswith("0x") and len(address) == 42

    def _get_price(self, url: str, currency: str) -> float:
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
            return data.get("ethereum", {}).get(currency, 0.0)
        except:
            return 0.0

    def _get_eth_transactions(self, address: str) -> List[Dict]:
        url = "https://api.etherscan.io/api"
        params = {
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": 0,
            "endblock": 99999999,
            "sort": "asc",
            "apikey": self.etherscan_api_key
        }
        try:
            resp = requests.get(url, params=params, timeout=15)
            data = resp.json()
            if data.get("status") == "1":
                return data["result"]
        except Exception:
            pass
        return []

    def _get_eth_balance(self, address: str) -> float:
        url = "https://api.etherscan.io/api"
        params = {
            "module": "account",
            "action": "balance",
            "address": address,
            "tag": "latest",
            "apikey": self.etherscan_api_key
        }
        try:
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            if data.get("status") == "1":
                return int(data["result"]) / 1e18
        except:
            pass
        return 0.0

    # --- Logic Helpers ---

    def _check_against_sanctions(self, address: str) -> List[Dict]:
        hits = []
        lower_addr = address.lower()
        for entity in self.sanctions_entities:
            matches = False
            if "addresses" in entity:
                 if any(a.lower() == lower_addr for a in entity["addresses"]):
                     matches = True
            elif "properties" in entity and "address" in entity["properties"]:
                 if entity["properties"]["address"].lower() == lower_addr:
                     matches = True
            
            if matches:
                entity['__source_file__'] = 'entities.ftm.json'
                hits.append(entity)
        return hits

    def _check_against_additional_sanctions(self, address: str) -> List[Dict]:
        hits = []
        lower_addr = address.lower()
        for entry in self.additional_datasets:
            addr = None
            if 'address' in entry:
                addr = entry['address']
            elif 'properties' in entry and 'address' in entry['properties']:
                addr = entry['properties']['address']
            elif 'addresses' in entry and isinstance(entry['addresses'], list):
                for a in entry['addresses']:
                    if a.lower() == lower_addr:
                        addr = a
                        break
            
            if addr and addr.lower() == lower_addr:
                hits.append(entry)
        return hits

    def _analyze_transactions(self, txs: List[Dict], wallet_addr: str) -> Dict[str, Any]:
        wallet_addr = wallet_addr.lower()
        value_in = 0.0
        value_out = 0.0
        gas_paid = 0.0
        counterparty_counts = {}
        malicious_interactions = []
        
        malicious_map = {c['address'].lower(): c for c in self.malicious_contracts}

        for tx in txs:
            from_addr = tx.get('from', '').lower()
            to_addr = tx.get('to', '').lower() if tx.get('to') else ''
            
            try:
                value_eth = int(tx.get('value', '0')) / 1e18
            except:
                value_eth = 0.0
            
            is_error = tx.get('isError', '0') == '1'
            if is_error:
                continue

            # Gas
            if from_addr == wallet_addr:
                try:
                    gas = int(tx.get('gasUsed', '0')) * int(tx.get('gasPrice', '0')) / 1e18
                    gas_paid += gas
                except:
                    pass

            # Malicious Check
            other_party = None
            if to_addr and to_addr in malicious_map:
                other_party = to_addr
            elif from_addr and from_addr in malicious_map:
                other_party = from_addr
            
            if other_party:
                contract_info = malicious_map[other_party]
                malicious_interactions.append({
                    'tx_hash': tx.get('hash'),
                    'other_party': other_party,
                    'direction': 'out' if from_addr == wallet_addr else 'in',
                    'contract_name': contract_info.get('name'),
                    'severity': contract_info.get('severity'),
                    'jurisdictions': contract_info.get('jurisdictions_blocked', []),
                    'value_eth': value_eth
                })

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
                counterparty_counts[counterparty] = counterparty_counts.get(counterparty, 0) + 1

        most_interacted = None
        if counterparty_counts:
            most_interacted = max(counterparty_counts.items(), key=lambda x: x[1])

        return {
            'total_txs': len(txs),
            'value_in': value_in,
            'value_out': value_out,
            'gas_paid': gas_paid,
            'malicious_interactions': malicious_interactions,
            'counterparty_counts': counterparty_counts,
            'most_interacted': most_interacted
        }

    def _summarize_sanctions(self, hits: List[Dict]) -> List[Dict]:
        summary = []
        for entity in hits:
            label = entity.get('label') or entity.get('properties', {}).get('name', 'Unknown')
            jurisdiction = entity.get('jurisdiction') or entity.get('properties', {}).get('country', 'Unknown')
            reason = entity.get('reason') or entity.get('properties', {}).get('reason', 'N/A')
            source_file = entity.get('__source_file__', 'Unknown')
            summary.append({
                'label': label,
                'jurisdiction': jurisdiction,
                'reason': reason,
                'source_file': source_file,
                # 'entity': entity # simplified for AI token usage, normally full entity is heavy
            })
        return summary

    def _generate_report_data(self, address, analysis, sanctions_hits, eth_balance, eth_usd, eth_eur, txs_count):
        pnl = analysis['value_out'] - analysis['value_in'] - analysis['gas_paid']
        pnl_pct = ((pnl) / analysis['value_in'] * 100) if analysis['value_in'] > 0 else 0.0

        # Create structured summaries
        sanctions_summary = self._summarize_sanctions(sanctions_hits)
        
        # Format Top Counterparties
        top_counterparties = sorted(
            [(k, v) for k, v in analysis.get('counterparty_counts', {}).items()], 
            key=lambda x: -x[1]
        )[:10]

        return {
            "metadata": {
                "screening_time": datetime.now().isoformat(),
                "wallet_address": address,
                "data_sources_count": len(self.additional_datasets) + 2
            },
            "summary": {
                "risk_flag": bool(sanctions_hits) or bool(analysis['malicious_interactions']),
                "sanctioned_entity_match": bool(sanctions_hits),
                "malicious_interaction_count": len(analysis['malicious_interactions']),
                "balance_eth": eth_balance,
                "balance_usd": eth_balance * eth_usd,
                "total_transactions": txs_count
            },
            "financial_analysis": {
                "value_in_eth": analysis['value_in'],
                "value_in_usd": analysis['value_in'] * eth_usd,
                "value_out_eth": analysis['value_out'],
                "value_out_usd": analysis['value_out'] * eth_usd,
                "gas_paid_eth": analysis['gas_paid'],
                "pnl_eth": pnl,
                "pnl_usd": pnl * eth_usd,
                "pnl_percent": pnl_pct
            },
            "risk_details": {
                "sanctions_hits": sanctions_summary,
                "malicious_interactions": analysis['malicious_interactions']
            },
            "network_analysis": {
                "most_interacted_wallet": analysis['most_interacted'],
                "top_10_counterparties": top_counterparties
            }
        }
