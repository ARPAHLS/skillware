"""
defi/token_security_scanner — read-only GoPlus token security report for agents.
"""

from __future__ import annotations

import os
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

import requests
import yaml
from skillware.core.base_skill import BaseSkill
from skillware.core.config import global_config_dir
from skillware.core.evm_config import (
    list_configured_chains,
    load_merged_evm_config,
    resolve_chain,
)

_SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
_GOPLUS_BASE = "https://api.gopluslabs.io/api/v1/token_security"
_REQUEST_TIMEOUT = 15
_BATCH_LIMIT = 5
_REPORT_SCHEMA_VERSION = "0.2"
_RETRY_STATUSES = {429, 500, 502, 503, 504}
_POLICY_ACTIONS = {"allow", "flag", "block"}
_CLOSED_SOURCE_MODES = {"high", "block", "ignore"}
_TIER_RANK = {"low": 0, "medium": 1, "unknown": 2, "high": 3, "critical": 4}

_VALID_ACTIONS = {"scan", "scan_batch", "supported_chains"}
_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
_OPERATOR_POLICY_NAME = "token_scan_policy.yaml"


class PolicyError(ValueError):
    """Operator token-scan policy could not be loaded."""


class ScanPolicy:
    """Resolved token-scan thresholds and host actions."""

    def __init__(
        self,
        profile: str,
        high_tax_pct: float,
        medium_tax_above_pct: float,
        closed_source_unknown_honeypot: str,
        min_holder_count: Optional[int],
        actions: Mapping[str, str],
    ) -> None:
        self.profile = profile
        self.high_tax_pct = high_tax_pct
        self.medium_tax_above_pct = medium_tax_above_pct
        self.closed_source_unknown_honeypot = closed_source_unknown_honeypot
        self.min_holder_count = min_holder_count
        self.actions = actions


def _bundled_policy_path() -> Path:
    return Path(_SKILL_DIR) / "data" / "default_policy.yaml"


