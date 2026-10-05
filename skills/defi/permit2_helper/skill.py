"""defi/permit2_helper — Uniswap Permit2 EIP-712 typed data builder and validator."""

from __future__ import annotations

import os
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from eth_account.messages import _hash_eip191_message, encode_typed_data

from skillware.core.base_skill import BaseSkill
from skillware.core.evm_config import (
    get_web3,
    is_rpc_configured,
    load_merged_evm_config,
    normalize_evm_address,
    resolve_chain,
)

try:
    from .constants import (
        CANONICAL_PERMIT2_ADDRESS,
        KNOWN_SPENDER_LABELS,
        MAX_UINT48,
        MAX_UINT160,
        MAX_UINT256,
        PERMIT2_VIEW_ABI,
        PERMIT_SINGLE_TYPES,
        PERMIT_TRANSFER_FROM_TYPES,
    )
except (ImportError, ValueError):
    try:
        from skills.defi.permit2_helper.constants import (
            CANONICAL_PERMIT2_ADDRESS,
            KNOWN_SPENDER_LABELS,
            MAX_UINT48,
            MAX_UINT160,
            MAX_UINT256,
            PERMIT2_VIEW_ABI,
            PERMIT_SINGLE_TYPES,
            PERMIT_TRANSFER_FROM_TYPES,
        )
    except (ImportError, ValueError):
        import importlib.util

        _skill_dir = os.path.dirname(os.path.abspath(__file__))
        _spec = importlib.util.spec_from_file_location(
            "permit2_helper_constants", os.path.join(_skill_dir, "constants.py")
        )
        if _spec and _spec.loader:
            _mod = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            CANONICAL_PERMIT2_ADDRESS = _mod.CANONICAL_PERMIT2_ADDRESS
            KNOWN_SPENDER_LABELS = _mod.KNOWN_SPENDER_LABELS
            MAX_UINT48 = _mod.MAX_UINT48
            MAX_UINT160 = _mod.MAX_UINT160
            MAX_UINT256 = _mod.MAX_UINT256
            PERMIT2_VIEW_ABI = _mod.PERMIT2_VIEW_ABI
            PERMIT_SINGLE_TYPES = _mod.PERMIT_SINGLE_TYPES
            PERMIT_TRANSFER_FROM_TYPES = _mod.PERMIT_TRANSFER_FROM_TYPES
        else:
            raise ImportError("Could not load constants.py for defi/permit2_helper")

_RAW_40HEX_RE = re.compile(r"^[0-9a-fA-F]{40}$")


