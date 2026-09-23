"""
EVM transaction handler — structured intent, Uni V2 quote/preview/execute,
transfer, balances, and wallet info for a dedicated agent wallet.
"""

from __future__ import annotations

import copy
import os
import re
import sys
import time
from decimal import Decimal, ROUND_DOWN
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import yaml
from eth_account import Account
from web3 import Web3
from web3.contract import Contract

from skillware.core.base_skill import BaseSkill

_SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
if _SKILL_DIR not in sys.path:
    sys.path.insert(0, _SKILL_DIR)
from abis import ERC20_ABI, MAX_UINT256, ROUTER_V2_ABI  # noqa: E402

_COINGECKO_PLATFORM = {"ethereum": "ethereum", "base": "base"}

_ETH_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
_SENSITIVE_ENV_SUFFIXES = ("PRIVATE_KEY", "SECRET", "MNEMONIC")
_PREFERENCE_KEYS = frozenset(
    {
        "default_chain",
        "default_spend_asset",
        "gas_policy",
        "confirm_before_send",
        "slippage_bps",
        "max_trade_usd",
        "allowed_chains",
        "allowed_tokens",
        "private_key_env",
    }
)
_GAS_MULTIPLIERS = {
    "low": (0.95, 1.0),
    "normal": (1.1, 1.5),
    "high": (1.25, 2.5),
    "aggressive": (1.5, 3.0),
}
_GAS_BUFFER_UNITS = 350_000
_PREVIEW_DRIFT_WARNING = (
    "execute re-quotes on-chain at broadcast time; preview amounts may drift."
)
_QUOTE_BEFORE_EXECUTE_WARNING = (
    "Call quote (or preview) immediately before user confirmation and execute."
)


