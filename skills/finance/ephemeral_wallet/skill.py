# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ARPA Hellenic Logical Systems

"""Spend-capped x402 agent payment sessions (PR1: mocked settlement)."""

from __future__ import annotations

import json
import os
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from skillware.core.base_skill import BaseSkill

try:
    from .providers import MockX402Provider, PaymentProvider
except (ImportError, ValueError):
    try:
        from skills.finance.ephemeral_wallet.providers import (  # type: ignore
            MockX402Provider,
            PaymentProvider,
        )
    except ImportError:
        _pkg_dir = os.path.dirname(os.path.abspath(__file__))
        if _pkg_dir not in sys.path:
            sys.path.insert(0, _pkg_dir)
        from providers import MockX402Provider, PaymentProvider  # noqa: E402

_CDP_ENV_KEYS = (
    "CDP_API_KEY_ID",
    "CDP_API_KEY_SECRET",
    "CDP_WALLET_SECRET",
)
_DEFAULT_NETWORK = "base-sepolia"
_DEFAULT_SPEND_CAP_USD = 5.0
_DEFAULT_TTL_SECONDS = 7200
_MOCK_WALLET = "0x1111111111111111111111111111111111111111"
_MAX_TTL_SECONDS = 7 * 24 * 3600
_MAX_SPEND_CAP_USD = 10_000.0

# Process-local session store (host passes session_id across turns).
_SESSIONS: Dict[str, Dict[str, Any]] = {}
_SESSIONS_LOCK = threading.RLock()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso(value: str) -> datetime:
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


