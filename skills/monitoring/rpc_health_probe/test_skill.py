# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ARPA Hellenic Logical Systems

"""Mocked HTTP tests for monitoring/rpc_health_probe (#459)."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
import yaml

from .skill import RpcHealthProbeSkill

BASE_CHAIN = "base"
EXPECTED_CHAIN_ID = 8453


@pytest.fixture
def skill():
    return RpcHealthProbeSkill()


@pytest.fixture
def manifest():
    path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_manifest_consistency(skill, manifest):
    assert skill.manifest["name"] == manifest["name"] == "monitoring/rpc_health_probe"
    assert skill.manifest["version"] == manifest["version"] == "0.1.0"
    assert skill.manifest["issuer"] == manifest["issuer"]


def test_missing_endpoints(skill):
    result = skill.execute({"action": "probe"})
    assert result["status"] == "error"
    assert result["all_healthy"] is False


def _hex(value: int) -> str:
    return hex(value)


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def _rpc_side_effect(mapping):
    """Map URL -> {method: result_or_error_dict}."""

    def side_effect(url, json=None, timeout=None):
        methods = mapping.get(url) or {}
        method = (json or {}).get("method")
        entry = methods.get(method)
        if entry is None:
            return _FakeResponse(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "error": {"message": f"unexpected {method}"},
                }
            )
        if isinstance(entry, dict) and entry.get("_http_status"):
            return _FakeResponse(
                entry.get("body", {}), status_code=entry["_http_status"]
            )
        if isinstance(entry, dict) and "error" in entry:
            return _FakeResponse({"jsonrpc": "2.0", "id": 1, "error": entry["error"]})
        return _FakeResponse({"jsonrpc": "2.0", "id": 1, "result": entry})

    return side_effect


@patch("skills.monitoring.rpc_health_probe.skill.resolve_chain")
@patch("skills.monitoring.rpc_health_probe.skill.requests.Session.post")
def test_healthy_without_reference(mock_post, mock_resolve, skill):
    mock_resolve.return_value = {
        "chain_id": EXPECTED_CHAIN_ID,
        "rpc_env": "BASE_RPC_URL",
    }
    target = "https://target.example"
    mock_post.side_effect = _rpc_side_effect(
        {
            target: {
                "eth_chainId": _hex(EXPECTED_CHAIN_ID),
                "eth_blockNumber": _hex(100),
            }
        }
    )
    result = skill.execute(
        {
            "endpoints": [{"chain": BASE_CHAIN, "url": target}],
            "max_latency_ms": 5000,
        }
    )
    assert result["status"] == "ok"
    assert result["all_healthy"] is True
    row = result["results"][0]
    assert row["healthy"] is True
    assert row["status"] == "healthy"
    assert row["chain_id"] == EXPECTED_CHAIN_ID
    assert row["block"] == 100
    assert row["block_lag"] is None
    assert row["lag_status"] == "unchecked"


@patch("skills.monitoring.rpc_health_probe.skill.resolve_chain")
@patch("skills.monitoring.rpc_health_probe.skill.requests.Session.post")
def test_wrong_chain_never_all_healthy(mock_post, mock_resolve, skill):
    """gjwang matrix: configured 8453; target+ref both 0x1 with equal heights."""
    mock_resolve.return_value = {"chain_id": EXPECTED_CHAIN_ID}
    target = "https://target.example"
    reference = "https://reference.example"
    mock_post.side_effect = _rpc_side_effect(
        {
            target: {"eth_chainId": _hex(1), "eth_blockNumber": _hex(50)},
            reference: {"eth_chainId": _hex(1), "eth_blockNumber": _hex(50)},
        }
    )
    result = skill.execute(
        {
            "endpoints": [
                {
                    "chain": BASE_CHAIN,
                    "url": target,
                    "reference_url": reference,
                }
            ]
        }
    )
    assert result["all_healthy"] is False
    row = result["results"][0]
    assert row["status"] == "unhealthy"
    assert "chain_mismatch" in row["reasons"]
    assert row["block_lag"] is None


@patch("skills.monitoring.rpc_health_probe.skill.resolve_chain")
@patch("skills.monitoring.rpc_health_probe.skill.requests.Session.post")
def test_reference_wrong_chain_not_verified_zero_lag(mock_post, mock_resolve, skill):
    """gjwang: target ID matches; reference ID differs → lag not verified zero."""
    mock_resolve.return_value = {"chain_id": EXPECTED_CHAIN_ID}
    target = "https://target.example"
    reference = "https://reference.example"
    mock_post.side_effect = _rpc_side_effect(
        {
            target: {
                "eth_chainId": _hex(EXPECTED_CHAIN_ID),
                "eth_blockNumber": _hex(100),
            },
            reference: {"eth_chainId": _hex(1), "eth_blockNumber": _hex(100)},
        }
    )
    result = skill.execute(
        {
            "endpoints": [
                {
                    "chain": BASE_CHAIN,
                    "url": target,
                    "reference_url": reference,
                }
            ]
        }
    )
    row = result["results"][0]
    assert row["healthy"] is True
    assert row["status"] == "healthy"
    assert row["block_lag"] is None
    assert row["lag_status"] == "reference_unusable"
    assert "reference_chain_mismatch" in row["reasons"]
    assert row["block_lag"] != 0 or row["lag_status"] != "ok"


@patch("skills.monitoring.rpc_health_probe.skill.resolve_chain")
@patch("skills.monitoring.rpc_health_probe.skill.requests.Session.post")
def test_jsonrpc_error_fails_even_if_http_fast(mock_post, mock_resolve, skill):
    mock_resolve.return_value = {"chain_id": EXPECTED_CHAIN_ID}
    target = "https://target.example"
    mock_post.side_effect = _rpc_side_effect(
        {
            target: {
                "eth_chainId": {"error": {"code": -32000, "message": "unavailable"}},
                "eth_blockNumber": {"error": {"message": "unavailable"}},
            }
        }
    )
    result = skill.execute({"endpoints": [{"chain": BASE_CHAIN, "url": target}]})
    assert result["all_healthy"] is False
    row = result["results"][0]
    assert row["status"] == "unhealthy"
    assert "rpc_error" in row["reasons"]
    assert row["block"] is None


@patch("skills.monitoring.rpc_health_probe.skill.resolve_chain")
@patch("skills.monitoring.rpc_health_probe.skill.requests.Session.post")
def test_no_reference_lag_unchecked_not_zero(mock_post, mock_resolve, skill):
    mock_resolve.return_value = {"chain_id": EXPECTED_CHAIN_ID}
    target = "https://target.example"
    mock_post.side_effect = _rpc_side_effect(
        {
            target: {
                "eth_chainId": _hex(EXPECTED_CHAIN_ID),
                "eth_blockNumber": _hex(42),
            }
        }
    )
    result = skill.execute({"endpoints": [{"chain": BASE_CHAIN, "url": target}]})
    row = result["results"][0]
    assert row["lag_status"] == "unchecked"
    assert row["block_lag"] is None
    assert "block_lag" in row
    assert row.get("block_lag", 0) is None


@patch("skills.monitoring.rpc_health_probe.skill.resolve_chain")
@patch("skills.monitoring.rpc_health_probe.skill.requests.Session.post")
def test_reference_lag_exceeded_degraded(mock_post, mock_resolve, skill):
    mock_resolve.return_value = {"chain_id": EXPECTED_CHAIN_ID}
    target = "https://target.example"
    reference = "https://reference.example"
    mock_post.side_effect = _rpc_side_effect(
        {
            target: {
                "eth_chainId": _hex(EXPECTED_CHAIN_ID),
                "eth_blockNumber": _hex(100),
            },
            reference: {
                "eth_chainId": _hex(EXPECTED_CHAIN_ID),
                "eth_blockNumber": _hex(110),
            },
        }
    )
    result = skill.execute(
        {
            "endpoints": [
                {
                    "chain": BASE_CHAIN,
                    "url": target,
                    "reference_url": reference,
                }
            ],
            "max_block_lag": 3,
            "max_latency_ms": 5000,
        }
    )
    row = result["results"][0]
    assert result["all_healthy"] is False
    assert row["status"] == "degraded"
    assert row["block_lag"] == 10
    assert "block_lag_exceeded" in row["reasons"]


@patch("skills.monitoring.rpc_health_probe.skill.resolve_chain")
@patch("skills.monitoring.rpc_health_probe.skill.requests.Session.post")
def test_endpoint_host_redacted(mock_post, mock_resolve, skill):
    mock_resolve.return_value = {"chain_id": EXPECTED_CHAIN_ID}
    target = "https://user:secret@rpc.example/v1/abcdef"
    mock_post.side_effect = _rpc_side_effect(
        {
            target: {
                "eth_chainId": _hex(EXPECTED_CHAIN_ID),
                "eth_blockNumber": _hex(1),
            }
        }
    )
    result = skill.execute({"endpoints": [{"chain": BASE_CHAIN, "url": target}]})
    row = result["results"][0]
    assert row["endpoint"] == "https://rpc.example"
    assert "secret" not in row["endpoint"]
    assert "abcdef" not in row["endpoint"]
