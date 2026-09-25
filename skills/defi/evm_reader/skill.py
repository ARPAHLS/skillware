"""
EVM Reader — read-only on-chain state queries via RPC eth_call.

Actions: erc20_metadata, erc20_balance, erc20_allowance,
         erc721_metadata, erc721_balance, erc721_owner_of,
         call_view, multicall.

Never signs transactions. Uses shared ``skillware.core.evm_config``
for chain/RPC resolution.
"""

from __future__ import annotations

import os
import sys
from decimal import Decimal
from typing import Any, Dict, List, Optional

import yaml
from web3 import Web3

from skillware.core.base_skill import BaseSkill
from skillware.core.evm_config import (
    get_web3,
    normalize_evm_address,
    resolve_chain,
)

_SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
if _SKILL_DIR not in sys.path:
    sys.path.insert(0, _SKILL_DIR)
from abis import (  # noqa: E402
    ABI_REGISTRY,
    MAX_MULTICALL_BATCH,
    MULTICALL3_ABI,
    MULTICALL3_ADDRESS,
)

_VIEW_MUTABILITIES = frozenset({"view", "pure"})


class EvmReaderSkill(BaseSkill):
    """Read-only EVM state queries — balances, metadata, allowances, and batch reads."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config or {})
        self._skill_dir = os.path.dirname(os.path.abspath(__file__))
        self._web3_cache: Dict[str, Web3] = {}

    @property
    def manifest(self) -> Dict[str, Any]:
        path = os.path.join(self._skill_dir, "manifest.yaml")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        action = (params.get("action") or "").strip().lower()

        handlers = {
            "erc20_metadata": self._action_erc20_metadata,
            "erc20_balance": self._action_erc20_balance,
            "erc20_allowance": self._action_erc20_allowance,
            "erc721_metadata": self._action_erc721_metadata,
            "erc721_balance": self._action_erc721_balance,
            "erc721_owner_of": self._action_erc721_owner_of,
            "call_view": self._action_call_view,
            "multicall": self._action_multicall,
        }
        if action not in handlers:
            return self._error(
                f"Unknown action {action!r}. "
                f"Use one of: {', '.join(sorted(handlers))}."
            )

        try:
            return handlers[action](params)
        except ValueError as exc:
            return self._error(str(exc))
        except Exception as exc:
            return self._error(self._safe_error_message(exc))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _error(message: str) -> Dict[str, Any]:
        return {"status": "error", "error": message}

    @staticmethod
    def _safe_error_message(exc: Exception) -> str:
        """Sanitize exception messages so RPC URLs / secrets aren't leaked."""
        msg = str(exc)
        for env_key in ("ETHEREUM_RPC_URL", "BASE_RPC_URL"):
            url = os.environ.get(env_key, "")
            if url and url in msg:
                msg = msg.replace(url, f"${env_key}")
        return msg

    def _get_web3(self, chain: str) -> Web3:
        if chain not in self._web3_cache:
            self._web3_cache[chain] = get_web3(chain)
        return self._web3_cache[chain]

    @staticmethod
    def _require_param(params: Dict[str, Any], key: str) -> str:
        value = params.get(key)
        if not value or not str(value).strip():
            raise ValueError(f"Missing required parameter: {key}")
        return str(value).strip()

    @staticmethod
    def _require_address(params: Dict[str, Any], key: str) -> str:
        raw = params.get(key)
        if not raw or not str(raw).strip():
            raise ValueError(f"Missing required address parameter: {key}")
        return normalize_evm_address(str(raw).strip())

    @staticmethod
    def _format_balance(raw: int, decimals: int) -> str:
        """Format a raw integer balance with the correct number of decimal places."""
        if decimals == 0:
            return str(raw)
        d = Decimal(raw) / Decimal(10**decimals)
        return format(d, f".{decimals}f")

    @staticmethod
    def _find_abi_function(
        abi: List[Dict[str, Any]], function_name: str
    ) -> Dict[str, Any]:
        """Locate a view/pure function in an ABI fragment list."""
        for entry in abi:
            if (
                entry.get("type") == "function"
                and entry.get("name") == function_name
                and entry.get("stateMutability") in _VIEW_MUTABILITIES
            ):
                return entry
        raise ValueError(
            f"Function {function_name!r} not found or is not view/pure in the ABI."
        )

    # ------------------------------------------------------------------
    # ERC-20 actions
    # ------------------------------------------------------------------

    def _action_erc20_metadata(self, params: Dict[str, Any]) -> Dict[str, Any]:
        chain = self._require_param(params, "chain")
        token = self._require_address(params, "token")
        w3 = self._get_web3(chain)
        abi = ABI_REGISTRY["erc20"]
        contract = w3.eth.contract(address=token, abi=abi)

        name = contract.functions.name().call()
        symbol = contract.functions.symbol().call()
        decimals = contract.functions.decimals().call()
        total_supply_raw = contract.functions.totalSupply().call()

        return {
            "status": "ok",
            "chain": chain,
            "token": token,
            "name": name,
            "symbol": symbol,
            "decimals": decimals,
            "total_supply_raw": str(total_supply_raw),
            "total_supply": self._format_balance(total_supply_raw, decimals),
        }

    def _action_erc20_balance(self, params: Dict[str, Any]) -> Dict[str, Any]:
        chain = self._require_param(params, "chain")
        token = self._require_address(params, "token")
        holder = self._require_address(params, "holder")
        w3 = self._get_web3(chain)
        abi = ABI_REGISTRY["erc20"]
        contract = w3.eth.contract(address=token, abi=abi)

        decimals = contract.functions.decimals().call()
        balance_raw = contract.functions.balanceOf(holder).call()

        return {
            "status": "ok",
            "chain": chain,
            "token": token,
            "holder": holder,
            "decimals": decimals,
            "balance_raw": str(balance_raw),
            "balance": self._format_balance(balance_raw, decimals),
        }

    def _action_erc20_allowance(self, params: Dict[str, Any]) -> Dict[str, Any]:
        chain = self._require_param(params, "chain")
        token = self._require_address(params, "token")
        holder = self._require_address(params, "holder")
        spender = self._require_address(params, "spender")
        w3 = self._get_web3(chain)
        abi = ABI_REGISTRY["erc20"]
        contract = w3.eth.contract(address=token, abi=abi)

        decimals = contract.functions.decimals().call()
        allowance_raw = contract.functions.allowance(holder, spender).call()

        return {
            "status": "ok",
            "chain": chain,
            "token": token,
            "holder": holder,
            "spender": spender,
            "decimals": decimals,
            "allowance_raw": str(allowance_raw),
            "allowance": self._format_balance(allowance_raw, decimals),
        }

    # ------------------------------------------------------------------
    # ERC-721 actions
    # ------------------------------------------------------------------

    def _action_erc721_metadata(self, params: Dict[str, Any]) -> Dict[str, Any]:
        chain = self._require_param(params, "chain")
        token = self._require_address(params, "token")
        w3 = self._get_web3(chain)
        abi = ABI_REGISTRY["erc721"]
        contract = w3.eth.contract(address=token, abi=abi)

        name = contract.functions.name().call()
        symbol = contract.functions.symbol().call()

        result: Dict[str, Any] = {
            "status": "ok",
            "chain": chain,
            "token": token,
            "name": name,
            "symbol": symbol,
        }

        # totalSupply is optional in ERC-721 (ERC721Enumerable).
        try:
            total_supply = contract.functions.totalSupply().call()
            result["total_supply"] = total_supply
        except Exception:
            result["total_supply"] = None

        return result

    def _action_erc721_balance(self, params: Dict[str, Any]) -> Dict[str, Any]:
        chain = self._require_param(params, "chain")
        token = self._require_address(params, "token")
        holder = self._require_address(params, "holder")
        w3 = self._get_web3(chain)
        abi = ABI_REGISTRY["erc721"]
        contract = w3.eth.contract(address=token, abi=abi)

        balance = contract.functions.balanceOf(holder).call()

        return {
            "status": "ok",
            "chain": chain,
            "token": token,
            "holder": holder,
            "balance": balance,
        }

    def _action_erc721_owner_of(self, params: Dict[str, Any]) -> Dict[str, Any]:
        chain = self._require_param(params, "chain")
        token = self._require_address(params, "token")
        token_id = params.get("token_id")
        if token_id is None:
            raise ValueError("Missing required parameter: token_id")
        token_id = int(token_id)

        w3 = self._get_web3(chain)
        abi = ABI_REGISTRY["erc721"]
        contract = w3.eth.contract(address=token, abi=abi)

        owner = contract.functions.ownerOf(token_id).call()

        return {
            "status": "ok",
            "chain": chain,
            "token": token,
            "token_id": token_id,
            "owner": Web3.to_checksum_address(owner),
        }

    # ------------------------------------------------------------------
    # Generic call_view
    # ------------------------------------------------------------------

    def _action_call_view(self, params: Dict[str, Any]) -> Dict[str, Any]:
        chain = self._require_param(params, "chain")
        target = self._require_address(params, "target")
        abi_name = self._require_param(params, "abi_name").lower()
        function = self._require_param(params, "function")
        args = params.get("args") or []
        if not isinstance(args, list):
            raise ValueError("args must be a list")

        if abi_name not in ABI_REGISTRY:
            allowed = ", ".join(sorted(ABI_REGISTRY))
            raise ValueError(
                f"Unknown ABI {abi_name!r}. Allowlisted: {allowed}."
            )

        abi = ABI_REGISTRY[abi_name]
        fn_abi = self._find_abi_function(abi, function)

        w3 = self._get_web3(chain)
        contract = w3.eth.contract(address=target, abi=[fn_abi])
        result = getattr(contract.functions, function)(*args).call()

        # Normalize tuples/lists to plain JSON-serializable types.
        return {
            "status": "ok",
            "chain": chain,
            "target": target,
            "abi_name": abi_name,
            "function": function,
            "result": self._normalize_result(result),
        }

    @staticmethod
    def _normalize_result(value: Any) -> Any:
        """Convert web3 result types to JSON-serializable primitives."""
        if isinstance(value, bytes):
            return "0x" + value.hex()
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        if isinstance(value, (list, tuple)):
            return [EvmReaderSkill._normalize_result(v) for v in value]
        return value

    # ------------------------------------------------------------------
    # Multicall3 batch
    # ------------------------------------------------------------------

    def _action_multicall(self, params: Dict[str, Any]) -> Dict[str, Any]:
        chain = self._require_param(params, "chain")
        calls = params.get("calls")
        if not isinstance(calls, list) or not calls:
            raise ValueError("calls must be a non-empty array of call objects")
        if len(calls) > MAX_MULTICALL_BATCH:
            raise ValueError(
                f"Multicall batch size {len(calls)} exceeds cap of {MAX_MULTICALL_BATCH}."
            )

        w3 = self._get_web3(chain)

        # Resolve Multicall3 address from chain config, fall back to canonical.
        chain_cfg = resolve_chain(chain)
        mc3_address = normalize_evm_address(
            chain_cfg.get("multicall3", MULTICALL3_ADDRESS)
        )

        # Build individual call data.
        encoded_calls = []
        call_meta = []
        for i, call_obj in enumerate(calls):
            if not isinstance(call_obj, dict):
                raise ValueError(f"calls[{i}] must be an object")
            target = normalize_evm_address(
                str(call_obj.get("target", "")).strip()
            )
            abi_name = str(call_obj.get("abi_name", "")).strip().lower()
            function = str(call_obj.get("function", "")).strip()
            args = call_obj.get("args") or []

            if abi_name not in ABI_REGISTRY:
                allowed = ", ".join(sorted(ABI_REGISTRY))
                raise ValueError(
                    f"calls[{i}]: unknown ABI {abi_name!r}. Allowlisted: {allowed}."
                )
            abi = ABI_REGISTRY[abi_name]
            fn_abi = self._find_abi_function(abi, function)

            contract = w3.eth.contract(address=target, abi=[fn_abi])
            call_data = getattr(contract.functions, function)(*args)._encode_transaction_data()

            encoded_calls.append((target, True, call_data))
            call_meta.append(
                {
                    "target": target,
                    "abi_name": abi_name,
                    "function": function,
                    "fn_abi": fn_abi,
                }
            )

        # Execute via Multicall3.
        mc3 = w3.eth.contract(address=mc3_address, abi=MULTICALL3_ABI)
        raw_results = mc3.functions.aggregate3(encoded_calls).call()

        # Decode results.
        results = []
        for j, (success, return_data) in enumerate(raw_results):
            meta = call_meta[j]
            entry: Dict[str, Any] = {
                "target": meta["target"],
                "function": meta["function"],
                "success": success,
            }
            if success and return_data:
                try:
                    fn_abi = meta["fn_abi"]
                    output_types = [o["type"] for o in fn_abi.get("outputs", [])]
                    decoded = w3.codec.decode(output_types, return_data)
                    if len(decoded) == 1:
                        entry["result"] = self._normalize_result(decoded[0])
                    else:
                        entry["result"] = self._normalize_result(list(decoded))
                except Exception as exc:
                    entry["result"] = None
                    entry["decode_error"] = str(exc)
            else:
                entry["result"] = None
                if not success:
                    entry["revert"] = True
            results.append(entry)

        return {
            "status": "ok",
            "chain": chain,
            "multicall3": mc3_address,
            "results": results,
        }