def _load_yaml(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise PolicyError(f"Policy file {path} must be a mapping.")
    return loaded


def _as_number(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise PolicyError(f"Policy field {field} must be a number.") from exc
    if number < 0:
        raise PolicyError(f"Policy field {field} must be >= 0.")
    return number


def load_scan_policy(path: Optional[Path] = None) -> ScanPolicy:
    """Load the bundled default, then overlay an operator file when given."""
    raw = _load_yaml(_bundled_policy_path())
    if path is not None:
        overlay = _load_yaml(path)
        raw.update({key: value for key, value in overlay.items() if key != "actions"})
        if isinstance(overlay.get("actions"), dict):
            base_actions = (
                raw.get("actions") if isinstance(raw.get("actions"), dict) else {}
            )
            merged_actions = dict(base_actions)
            merged_actions.update(overlay["actions"])
            raw["actions"] = merged_actions

    profile = str(raw.get("profile") or "").strip()
    if not profile:
        raise PolicyError("Policy profile name is required.")

    mode = str(raw.get("closed_source_unknown_honeypot") or "high").strip().lower()
    if mode not in _CLOSED_SOURCE_MODES:
        raise PolicyError(
            "closed_source_unknown_honeypot must be one of "
            f"{sorted(_CLOSED_SOURCE_MODES)}."
        )

    holder_raw = raw.get("min_holder_count")
    min_holders: Optional[int]
    if holder_raw is None or holder_raw == "":
        min_holders = None
    else:
        try:
            min_holders = int(holder_raw)
        except (TypeError, ValueError) as exc:
            raise PolicyError("min_holder_count must be an integer or null.") from exc
        if min_holders < 0:
            raise PolicyError("min_holder_count must be >= 0.")

    actions_raw = raw.get("actions")
    if not isinstance(actions_raw, dict):
        raise PolicyError("Policy actions must be a mapping.")
    actions: Dict[str, str] = {}
    for tier in _TIER_RANK:
        action = str(actions_raw.get(tier) or "").strip().lower()
        if action not in _POLICY_ACTIONS:
            raise PolicyError(
                f"Policy action for {tier} must be allow, flag, or block."
            )
        actions[tier] = action

    return ScanPolicy(
        profile=profile,
        high_tax_pct=_as_number(raw.get("high_tax_pct"), "high_tax_pct"),
        medium_tax_above_pct=_as_number(
            raw.get("medium_tax_above_pct"), "medium_tax_above_pct"
        ),
        closed_source_unknown_honeypot=mode,
        min_holder_count=min_holders,
        actions=actions,
    )


def load_goplus_chain_ids() -> set:
    path = Path(_SKILL_DIR) / "data" / "goplus_chain_ids.yaml"
    raw = _load_yaml(path)
    values = raw.get("chain_ids")
    if not isinstance(values, list) or not values:
        raise PolicyError("goplus_chain_ids.yaml is missing chain_ids.")
    return {int(item) for item in values}


class TokenSecurityScannerSkill(BaseSkill):
    """Deterministic GoPlus-backed token contract safety report."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._session = requests.Session()
        self._goplus_chain_ids = load_goplus_chain_ids()

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
        try:
            policy = self._resolve_policy(params.get("policy_path"))
        except PolicyError as exc:
            return self._error("invalid_policy", str(exc))
        if action == "scan_batch":
            return self._scan_batch(params, policy)
        return self._scan(params, policy)

    # --- Actions ---

    def _supported_chains(self) -> Dict[str, Any]:
        chains = []
        for slug, meta in list_configured_chains(enabled_only=True):
            chain_id = meta.get("chain_id")
            if chain_id is None:
                continue
            chains.append(
                {
                    "slug": slug,
                    "chain_id": str(chain_id),
                    "label": meta.get("label") or slug,
                    "goplus_supported": int(chain_id) in self._goplus_chain_ids,
                }
            )
        return {
            "status": "ok",
            "chains": chains,
            "fetched_at": self._now(),
        }

    def _scan_batch(self, params: Dict[str, Any], policy: ScanPolicy) -> Dict[str, Any]:
        items = params.get("items")
        if not isinstance(items, list) or not items:
            return self._error(
                "missing_items",
                "Action 'scan_batch' requires a non-empty 'items' list.",
            )
        if len(items) > _BATCH_LIMIT:
            return self._error(
                "batch_too_large",
                f"scan_batch accepts at most {_BATCH_LIMIT} items.",
            )
        reports: List[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                reports.append(
                    self._error(
                        "invalid_batch_item",
                        "Each scan_batch item must be an object.",
                    )
                )
                continue
            reports.append(self._scan(item, policy))

        worst = None
        for report in reports:
            tier = report.get("risk_tier")
            if report.get("status") != "ok" or tier not in _TIER_RANK:
                continue
            if worst is None or _TIER_RANK[tier] > _TIER_RANK[worst]:
                worst = tier
        return {
            "status": "ok",
            "reports": reports,
            "worst_risk_tier": worst,
            "policy_profile": policy.profile,
            "report_schema_version": _REPORT_SCHEMA_VERSION,
            "fetched_at": self._now(),
        }

    def _scan(self, params: Dict[str, Any], policy: ScanPolicy) -> Dict[str, Any]:
        chain = (params.get("chain") or "").strip().lower()
        contract_raw = (params.get("contract") or "").strip()
        token_slug = (params.get("token") or "").strip()

        if not chain:
            return self._error(
                "missing_chain",
                "Action 'scan' requires 'chain' (call supported_chains for slugs).",
            )
        try:
            chain_cfg = resolve_chain(chain)
        except ValueError as exc:
            return self._error("unsupported_chain", str(exc))

        chain_id_raw = chain_cfg.get("chain_id")
        if chain_id_raw is None:
            return self._error(
                "unsupported_chain",
                f"Chain '{chain}' has no chain_id in EVM config.",
            )
        chain_id = str(chain_id_raw)
        if int(chain_id_raw) not in self._goplus_chain_ids:
            return self._error(
                "goplus_unsupported_chain",
                f"Chain '{chain}' (id {chain_id}) is not in the GoPlus Token Security map.",
            )

        if token_slug and not contract_raw:
            resolved, token_err = self._resolve_token_slug(chain, token_slug)
            if token_err:
                return token_err
            contract_raw = resolved
        elif token_slug and contract_raw:
            resolved, token_err = self._resolve_token_slug(chain, token_slug)
            if token_err:
                return token_err

        if not contract_raw:
            return self._error(
                "missing_contract",
                "Action 'scan' requires 'contract' (0x…) or 'token' (evm.tokens slug).",
            )

        ok, contract_or_err = self._normalize_address(contract_raw)
        if not ok:
            return self._error("invalid_contract", contract_or_err)
        contract = contract_or_err

        if token_slug and contract_raw:
            ok_slug, slug_addr = self._normalize_address(
                self._resolve_token_slug(chain, token_slug)[0] or ""
            )
            if ok_slug and slug_addr != contract:
                return self._error(
                    "token_contract_mismatch",
                    f"Token '{token_slug}' on {chain} is {slug_addr}, not {contract}.",
                )

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
            return self._with_policy(
                {
                    "status": "ok",
                    "chain": chain,
                    "contract": contract,
                    "token_slug": token_slug or None,
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
                },
                policy,
                http_meta["fetched_at"],
                force_action=None,
            )

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
        risk_tier, contract_errors, force_action = self._derive_risk(signals, policy)

        return self._with_policy(
            {
                "status": "ok",
                "chain": chain,
                "contract": contract,
                "token_slug": token_slug or None,
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
            },
            policy,
            http_meta["fetched_at"],
            force_action=force_action,
        )

    # --- Policy ---

    def _operator_policy_file(self) -> Optional[Path]:
        env = (self.credential("TOKEN_SCAN_POLICY_PATH") or "").strip()
        if env:
            return Path(env).expanduser()
        candidate = global_config_dir() / _OPERATOR_POLICY_NAME
        if candidate.is_file():
            return candidate
        return None

    def _resolve_policy(self, explicit: Any) -> ScanPolicy:
        if explicit:
            path = Path(str(explicit)).expanduser()
            if not path.is_file():
                raise PolicyError(f"Policy file not found: {path}")
            return load_scan_policy(path)
        operator = self._operator_policy_file()
        if operator is None:
            return load_scan_policy(None)
        if not operator.is_file():
            raise PolicyError(f"Policy file not found: {operator}")
        return load_scan_policy(operator)

    def _with_policy(
        self,
        report: Dict[str, Any],
        policy: ScanPolicy,
        fetched_at: str,
        force_action: Optional[str],
    ) -> Dict[str, Any]:
        tier = str(report.get("risk_tier") or "unknown")
        action = force_action or policy.actions.get(tier, "block")
        stamp = fetched_at.replace("-", "").replace(":", "")
        prefix = str(report.get("contract") or "")[2:6]
        report["policy_action"] = action
        report["policy_profile"] = policy.profile
        report["report_schema_version"] = _REPORT_SCHEMA_VERSION
        report["report_id"] = f"tsr_{stamp}_{report.get('chain')}_{prefix}"
        return report

    def _resolve_token_slug(
        self, chain: str, symbol: str
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        merged = load_merged_evm_config()
        chain_tokens = merged.tokens.get(chain, {})
        if not isinstance(chain_tokens, dict):
            chain_tokens = {}
        meta = chain_tokens.get(symbol.lower())
        if not isinstance(meta, dict) or not meta.get("address"):
            return None, self._error(
                "unknown_token",
                f"Token '{symbol}' is not in evm.tokens for chain '{chain}'.",
            )
        return str(meta["address"]), None

    # --- GoPlus ---

    def _backoff(self) -> None:
        time.sleep(random.uniform(0.05, 0.25))

    def _fetch_goplus(
        self, chain_id: str, contract: str
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        url = f"{_GOPLUS_BASE}/{chain_id}"
        headers: Dict[str, str] = {"Accept": "application/json"}
        app_key = self.credential("GOPLUS_APP_KEY")
        if app_key:
            headers["Authorization"] = f"Bearer {app_key}"

        response = None
        for attempt in (0, 1):
            response = self._session.get(
                url,
                params={"contract_addresses": contract},
                headers=headers,
                timeout=_REQUEST_TIMEOUT,
            )
            if response.status_code in _RETRY_STATUSES and attempt == 0:
                self._backoff()
                continue
            break
        assert response is not None
        fetched_at = self._now()
        if response.status_code >= 400:
            response.raise_for_status()

        try:
            payload = response.json()
        except ValueError as exc:
            raise ValueError("GoPlus returned non-JSON body.") from exc

        if not isinstance(payload, dict):
            raise ValueError("GoPlus returned a non-object JSON payload.")

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

        holders = raw.get("holders")
        top_holder = None
        if isinstance(holders, list):
            percents = [
                self._as_pct(item.get("percent"))
                for item in holders
                if isinstance(item, dict)
            ]
            known = [item for item in percents if item is not None]
            if known:
                top_holder = max(known)

        dex = raw.get("dex")
        dex_count = (
            len(dex) if isinstance(dex, list) else self._as_int(raw.get("dex_count"))
        )

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
            "top_holder_pct": top_holder,
            "creator_percent": self._as_pct(raw.get("creator_percent")),
            "owner_percent": self._as_pct(raw.get("owner_percent")),
            "is_in_dex": self._as_bool(raw.get("is_in_dex")),
            "dex_count": dex_count,
            "lp_total_supply": raw.get("lp_total_supply") or None,
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

    def _derive_risk(
        self, signals: Dict[str, Any], policy: ScanPolicy
    ) -> Tuple[str, List[str], Optional[str]]:
        errors: List[str] = []
        force_action: Optional[str] = None
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
            return "critical", errors, None

        high_flags = []
        if signals.get("is_blacklisted") is True:
            high_flags.append("is_blacklisted")
        if signals.get("transfer_pausable") is True:
            high_flags.append("transfer_pausable")
        if isinstance(buy, (int, float)) and buy >= policy.high_tax_pct:
            high_flags.append("buy_tax_high")
        if isinstance(sell, (int, float)) and sell >= policy.high_tax_pct:
            high_flags.append("sell_tax_high")
        if (
            signals.get("is_open_source") is False
            and signals.get("is_honeypot") is None
        ):
            mode = policy.closed_source_unknown_honeypot
            if mode == "ignore":
                pass
            else:
                high_flags.append("closed_source_unknown_honeypot")
                if mode == "block":
                    force_action = "block"

        if high_flags:
            return "high", high_flags, force_action

        medium_flags = []
        if signals.get("can_mint") is True:
            medium_flags.append("can_mint")
        if signals.get("is_proxy") is True:
            medium_flags.append("is_proxy")
        if signals.get("tax_modifiable") is True:
            medium_flags.append("tax_modifiable")
        if signals.get("owner_renounced") is False:
            medium_flags.append("owner_not_renounced")
        if isinstance(buy, (int, float)) and buy > policy.medium_tax_above_pct:
            medium_flags.append("buy_tax")
        if isinstance(sell, (int, float)) and sell > policy.medium_tax_above_pct:
            medium_flags.append("sell_tax")
        if signals.get("trading_cooldown") is True:
            medium_flags.append("trading_cooldown")
        if signals.get("external_call") is True:
            medium_flags.append("external_call")
        holders = signals.get("holder_count")
        if (
            policy.min_holder_count is not None
            and isinstance(holders, int)
            and holders < policy.min_holder_count
        ):
            medium_flags.append("low_liquidity_holders")

        if medium_flags:
            return "medium", medium_flags, None

        if signals.get("is_honeypot") is None:
            return "unknown", ["honeypot_unknown"], None

        return "low", [], None

    # --- Helpers ---

    @staticmethod
    def _normalize_address(value: str) -> Tuple[bool, str]:
        """Validate hex address; checksum when web3 is present, else lowercase."""
        try:
            from skillware.core.evm_config import normalize_evm_address

            return True, normalize_evm_address(value).lower()
        except ImportError:
            pass
        except ValueError as exc:
            return False, str(exc)

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
            num = float(value)
        except (TypeError, ValueError):
            return None
        if num < 0:
            return None
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