class EvmTxHandlerSkill(BaseSkill):
    """Structured EVM buy/sell quotes and transfers for a dedicated agent wallet."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config or {})
        self._skill_dir = os.path.dirname(os.path.abspath(__file__))
        self._data_dir = os.path.join(self._skill_dir, "data")
        self._legacy_addressbook = self._load_yaml("addressbook.yaml")
        self.chains = self._build_chain_registry()
        self.tokens = self._build_token_registry()
        self.user_config = self._load_user_config()
        self._web3_cache: Dict[str, Web3] = {}

    @property
    def manifest(self) -> Dict[str, Any]:
        path = os.path.join(self._skill_dir, "manifest.yaml")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        action = (params.get("action") or "").strip().lower()
        intent = params.get("intent") or {}
        if not isinstance(intent, dict):
            return self._error("intent must be an object")

        handlers = {
            "resolve": self._action_resolve,
            "quote": self._action_quote,
            "preview": self._action_preview,
            "execute": self._action_execute,
            "transfer": self._action_transfer,
            "balances": self._action_balances,
            "wallet_info": self._action_wallet_info,
            "update_preferences": self._action_update_preferences,
        }
        if action not in handlers:
            return self._error(
                f"Unknown action {action!r}. "
                f"Use one of: {', '.join(sorted(handlers))}."
            )

        try:
            return handlers[action](intent, params)
        except ValueError as exc:
            return self._error(str(exc))
        except Exception as exc:
            return self._error(self._safe_error_message(exc))

    # --- Config & registry ---

    def _load_yaml(self, name: str) -> Dict[str, Any]:
        path = os.path.join(self._data_dir, name)
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}

    def _build_chain_registry(self) -> Dict[str, Any]:
        bundle = self._load_yaml("chains.yaml")
        try:
            from skillware.core.evm_config import load_merged_evm_config

            merged = load_merged_evm_config()
            result = copy.deepcopy(bundle)
            for name, cfg in merged.chains.items():
                if not isinstance(cfg, dict):
                    continue
                if cfg.get("enabled") is False:
                    result.pop(name, None)
                    continue
                overlay = {k: v for k, v in cfg.items() if k != "enabled"}
                if name in result:
                    result[name].update(overlay)
                else:
                    result[name] = overlay
            return result
        except Exception:
            return bundle

    def _build_token_registry(self) -> Dict[str, Any]:
        bundle = self._load_yaml("tokens.yaml")
        try:
            from skillware.core.evm_config import load_merged_evm_config

            merged = load_merged_evm_config()
            result = copy.deepcopy(bundle)
            for chain, chain_tokens in merged.tokens.items():
                if not isinstance(chain_tokens, dict):
                    continue
                result.setdefault(chain, {})
                result[chain].update(chain_tokens)
            return result
        except Exception:
            return bundle

    def _load_user_config(self) -> Dict[str, Any]:
        defaults = {
            "default_chain": "ethereum",
            "default_spend_asset": "usdc",
            "gas_policy": "normal",
            "confirm_before_send": True,
            "slippage_bps": 50,
            "private_key_env": "AGENT_WALLET_PRIVATE_KEY",
        }
        path = os.path.join(self._skill_dir, "config.yaml")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
            if isinstance(loaded, dict):
                defaults.update(loaded)
        return defaults

    def _save_user_config(self, updates: Dict[str, Any]) -> None:
        merged = copy.deepcopy(self.user_config)
        merged.update(updates)
        path = os.path.join(self._skill_dir, "config.yaml")
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(merged, f, default_flow_style=False, sort_keys=False)
        self.user_config = merged

    def _chain_key(self, chain: Optional[str]) -> str:
        key = (
            (chain or self.user_config.get("default_chain") or "ethereum")
            .strip()
            .lower()
        )
        if key not in self.chains:
            raise ValueError(
                f"Unknown chain {key!r}. Supported: {', '.join(self.chains)}."
            )
        allowed = self.user_config.get("allowed_chains")
        if allowed and key not in [c.lower() for c in allowed]:
            raise ValueError(f"Chain {key!r} is not in allowed_chains.")
        return key

    def _token_allowed(self, symbol: str) -> None:
        allowed = self.user_config.get("allowed_tokens")
        if allowed and symbol.lower() not in [t.lower() for t in allowed]:
            raise ValueError(f"Token {symbol!r} is not in allowed_tokens.")

    def _resolve_token_meta(self, chain: str, symbol: str) -> Dict[str, Any]:
        sym = symbol.strip().lower()
        self._token_allowed(sym)
        chain_tokens = self.tokens.get(chain) or {}
        if sym not in chain_tokens:
            raise ValueError(f"Token {sym!r} not in tokens.yaml for chain {chain!r}.")
        meta = dict(chain_tokens[sym])
        meta["symbol"] = sym
        meta["chain"] = chain
        if meta.get("native"):
            meta["address"] = None
        elif meta.get("address"):
            meta["address"] = Web3.to_checksum_address(meta["address"])
        return meta

    def _resolve_recipient_detail(self, recipient: str) -> Dict[str, Any]:
        raw = recipient.strip()
        if _ETH_ADDRESS_RE.match(raw):
            return {
                "status": "resolved",
                "address": Web3.to_checksum_address(raw),
                "recipient_source": "explicit",
            }

        label = raw.lower()
        legacy = self._legacy_addressbook.get(label)
        if legacy:
            return {
                "status": "resolved",
                "address": Web3.to_checksum_address(str(legacy)),
                "recipient_source": f"legacy:{label}",
            }

        from skillware.core.mail_config import (
            load_addressbook_yaml,
            resolve_addressbook_path,
            resolve_recipient_query,
        )

        path = resolve_addressbook_path(skill_data_dir=Path(self._data_dir))
        data = load_addressbook_yaml(path)
        result = resolve_recipient_query(data, raw)
        if result.get("status") == "resolved":
            return result
        return result

    def _resolve_recipient(self, recipient: str) -> str:
        detail = self._resolve_recipient_detail(recipient)
        if detail.get("status") == "resolved":
            return str(detail["address"])
        message = detail.get("message") or detail.get("agent_hint") or (
            f"Recipient {recipient!r} could not be resolved."
        )
        raise ValueError(message)

    def _rpc_url(self, chain: str) -> str:
        try:
            from skillware.core.evm_config import resolve_rpc_url

            return resolve_rpc_url(chain, credential_fn=self.credential)
        except Exception:
            chain_cfg = self.chains[chain]
            env_key = chain_cfg.get("rpc_env")
            if not env_key:
                raise ValueError(f"chains.yaml missing rpc_env for {chain!r}.")
            url = self.credential(env_key)
            if not url:
                raise ValueError(f"Missing RPC: set environment variable {env_key}.")
            return url

    def _get_web3(self, chain: str) -> Web3:
        if chain not in self._web3_cache:
            self._web3_cache[chain] = Web3(Web3.HTTPProvider(self._rpc_url(chain)))
        return self._web3_cache[chain]

    def _private_key_env(self) -> str:
        return str(
            self.user_config.get("private_key_env") or "AGENT_WALLET_PRIVATE_KEY"
        )

    def _wallet_key_configured(self) -> bool:
        env_name = self._private_key_env()
        key = self.credential(env_name)
        return bool(key and str(key).strip())

    def _missing_wallet_key_response(self) -> Dict[str, Any]:
        env_name = self._private_key_env()
        return {
            "status": "missing_config",
            "message": f"Dedicated agent wallet key is not configured ({env_name}).",
            "agent_hint": (
                "Create or fund a disposable agent-only wallet, add its private key to "
                f"{env_name} in a local .env file, then retry. Never use a personal, "
                "treasury, or exchange hot wallet."
            ),
            "setup": {
                "env_var": env_name,
                "where": "Project-root .env (loaded via skillware.core.env.load_env_file)",
                "never": "Do not pass private keys in tool arguments, YAML, or chat.",
                "wallet_policy": (
                    "Use a dedicated agent wallet with limited funds for automated trades only."
                ),
                "docs": "docs/skills/evm_tx_handler.md#environment",
                "api_keys_guide": "docs/usage/api_keys.md",
            },
        }

    def _require_wallet_key(self) -> Optional[Dict[str, Any]]:
        if self._wallet_key_configured():
            return None
        return self._missing_wallet_key_response()

    def _account(self):
        missing = self._require_wallet_key()
        if missing:
            raise ValueError(missing["message"])
        env_name = self._private_key_env()
        key = self.credential(env_name)
        if key.startswith("0x"):
            key = key[2:]
        return Account.from_key(key)

    def _wallet_address(self) -> str:
        return self._account().address

    def _estimate_gas_buffer_wei(self, w3: Web3, policy: str) -> int:
        max_fee, _priority = self._eip1559_fees(w3, policy)
        return max_fee * _GAS_BUFFER_UNITS

    def _token_balance_wei(
        self, w3: Web3, chain: str, token: Dict[str, Any], address: str
    ) -> int:
        if token.get("native"):
            return w3.eth.get_balance(address)
        contract = w3.eth.contract(address=token["address"], abi=ERC20_ABI)
        return contract.functions.balanceOf(address).call()

    def _preflight_spend_balance(
        self,
        w3: Web3,
        chain: str,
        token: Dict[str, Any],
        amount_wei: int,
        address: str,
        policy: str,
        *,
        needs_gas: bool,
    ) -> Optional[Dict[str, Any]]:
        balance = self._token_balance_wei(w3, chain, token, address)
        if balance < amount_wei:
            return {
                "status": "insufficient_balance",
                "message": (
                    f"Insufficient {token['symbol']} balance for this operation."
                ),
                "agent_hint": (
                    f"Wallet holds {self._from_wei(balance, token['decimals'])} "
                    f"{token['symbol']} but needs at least "
                    f"{self._from_wei(amount_wei, token['decimals'])}."
                ),
                "balance": {
                    "asset": token["symbol"],
                    "available": self._from_wei(balance, token["decimals"]),
                    "required": self._from_wei(amount_wei, token["decimals"]),
                },
            }

        if needs_gas and not token.get("native"):
            gas_buffer = self._estimate_gas_buffer_wei(w3, policy)
            native_bal = w3.eth.get_balance(address)
            if native_bal < gas_buffer:
                return {
                    "status": "insufficient_balance",
                    "message": "Insufficient native ETH for gas.",
                    "agent_hint": (
                        "ERC20 swaps and transfers also require ETH on the chain for gas. "
                        "Top up the agent wallet with a small ETH balance and retry."
                    ),
                    "balance": {
                        "asset": "eth",
                        "available": self._from_wei(native_bal, 18),
                        "required_gas_buffer_eth": self._from_wei(gas_buffer, 18),
                    },
                }
        return None

    # --- Intent merge / resolve ---

    def _merge_intent(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}
        chain = self._chain_key(intent.get("chain"))
        merged["chain"] = chain
        merged["gas_policy"] = (
            intent.get("gas_policy") or self.user_config.get("gas_policy") or "normal"
        ).lower()
        if merged["gas_policy"] not in _GAS_MULTIPLIERS:
            raise ValueError(f"Invalid gas_policy {merged['gas_policy']!r}.")

        side = (intent.get("side") or "").strip().lower()
        if side:
            merged["side"] = side

        for key in (
            "target_asset",
            "spend_asset",
            "amount",
            "amount_kind",
            "recipient",
            "slippage_bps",
        ):
            if intent.get(key) is not None:
                merged[key] = intent[key]

        if (
            intent.get("slippage_bps") is None
            and self.user_config.get("slippage_bps") is not None
        ):
            merged.setdefault("slippage_bps", self.user_config["slippage_bps"])

        if side in ("buy", "sell"):
            if not merged.get("target_asset"):
                raise ValueError("target_asset is required for buy/sell.")
            merged["target_asset"] = str(merged["target_asset"]).lower()
            if merged.get("spend_asset"):
                merged["spend_asset"] = str(merged["spend_asset"]).lower()
            if not merged.get("amount_kind"):
                merged["amount_kind"] = "target_out" if side == "buy" else "spend_in"
        elif merged.get("target_asset"):
            merged["target_asset"] = str(merged["target_asset"]).lower()
        if merged.get("recipient"):
            merged["recipient"] = str(merged["recipient"]).strip()

        return merged

    def _missing_for_trade(self, resolved: Dict[str, Any]) -> List[str]:
        missing = []
        if not resolved.get("spend_asset"):
            missing.append("spend_asset")
        if resolved.get("amount") is None:
            missing.append("amount")
        return missing

    def _suggested_defaults(
        self, resolved: Dict[str, Any], missing: List[str]
    ) -> Dict[str, Any]:
        suggestions: Dict[str, Any] = {}
        if "spend_asset" in missing:
            side = resolved.get("side")
            if side == "buy":
                suggestions["spend_asset"] = self.user_config.get(
                    "default_spend_asset", "usdc"
                )
            elif side == "sell":
                suggestions["spend_asset"] = self.user_config.get(
                    "default_spend_asset", "usdc"
                )
        return suggestions

    def _action_resolve(
        self, intent: Dict[str, Any], _params: Dict[str, Any]
    ) -> Dict[str, Any]:
        resolved = self._merge_intent(intent)
        side = resolved.get("side")

        if side in ("buy", "sell"):
            missing = self._missing_for_trade(resolved)
            if missing:
                return {
                    "status": "needs_input",
                    "resolved": resolved,
                    "missing_fields": missing,
                    "suggested_defaults": self._suggested_defaults(resolved, missing),
                    "agent_hint": (
                        f"Ask which token to pay with; suggest "
                        f"{self._suggested_defaults(resolved, missing).get('spend_asset', 'usdc').upper()} "
                        f"from config."
                        if "spend_asset" in missing
                        else "Ask for the trade amount."
                    ),
                }
            self._resolve_token_meta(resolved["chain"], resolved["target_asset"])
            self._resolve_token_meta(resolved["chain"], resolved["spend_asset"])
            return {"status": "ready", "resolved": resolved}

        if (
            side == "send"
            or intent.get("recipient")
            or _params.get("action") == "transfer"
        ):
            missing = []
            if not resolved.get("target_asset"):
                missing.append("target_asset")
            if resolved.get("amount") is None:
                missing.append("amount")
            if not resolved.get("recipient") and not intent.get("recipient"):
                missing.append("recipient")
            if missing:
                return {
                    "status": "needs_input",
                    "resolved": resolved,
                    "missing_fields": missing,
                    "suggested_defaults": {},
                    "agent_hint": "Ask for token, amount, and recipient (address or addressbook label).",
                }
            return {"status": "ready", "resolved": resolved}

        return self._error(
            "intent.side must be buy, sell, or use transfer action for sends."
        )

    # --- Quote / preview ---

    def _swap_path(
        self, chain: str, token_in: Dict[str, Any], token_out: Dict[str, Any]
    ) -> List[str]:
        weth = Web3.to_checksum_address(self.chains[chain]["weth"])

        def addr(meta: Dict[str, Any]) -> str:
            if meta.get("native"):
                return weth
            return meta["address"]

        a_in, a_out = addr(token_in), addr(token_out)
        if a_in == a_out:
            raise ValueError("Cannot swap an asset into itself.")
        if a_in == weth or a_out == weth:
            return [a_in, a_out]
        return [a_in, weth, a_out]

    def _to_wei(self, amount: float, decimals: int) -> int:
        quant = Decimal(str(amount)).quantize(
            Decimal(10) ** -decimals, rounding=ROUND_DOWN
        )
        return int(quant * (10**decimals))

    def _from_wei(self, wei: int, decimals: int) -> str:
        value = Decimal(wei) / Decimal(10**decimals)
        return format(value.normalize(), "f")

    def _router(self, w3: Web3, chain: str) -> Contract:
        router_addr = Web3.to_checksum_address(self.chains[chain]["router_v2"])
        return w3.eth.contract(address=router_addr, abi=ROUTER_V2_ABI)

    def _trade_assets(
        self, resolved: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        chain = resolved["chain"]
        side = resolved["side"]
        target = self._resolve_token_meta(chain, resolved["target_asset"])
        spend = self._resolve_token_meta(chain, resolved["spend_asset"])
        if side == "buy":
            return spend, target
        return target, spend

    def _build_quote(self, resolved: Dict[str, Any]) -> Dict[str, Any]:
        chain = resolved["chain"]
        w3 = self._get_web3(chain)
        token_in, token_out = self._trade_assets(resolved)
        path = self._swap_path(chain, token_in, token_out)
        router = self._router(w3, chain)
        amount_kind = (resolved.get("amount_kind") or "target_out").lower()
        amount = float(resolved["amount"])
        slippage_bps = int(
            resolved.get("slippage_bps") or self.user_config.get("slippage_bps") or 50
        )

        if amount_kind == "target_out":
            amount_out_wei = self._to_wei(amount, token_out["decimals"])
            amounts = router.functions.getAmountsIn(amount_out_wei, path).call()
            amount_in_wei = amounts[0]
            amount_out_wei = amounts[-1]
        elif amount_kind == "spend_in":
            amount_in_wei = self._to_wei(amount, token_in["decimals"])
            amounts = router.functions.getAmountsOut(amount_in_wei, path).call()
            amount_out_wei = amounts[-1]
        else:
            raise ValueError("amount_kind must be target_out or spend_in.")

        min_out_wei = amount_out_wei * (10_000 - slippage_bps) // 10_000
        deadline = int(time.time()) + 1200
        gas = self._estimate_gas(w3, resolved.get("gas_policy", "normal"))

        return {
            "path": path,
            "token_in": token_in,
            "token_out": token_out,
            "amount_in_wei": str(amount_in_wei),
            "amount_out_wei": str(amount_out_wei),
            "min_out_wei": str(min_out_wei),
            "deadline": deadline,
            "slippage_bps": slippage_bps,
            "gas_estimate": gas,
            "side": resolved["side"],
            "chain": chain,
            "amount_kind": amount_kind,
        }

    @staticmethod
    def _quote_api_payload(quote: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "path": quote["path"],
            "amount_in_wei": quote["amount_in_wei"],
            "amount_out_wei": quote["amount_out_wei"],
            "min_out_wei": quote["min_out_wei"],
            "deadline": quote["deadline"],
        }

    def _coingecko_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {"Accept": "application/json"}
        api_key = self.credential("COINGECKO_API_KEY")
        if api_key:
            headers["x-cg-pro-api-key"] = str(api_key)
        return headers

    def _coingecko_usd_unit_price(
        self, chain: str, token: Dict[str, Any]
    ) -> Optional[float]:
        if chain not in _COINGECKO_PLATFORM:
            return None
        try:
            if token.get("native"):
                response = requests.get(
                    "https://api.coingecko.com/api/v3/simple/price",
                    params={"ids": "ethereum", "vs_currencies": "usd"},
                    headers=self._coingecko_headers(),
                    timeout=10,
                )
                response.raise_for_status()
                return float(response.json()["ethereum"]["usd"])

            platform = _COINGECKO_PLATFORM[chain]
            address = token["address"].lower()
            response = requests.get(
                f"https://api.coingecko.com/api/v3/simple/token_price/{platform}",
                params={"contract_addresses": address, "vs_currencies": "usd"},
                headers=self._coingecko_headers(),
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            for key, value in data.items():
                if key.lower() == address:
                    return float(value["usd"])
            return None
        except (requests.RequestException, KeyError, TypeError, ValueError):
            return None

    def _usd_for_token_amount(
        self, chain: str, token: Dict[str, Any], amount_wei: int
    ) -> Optional[float]:
        unit = self._coingecko_usd_unit_price(chain, token)
        if unit is None:
            return None
        human = Decimal(amount_wei) / Decimal(10 ** int(token["decimals"]))
        return float(human * Decimal(str(unit)))

    def _enforce_max_trade_usd(self, quote: Dict[str, Any]) -> None:
        cap = self.user_config.get("max_trade_usd")
        if cap is None:
            return
        pay_usd = self._usd_for_token_amount(
            quote["chain"], quote["token_in"], int(quote["amount_in_wei"])
        )
        if pay_usd is None:
            raise ValueError(
                "max_trade_usd is configured but USD price for the pay asset is unavailable. "
                "Set COINGECKO_API_KEY or retry later."
            )
        if pay_usd > float(cap):
            raise ValueError(
                f"Trade pay amount ${pay_usd:.2f} exceeds max_trade_usd ${float(cap):.2f}."
            )

    def _preview_usd(self, quote: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        pay = self._usd_for_token_amount(
            quote["chain"], quote["token_in"], int(quote["amount_in_wei"])
        )
        receive = self._usd_for_token_amount(
            quote["chain"], quote["token_out"], int(quote["amount_out_wei"])
        )
        if pay is None and receive is None:
            return None
        return {"pay": pay, "receive": receive}

    def _preview_from_quote(self, quote: Dict[str, Any]) -> Dict[str, Any]:
        tin, tout = quote["token_in"], quote["token_out"]
        pay_amt = self._from_wei(int(quote["amount_in_wei"]), tin["decimals"])
        recv_amt = self._from_wei(int(quote["amount_out_wei"]), tout["decimals"])
        rate = ""
        if Decimal(pay_amt) > 0:
            rate = (
                f"1 {tin['symbol']} = "
                f"{format(Decimal(recv_amt) / Decimal(pay_amt), 'f')} {tout['symbol']}"
            )

        preview: Dict[str, Any] = {
            "side": quote["side"],
            "chain": quote["chain"],
            "you_pay": {"asset": tin["symbol"], "amount": pay_amt},
            "you_receive": {"asset": tout["symbol"], "amount": recv_amt},
            "rate": rate,
            "gas_estimate": quote["gas_estimate"],
            "router": "uniswap_v2",
            "warnings": [
                "Rates are indicative; slippage may apply.",
                _PREVIEW_DRIFT_WARNING,
                _QUOTE_BEFORE_EXECUTE_WARNING,
            ],
        }
        usd = self._preview_usd(quote)
        if usd is not None:
            preview["usd"] = usd
        return preview

    def _action_quote(
        self, intent: Dict[str, Any], _params: Dict[str, Any]
    ) -> Dict[str, Any]:
        resolved = self._merge_intent(intent)
        if resolved.get("side") not in ("buy", "sell"):
            return self._error("quote requires intent.side buy or sell.")
        missing = self._missing_for_trade(resolved)
        if missing:
            return self._error(f"Cannot quote; missing fields: {', '.join(missing)}.")

        quote = self._build_quote(resolved)
        self._enforce_max_trade_usd(quote)
        preview = self._preview_from_quote(quote)
        confirm = bool(self.user_config.get("confirm_before_send", True))
        return {
            "status": "ready",
            "preview": preview,
            "quote": self._quote_api_payload(quote),
            "requires_confirmation": confirm,
        }

    def _action_preview(
        self, intent: Dict[str, Any], params: Dict[str, Any]
    ) -> Dict[str, Any]:
        result = self._action_quote(intent, params)
        if result.get("status") != "ready":
            return result
        return {
            "status": "ready",
            "preview": result["preview"],
            "requires_confirmation": result.get("requires_confirmation", True),
        }

    def _base_tx_params(
        self, w3: Web3, chain: str, policy: str, from_address: str
    ) -> Dict[str, Any]:
        max_fee, priority = self._eip1559_fees(w3, policy)
        return {
            "from": from_address,
            "chainId": int(self.chains[chain]["chain_id"]),
            "nonce": w3.eth.get_transaction_count(from_address),
            "maxFeePerGas": max_fee,
            "maxPriorityFeePerGas": priority,
        }

    def _approve_router_if_needed(
        self,
        w3: Web3,
        chain: str,
        token_address: str,
        router_address: str,
        amount_wei: int,
        policy: str,
        owner: str,
    ) -> Optional[str]:
        erc20 = w3.eth.contract(address=token_address, abi=ERC20_ABI)
        allowance = erc20.functions.allowance(owner, router_address).call()
        if allowance >= amount_wei:
            return None
        base = self._base_tx_params(w3, chain, policy, owner)
        tx = erc20.functions.approve(router_address, MAX_UINT256).build_transaction(
            base
        )
        return self._sign_and_send(w3, tx)

    def _build_swap_transaction(
        self,
        w3: Web3,
        chain: str,
        quote: Dict[str, Any],
        to_address: str,
        policy: str,
        from_address: str,
    ) -> Dict[str, Any]:
        router = self._router(w3, chain)
        token_in = quote["token_in"]
        token_out = quote["token_out"]
        amount_in = int(quote["amount_in_wei"])
        amount_out = int(quote["amount_out_wei"])
        min_out = int(quote["min_out_wei"])
        path = quote["path"]
        deadline = quote["deadline"]
        amount_kind = quote.get("amount_kind", "target_out")
        base = self._base_tx_params(w3, chain, policy, from_address)

        if token_in.get("native"):
            if amount_kind == "target_out":
                return router.functions.swapETHForExactTokens(
                    amount_out, path, to_address, deadline
                ).build_transaction({**base, "value": amount_in})
            return router.functions.swapExactETHForTokens(
                min_out, path, to_address, deadline
            ).build_transaction({**base, "value": amount_in})

        if token_out.get("native"):
            return router.functions.swapExactTokensForETH(
                amount_in, min_out, path, to_address, deadline
            ).build_transaction(base)

        if amount_kind == "target_out":
            return router.functions.swapTokensForExactTokens(
                amount_out, amount_in, path, to_address, deadline
            ).build_transaction(base)

        return router.functions.swapExactTokensForTokens(
            amount_in, min_out, path, to_address, deadline
        ).build_transaction(base)

    def _action_execute(
        self, intent: Dict[str, Any], params: Dict[str, Any]
    ) -> Dict[str, Any]:
        need_confirm = self._require_confirmed(params)
        if need_confirm:
            need_confirm["agent_hint"] = (
                "Show the latest quote/preview to the user, obtain explicit approval, "
                "then call execute with confirmed: true. ERC20 swaps may require an "
                "on-chain approve transaction before the swap when allowance is low."
            )
            return need_confirm

        missing_key = self._require_wallet_key()
        if missing_key:
            return missing_key

        resolved = self._merge_intent(intent)
        if resolved.get("side") not in ("buy", "sell"):
            return self._error("execute requires intent.side buy or sell.")
        missing = self._missing_for_trade(resolved)
        if missing:
            return self._error(f"Cannot execute; missing fields: {', '.join(missing)}.")

        quote = self._build_quote(resolved)
        self._enforce_max_trade_usd(quote)

        chain = quote["chain"]
        w3 = self._get_web3(chain)
        account = self._account()
        router_address = Web3.to_checksum_address(self.chains[chain]["router_v2"])
        policy = resolved.get("gas_policy", "normal")
        amount_in = int(quote["amount_in_wei"])
        token_in = quote["token_in"]

        balance_issue = self._preflight_spend_balance(
            w3,
            chain,
            token_in,
            amount_in,
            account.address,
            policy,
            needs_gas=True,
        )
        if balance_issue:
            return balance_issue
        if token_in.get("native"):
            gas_buffer = self._estimate_gas_buffer_wei(w3, policy)
            native_bal = self._token_balance_wei(w3, chain, token_in, account.address)
            if native_bal < amount_in + gas_buffer:
                return {
                    "status": "insufficient_balance",
                    "message": "Insufficient native ETH for swap amount and gas.",
                    "agent_hint": (
                        "The agent wallet needs enough ETH to cover the swap input and "
                        "estimated gas. Re-quote after topping up ETH."
                    ),
                    "balance": {
                        "asset": "eth",
                        "available": self._from_wei(native_bal, 18),
                        "required": self._from_wei(amount_in + gas_buffer, 18),
                    },
                }

        approve_tx_hash: Optional[str] = None
        if not token_in.get("native"):
            approve_tx_hash = self._approve_router_if_needed(
                w3,
                chain,
                token_in["address"],
                router_address,
                amount_in,
                policy,
                account.address,
            )
            if approve_tx_hash:
                approve_receipt = self._wait_receipt(w3, approve_tx_hash)
                if not approve_receipt.get("success"):
                    return self._error("Router approve transaction failed.")

        swap_tx = self._build_swap_transaction(
            w3, chain, quote, account.address, policy, account.address
        )
        tx_hash = self._sign_and_send(w3, swap_tx)
        receipt = self._wait_receipt(w3, tx_hash)

        result: Dict[str, Any] = {
            "status": "confirmed",
            "tx_hash": tx_hash,
            "explorer_url": self._explorer_url(chain, tx_hash),
            "receipt": receipt,
            "quote": self._quote_api_payload(quote),
        }
        if approve_tx_hash:
            result["approve_tx_hash"] = approve_tx_hash
            result["approve_explorer_url"] = self._explorer_url(chain, approve_tx_hash)
            result["agent_hint"] = (
                "Two-step ERC20 swap: approve transaction confirmed; swap broadcast "
                "follows in this response. When confirm_before_send is enabled, each "
                "step should be shown to the user before signing."
            )
        else:
            result["agent_hint"] = (
                "Swap broadcast uses a fresh on-chain quote at execute time; amounts "
                "may differ slightly from the last preview."
            )
        return result

    # --- Transfer ---

    def _require_confirmed(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if self.user_config.get("confirm_before_send", True) and not params.get(
            "confirmed"
        ):
            return {
                "status": "needs_confirmation",
                "message": "Set confirmed: true after the user approves this transaction.",
            }
        return None

    def _estimate_gas(self, w3: Web3, policy: str) -> Dict[str, Any]:
        policy = policy if policy in _GAS_MULTIPLIERS else "normal"
        base_fee = w3.eth.gas_price
        max_mult, tip_gwei = _GAS_MULTIPLIERS[policy]
        max_fee = int(base_fee * max_mult)
        priority = w3.to_wei(tip_gwei, "gwei")
        return {
            "policy": policy,
            "max_fee_gwei": str(Decimal(max_fee) / Decimal(10**9)),
            "max_priority_fee_gwei": str(Decimal(priority) / Decimal(10**9)),
        }

    def _eip1559_fees(self, w3: Web3, policy: str) -> Tuple[int, int]:
        policy = policy if policy in _GAS_MULTIPLIERS else "normal"
        base_fee = w3.eth.gas_price
        max_mult, tip_gwei = _GAS_MULTIPLIERS[policy]
        return int(base_fee * max_mult), w3.to_wei(tip_gwei, "gwei")

    def _sign_and_send(self, w3: Web3, tx: Dict[str, Any]) -> str:
        signed = self._account().sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        return tx_hash.hex()

    def _wait_receipt(
        self, w3: Web3, tx_hash: str, timeout: int = 120
    ) -> Dict[str, Any]:
        try:
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
            return {
                "block_number": receipt["blockNumber"],
                "gas_used": receipt["gasUsed"],
                "success": receipt["status"] == 1,
            }
        except Exception:
            return {"success": None, "note": "Receipt not confirmed within timeout."}

    def _explorer_url(self, chain: str, tx_hash: str) -> str:
        template = self.chains[chain].get("explorer_tx_url", "")
        return template.format(tx_hash=tx_hash)

    def _action_transfer(
        self, intent: Dict[str, Any], params: Dict[str, Any]
    ) -> Dict[str, Any]:
        need_confirm = self._require_confirmed(params)
        if need_confirm:
            need_confirm["agent_hint"] = (
                "Confirm recipient, asset, amount, and chain with the user before "
                "calling transfer with confirmed: true."
            )
            return need_confirm

        missing_key = self._require_wallet_key()
        if missing_key:
            return missing_key

        resolved = self._merge_intent({**intent, "side": "send"})
        chain = resolved["chain"]
        if not resolved.get("target_asset"):
            return self._error("target_asset is required for transfer.")
        if resolved.get("amount") is None:
            return self._error("amount is required for transfer.")
        if not resolved.get("recipient"):
            return self._error("recipient is required for transfer.")

        recipient_detail = self._resolve_recipient_detail(str(resolved["recipient"]))
        if recipient_detail.get("status") != "resolved":
            response = dict(recipient_detail)
            response["action"] = "transfer"
            if response.get("status") == "error":
                response["message"] = response.get("message") or response.get(
                    "agent_hint"
                )
            return response

        recipient = str(recipient_detail["address"])
        token = self._resolve_token_meta(chain, str(resolved["target_asset"]))
        w3 = self._get_web3(chain)
        amount_wei = self._to_wei(float(resolved["amount"]), token["decimals"])
        policy = resolved.get("gas_policy", "normal")

        account = self._account()
        balance_issue = self._preflight_spend_balance(
            w3,
            chain,
            token,
            amount_wei,
            account.address,
            policy,
            needs_gas=not token.get("native"),
        )
        if balance_issue:
            return balance_issue
        if token.get("native"):
            gas_buffer = self._estimate_gas_buffer_wei(w3, policy)
            native_bal = w3.eth.get_balance(account.address)
            if native_bal < amount_wei + gas_buffer:
                return {
                    "status": "insufficient_balance",
                    "message": "Insufficient native ETH for transfer amount and gas.",
                    "agent_hint": "Top up the agent wallet with ETH on this chain and retry.",
                    "balance": {
                        "asset": "eth",
                        "available": self._from_wei(native_bal, 18),
                        "required": self._from_wei(amount_wei + gas_buffer, 18),
                    },
                }

        chain_id = int(self.chains[chain]["chain_id"])
        max_fee, priority = self._eip1559_fees(w3, policy)
        base_tx: Dict[str, Any] = {
            "from": account.address,
            "chainId": chain_id,
            "nonce": w3.eth.get_transaction_count(account.address),
            "maxFeePerGas": max_fee,
            "maxPriorityFeePerGas": priority,
        }

        if token.get("native"):
            tx = {
                **base_tx,
                "to": recipient,
                "value": amount_wei,
                "gas": 21_000,
            }
        else:
            contract = w3.eth.contract(address=token["address"], abi=ERC20_ABI)
            tx = contract.functions.transfer(recipient, amount_wei).build_transaction(
                base_tx
            )

        tx_hash = self._sign_and_send(w3, tx)
        receipt = self._wait_receipt(w3, tx_hash)
        return {
            "status": "confirmed",
            "tx_hash": tx_hash,
            "explorer_url": self._explorer_url(chain, tx_hash),
            "recipient_resolved": recipient,
            "recipient_source": recipient_detail.get("recipient_source"),
            "recipient_name": recipient_detail.get("recipient_name"),
            "receipt": receipt,
        }

    # --- Read-only ---

    def _action_balances(
        self, intent: Dict[str, Any], _params: Dict[str, Any]
    ) -> Dict[str, Any]:
        missing_key = self._require_wallet_key()
        if missing_key:
            return missing_key

        chain = self._chain_key(intent.get("chain"))
        w3 = self._get_web3(chain)
        address = self._wallet_address()
        chain_tokens = self.tokens.get(chain) or {}
        balances: Dict[str, str] = {}

        native_bal = w3.eth.get_balance(address)
        balances["eth"] = self._from_wei(native_bal, 18)

        for symbol, meta in chain_tokens.items():
            if meta.get("native"):
                continue
            contract = w3.eth.contract(
                address=Web3.to_checksum_address(meta["address"]), abi=ERC20_ABI
            )
            raw = contract.functions.balanceOf(address).call()
            balances[symbol] = self._from_wei(raw, int(meta["decimals"]))

        return {
            "status": "ready",
            "chain": chain,
            "address": address,
            "balances": balances,
        }

    def _action_wallet_info(
        self, _intent: Dict[str, Any], _params: Dict[str, Any]
    ) -> Dict[str, Any]:
        missing_key = self._require_wallet_key()
        if missing_key:
            return missing_key

        address = self._wallet_address()

        prefs = {
            k: self.user_config[k]
            for k in (
                "default_chain",
                "default_spend_asset",
                "gas_policy",
                "confirm_before_send",
                "slippage_bps",
                "max_trade_usd",
            )
            if k in self.user_config
        }
        return {
            "status": "ready",
            "address": address,
            "supported_chains": list(self.chains.keys()),
            "preferences": prefs,
            "capabilities": {
                "resolve": True,
                "quote": True,
                "preview": True,
                "transfer": True,
                "balances": True,
                "execute": True,
            },
        }

    def _action_update_preferences(
        self, intent: Dict[str, Any], params: Dict[str, Any]
    ) -> Dict[str, Any]:
        updates = params.get("preferences") or intent.get("preferences") or {}
        if not isinstance(updates, dict) or not updates:
            return self._error("preferences object with fields to update is required.")

        invalid = [k for k in updates if k not in _PREFERENCE_KEYS]
        if invalid:
            return self._error(
                f"Cannot update unknown preference keys: {', '.join(invalid)}."
            )

        if "gas_policy" in updates and updates["gas_policy"] not in _GAS_MULTIPLIERS:
            return self._error("Invalid gas_policy in preferences.")

        self._save_user_config(updates)
        return {"status": "updated", "preferences": copy.deepcopy(self.user_config)}

    # --- Helpers ---

    @staticmethod
    def _error(message: str) -> Dict[str, Any]:
        return {"status": "error", "message": message}

    def _safe_error_message(self, exc: Exception) -> str:
        text = str(exc)
        for key, value in os.environ.items():
            if not value or len(value) < 8:
                continue
            if any(s in key.upper() for s in _SENSITIVE_ENV_SUFFIXES):
                text = text.replace(value, "[REDACTED]")
                if value.startswith("0x"):
                    text = text.replace(value[2:], "[REDACTED]")
        cfg_key = (self.config or {}).get(self._private_key_env())
        if cfg_key and len(str(cfg_key)) >= 8:
            text = text.replace(str(cfg_key), "[REDACTED]")
        if len(text) > 500:
            text = text[:500] + "..."
        return text