class EphemeralWalletSkill(BaseSkill):
    """Create, status, pay, and revoke spend-capped agent payment sessions."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        *,
        provider: Optional[PaymentProvider] = None,
        sessions: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        super().__init__(config=config)
        self._provider: PaymentProvider = provider or MockX402Provider()
        # Allow tests to inject an isolated store; default is process memory.
        self._sessions = sessions if sessions is not None else _SESSIONS

    @property
    def manifest(self) -> Dict[str, Any]:
        return self.load_manifest_from_dir(os.path.dirname(__file__))

    def execute(
        self,
        params: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        payload = dict(params or {})
        payload.update(kwargs)
        try:
            self.validate_params(payload)
        except Exception as exc:
            return self._error("error", str(exc))

        action = str(payload.get("action") or "").strip().lower()
        if action == "create_session":
            return self._create_session(payload)
        if action == "status":
            return self._status(payload)
        if action == "pay":
            return self._pay(payload)
        if action == "revoke":
            return self._revoke(payload)
        return self._error(
            "error",
            f"Unsupported action {action!r}; "
            "use create_session, status, pay, or revoke.",
        )

    # ----- actions ---------------------------------------------------------

    def _create_session(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        live_gate = self._live_gate(payload)
        if live_gate is not None:
            return live_gate

        if "spend_cap_usd" in payload and payload.get("spend_cap_usd") not in (
            None,
            "",
        ):
            try:
                spend_cap = float(payload["spend_cap_usd"])
            except (TypeError, ValueError):
                return self._error("error", "spend_cap_usd must be a number.")
        else:
            spend_cap = self._config_float(
                "default_spend_cap_usd", _DEFAULT_SPEND_CAP_USD
            )
            if spend_cap is None:
                spend_cap = _DEFAULT_SPEND_CAP_USD

        if "ttl_seconds" in payload and payload.get("ttl_seconds") not in (None, ""):
            try:
                ttl_seconds = int(payload["ttl_seconds"])
            except (TypeError, ValueError):
                return self._error("error", "ttl_seconds must be an integer.")
        else:
            ttl_seconds = self._config_int("default_ttl_seconds", _DEFAULT_TTL_SECONDS)

        if spend_cap <= 0 or spend_cap > _MAX_SPEND_CAP_USD:
            return self._error(
                "error",
                f"spend_cap_usd must be in (0, {_MAX_SPEND_CAP_USD}].",
            )
        if ttl_seconds <= 0 or ttl_seconds > _MAX_TTL_SECONDS:
            return self._error(
                "error",
                f"ttl_seconds must be in (0, {_MAX_TTL_SECONDS}].",
            )

        network = (
            str(
                payload.get("network")
                or self.credential("EPHEMERAL_WALLET_NETWORK")
                or self.config.get("network")
                or _DEFAULT_NETWORK
            )
            .strip()
            .lower()
        )
        now = _utc_now()
        session_id = f"ews_{uuid4().hex}"
        session = {
            "session_id": session_id,
            "spend_cap_usd": float(spend_cap),
            "remaining_usd": float(spend_cap),
            "ttl_seconds": int(ttl_seconds),
            "created_at": _iso(now),
            "expires_at": _iso(now + timedelta(seconds=int(ttl_seconds))),
            "network": network,
            "wallet_address": _MOCK_WALLET,
            "revoked": False,
            "revoked_at": None,
            "payments": [],
            "policy_note": (
                "spend_cap_usd / TTL / revoke are soft in-process policy in v0.1; "
                "funded-to-cap enforcement lands with live settle."
            ),
            "settlement": "mock",
        }

        try:
            session_dir = self._session_dir()
            if session_dir is not None:
                self._append_jsonl(
                    session_dir / "sessions.jsonl",
                    {
                        "event": "create",
                        "session_id": session_id,
                        "spend_cap_usd": session["spend_cap_usd"],
                        "expires_at": session["expires_at"],
                        "network": network,
                        "at": session["created_at"],
                    },
                )
        except OSError as exc:
            return self._error(
                "error",
                f"EPHEMERAL_WALLET_SESSION_DIR is set but not writable: {exc}",
                agent_hint=(
                    "Fix the session dir path/permissions, or unset "
                    "EPHEMERAL_WALLET_SESSION_DIR to use process memory only."
                ),
            )

        with _SESSIONS_LOCK:
            self._sessions[session_id] = session

        return {
            "status": "ready",
            "session_id": session_id,
            "spend_cap_usd": session["spend_cap_usd"],
            "remaining_usd": session["remaining_usd"],
            "expires_at": session["expires_at"],
            "network": network,
            "wallet_address": session["wallet_address"],
            "settlement": "mock",
            "agent_hint": (
                "Pass session_id on later status/pay/revoke. "
                "No secrets in this payload. Cap/TTL are soft policy until live settle."
            ),
        }

    def _status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        session, err = self._load_session(payload)
        if err is not None:
            return err
        assert session is not None
        expired = self._is_expired(session)
        last = session["payments"][-1] if session["payments"] else None
        status = "ready"
        if session["revoked"]:
            status = "revoked"
        elif expired:
            status = "expired"
        return {
            "status": status,
            "session_id": session["session_id"],
            "remaining_usd": session["remaining_usd"],
            "expires_at": session["expires_at"],
            "revoked": bool(session["revoked"]),
            "payments_count": len(session["payments"]),
            "last_payment": last,
            "settlement": session.get("settlement", "mock"),
            "policy_note": session.get("policy_note"),
            "agent_hint": (
                "remaining_usd is a display counter for soft session policy; "
                "do not treat it as a hard on-chain bound in v1."
            ),
        }

    def _pay(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        live_gate = self._live_gate(payload)
        if live_gate is not None:
            return live_gate

        session, err = self._load_session(payload)
        if err is not None:
            return err
        assert session is not None

        if session["revoked"]:
            return self._error(
                "revoked",
                f"Session {session['session_id']} is revoked.",
                session_id=session["session_id"],
            )
        if self._is_expired(session):
            return self._error(
                "expired",
                f"Session {session['session_id']} expired at {session['expires_at']}.",
                session_id=session["session_id"],
            )

        url = str(payload.get("url") or "").strip()
        if not url:
            return self._error(
                "error",
                "url is required for pay.",
                session_id=session["session_id"],
            )

        amount = self._as_float(payload.get("amount_usd"), None)
        if amount is None or amount <= 0:
            return self._error(
                "error",
                "amount_usd must be a positive number.",
                session_id=session["session_id"],
            )
        if amount > float(session["remaining_usd"]) + 1e-9:
            return self._error(
                "over_cap",
                (
                    f"amount_usd {amount} exceeds remaining_usd "
                    f"{session['remaining_usd']} (soft session policy)."
                ),
                session_id=session["session_id"],
                remaining_usd=session["remaining_usd"],
                agent_hint=(
                    "Lower amount_usd, create a new session with a higher cap, "
                    "or revoke and restart. Cap is soft until funded-to-cap live settle."
                ),
            )

        payment = self._provider.pay(
            session_id=session["session_id"],
            url=url,
            amount_usd=float(amount),
            network=session["network"],
        )
        # Strip any accidental secret-looking keys from provider output.
        payment = self._sanitize_payment(payment)

        session["remaining_usd"] = round(
            float(session["remaining_usd"]) - float(amount), 8
        )
        session["payments"].append(payment)

        try:
            session_dir = self._session_dir()
            if session_dir is not None:
                self._append_jsonl(
                    session_dir / "payments.jsonl",
                    {
                        "event": "pay",
                        "session_id": session["session_id"],
                        "url": payment.get("url"),
                        "amount_usd": payment.get("amount_usd"),
                        "tx_ref": payment.get("tx_ref"),
                        "receipt_ref": payment.get("receipt_ref"),
                        "at": payment.get("at"),
                    },
                )
        except OSError as exc:
            # Roll back in-memory debit if durability was requested.
            session["remaining_usd"] = round(
                float(session["remaining_usd"]) + float(amount), 8
            )
            session["payments"].pop()
            return self._error(
                "error",
                f"EPHEMERAL_WALLET_SESSION_DIR is set but not writable: {exc}",
                session_id=session["session_id"],
            )

        return {
            "status": "confirmed",
            "session_id": session["session_id"],
            "remaining_usd": session["remaining_usd"],
            "payment": payment,
            "settlement": "mock",
            "agent_hint": (
                "Do not ask for or display private keys or card PANs. "
                "This confirmation is from the mock provider (v0.1)."
            ),
        }

    def _revoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        session, err = self._load_session(payload)
        if err is not None:
            return err
        assert session is not None

        now = _utc_now()
        session["revoked"] = True
        session["revoked_at"] = _iso(now)

        try:
            session_dir = self._session_dir()
            if session_dir is not None:
                self._append_jsonl(
                    session_dir / "sessions.jsonl",
                    {
                        "event": "revoke",
                        "session_id": session["session_id"],
                        "remaining_usd": session["remaining_usd"],
                        "at": session["revoked_at"],
                    },
                )
        except OSError as exc:
            return self._error(
                "error",
                f"EPHEMERAL_WALLET_SESSION_DIR is set but not writable: {exc}",
                session_id=session["session_id"],
            )

        return {
            "status": "revoked",
            "session_id": session["session_id"],
            "remaining_usd": session["remaining_usd"],
            "revoked_at": session["revoked_at"],
            "agent_hint": (
                "Session revoked in-process. Further pay calls fail closed. "
                "Revoke is soft policy until funded-to-cap / sweep."
            ),
        }

    # ----- helpers ---------------------------------------------------------

    def _live_gate(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """PR1: mock by default; live request without CDP → missing_config."""
        wants_live = self._wants_live(payload)
        if not wants_live:
            return None
        missing = [k for k in _CDP_ENV_KEYS if not self.credential(k)]
        if missing:
            return {
                "status": "missing_config",
                "error": (
                    "Live settlement requested but CDP wallet env is incomplete: "
                    + ", ".join(missing)
                ),
                "agent_hint": (
                    "Add CDP_API_KEY_ID, CDP_API_KEY_SECRET, and CDP_WALLET_SECRET "
                    "to a local .env (never tool args). Or omit live / keep mock "
                    "mode for offline demos. Live x402 settle is not in v0.1."
                ),
                "setup": {
                    "env_vars": list(_CDP_ENV_KEYS),
                    "where": "Project-root .env (skillware.core.env.load_env_file)",
                    "never": "Do not pass CDP secrets in tool arguments, YAML, or chat.",
                    "docs": "docs/skills/finance/ephemeral_wallet.md#environment",
                },
            }
        return {
            "status": "error",
            "error": "Live x402 + CDP settlement is not wired in v0.1 (mock only).",
            "agent_hint": (
                "Retry without live=true / with EPHEMERAL_WALLET_MOCK=1. "
                "Live settle is a later slice."
            ),
        }

    def _wants_live(self, payload: Dict[str, Any]) -> bool:
        if payload.get("live") is True:
            return True
        live_raw = payload.get("live")
        if isinstance(live_raw, str) and live_raw.strip().lower() in {
            "1",
            "true",
            "yes",
        }:
            return True
        mock_env = (self.credential("EPHEMERAL_WALLET_MOCK") or "1").strip().lower()
        return mock_env in {"0", "false", "no"}

    def _load_session(
        self,
        payload: Dict[str, Any],
    ) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        session_id = str(payload.get("session_id") or "").strip()
        if not session_id:
            return None, self._error(
                "error",
                "session_id is required.",
                agent_hint="Call create_session first and pass the returned session_id.",
            )
        with _SESSIONS_LOCK:
            session = self._sessions.get(session_id)
        if session is None:
            return None, self._error(
                "error",
                f"Unknown session_id {session_id!r}.",
                agent_hint=(
                    "Session is process-local unless EPHEMERAL_WALLET_SESSION_DIR "
                    "was set at create time; create a new session."
                ),
            )
        return session, None

    def _is_expired(self, session: Dict[str, Any]) -> bool:
        try:
            return _utc_now() >= _parse_iso(session["expires_at"])
        except (KeyError, TypeError, ValueError):
            return True

    def _session_dir(self) -> Optional[Path]:
        raw = self.credential("EPHEMERAL_WALLET_SESSION_DIR") or self.config.get(
            "session_dir"
        )
        if not raw:
            return None
        path = Path(str(raw)).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def _append_jsonl(path: Path, row: Dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    @staticmethod
    def _sanitize_payment(payment: Dict[str, Any]) -> Dict[str, Any]:
        blocked = {
            "private_key",
            "seed",
            "mnemonic",
            "cvv",
            "pan",
            "card_number",
            "secret",
            "api_key",
            "wallet_secret",
        }
        clean: Dict[str, Any] = {}
        for key, value in payment.items():
            if str(key).lower() in blocked:
                continue
            clean[key] = value
        return clean

    def _config_float(self, key: str, default: float) -> float:
        return self._as_float(self.config.get(key), default)

    def _config_int(self, key: str, default: int) -> int:
        return self._as_int(self.config.get(key), default)

    @staticmethod
    def _as_float(value: Any, default: Optional[float]) -> Optional[float]:
        if value is None or value == "":
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _as_int(value: Any, default: int) -> int:
        if value is None or value == "":
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _error(
        status: str,
        message: str,
        *,
        agent_hint: Optional[str] = None,
        session_id: Optional[str] = None,
        remaining_usd: Optional[float] = None,
    ) -> Dict[str, Any]:
        out: Dict[str, Any] = {"status": status, "error": message}
        if agent_hint:
            out["agent_hint"] = agent_hint
        else:
            out["agent_hint"] = (
                "Fail closed. Do not retry with secrets in tool args; "
                "fix the session or operator config."
            )
        if session_id is not None:
            out["session_id"] = session_id
        if remaining_usd is not None:
            out["remaining_usd"] = remaining_usd
        return out


# Clear process store (tests).
def _reset_sessions_for_tests() -> None:
    with _SESSIONS_LOCK:
        _SESSIONS.clear()
