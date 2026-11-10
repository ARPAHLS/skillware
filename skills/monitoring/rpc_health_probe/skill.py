# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ARPA Hellenic Logical Systems

"""Read-only EVM JSON-RPC health probe for agent pre-trade gates."""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

from skillware.core.base_skill import BaseSkill
from skillware.core.evm_config import resolve_chain, resolve_rpc_url

_DEFAULT_MAX_LATENCY_MS = 2000
_DEFAULT_MAX_BLOCK_LAG = 3
_DEFAULT_TIMEOUT_S = 5.0
_MAX_TIMEOUT_S = 30.0


class RpcHealthProbeSkill(BaseSkill):
    """Probe operator RPC endpoints: chain ID, block height, latency, lag."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config=config)
        self._session = requests.Session()

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
            return {"status": "error", "error": str(exc), "all_healthy": False}

        action = str(payload.get("action") or "probe").strip().lower()
        if action != "probe":
            return {
                "status": "error",
                "error": f"Unsupported action {action!r}; only 'probe' is available.",
                "all_healthy": False,
            }

        endpoints = payload.get("endpoints") or []
        if not isinstance(endpoints, list) or not endpoints:
            return {
                "status": "error",
                "error": "endpoints must be a non-empty array.",
                "all_healthy": False,
            }

        max_latency_ms = self._as_int(
            payload.get("max_latency_ms"), _DEFAULT_MAX_LATENCY_MS
        )
        max_block_lag = self._as_int(
            payload.get("max_block_lag"), _DEFAULT_MAX_BLOCK_LAG
        )
        timeout_s = self._as_float(payload.get("timeout_s"), _DEFAULT_TIMEOUT_S)
        timeout_s = max(0.1, min(timeout_s, _MAX_TIMEOUT_S))

        results: List[Dict[str, Any]] = []
        for raw in endpoints:
            if not isinstance(raw, dict):
                results.append(
                    self._failed_row(
                        chain="unknown",
                        reasons=["invalid_endpoint_entry"],
                        detail="endpoint entries must be objects",
                    )
                )
                continue
            results.append(
                self._probe_endpoint(
                    raw,
                    max_latency_ms=max_latency_ms,
                    max_block_lag=max_block_lag,
                    timeout_s=timeout_s,
                )
            )

        all_healthy = bool(results) and all(
            row.get("status") == "healthy" for row in results
        )
        return {
            "status": "ok",
            "results": results,
            "all_healthy": all_healthy,
        }

    def _probe_endpoint(
        self,
        endpoint: Dict[str, Any],
        *,
        max_latency_ms: int,
        max_block_lag: int,
        timeout_s: float,
    ) -> Dict[str, Any]:
        chain = str(endpoint.get("chain") or "").strip().lower()
        if not chain:
            return self._failed_row(
                chain="unknown",
                reasons=["missing_chain"],
                detail="endpoint.chain is required",
            )

        try:
            chain_cfg = resolve_chain(chain, require_enabled=True)
            expected_chain_id = int(chain_cfg["chain_id"])
        except Exception as exc:
            return self._failed_row(
                chain=chain,
                reasons=["chain_config_error"],
                detail=str(exc),
            )

        try:
            target_url = self._resolve_target_url(chain, endpoint)
        except Exception as exc:
            return self._failed_row(
                chain=chain,
                reasons=["rpc_url_unresolved"],
                detail=str(exc),
                expected_chain_id=expected_chain_id,
            )

        chain_probe = self._rpc_call(target_url, "eth_chainId", [], timeout_s)
        block_probe = self._rpc_call(target_url, "eth_blockNumber", [], timeout_s)
        latency_ms = max(chain_probe["latency_ms"], block_probe["latency_ms"])

        reasons: List[str] = []
        if chain_probe["error"] is not None or block_probe["error"] is not None:
            err = chain_probe["error"] or block_probe["error"]
            reasons.append("rpc_error")
            return {
                "chain": chain,
                "healthy": False,
                "status": "unhealthy",
                "latency_ms": latency_ms,
                "block": None,
                "chain_id": None,
                "expected_chain_id": expected_chain_id,
                "block_lag": None,
                "lag_status": "unchecked",
                "reasons": reasons,
                "endpoint": self._safe_host(target_url),
                "detail": err,
            }

        try:
            observed_chain_id = self._parse_hex_int(chain_probe["result"])
            block_height = self._parse_hex_int(block_probe["result"])
        except Exception as exc:
            return self._failed_row(
                chain=chain,
                reasons=["rpc_decode_error"],
                detail=str(exc),
                expected_chain_id=expected_chain_id,
                latency_ms=latency_ms,
                endpoint=self._safe_host(target_url),
            )

        if observed_chain_id != expected_chain_id:
            return {
                "chain": chain,
                "healthy": False,
                "status": "unhealthy",
                "latency_ms": latency_ms,
                "block": block_height,
                "chain_id": observed_chain_id,
                "expected_chain_id": expected_chain_id,
                "block_lag": None,
                "lag_status": "unchecked",
                "reasons": ["chain_mismatch"],
                "endpoint": self._safe_host(target_url),
                "detail": (
                    f"eth_chainId {observed_chain_id} != configured {expected_chain_id}"
                ),
            }

        lag_info = self._evaluate_reference_lag(
            chain=chain,
            endpoint=endpoint,
            expected_chain_id=expected_chain_id,
            target_block=block_height,
            max_block_lag=max_block_lag,
            timeout_s=timeout_s,
        )
        reasons.extend(lag_info["reasons"])

        status = "healthy"
        if latency_ms > max_latency_ms:
            status = "degraded"
            reasons.append("latency_exceeded")
        if lag_info["lag_status"] == "lag_exceeded":
            status = "degraded"
            if "block_lag_exceeded" not in reasons:
                reasons.append("block_lag_exceeded")

        healthy = status == "healthy"
        return {
            "chain": chain,
            "healthy": healthy,
            "status": status,
            "latency_ms": latency_ms,
            "block": block_height,
            "chain_id": observed_chain_id,
            "expected_chain_id": expected_chain_id,
            "block_lag": lag_info["block_lag"],
            "lag_status": lag_info["lag_status"],
            "reasons": reasons,
            "endpoint": self._safe_host(target_url),
            "reference": lag_info.get("reference"),
        }

    def _evaluate_reference_lag(
        self,
        *,
        chain: str,
        endpoint: Dict[str, Any],
        expected_chain_id: int,
        target_block: int,
        max_block_lag: int,
        timeout_s: float,
    ) -> Dict[str, Any]:
        ref_url = self._resolve_reference_url(chain, endpoint)
        if not ref_url:
            return {
                "block_lag": None,
                "lag_status": "unchecked",
                "reasons": [],
                "reference": None,
            }

        chain_probe = self._rpc_call(ref_url, "eth_chainId", [], timeout_s)
        block_probe = self._rpc_call(ref_url, "eth_blockNumber", [], timeout_s)
        ref_meta = {
            "endpoint": self._safe_host(ref_url),
            "latency_ms": max(chain_probe["latency_ms"], block_probe["latency_ms"]),
        }

        if chain_probe["error"] is not None or block_probe["error"] is not None:
            return {
                "block_lag": None,
                "lag_status": "reference_failed",
                "reasons": ["reference_rpc_error"],
                "reference": {
                    **ref_meta,
                    "detail": chain_probe["error"] or block_probe["error"],
                },
            }

        try:
            ref_chain_id = self._parse_hex_int(chain_probe["result"])
            ref_block = self._parse_hex_int(block_probe["result"])
        except Exception as exc:
            return {
                "block_lag": None,
                "lag_status": "reference_failed",
                "reasons": ["reference_rpc_decode_error"],
                "reference": {**ref_meta, "detail": str(exc)},
            }

        ref_meta["chain_id"] = ref_chain_id
        ref_meta["block"] = ref_block

        if ref_chain_id != expected_chain_id:
            # Same height on a wrong-chain reference must not look like sync.
            return {
                "block_lag": None,
                "lag_status": "reference_unusable",
                "reasons": ["reference_chain_mismatch"],
                "reference": ref_meta,
            }

        lag = abs(target_block - ref_block)
        if lag > max_block_lag:
            return {
                "block_lag": lag,
                "lag_status": "lag_exceeded",
                "reasons": ["block_lag_exceeded"],
                "reference": ref_meta,
            }
        return {
            "block_lag": lag,
            "lag_status": "ok",
            "reasons": [],
            "reference": ref_meta,
        }

    def _resolve_target_url(self, chain: str, endpoint: Dict[str, Any]) -> str:
        inline = endpoint.get("url")
        if isinstance(inline, str) and inline.strip():
            return inline.strip()
        env_key = endpoint.get("url_env")
        if isinstance(env_key, str) and env_key.strip():
            url = self.credential(env_key.strip())
            if not url:
                raise ValueError(
                    f"Missing RPC URL: set environment variable {env_key.strip()}."
                )
            return url
        return resolve_rpc_url(chain, credential_fn=self.credential)

    def _resolve_reference_url(
        self, chain: str, endpoint: Dict[str, Any]
    ) -> Optional[str]:
        inline = endpoint.get("reference_url")
        if isinstance(inline, str) and inline.strip():
            return inline.strip()
        env_key = endpoint.get("reference_url_env")
        if isinstance(env_key, str) and env_key.strip():
            return self.credential(env_key.strip()) or None
        # Convention from #459: REFERENCE_RPC_URL_<CHAIN>
        convention = f"REFERENCE_RPC_URL_{chain.upper()}"
        return self.credential(convention) or None

    def _rpc_call(
        self,
        url: str,
        method: str,
        params: List[Any],
        timeout_s: float,
    ) -> Dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }
        started = time.perf_counter()
        try:
            resp = self._session.post(url, json=payload, timeout=timeout_s)
        except requests.RequestException as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            return {
                "result": None,
                "error": f"transport_error: {exc}",
                "latency_ms": latency_ms,
            }
        latency_ms = int((time.perf_counter() - started) * 1000)
        if resp.status_code >= 400:
            return {
                "result": None,
                "error": f"http_{resp.status_code}",
                "latency_ms": latency_ms,
            }
        try:
            body = resp.json()
        except ValueError:
            return {
                "result": None,
                "error": "invalid_json",
                "latency_ms": latency_ms,
            }
        if not isinstance(body, dict):
            return {
                "result": None,
                "error": "invalid_jsonrpc_shape",
                "latency_ms": latency_ms,
            }
        if body.get("error") is not None:
            err = body.get("error")
            if isinstance(err, dict):
                detail = err.get("message") or err.get("code") or str(err)
            else:
                detail = str(err)
            return {
                "result": None,
                "error": f"jsonrpc_error: {detail}",
                "latency_ms": latency_ms,
            }
        if "result" not in body:
            return {
                "result": None,
                "error": "jsonrpc_missing_result",
                "latency_ms": latency_ms,
            }
        return {
            "result": body.get("result"),
            "error": None,
            "latency_ms": latency_ms,
        }

    @staticmethod
    def _parse_hex_int(value: Any) -> int:
        if isinstance(value, int):
            return value
        text = str(value or "").strip()
        if not text:
            raise ValueError("empty hex quantity")
        return int(text, 16)

    @staticmethod
    def _safe_host(url: str) -> str:
        try:
            parsed = urlparse(url)
            host = parsed.hostname
            if parsed.scheme and host:
                port = f":{parsed.port}" if parsed.port else ""
                return f"{parsed.scheme}://{host}{port}"
        except Exception:
            pass
        return "redacted"

    @staticmethod
    def _as_int(value: Any, default: int) -> int:
        if value is None:
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _as_float(value: Any, default: float) -> float:
        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _failed_row(
        *,
        chain: str,
        reasons: List[str],
        detail: str,
        expected_chain_id: Optional[int] = None,
        latency_ms: Optional[int] = None,
        endpoint: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "chain": chain,
            "healthy": False,
            "status": "unhealthy",
            "latency_ms": latency_ms,
            "block": None,
            "chain_id": None,
            "expected_chain_id": expected_chain_id,
            "block_lag": None,
            "lag_status": "unchecked",
            "reasons": reasons,
            "endpoint": endpoint,
            "detail": detail,
        }
