"""Live EVM integration tests (optional — uses RPC URLs from project .env)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from skillware.core.env import load_env_file

_REPO_ROOT = Path(__file__).resolve().parents[1]
load_env_file(str(_REPO_ROOT / ".env"))

pytestmark = pytest.mark.integration


def _rpc_configured() -> bool:
    return bool(
        os.environ.get("BASE_RPC_URL", "").strip()
        or os.environ.get("ETHEREUM_RPC_URL", "").strip()
    )


def _wallet_key_configured() -> bool:
    for name in ("AGENT_WALLET_PRIVATE_KEY", "AGENT_PRIVATE_KEY"):
        if os.environ.get(name, "").strip():
            return True
    return False


@pytest.fixture(autouse=True)
def _require_live_rpc():
    if not _rpc_configured():
        pytest.skip(
            "Set BASE_RPC_URL and/or ETHEREUM_RPC_URL in .env for live EVM tests"
        )


def test_live_base_rpc_chain_id():
    from skillware.core.evm_config import get_web3

    w3 = get_web3("base")
    assert w3.eth.chain_id == 8453


def test_live_is_rpc_configured_for_defaults():
    from skillware.core.evm_config import is_rpc_configured

    if os.environ.get("BASE_RPC_URL", "").strip():
        assert is_rpc_configured("base") is True
    if os.environ.get("ETHEREUM_RPC_URL", "").strip():
        assert is_rpc_configured("ethereum") is True


def _load_evm_skill():
    from skillware.core.loader import SkillLoader

    bundle = SkillLoader.load_skill("defi/evm_tx_handler")
    cls = bundle["module"].EvmTxHandlerSkill
    return cls()


def test_live_evm_tx_handler_quote_base_degen():
    skill = _load_evm_skill()
    result = skill.execute(
        {
            "action": "quote",
            "intent": {
                "side": "buy",
                "chain": "base",
                "target_asset": "degen",
                "spend_asset": "usdc",
                "amount": 1,
                "amount_kind": "target_out",
            },
        }
    )
    assert result["status"] == "ready", result
    assert result["preview"]["you_receive"]["asset"] == "degen"


@pytest.mark.skipif(not _wallet_key_configured(), reason="Agent wallet key not in .env")
def test_live_evm_tx_handler_wallet_info():
    skill = _load_evm_skill()
    result = skill.execute({"action": "wallet_info", "intent": {}})
    assert result["status"] == "ready"
    assert result["address"].startswith("0x")
    assert len(result["address"]) == 42