class Permit2HelperSkill(BaseSkill):
    """
    Builds, validates, and hashes EIP-712 typed data payloads for Uniswap Permit2.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        credential_fn: Optional[Callable[[str], Optional[str]]] = None,
        web3_factory: Optional[Callable[[str], Any]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(config=config, credential_fn=credential_fn, **kwargs)
        self._web3_factory = web3_factory

    @property
    def manifest(self) -> Dict[str, Any]:
        return self.load_manifest_from_dir(os.path.dirname(__file__))

    def execute(
        self,
        params: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        merged_params = dict(params or {})
        merged_params.update(kwargs)

        action = str(merged_params.get("action", "")).strip().lower()
        if not action:
            return {
                "status": "error",
                "error_code": "missing_action",
                "message": "Parameter 'action' is required.",
            }

        handlers = {
            "build_permit2": self._action_build_permit2,
            "validate_typed_data": self._action_validate_typed_data,
            "hash_typed_data": self._action_hash_typed_data,
            "read_nonce": self._action_read_nonce,
        }

        handler = handlers.get(action)
        if not handler:
            valid_actions = ", ".join(sorted(handlers.keys()))
            return {
                "status": "error",
                "error_code": "invalid_action",
                "message": f"Action {action!r} is not supported. Supported actions: {valid_actions}.",
            }

        try:
            return handler(merged_params)
        except Exception as exc:
            return {
                "status": "error",
                "error_code": "execution_failed",
                "message": str(exc),
            }

    # -------------------------------------------------------------------------
    # Action: build_permit2
    # -------------------------------------------------------------------------

    def _action_build_permit2(self, params: Dict[str, Any]) -> Dict[str, Any]:
        chain_name = params.get("chain")
        if not chain_name:
            return {
                "status": "error",
                "error_code": "missing_chain",
                "message": "Parameter 'chain' is required (e.g. 'ethereum', 'base').",
            }

        try:
            chain_cfg = resolve_chain(str(chain_name), require_enabled=False)
        except Exception as exc:
            return {
                "status": "error",
                "error_code": "invalid_chain",
                "message": str(exc),
            }

        chain_id = int(chain_cfg["chain_id"])

        # Token address or symbol (e.g. "usdc", "0xA0b8...")
        raw_token = params.get("token") or params.get("token_address")
        if not raw_token:
            return {
                "status": "error",
                "error_code": "missing_token",
                "message": "Parameter 'token' address or symbol is required.",
            }

        try:
            token_address = self._resolve_token_address(str(chain_name), str(raw_token))
        except Exception as exc:
            return {
                "status": "error",
                "error_code": "invalid_token_address",
                "message": f"Invalid token address or symbol: {exc}",
            }

        # Spender address (supports alias router_v2)
        raw_spender = params.get("spender")
        if not raw_spender:
            return {
                "status": "error",
                "error_code": "missing_spender",
                "message": "Parameter 'spender' address or alias is required.",
            }

        try:
            spender_address, spender_label = self._resolve_spender_address(
                str(chain_name), chain_cfg, str(raw_spender)
            )
        except Exception as exc:
            return {
                "status": "error",
                "error_code": "invalid_spender_address",
                "message": f"Invalid spender address: {exc}",
            }

        # Amount parsing
        raw_amount = params.get("amount")
        if raw_amount is None:
            return {
                "status": "error",
                "error_code": "missing_amount",
                "message": "Parameter 'amount' is required.",
            }

        allow_unlimited = bool(params.get("allow_unlimited", False))
        permit_type = str(params.get("permit_type", "PermitSingle")).strip()

        try:
            amount_int = self._parse_amount(raw_amount, permit_type=permit_type)
        except ValueError as exc:
            return {
                "status": "error",
                "error_code": "invalid_amount",
                "message": str(exc),
            }

        # Check limits & unlimited amounts
        if permit_type == "PermitSingle":
            if amount_int > MAX_UINT160:
                return {
                    "status": "error",
                    "error_code": "amount_exceeds_uint160",
                    "message": f"Amount {amount_int} exceeds uint160 max ({MAX_UINT160}).",
                }
            if amount_int == MAX_UINT160 and not allow_unlimited:
                return {
                    "status": "error",
                    "error_code": "unlimited_amount_forbidden",
                    "message": (
                        "Unlimited approval amount (type(uint160).max) rejected by default for safety. "
                        "To permit unlimited allowance, explicitly set 'allow_unlimited: true'."
                    ),
                }
        else:
            if amount_int > MAX_UINT256:
                return {
                    "status": "error",
                    "error_code": "amount_exceeds_uint256",
                    "message": "Amount exceeds uint256 max.",
                }
            if amount_int == MAX_UINT256 and not allow_unlimited:
                return {
                    "status": "error",
                    "error_code": "unlimited_amount_forbidden",
                    "message": (
                        "Unlimited transfer amount (type(uint256).max) rejected by default for safety. "
                        "To permit unlimited transfer, explicitly set 'allow_unlimited: true'."
                    ),
                }

        # Nonce
        raw_nonce = params.get("nonce", 0)
        try:
            nonce_int = int(raw_nonce)
            if nonce_int < 0:
                raise ValueError("Nonce must be non-negative.")
        except Exception:
            return {
                "status": "error",
                "error_code": "invalid_nonce",
                "message": f"Parameter 'nonce' must be a non-negative integer, got {raw_nonce!r}.",
            }

        # Deadline / Expiration
        now_ts = int(time.time())
        raw_deadline = (
            params.get("deadline")
            or params.get("sig_deadline")
            or params.get("expiration")
        )
        if raw_deadline is None:
            # Default to 30 minutes from now
            deadline_int = now_ts + 1800
        else:
            try:
                deadline_int = int(raw_deadline)
                if deadline_int <= 0:
                    raise ValueError("Deadline must be positive.")
            except Exception:
                return {
                    "status": "error",
                    "error_code": "invalid_deadline",
                    "message": f"Parameter 'deadline' must be a positive integer timestamp, got {raw_deadline!r}.",
                }

        # Verifying contract (Permit2 address)
        raw_verifying = (
            params.get("verifying_contract")
            or chain_cfg.get("permit2")
            or CANONICAL_PERMIT2_ADDRESS
        )
        try:
            verifying_contract = normalize_evm_address(str(raw_verifying))
        except Exception as exc:
            return {
                "status": "error",
                "error_code": "invalid_verifying_contract",
                "message": f"Invalid verifyingContract address: {exc}",
            }

        domain = {
            "name": "Permit2",
            "chainId": chain_id,
            "verifyingContract": verifying_contract,
        }

        # Build typed_data according to permit_type
        if permit_type == "PermitTransferFrom":
            types_def = PERMIT_TRANSFER_FROM_TYPES
            message = {
                "permitted": {
                    "token": token_address,
                    "amount": amount_int,
                },
                "spender": spender_address,
                "nonce": nonce_int,
                "deadline": deadline_int,
            }
        else:
            permit_type = "PermitSingle"
            types_def = PERMIT_SINGLE_TYPES
            expiration_int = int(params.get("expiration", deadline_int))
            if expiration_int > MAX_UINT48:
                expiration_int = MAX_UINT48

            message = {
                "details": {
                    "token": token_address,
                    "amount": amount_int,
                    "expiration": expiration_int,
                    "nonce": nonce_int,
                },
                "spender": spender_address,
                "sigDeadline": deadline_int,
            }

        typed_data = {
            "types": types_def,
            "primaryType": permit_type,
            "domain": domain,
            "message": message,
        }

        # Compute EIP-712 digest
        try:
            signable_msg = encode_typed_data(full_message=typed_data)
            digest = "0x" + _hash_eip191_message(signable_msg).hex()
        except Exception as exc:
            return {
                "status": "error",
                "error_code": "encoding_error",
                "message": f"Failed to encode EIP-712 typed data: {exc}",
            }

        return {
            "status": "ok",
            "action": "build_permit2",
            "chain": str(chain_name).lower(),
            "chain_id": chain_id,
            "token": token_address,
            "spender": spender_address,
            "amount": str(amount_int),
            "primary_type": permit_type,
            "verifying_contract": verifying_contract,
            "typed_data": typed_data,
            "digest": digest,
            "preview": {
                "token": token_address,
                "spender": spender_address,
                "spender_label": spender_label,
                "amount": str(amount_int),
                "nonce": nonce_int,
                "deadline": deadline_int,
                "is_expired": deadline_int <= now_ts,
            },
        }

    # -------------------------------------------------------------------------
    # Action: validate_typed_data
    # -------------------------------------------------------------------------

    def _action_validate_typed_data(self, params: Dict[str, Any]) -> Dict[str, Any]:
        typed_data = params.get("typed_data")
        if not isinstance(typed_data, dict):
            return {
                "status": "error",
                "error_code": "missing_typed_data",
                "message": "Parameter 'typed_data' must be a valid EIP-712 dictionary.",
            }

        domain = typed_data.get("domain")
        types_map = typed_data.get("types")
        primary_type = typed_data.get("primaryType")
        message = typed_data.get("message")

        errors: List[str] = []
        warnings: List[str] = []

        if not isinstance(domain, dict):
            errors.append("Missing or invalid 'domain' object.")
        if not isinstance(types_map, dict):
            errors.append("Missing or invalid 'types' definition.")
        if not primary_type or not isinstance(primary_type, str):
            errors.append("Missing or invalid 'primaryType'.")
        if not isinstance(message, dict):
            errors.append("Missing or invalid 'message' payload.")

        if errors:
            return {
                "status": "error",
                "is_valid": False,
                "errors": errors,
                "warnings": warnings,
            }

        # Check domain fields
        domain_name = domain.get("name")
        if domain_name != "Permit2":
            errors.append(f"Domain name must be 'Permit2', got {domain_name!r}.")

        chain_id = domain.get("chainId")
        if not isinstance(chain_id, int) or chain_id <= 0:
            errors.append(
                f"Domain chainId must be a positive integer, got {chain_id!r}."
            )

        expected_chain = params.get("expected_chain")
        if expected_chain:
            try:
                exp_cfg = resolve_chain(str(expected_chain), require_enabled=False)
                if int(exp_cfg["chain_id"]) != chain_id:
                    errors.append(
                        f"Domain chainId {chain_id} does not match expected chain "
                        f"{expected_chain!r} (chainId {exp_cfg['chain_id']})."
                    )
            except Exception as exc:
                errors.append(
                    f"Could not resolve expected_chain {expected_chain!r}: {exc}"
                )

        verifying_contract = domain.get("verifyingContract")
        try:
            verifying_norm = normalize_evm_address(str(verifying_contract))
        except Exception:
            errors.append(f"Invalid verifyingContract address: {verifying_contract!r}.")
            verifying_norm = str(verifying_contract)

        # Check message content based on primaryType
        now_ts = int(time.time())
        token_found: Optional[str] = None
        spender_found: Optional[str] = None
        amount_found: Optional[int] = None
        deadline_found: Optional[int] = None

        if primary_type == "PermitSingle":
            details = message.get("details", {})
            if isinstance(details, dict):
                token_found = details.get("token")
                amount_found = details.get("amount")
                expiration_found = details.get("expiration")
                if isinstance(expiration_found, int) and expiration_found <= now_ts:
                    warnings.append(
                        f"Permit expiration timestamp ({expiration_found}) has already passed."
                    )
            spender_found = message.get("spender")
            deadline_found = message.get("sigDeadline")
        elif primary_type == "PermitTransferFrom":
            permitted = message.get("permitted", {})
            if isinstance(permitted, dict):
                token_found = permitted.get("token")
                amount_found = permitted.get("amount")
            spender_found = message.get("spender")
            deadline_found = message.get("deadline")
        else:
            warnings.append(
                f"Primary type {primary_type!r} is not a standard Uniswap Permit2 single action."
            )

        # Validate token address
        if token_found:
            try:
                normalize_evm_address(str(token_found))
            except Exception:
                errors.append(f"Invalid token address in message: {token_found!r}.")

        # Validate spender address
        if spender_found:
            try:
                norm_spender = normalize_evm_address(str(spender_found))
                expected_spender = params.get("expected_spender")
                if expected_spender:
                    if norm_spender.lower() != str(expected_spender).strip().lower():
                        errors.append(
                            f"Spender address {norm_spender} does not match expected_spender {expected_spender}."
                        )
            except Exception:
                errors.append(f"Invalid spender address in message: {spender_found!r}.")

        # Check deadline
        if isinstance(deadline_found, int):
            if deadline_found <= now_ts:
                warnings.append(
                    f"Signature deadline ({deadline_found}) has already expired."
                )

        # Check amount against safety limits
        allow_unlimited = bool(params.get("allow_unlimited", False))
        if isinstance(amount_found, int):
            max_limit = (
                MAX_UINT256 if primary_type == "PermitTransferFrom" else MAX_UINT160
            )
            type_label = (
                "uint256" if primary_type == "PermitTransferFrom" else "uint160"
            )
            if amount_found >= max_limit and not allow_unlimited:
                warnings.append(
                    f"Approval amount is max/unlimited (>= type({type_label}).max). Ensure this is intentional."
                )

        # Try computing digest
        digest: Optional[str] = None
        try:
            signable_msg = encode_typed_data(full_message=typed_data)
            digest = "0x" + _hash_eip191_message(signable_msg).hex()
        except Exception as exc:
            errors.append(f"EIP-712 encode error: {exc}")

        is_valid = len(errors) == 0

        return {
            "status": "ok" if is_valid else "error",
            "is_valid": is_valid,
            "primary_type": primary_type,
            "chain_id": chain_id,
            "verifying_contract": verifying_norm,
            "digest": digest,
            "errors": errors,
            "warnings": warnings,
        }

    # -------------------------------------------------------------------------
    # Action: hash_typed_data
    # -------------------------------------------------------------------------

    def _action_hash_typed_data(self, params: Dict[str, Any]) -> Dict[str, Any]:
        typed_data = params.get("typed_data")
        if not isinstance(typed_data, dict):
            return {
                "status": "error",
                "error_code": "missing_typed_data",
                "message": "Parameter 'typed_data' is required and must be an EIP-712 dictionary.",
            }

        try:
            signable_msg = encode_typed_data(full_message=typed_data)
            digest = "0x" + _hash_eip191_message(signable_msg).hex()
            primary_type = typed_data.get("primaryType", "PermitSingle")
            return {
                "status": "ok",
                "digest": digest,
                "primary_type": primary_type,
            }
        except Exception as exc:
            return {
                "status": "error",
                "error_code": "hashing_failed",
                "message": f"Failed to compute EIP-712 hash: {exc}",
            }

    # -------------------------------------------------------------------------
    # Action: read_nonce
    # -------------------------------------------------------------------------

    def _action_read_nonce(self, params: Dict[str, Any]) -> Dict[str, Any]:
        chain_name = params.get("chain")
        if not chain_name:
            return {
                "status": "error",
                "error_code": "missing_chain",
                "message": "Parameter 'chain' is required to read on-chain nonce.",
            }

        owner_raw = params.get("owner") or params.get("holder") or params.get("user")
        if not owner_raw:
            return {
                "status": "error",
                "error_code": "missing_owner",
                "message": "Parameter 'owner' address is required to query nonce.",
            }

        token_raw = params.get("token")
        if not token_raw:
            return {
                "status": "error",
                "error_code": "missing_token",
                "message": "Parameter 'token' address or symbol is required to query nonce.",
            }

        spender_raw = params.get("spender")
        if not spender_raw:
            return {
                "status": "error",
                "error_code": "missing_spender",
                "message": "Parameter 'spender' address or alias is required to query nonce.",
            }

        try:
            chain_cfg = resolve_chain(str(chain_name))
        except Exception as exc:
            return {
                "status": "error",
                "error_code": "invalid_chain",
                "message": str(exc),
            }

        try:
            owner_str = str(owner_raw).strip()
            if _RAW_40HEX_RE.match(owner_str) and not owner_str.startswith("0x"):
                owner_str = "0x" + owner_str
            owner_addr = normalize_evm_address(owner_str)
            token_addr = self._resolve_token_address(str(chain_name), str(token_raw))
            spender_addr, _ = self._resolve_spender_address(
                str(chain_name), chain_cfg, str(spender_raw)
            )
        except Exception as exc:
            return {
                "status": "error",
                "error_code": "invalid_address",
                "message": f"Address normalization failed: {exc}",
            }

        if not self._web3_factory and not is_rpc_configured(
            str(chain_name), credential_fn=self.credential
        ):
            return {
                "status": "error",
                "error_code": "rpc_not_configured",
                "message": (
                    f"RPC URL is not configured for chain {chain_name!r}. "
                    "Set RPC environment variable in .env."
                ),
            }

        try:
            if self._web3_factory:
                w3 = self._web3_factory(str(chain_name))
            else:
                w3 = get_web3(str(chain_name), credential_fn=self.credential)

            permit2_raw = chain_cfg.get("permit2") or CANONICAL_PERMIT2_ADDRESS
            permit2_addr = normalize_evm_address(str(permit2_raw))
            contract = w3.eth.contract(address=permit2_addr, abi=PERMIT2_VIEW_ABI)
            allowance_result = contract.functions.allowance(
                owner_addr, token_addr, spender_addr
            ).call()
            amount, expiration, nonce = allowance_result

            return {
                "status": "ok",
                "chain": str(chain_name).lower(),
                "owner": owner_addr,
                "token": token_addr,
                "spender": spender_addr,
                "nonce": int(nonce),
                "current_allowance": str(amount),
                "expiration": int(expiration),
            }
        except Exception as exc:
            return {
                "status": "error",
                "error_code": "rpc_call_failed",
                "message": f"Failed to query Permit2 allowance from RPC: {exc}",
            }

    # -------------------------------------------------------------------------
    # Helper utilities
    # -------------------------------------------------------------------------

    def _resolve_token_address(self, chain_name: str, raw_token: str) -> str:
        token_str = str(raw_token or "").strip()
        if not token_str:
            raise ValueError("Parameter 'token' address or symbol is required.")

        cfg = load_merged_evm_config()
        chain_key = chain_name.strip().lower()
        chain_tokens = cfg.tokens.get(chain_key, {})
        sym_lower = token_str.lower()
        if sym_lower in chain_tokens:
            token_info = chain_tokens[sym_lower]
            addr = token_info.get("address")
            if addr:
                return normalize_evm_address(addr)

        if _RAW_40HEX_RE.match(token_str) and not token_str.startswith("0x"):
            token_str = "0x" + token_str
        return normalize_evm_address(token_str)

    def _resolve_spender_address(
        self,
        chain_name: str,
        chain_cfg: Dict[str, Any],
        raw_spender: str,
    ) -> Tuple[str, str]:
        spender_str = str(raw_spender or "").strip()
        if not spender_str:
            raise ValueError("Parameter 'spender' address or alias is required.")

        if spender_str.lower() in ("router_v2", "router"):
            router_addr = chain_cfg.get("router_v2")
            if not router_addr:
                raise ValueError(
                    f"router_v2 is not configured for chain {chain_name!r}."
                )
            norm_addr = normalize_evm_address(router_addr)
            return norm_addr, "Uniswap V2 Router"

        if _RAW_40HEX_RE.match(spender_str) and not spender_str.startswith("0x"):
            spender_str = "0x" + spender_str
        norm_addr = normalize_evm_address(spender_str)

        # Map configured router to human-readable label if addresses match
        configured_router = chain_cfg.get("router_v2")
        if configured_router and norm_addr.lower() == str(configured_router).lower():
            label = "Uniswap V2 Router"
        else:
            label = KNOWN_SPENDER_LABELS.get(norm_addr.lower(), "Unknown Spender")

        return norm_addr, label

    def _parse_amount(self, raw_amount: Any, permit_type: str = "PermitSingle") -> int:
        if isinstance(raw_amount, float):
            if raw_amount != int(raw_amount):
                raise ValueError(
                    f"Amount {raw_amount} has fractional decimals. "
                    "Amount must be an integer in atomic base units (wei)."
                )
            val = int(raw_amount)
            if val < 0:
                raise ValueError("Amount cannot be negative.")
            return val

        if isinstance(raw_amount, int):
            if raw_amount < 0:
                raise ValueError("Amount cannot be negative.")
            return raw_amount

        text = str(raw_amount).strip().lower()
        if text in ("max", "unlimited"):
            return MAX_UINT256 if permit_type == "PermitTransferFrom" else MAX_UINT160

        try:
            if "." in text:
                f_val = float(text)
                if f_val != int(f_val):
                    raise ValueError(
                        f"Amount '{raw_amount}' has fractional decimals. "
                        "Amount must be an integer in atomic base units (wei)."
                    )
                val = int(f_val)
                if val < 0:
                    raise ValueError("Amount cannot be negative.")
                return val
        except ValueError as exc:
            if "fractional decimals" in str(exc):
                raise

        if text.startswith("0x"):
            val = int(text, 16)
        else:
            val = int(text)

        if val < 0:
            raise ValueError("Amount cannot be negative.")
        return val
