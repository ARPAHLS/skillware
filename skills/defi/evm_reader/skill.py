"""Read-only EVM chain state reader skill (defi/evm_reader).

Provides safe, deterministic queries for ERC-20/721 tokens, view functions,
Multicall3 batch reads, and addressbook holder resolution.
Never signs transactions; requires no private keys.
"""

from __future__ import annotations

import decimal
import re
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Union

try:
    from .abis import get_preset_abi
except (ImportError, ValueError):
    try:
        from skills.defi.evm_reader.abis import get_preset_abi
    except (ImportError, ValueError):
        import importlib.util
        import os

        _skill_dir = os.path.dirname(os.path.abspath(__file__))
        _spec = importlib.util.spec_from_file_location(
            "evm_reader_abis", os.path.join(_skill_dir, "abis.py")
        )
        if _spec and _spec.loader:
            _mod = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            get_preset_abi = _mod.get_preset_abi
        else:
            raise ImportError("Could not load abis.py for defi/evm_reader")
from skillware.core.base_skill import BaseSkill
from skillware.core.evm_config import (
    load_merged_evm_config,
    normalize_evm_address,
    resolve_chain,
    resolve_rpc_url,
)
from skillware.core.mail_config import (
    load_addressbook_yaml,
    resolve_addressbook_path,
    resolve_recipient_query,
)

_MAX_MULTICALL_BATCH = 50
_HEX_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
_RAW_40HEX_RE = re.compile(r"^[a-fA-F0-9]{40}$")


