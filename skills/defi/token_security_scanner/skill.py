"""
defi/token_security_scanner — read-only GoPlus token security report for agents.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
import yaml
from skillware.core.base_skill import BaseSkill

_SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
_GOPLUS_BASE = "https://api.gopluslabs.io/api/v1/token_security"
_REQUEST_TIMEOUT = 15

_VALID_ACTIONS = {"scan", "supported_chains"}
_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


class TokenSecurityScannerSkill(BaseSkill):
    """Deterministic GoPlus-backed token contract safety report."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.chains = self._load_chains()
        self._session = requests.Session()

    @property
    def manifest(self) -> Dict[str, Any]:
        path = os.path.join(_SKILL_DIR, "manifest.yaml")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as handle:
                return yaml.safe_load(handle) or {}
        return {}

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        action = params.get("action")
        if not action:
            return self._error(
                "missing_action",
                "The 'action' parameter is required "
                f"(one of: {sorted(_VALID_ACTIONS)}).",
            )
        if action not in _VALID_ACTIONS:
            return self._error(
                "invalid_action",
                f"Unknown action '{action}'. Valid: {sorted(_VALID_ACTIONS)}.",
            )

        if action == "supported_chains":
            return self._supported_chains()
        return self._scan(params)

    # --- Actions ---

    def _supported_chains(self) -> Dict[str, Any]:
        chains = [
            {
                "slug": slug,
                "chain_id": meta["chain_id"],
                "label": meta.get("label", slug),
            }
            for slug, meta in sorted(self.chains.items(), key=lambda item: item[0])
        ]
        return {
            "status": "ok",
            "chains": chains,
            "fetched_at": self._now(),
        }

    def _scan(self, params: Dict[str, Any]) -> Dict[str, Any]:
        chain = (params.get("chain") or "").strip().lower()
        contract_raw = (params.get("contract") or "").strip()

        if not chain:
            return self._error(
                "missing_chain",
                "Action 'scan' requires 'chain' " "(call supported_chains for slugs).",
            )
        if chain not in self.chains:
            return self._error(
                "unsupported_chain",
                f"Chain '{chain}' is not supported. "
                "Call supported_chains for the list.",
            )
        if not contract_raw:
            return self._error(
                "missing_contract",
                "Action 'scan' requires 'contract' (0x… address).",
            )

        ok, contract_or_err = self._normalize_address(contract_raw)
        if not ok:
            return self._error("invalid_contract", contract_or_err)

        contract = contract_or_err
        chain_id = str(self.chains[chain]["chain_id"])
        warnings: List[str] = [
            "API coverage varies by chain",
            "Not a substitute for a professional audit",
        ]

        try:
            payload, http_meta = self._fetch_goplus(chain_id, contract)
        except requests.exceptions.Timeout:
            return self._error(
                "timeout",
                "GoPlus Token Security request timed out.",
            )
        except requests.exceptions.ConnectionError:
            return self._error(
                "connection_error",
                "Could not connect to GoPlus Token Security API.",
            )
        except requests.exceptions.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code == 429:
                return self._error(
                    "rate_limited",
                    "GoPlus API rate limit exceeded. Wait and retry.",
                )
            if status_code == 401:
                return self._error(
                    "auth_error",
                    "GoPlus rejected the Authorization header. "
                    "Check GOPLUS_APP_KEY or omit it for free tier.",
                )
            return self._error(
                "api_error",
                f"GoPlus API returned HTTP {status_code}.",
            )
        except ValueError as exc:
            return self._error("api_error", str(exc))

        result_map = payload.get("result") or {}
        if not isinstance(result_map, dict) or not result_map:
            return {
                "status": "ok",
                "chain": chain,
                "contract": contract,
                "risk_tier": "unknown",
                "signals": {},
                "token": {},
                "sources": [
                    {
                        "provider": "goplus",
                        "fetched_at": http_meta["fetched_at"],
                        "chain_id": chain_id,
                    }
                ],
                "warnings": warnings
                + ["No GoPlus result for this contract on this chain"],
                "contract_errors": ["goplus_empty_result"],
            }

        raw = result_map.get(contract.lower())
        if raw is None and len(result_map) == 1:
            raw = next(iter(result_map.values()))
        if not isinstance(raw, dict):
            return self._error(
                "api_error",
                "GoPlus returned an unexpected result shape.",
            )

        signals, token_meta, parse_warnings = self._normalize_goplus(raw)
        warnings.extend(parse_warnings)
        risk_tier, contract_errors = self._derive_risk(signals)

        return {
            "status": "ok",
            "chain": chain,
            "contract": contract,
            "risk_tier": risk_tier,
            "signals": signals,
            "token": token_meta,
            "sources": [
                {
                    "provider": "goplus",
                    "fetched_at": http_meta["fetched_at"],
                    "chain_id": chain_id,
                    "code": payload.get("code"),
                    "message": payload.get("message"),
                }
            ],
            "warnings": warnings,
            "contract_errors": contract_errors,
        }

    # --- GoPlus ---

    def _fetch_goplus(
        self, chain_id: str, contract: str
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        url = f"{_GOPLUS_BASE}/{chain_id}"
        headers: Dict[str, str] = {"Accept": "application/json"}
        app_key = self.credential("GOPLUS_APP_KEY")
        if app_key:
            headers["Authorization"] = f"Bearer {app_key}"

        response = self._session.get(
            url,
            params={"contract_addresses": contract},
            headers=headers,
            timeout=_REQUEST_TIMEOUT,
        )
        fetched_at = self._now()
        if response.status_code >= 400:
            response.raise_for_status()

        try:
            payload = response.json()
        except ValueError as exc:
            raise ValueError("GoPlus returned non-JSON body.") from exc

        if not isinstance(payload, dict):
            raise ValueError("GoPlus returned a non-object JSON payload.")

        # GoPlus wraps business errors in HTTP 200 with code != 1.
        code = payload.get("code")
        if code is not None and int(code) != 1:
            message = payload.get("message") or "GoPlus business error"
            raise ValueError(f"GoPlus error code {code}: {message}")

        return payload, {"fetched_at": fetched_at}

    def _normalize_goplus(
        self, raw: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
        warnings: List[str] = []
        owner = raw.get("owner_address")
        owner_renounced = None
        if isinstance(owner, str) and owner:
            owner_renounced = owner.lower() in {
                "0x0000000000000000000000000000000000000000",
                "0x000000000000000000000000000000000000dead",
            }
        elif "owner_address" in raw and (owner is None or owner == ""):
            owner_renounced = True

        signals: Dict[str, Any] = {
            "is_honeypot": self._as_bool(raw.get("is_honeypot")),
            "buy_tax_pct": self._as_pct(raw.get("buy_tax")),
            "sell_tax_pct": self._as_pct(raw.get("sell_tax")),
            "is_proxy": self._as_bool(raw.get("is_proxy")),
            "owner_renounced": owner_renounced,
            "can_mint": self._as_bool(raw.get("is_mintable")),
            "is_open_source": self._as_bool(raw.get("is_open_source")),
            "is_blacklisted": self._as_bool(raw.get("is_blacklisted")),
            "is_whitelisted": self._as_bool(raw.get("is_whitelisted")),
            "transfer_pausable": self._as_bool(raw.get("transfer_pausable")),
            "tax_modifiable": (
                self._as_bool(raw.get("tax_modifiable"))
                if raw.get("tax_modifiable") not in (None, "")
                else self._as_bool(raw.get("slippage_modifiable"))
            ),
            "cannot_sell_all": self._as_bool(raw.get("cannot_sell_all")),
            "owner_change_balance": self._as_bool(raw.get("owner_change_balance")),
            "hidden_owner": self._as_bool(raw.get("hidden_owner")),
            "external_call": self._as_bool(raw.get("external_call")),
            "trading_cooldown": self._as_bool(raw.get("trading_cooldown")),
            "is_anti_whale": self._as_bool(raw.get("is_anti_whale")),
            "holder_count": self._as_int(raw.get("holder_count")),
        }

        if signals["is_open_source"] is False:
            warnings.append(
                "Contract source not verified on explorer — some signals unknown"
            )
        if signals["is_proxy"] is True:
            warnings.append(
                "Proxy contract — implementation may change; honeypot may be unknown"
            )
        if signals["is_honeypot"] is None and signals["is_open_source"] is not True:
            warnings.append("Honeypot status unknown")

        token_meta = {
            "name": raw.get("token_name"),
            "symbol": raw.get("token_symbol"),
            "decimals": self._as_int(raw.get("decimals")),
            "total_supply": raw.get("total_supply"),
            "owner_address": owner if isinstance(owner, str) else None,
            "creator_address": raw.get("creator_address"),
        }
        return signals, token_meta, warnings

    def _derive_risk(self, signals: Dict[str, Any]) -> Tuple[str, List[str]]:
        errors: List[str] = []
        buy = signals.get("buy_tax_pct")
        sell = signals.get("sell_tax_pct")

        if signals.get("is_honeypot") is True:
            errors.append("is_honeypot")
        if signals.get("cannot_sell_all") is True:
            errors.append("cannot_sell_all")
        if signals.get("owner_change_balance") is True:
            errors.append("owner_change_balance")
        if signals.get("hidden_owner") is True:
            errors.append("hidden_owner")

        if errors:
            return "critical", errors

        high_flags = []
        if signals.get("is_blacklisted") is True:
            high_flags.append("is_blacklisted")
        if signals.get("transfer_pausable") is True:
            high_flags.append("transfer_pausable")
        if isinstance(buy, (int, float)) and buy >= 10:
            high_flags.append("buy_tax_high")
        if isinstance(sell, (int, float)) and sell >= 10:
            high_flags.append("sell_tax_high")
        if (
            signals.get("is_open_source") is False
            and signals.get("is_honeypot") is None
        ):
            high_flags.append("closed_source_unknown_honeypot")

        if high_flags:
            return "high", high_flags

        medium_flags = []
        if signals.get("can_mint") is True:
            medium_flags.append("can_mint")
        if signals.get("is_proxy") is True:
            medium_flags.append("is_proxy")
        if signals.get("tax_modifiable") is True:
            medium_flags.append("tax_modifiable")
        if signals.get("owner_renounced") is False:
            medium_flags.append("owner_not_renounced")
        if isinstance(buy, (int, float)) and buy > 0:
            medium_flags.append("buy_tax")
        if isinstance(sell, (int, float)) and sell > 0:
            medium_flags.append("sell_tax")
        if signals.get("trading_cooldown") is True:
            medium_flags.append("trading_cooldown")
        if signals.get("external_call") is True:
            medium_flags.append("external_call")

        if medium_flags:
            return "medium", medium_flags

        # All known critical/high/medium clear — still unknown if key signals missing.
        if signals.get("is_honeypot") is None:
            return "unknown", ["honeypot_unknown"]

        return "low", []

    # --- Helpers ---

    def _load_chains(self) -> Dict[str, Dict[str, Any]]:
        path = os.path.join(_SKILL_DIR, "data", "chains.yaml")
        with open(path, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        if not isinstance(data, dict):
            return {}
        return {str(k).lower(): v for k, v in data.items() if isinstance(v, dict)}

    @staticmethod
    def _normalize_address(value: str) -> Tuple[bool, str]:
        if not _ADDRESS_RE.match(value):
            return False, (
                f"Invalid contract address '{value}'. "
                "Expected 0x followed by 40 hex characters."
            )
        return True, value.lower()

    @staticmethod
    def _as_bool(value: Any) -> Optional[bool]:
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in {"1", "true", "yes"}:
            return True
        if text in {"0", "false", "no"}:
            return False
        return None

    @staticmethod
    def _as_pct(value: Any) -> Optional[float]:
        if value is None or value == "":
            return None
        try:
            # GoPlus buy_tax / sell_tax are fractions (e.g. "0.05" = 5%) or already %.
            num = float(value)
        except (TypeError, ValueError):
            return None
        if num < 0:
            return None
        # Values <= 1 treated as fraction; > 1 treated as already percent.
        if num <= 1:
            return round(num * 100, 4)
        return round(num, 4)

    @staticmethod
    def _as_int(value: Any) -> Optional[int]:
        if value is None or value == "":
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _error(
        self,
        error_code: str,
        message: str,
        **extra: Any,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "status": "error",
            "error_code": error_code,
            "message": message,
            "fetched_at": self._now(),
        }
        body.update(extra)
        return body