class EVMReaderSkill(BaseSkill):
    """Read-only EVM state reader."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        credential_fn: Optional[Callable[[str], Optional[str]]] = None,
        addressbook_path: Optional[Union[str, Path]] = None,
        web3_factory: Optional[Callable[[str], Any]] = None,
    ):
        super().__init__(config)
        self._credential_fn = credential_fn or self.credential
        self._addressbook_path = (
            Path(addressbook_path).resolve() if addressbook_path else None
        )
        self._web3_factory = web3_factory

    @property
    def manifest(self) -> Dict[str, Any]:
        path = Path(__file__).resolve().parent / "manifest.yaml"
        if path.is_file():
            import yaml

            return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return {}

    def run(self, action: str, **kwargs: Any) -> Dict[str, Any]:
        """Execute the requested skill operation."""
        return self.execute(action=action, **kwargs)

    def execute(
        self,
        params: Optional[Union[Dict[str, Any], str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Execute a read-only EVM action."""
        if params is not None and isinstance(params, dict):
            combined = {**params, **kwargs}
        elif params is not None and isinstance(params, str):
            combined = {"action": params, **kwargs}
        else:
            combined = dict(kwargs)

        action = combined.pop("action", None)
        act = str(action or "").strip().lower()
        handlers = {
            "erc20_metadata": self._action_erc20_metadata,
            "erc20_balance": self._action_erc20_balance,
            "erc20_allowance": self._action_erc20_allowance,
            "erc721_metadata": self._action_erc721_metadata,
            "erc721_balance": self._action_erc721_balance,
            "erc721_owner_of": self._action_erc721_owner_of,
            "erc721_owner": self._action_erc721_owner_of,
            "call_view": self._action_call_view,
            "multicall": self._action_multicall,
            "batch_balances": self._action_multicall,
            "resolve_holder": self._action_resolve_holder,
        }
        handler = handlers.get(act)
        if not handler:
            known = ", ".join(sorted(handlers.keys()))
            return {
                "status": "error",
                "error_code": "unsupported_action",
                "message": f"Action {action!r} is not supported. Supported: {known}.",
            }

        try:
            return handler(**combined)
        except Exception as exc:
            return {
                "status": "error",
                "error_code": "execution_failed",
                "message": str(exc),
            }

    # -------------------------------------------------------------------------
    # Core Helpers
    # -------------------------------------------------------------------------

    def _get_web3(self, chain_name: str) -> Any:
        if self._web3_factory:
            return self._web3_factory(chain_name)
        try:
            from web3 import Web3
        except ImportError as exc:
            raise ImportError(
                "web3 is required for defi/evm_reader. Install with: pip install 'web3>=6.0.0'"
            ) from exc

        url = resolve_rpc_url(chain_name, credential_fn=self._credential_fn)
        return Web3(Web3.HTTPProvider(url))

    def _resolve_contract_address(
        self, chain_name: str, contract_or_symbol: str
    ) -> str:
        raw = str(contract_or_symbol or "").strip()
        if not raw:
            raise ValueError("contract address or token symbol is required")

        # Check if known symbol in merged EVM config for this chain
        cfg = load_merged_evm_config()
        chain_key = chain_name.strip().lower()
        chain_tokens = cfg.tokens.get(chain_key, {})
        sym_lower = raw.lower()
        if sym_lower in chain_tokens:
            token_info = chain_tokens[sym_lower]
            addr = token_info.get("address")
            if addr:
                return normalize_evm_address(addr)

        # Otherwise normalize as hex address
        if _RAW_40HEX_RE.match(raw) and not raw.startswith("0x"):
            raw = "0x" + raw
        return normalize_evm_address(raw)

    def _resolve_holder_address(
        self,
        holder: str,
        addressbook_path: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        """Resolve a holder from 0x address or addressbook contact/alias."""
        raw = str(holder or "").strip()
        if not raw:
            return {
                "status": "error",
                "error_code": "invalid_holder",
                "message": "holder address or contact identifier is required",
            }

        # Check if already 40-char hex
        candidate_hex = "0x" + raw if _RAW_40HEX_RE.match(raw) else raw
        if _HEX_ADDRESS_RE.match(candidate_hex):
            try:
                normalized = normalize_evm_address(candidate_hex)
                return {
                    "status": "resolved",
                    "address": normalized,
                    "holder_source": "explicit",
                }
            except Exception as exc:
                return {
                    "status": "error",
                    "error_code": "invalid_address",
                    "message": f"Invalid address {holder!r}: {exc}",
                }

        # Central address book lookup
        book_path = (
            Path(addressbook_path).resolve()
            if addressbook_path
            else (self._addressbook_path or resolve_addressbook_path())
        )
        if not book_path.is_file():
            return {
                "status": "error",
                "error_code": "addressbook_not_found",
                "message": f"Address book not found at {book_path}. Cannot resolve alias {raw!r}.",
            }

        data = load_addressbook_yaml(book_path)
        res = resolve_recipient_query(data, raw)
        if res.get("status") == "resolved":
            return {
                "status": "resolved",
                "address": res["address"],
                "holder_source": res.get("recipient_source", f"addressbook:{raw}"),
                "recipient_name": res.get("recipient_name"),
            }
        if res.get("status") == "needs_input":
            return {
                "status": "needs_input",
                "error_code": "ambiguous_recipient",
                "missing_fields": res.get("missing_fields", ["holder_disambiguation"]),
                "ambiguous_recipient": res.get("ambiguous_recipient"),
                "agent_hint": res.get("agent_hint"),
            }

        return {
            "status": "error",
            "error_code": res.get("code", "holder_not_found"),
            "message": res.get("message", f"Could not resolve holder {raw!r}."),
            "agent_hint": res.get("agent_hint"),
        }

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------

    def _action_resolve_holder(
        self,
        holder: str,
        addressbook_path: Optional[str] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        """Resolve contact alias or name to public_0x address."""
        res = self._resolve_holder_address(holder, addressbook_path=addressbook_path)
        if res.get("status") == "resolved":
            return {
                "status": "ok",
                "holder": res["address"],
                "holder_source": res["holder_source"],
                "recipient_name": res.get("recipient_name"),
            }
        return res

    def _action_erc20_metadata(
        self,
        chain: str,
        contract: Optional[str] = None,
        token: Optional[str] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        """Fetch ERC-20 name, symbol, decimals, and total_supply."""
        contract_target = contract or token
        if not contract_target:
            return {
                "status": "error",
                "error_code": "missing_contract",
                "message": "contract address or token symbol is required",
            }

        target_addr = self._resolve_contract_address(chain, contract_target)
        w3 = self._get_web3(chain)
        ct = w3.eth.contract(address=target_addr, abi=get_preset_abi("erc20"))

        name = ct.functions.name().call()
        symbol = ct.functions.symbol().call()
        decimals = ct.functions.decimals().call()
        total_supply = ct.functions.totalSupply().call()

        return {
            "status": "ok",
            "chain": chain.lower(),
            "token": target_addr,
            "contract": target_addr,
            "name": name,
            "symbol": symbol,
            "decimals": decimals,
            "total_supply": str(total_supply),
        }

    def _action_erc20_balance(
        self,
        chain: str,
        holder: str,
        contract: Optional[str] = None,
        token: Optional[str] = None,
        addressbook_path: Optional[str] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        """Query ERC-20 token balance for a holder."""
        contract_target = contract or token
        if not contract_target:
            return {
                "status": "error",
                "error_code": "missing_contract",
                "message": "contract address or token symbol is required",
            }

        target_addr = self._resolve_contract_address(chain, contract_target)
        holder_res = self._resolve_holder_address(
            holder, addressbook_path=addressbook_path
        )
        if holder_res.get("status") != "resolved":
            return holder_res

        holder_addr = holder_res["address"]
        w3 = self._get_web3(chain)
        ct = w3.eth.contract(address=target_addr, abi=get_preset_abi("erc20"))

        balance_raw = ct.functions.balanceOf(holder_addr).call()
        try:
            decimals = ct.functions.decimals().call()
        except Exception:
            decimals = 18

        symbol = ""
        try:
            symbol = ct.functions.symbol().call()
        except Exception:
            pass

        # Format decimal balance
        d_val = decimal.Decimal(balance_raw) / (decimal.Decimal(10) ** decimals)
        fmt = f"{d_val:.{decimals}f}" if decimals <= 18 else str(d_val)

        res: Dict[str, Any] = {
            "status": "ok",
            "chain": chain.lower(),
            "token": target_addr,
            "contract": target_addr,
            "holder": holder_addr,
            "holder_source": holder_res.get("holder_source", "explicit"),
            "decimals": decimals,
            "balance_raw": str(balance_raw),
            "balance": fmt,
        }
        if symbol:
            res["symbol"] = symbol
        return res

    def _action_erc20_allowance(
        self,
        chain: str,
        owner: str,
        spender: str,
        contract: Optional[str] = None,
        token: Optional[str] = None,
        addressbook_path: Optional[str] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        """Query ERC-20 allowance granted by owner to spender."""
        contract_target = contract or token
        if not contract_target:
            return {
                "status": "error",
                "error_code": "missing_contract",
                "message": "contract address or token symbol is required",
            }

        target_addr = self._resolve_contract_address(chain, contract_target)
        owner_res = self._resolve_holder_address(
            owner, addressbook_path=addressbook_path
        )
        if owner_res.get("status") != "resolved":
            return owner_res

        # Spender can be an address or router keyword
        spender_raw = spender.strip().lower()
        if spender_raw in ("router_v2", "router"):
            chain_cfg = resolve_chain(chain)
            router = chain_cfg.get("router_v2")
            if not router:
                return {
                    "status": "error",
                    "error_code": "router_not_configured",
                    "message": f"router_v2 address is not configured for chain {chain!r}.",
                }
            spender_addr = normalize_evm_address(router)
        else:
            spender_res = self._resolve_holder_address(
                spender, addressbook_path=addressbook_path
            )
            if spender_res.get("status") != "resolved":
                return spender_res
            spender_addr = spender_res["address"]

        w3 = self._get_web3(chain)
        ct = w3.eth.contract(address=target_addr, abi=get_preset_abi("erc20"))
        allowance_raw = ct.functions.allowance(
            owner_res["address"], spender_addr
        ).call()

        try:
            decimals = ct.functions.decimals().call()
        except Exception:
            decimals = 18

        d_val = decimal.Decimal(allowance_raw) / (decimal.Decimal(10) ** decimals)
        fmt = f"{d_val:.{decimals}f}" if decimals <= 18 else str(d_val)

        return {
            "status": "ok",
            "chain": chain.lower(),
            "token": target_addr,
            "contract": target_addr,
            "owner": owner_res["address"],
            "spender": spender_addr,
            "decimals": decimals,
            "allowance_raw": str(allowance_raw),
            "allowance": fmt,
        }

    def _action_erc721_metadata(
        self,
        chain: str,
        contract: Optional[str] = None,
        token: Optional[str] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        """Fetch ERC-721 collection name, symbol, and total supply."""
        contract_target = contract or token
        if not contract_target:
            return {
                "status": "error",
                "error_code": "missing_contract",
                "message": "contract address is required",
            }

        target_addr = self._resolve_contract_address(chain, contract_target)
        w3 = self._get_web3(chain)
        ct = w3.eth.contract(address=target_addr, abi=get_preset_abi("erc721"))

        name = ""
        symbol = ""
        total_supply = None

        try:
            name = ct.functions.name().call()
        except Exception:
            pass
        try:
            symbol = ct.functions.symbol().call()
        except Exception:
            pass
        try:
            total_supply = ct.functions.totalSupply().call()
        except Exception:
            pass

        res: Dict[str, Any] = {
            "status": "ok",
            "chain": chain.lower(),
            "token": target_addr,
            "contract": target_addr,
            "name": name,
            "symbol": symbol,
        }
        if total_supply is not None:
            res["total_supply"] = str(total_supply)
        return res

    def _action_erc721_balance(
        self,
        chain: str,
        holder: str,
        contract: Optional[str] = None,
        token: Optional[str] = None,
        addressbook_path: Optional[str] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        """Query ERC-721 token balance (count of NFTs owned)."""
        contract_target = contract or token
        if not contract_target:
            return {
                "status": "error",
                "error_code": "missing_contract",
                "message": "contract address is required",
            }

        target_addr = self._resolve_contract_address(chain, contract_target)
        holder_res = self._resolve_holder_address(
            holder, addressbook_path=addressbook_path
        )
        if holder_res.get("status") != "resolved":
            return holder_res

        w3 = self._get_web3(chain)
        ct = w3.eth.contract(address=target_addr, abi=get_preset_abi("erc721"))
        balance = ct.functions.balanceOf(holder_res["address"]).call()

        return {
            "status": "ok",
            "chain": chain.lower(),
            "token": target_addr,
            "contract": target_addr,
            "holder": holder_res["address"],
            "holder_source": holder_res.get("holder_source", "explicit"),
            "balance": str(balance),
            "balance_count": int(balance),
        }

    def _action_erc721_owner_of(
        self,
        chain: str,
        token_id: Union[int, str],
        contract: Optional[str] = None,
        token: Optional[str] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        """Query the owner of an ERC-721 token ID."""
        contract_target = contract or token
        if not contract_target:
            return {
                "status": "error",
                "error_code": "missing_contract",
                "message": "contract address is required",
            }

        try:
            tid = int(token_id)
        except (ValueError, TypeError):
            return {
                "status": "error",
                "error_code": "invalid_token_id",
                "message": f"token_id must be an integer, got {token_id!r}",
            }

        target_addr = self._resolve_contract_address(chain, contract_target)
        w3 = self._get_web3(chain)
        ct = w3.eth.contract(address=target_addr, abi=get_preset_abi("erc721"))
        owner_addr = ct.functions.ownerOf(tid).call()
        normalized_owner = normalize_evm_address(owner_addr)

        return {
            "status": "ok",
            "chain": chain.lower(),
            "token": target_addr,
            "contract": target_addr,
            "token_id": tid,
            "owner": normalized_owner,
        }

    def _action_call_view(
        self,
        chain: str,
        contract: str,
        method: str,
        abi_preset: str = "erc20",
        args: Optional[Sequence[Any]] = None,
        block_identifier: Optional[Union[str, int]] = "latest",
        **_: Any,
    ) -> Dict[str, Any]:
        """Execute a read-only view call on a contract using an allowlisted ABI preset."""
        target_addr = self._resolve_contract_address(chain, contract)
        preset_abi = get_preset_abi(abi_preset)

        w3 = self._get_web3(chain)
        ct = w3.eth.contract(address=target_addr, abi=preset_abi)

        func = getattr(ct.functions, method, None)
        if func is None:
            return {
                "status": "error",
                "error_code": "method_not_found",
                "message": f"Method {method!r} not found in ABI preset {abi_preset!r}.",
            }

        call_args = list(args) if args is not None else []
        # Normalize any address arguments in call_args
        clean_args = []
        for a in call_args:
            if isinstance(a, str) and (
                _HEX_ADDRESS_RE.match(a) or _RAW_40HEX_RE.match(a)
            ):
                try:
                    clean_args.append(normalize_evm_address(a))
                except Exception:
                    clean_args.append(a)
            else:
                clean_args.append(a)

        call_func = func(*clean_args)
        block = block_identifier if block_identifier is not None else "latest"
        result = call_func.call(block_identifier=block)

        # Format result safely
        formatted_result: Any
        if isinstance(result, (list, tuple)):
            formatted_result = [
                str(x) if isinstance(x, int) and x > 2**63 else x for x in result
            ]
        elif isinstance(result, int) and result > 2**63:
            formatted_result = str(result)
        elif isinstance(result, bytes):
            formatted_result = "0x" + result.hex()
        else:
            formatted_result = result

        return {
            "status": "ok",
            "chain": chain.lower(),
            "contract": target_addr,
            "method": method,
            "abi_preset": abi_preset.lower(),
            "result": formatted_result,
        }

    def _action_multicall(
        self,
        chain: str,
        calls: Sequence[Mapping[str, Any]],
        multicall_address: Optional[str] = None,
        require_success: bool = False,
        **_: Any,
    ) -> Dict[str, Any]:
        """Execute batched view calls via Multicall3 (tryAggregate)."""
        if not calls:
            return {
                "status": "error",
                "error_code": "empty_calls",
                "message": "calls list cannot be empty",
            }

        if len(calls) > _MAX_MULTICALL_BATCH:
            return {
                "status": "error",
                "error_code": "batch_too_large",
                "message": (
                    f"Multicall batch size ({len(calls)}) exceeds constitution maximum "
                    f"of {_MAX_MULTICALL_BATCH} calls."
                ),
            }

        # Resolve Multicall3 contract address
        mc_addr: Optional[str] = None
        if multicall_address:
            mc_addr = normalize_evm_address(multicall_address)
        else:
            chain_cfg = resolve_chain(chain)
            configured_mc = chain_cfg.get("multicall3")
            if configured_mc:
                mc_addr = normalize_evm_address(configured_mc)
            else:
                # Default standard Multicall3 deployment
                mc_addr = "0xcA11bde05977b3631167028862bE2a173976CA11"

        w3 = self._get_web3(chain)
        mc_contract = w3.eth.contract(address=mc_addr, abi=get_preset_abi("multicall3"))

        encoded_calls = []
        parsed_metadata = []

        for idx, call_spec in enumerate(calls):
            target = (
                call_spec.get("target")
                or call_spec.get("contract")
                or call_spec.get("token")
            )
            if not target:
                return {
                    "status": "error",
                    "error_code": "invalid_call_spec",
                    "message": f"Call at index {idx} missing 'target' address.",
                }
            norm_target = self._resolve_contract_address(chain, str(target))
            method = call_spec.get("method")
            if not method:
                return {
                    "status": "error",
                    "error_code": "invalid_call_spec",
                    "message": f"Call at index {idx} missing 'method' name.",
                }
            abi_preset = call_spec.get("abi_preset", "erc20")
            preset_abi = get_preset_abi(abi_preset)
            call_args = list(call_spec.get("args") or [])

            target_contract = w3.eth.contract(address=norm_target, abi=preset_abi)
            func = getattr(target_contract.functions, method, None)
            if func is None:
                return {
                    "status": "error",
                    "error_code": "method_not_found",
                    "message": f"Method {method!r} not found in preset {abi_preset!r} for call {idx}.",
                }

            calldata = target_contract.encodeABI(fn_name=method, args=call_args)
            encoded_calls.append(
                {"target": norm_target, "callData": bytes.fromhex(calldata[2:])}
            )
            parsed_metadata.append(
                {
                    "target": norm_target,
                    "method": method,
                    "abi_preset": abi_preset,
                    "contract": target_contract,
                    "fn_name": method,
                }
            )

        # Execute tryAggregate
        try:
            results = mc_contract.functions.tryAggregate(
                require_success, encoded_calls
            ).call()
        except Exception as exc:
            return {
                "status": "error",
                "error_code": "multicall_failed",
                "message": f"Multicall3 execution failed: {exc}",
            }

        decoded_results = []
        for idx, (success, raw_bytes) in enumerate(results):
            meta = parsed_metadata[idx]
            entry: Dict[str, Any] = {
                "index": idx,
                "target": meta["target"],
                "method": meta["method"],
                "success": success,
            }
            if success and raw_bytes:
                try:
                    c_inst = meta["contract"]
                    decoded = c_inst.decode_function_output(meta["fn_name"], raw_bytes)
                    if isinstance(decoded, (list, tuple)) and len(decoded) == 1:
                        entry["result"] = decoded[0]
                    else:
                        entry["result"] = decoded
                except Exception as decode_err:
                    entry["result"] = "0x" + raw_bytes.hex()
                    entry["decode_error"] = str(decode_err)
            else:
                entry["result"] = None
            decoded_results.append(entry)

        return {
            "status": "ok",
            "chain": chain.lower(),
            "multicall_address": mc_addr,
            "total_calls": len(calls),
            "results": decoded_results,
        }
