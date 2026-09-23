import os
import sys
from unittest.mock import MagicMock, patch

import pytest
import yaml

from skillware.core.loader import SkillLoader

_SKILL_DIR = os.path.dirname(__file__)
if _SKILL_DIR not in sys.path:
    sys.path.insert(0, _SKILL_DIR)
from abis import ROUTER_V2_ABI  # noqa: E402

from .skill import EvmTxHandlerSkill  # noqa: E402

TEST_KEY = "0x" + "11" * 32


def _mock_w3_for_erc20_swap(*, allowance: int = 0, token_balance: int = 10**18):
    w3 = MagicMock()
    w3.eth.gas_price = 10**9
    w3.eth.get_transaction_count.return_value = 0
    w3.eth.get_balance = MagicMock(return_value=10**20)
    w3.to_wei.side_effect = lambda val, unit: (
        int(val * 10**9) if unit == "gwei" else val
    )

    router = MagicMock()
    router.functions.getAmountsIn.return_value.call.return_value = [
        100_000_000,
        10_000_000_000_000_000_000,
    ]
    router.functions.swapTokensForExactTokens.return_value.build_transaction.return_value = {
        "to": "0x4752ba5DBC23f44d87826276bf6fd6b1c372aD24",
        "gas": 250000,
    }

    erc20 = MagicMock()

    def _allowance(_owner, _spender):
        fn = MagicMock()
        fn.call.return_value = allowance
        return fn

    def _balance_of(_addr):
        fn = MagicMock()
        fn.call.return_value = token_balance
        return fn

    erc20.functions.allowance.side_effect = _allowance
    erc20.functions.balanceOf.side_effect = _balance_of
    erc20.functions.approve.return_value.build_transaction.return_value = {
        "to": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "gas": 60000,
    }

    def contract_factory(address=None, abi=None):
        if abi == ROUTER_V2_ABI:
            return router
        return erc20

    w3.eth.contract.side_effect = contract_factory
    return w3


@pytest.fixture
def skill(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_WALLET_PRIVATE_KEY", TEST_KEY)
    monkeypatch.setenv("ETHEREUM_RPC_URL", "http://localhost:8545")
    monkeypatch.setenv("BASE_RPC_URL", "http://localhost:8546")
    return EvmTxHandlerSkill()


@pytest.fixture
def manifest():
    path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_manifest_consistency(skill, manifest):
    assert skill.manifest["name"] == manifest["name"]
    assert manifest["name"] == "defi/evm_tx_handler"


def test_loader_loads_skill(monkeypatch):
    monkeypatch.setenv("AGENT_WALLET_PRIVATE_KEY", TEST_KEY)
    bundle = SkillLoader.load_skill("defi/evm_tx_handler")
    assert bundle["manifest"]["name"] == "defi/evm_tx_handler"
    cls = bundle["module"].EvmTxHandlerSkill
    instance = cls()
    assert (
        instance.execute({"action": "wallet_info", "intent": {}})["status"] == "ready"
    )


def test_resolve_missing_spend_asset(skill):
    result = skill.execute(
        {
            "action": "resolve",
            "intent": {
                "side": "buy",
                "chain": "base",
                "target_asset": "degen",
                "amount": 10,
                "amount_kind": "target_out",
            },
        }
    )
    assert result["status"] == "needs_input"
    assert "spend_asset" in result["missing_fields"]
    assert result["suggested_defaults"]["spend_asset"] == "usdc"


@patch.object(EvmTxHandlerSkill, "_get_web3")
def test_quote_buy(mock_web3, skill):
    w3 = MagicMock()
    w3.eth.gas_price = 10**9
    w3.to_wei.side_effect = lambda val, unit: (
        int(val * 10**9) if unit == "gwei" else val
    )
    mock_web3.return_value = w3

    router = MagicMock()
    router.functions.getAmountsIn.return_value.call.return_value = [
        100_000_000,
        10_000_000_000_000_000_000,
    ]
    w3.eth.contract.return_value = router

    result = skill.execute(
        {
            "action": "quote",
            "intent": {
                "side": "buy",
                "chain": "base",
                "target_asset": "degen",
                "spend_asset": "usdc",
                "amount": 10,
                "amount_kind": "target_out",
            },
        }
    )
    assert result["status"] == "ready"
    assert result["preview"]["you_pay"]["asset"] == "usdc"
    assert result["preview"]["you_receive"]["asset"] == "degen"
    assert "quote" in result
    assert result["requires_confirmation"] is True


@patch.object(EvmTxHandlerSkill, "_get_web3")
def test_quote_sell(mock_web3, skill):
    w3 = MagicMock()
    w3.eth.gas_price = 10**9
    w3.to_wei.side_effect = lambda val, unit: (
        int(val * 10**9) if unit == "gwei" else val
    )
    mock_web3.return_value = w3

    router = MagicMock()
    router.functions.getAmountsOut.return_value.call.return_value = [10**18, 50_000_000]
    w3.eth.contract.return_value = router

    result = skill.execute(
        {
            "action": "quote",
            "intent": {
                "side": "sell",
                "chain": "base",
                "target_asset": "degen",
                "spend_asset": "usdc",
                "amount": 1,
                "amount_kind": "spend_in",
            },
        }
    )
    assert result["status"] == "ready"
    assert result["preview"]["side"] == "sell"


def test_execute_needs_confirmation_when_enabled(skill):
    result = skill.execute(
        {
            "action": "execute",
            "intent": {
                "side": "buy",
                "chain": "base",
                "target_asset": "degen",
                "spend_asset": "usdc",
            },
            "confirmed": False,
        }
    )
    assert result["status"] == "needs_confirmation"


@patch.object(EvmTxHandlerSkill, "_usd_for_token_amount", return_value=10.0)
@patch.object(EvmTxHandlerSkill, "_wait_receipt")
@patch.object(EvmTxHandlerSkill, "_sign_and_send")
@patch.object(EvmTxHandlerSkill, "_get_web3")
def test_execute_buy_with_approve(mock_web3, mock_send, mock_receipt, _mock_usd, skill):
    mock_web3.return_value = _mock_w3_for_erc20_swap(allowance=0)
    mock_send.side_effect = ["0xapprovehash", "0xswaphash"]
    mock_receipt.return_value = {"block_number": 1, "gas_used": 250000, "success": True}

    result = skill.execute(
        {
            "action": "execute",
            "confirmed": True,
            "intent": {
                "side": "buy",
                "chain": "base",
                "target_asset": "degen",
                "spend_asset": "usdc",
                "amount": 10,
                "amount_kind": "target_out",
            },
        }
    )
    assert result["status"] == "confirmed"
    assert result["tx_hash"] == "0xswaphash"
    assert result["approve_tx_hash"] == "0xapprovehash"
    assert mock_send.call_count == 2
    assert "quote" in result


@patch.object(EvmTxHandlerSkill, "_usd_for_token_amount", return_value=10.0)
@patch.object(EvmTxHandlerSkill, "_wait_receipt")
@patch.object(EvmTxHandlerSkill, "_sign_and_send")
@patch.object(EvmTxHandlerSkill, "_get_web3")
def test_execute_buy_skips_approve_when_allowance_sufficient(
    mock_web3, mock_send, mock_receipt, _mock_usd, skill
):
    mock_web3.return_value = _mock_w3_for_erc20_swap(allowance=10**30)
    mock_send.return_value = "0xswaphash"
    mock_receipt.return_value = {"block_number": 1, "gas_used": 250000, "success": True}

    result = skill.execute(
        {
            "action": "execute",
            "confirmed": True,
            "intent": {
                "side": "buy",
                "chain": "base",
                "target_asset": "degen",
                "spend_asset": "usdc",
                "amount": 10,
                "amount_kind": "target_out",
            },
        }
    )
    assert result["status"] == "confirmed"
    assert "approve_tx_hash" not in result
    mock_send.assert_called_once()


@patch.object(EvmTxHandlerSkill, "_get_web3")
@patch.object(EvmTxHandlerSkill, "_usd_for_token_amount", return_value=1000.0)
def test_max_trade_usd_blocks_quote(mock_usd, mock_web3, skill):
    original_cap = skill.user_config.get("max_trade_usd")
    skill.user_config["max_trade_usd"] = 500
    mock_web3.return_value = _mock_w3_for_erc20_swap()

    result = skill.execute(
        {
            "action": "quote",
            "intent": {
                "side": "buy",
                "chain": "base",
                "target_asset": "degen",
                "spend_asset": "usdc",
                "amount": 10,
                "amount_kind": "target_out",
            },
        }
    )
    assert result["status"] == "error"
    assert "max_trade_usd" in result["message"]
    if original_cap is None:
        skill.user_config.pop("max_trade_usd", None)
    else:
        skill.user_config["max_trade_usd"] = original_cap


@patch.object(EvmTxHandlerSkill, "_get_web3")
@patch.object(EvmTxHandlerSkill, "_usd_for_token_amount", return_value=None)
def test_max_trade_usd_fail_closed_without_price(mock_usd, mock_web3, skill):
    original_cap = skill.user_config.get("max_trade_usd")
    skill.user_config["max_trade_usd"] = 500
    mock_web3.return_value = _mock_w3_for_erc20_swap()

    result = skill.execute(
        {
            "action": "quote",
            "intent": {
                "side": "buy",
                "chain": "base",
                "target_asset": "degen",
                "spend_asset": "usdc",
                "amount": 10,
                "amount_kind": "target_out",
            },
        }
    )
    assert result["status"] == "error"
    assert "USD price" in result["message"]
    if original_cap is None:
        skill.user_config.pop("max_trade_usd", None)
    else:
        skill.user_config["max_trade_usd"] = original_cap


def test_missing_rpc_fail_closed(skill, monkeypatch):
    monkeypatch.delenv("BASE_RPC_URL", raising=False)
    result = skill.execute(
        {
            "action": "balances",
            "intent": {"chain": "base"},
        }
    )
    assert result["status"] == "error"
    assert "BASE_RPC_URL" in result["message"]


def test_update_preferences_rejects_unknown_keys(skill):
    result = skill.execute(
        {
            "action": "update_preferences",
            "preferences": {"not_a_real_key": True},
        }
    )
    assert result["status"] == "error"
    assert "not_a_real_key" in result["message"]


def test_resolve_ready_buy(skill):
    result = skill.execute(
        {
            "action": "resolve",
            "intent": {
                "side": "buy",
                "chain": "base",
                "target_asset": "degen",
                "spend_asset": "usdc",
                "amount": 10,
                "amount_kind": "target_out",
            },
        }
    )
    assert result["status"] == "ready"
    assert result["resolved"]["spend_asset"] == "usdc"


def test_transfer_requires_confirmation(skill):
    result = skill.execute(
        {
            "action": "transfer",
            "intent": {
                "chain": "base",
                "target_asset": "usdc",
                "amount": 10,
                "recipient": "mom",
            },
        }
    )
    assert result["status"] == "needs_confirmation"


@patch.object(EvmTxHandlerSkill, "_wait_receipt")
@patch.object(EvmTxHandlerSkill, "_sign_and_send")
@patch.object(EvmTxHandlerSkill, "_get_web3")
def test_transfer_resolves_addressbook(mock_web3, mock_send, mock_receipt, skill):
    w3 = MagicMock()
    w3.eth.gas_price = 10**9
    w3.eth.get_transaction_count.return_value = 0
    w3.to_wei.side_effect = lambda val, unit: (
        int(val * 10**9) if unit == "gwei" else val
    )
    mock_web3.return_value = w3
    mock_send.return_value = "0xabc"
    mock_receipt.return_value = {"block_number": 1, "gas_used": 21000, "success": True}

    contract = MagicMock()

    def _balance_of(_addr):
        fn = MagicMock()
        fn.call.return_value = 10**18
        return fn

    contract.functions.balanceOf.side_effect = _balance_of
    contract.functions.transfer.return_value.build_transaction.return_value = {
        "to": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "gas": 100000,
    }
    w3.eth.contract.return_value = contract
    w3.eth.get_balance = MagicMock(return_value=10**18)

    result = skill.execute(
        {
            "action": "transfer",
            "confirmed": True,
            "intent": {
                "chain": "base",
                "target_asset": "usdc",
                "amount": 10,
                "recipient": "mom",
            },
        }
    )
    assert result["status"] == "confirmed"
    assert result["recipient_resolved"] == "0x000000000000000000000000000000000000dEaD"
    mock_send.assert_called_once()


def test_gas_override_does_not_mutate_config(skill, tmp_path):
    config_path = os.path.join(skill._skill_dir, "config.yaml")
    original_gas = skill.user_config.get("gas_policy")
    skill.execute(
        {
            "action": "resolve",
            "intent": {
                "side": "buy",
                "chain": "base",
                "target_asset": "degen",
                "spend_asset": "usdc",
                "amount": 1,
                "gas_policy": "aggressive",
            },
        }
    )
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            on_disk = yaml.safe_load(f)
        assert on_disk.get("gas_policy") == original_gas
    assert skill.user_config.get("gas_policy") == original_gas


def test_update_preferences(skill, tmp_path):
    config_path = os.path.join(skill._skill_dir, "config.yaml")
    try:
        result = skill.execute(
            {
                "action": "update_preferences",
                "preferences": {"default_chain": "base", "slippage_bps": 75},
            }
        )
        assert result["status"] == "updated"
        assert result["preferences"]["default_chain"] == "base"
        assert result["preferences"]["slippage_bps"] == 75
        with open(config_path, "r", encoding="utf-8") as f:
            saved = yaml.safe_load(f)
        assert saved["default_chain"] == "base"
    finally:
        if os.path.exists(config_path):
            os.remove(config_path)
        skill.user_config = skill._load_user_config()


def test_missing_wallet_key_structured(skill, monkeypatch):
    monkeypatch.delenv("AGENT_WALLET_PRIVATE_KEY", raising=False)
    result = skill.execute({"action": "wallet_info", "intent": {}})
    assert result["status"] == "missing_config"
    assert "AGENT_WALLET_PRIVATE_KEY" in result["setup"]["env_var"]
    assert "docs/skills/evm_tx_handler.md" in result["setup"]["docs"]


@patch.object(EvmTxHandlerSkill, "_get_web3")
def test_transfer_insufficient_balance(mock_web3, skill):
    w3 = MagicMock()
    w3.eth.gas_price = 10**9
    w3.to_wei.side_effect = lambda val, unit: (
        int(val * 10**9) if unit == "gwei" else val
    )
    mock_web3.return_value = w3
    erc20 = MagicMock()
    erc20.functions.balanceOf.side_effect = lambda _a: MagicMock(
        call=MagicMock(return_value=1)
    )
    w3.eth.contract.return_value = erc20
    w3.eth.get_balance = MagicMock(return_value=10**18)

    result = skill.execute(
        {
            "action": "transfer",
            "confirmed": True,
            "intent": {
                "chain": "base",
                "target_asset": "usdc",
                "amount": 10,
                "recipient": "mom",
            },
        }
    )
    assert result["status"] == "insufficient_balance"
    assert "agent_hint" in result


@patch.object(EvmTxHandlerSkill, "_get_web3")
def test_preview_includes_drift_warning(mock_web3, skill):
    mock_web3.return_value = _mock_w3_for_erc20_swap()
    result = skill.execute(
        {
            "action": "quote",
            "intent": {
                "side": "buy",
                "chain": "base",
                "target_asset": "degen",
                "spend_asset": "usdc",
                "amount": 10,
                "amount_kind": "target_out",
            },
        }
    )
    warnings = " ".join(result["preview"]["warnings"])
    assert "re-quotes" in warnings
    assert "immediately before" in warnings


def test_wallet_info_no_secrets(skill):
    result = skill.execute({"action": "wallet_info", "intent": {}})
    assert result["status"] == "ready"
    assert result["capabilities"]["execute"] is True
    assert "address" in result
    body = str(result)
    assert TEST_KEY not in body
    assert TEST_KEY[2:] not in body


def test_transfer_missing_config_without_wallet(skill, tmp_path, monkeypatch):
    from skillware.core.mail_config import init_addressbook_file, add_addressbook_contact

    ab_path = tmp_path / "addressbook.yaml"
    init_addressbook_file(ab_path)
    add_addressbook_contact(
        ab_path,
        display_name="John Doe",
        contact_id="john_doe",
        email="john@example.com",
    )
    monkeypatch.setenv("GMAIL_ADDRESSBOOK_PATH", str(ab_path))

    result = skill.execute(
        {
            "action": "transfer",
            "confirmed": True,
            "intent": {
                "chain": "base",
                "target_asset": "usdc",
                "amount": 1,
                "recipient": "john_doe",
            },
        }
    )
    assert result["status"] == "missing_config"
    assert result["code"] == "NO_EVM_WALLET_CONFIGURED"


def test_transfer_resolves_unique_central_contact(skill, tmp_path, monkeypatch):
    from skillware.core.mail_config import init_addressbook_file, add_addressbook_contact

    ab_path = tmp_path / "addressbook.yaml"
    init_addressbook_file(ab_path)
    add_addressbook_contact(
        ab_path,
        display_name="Alice",
        contact_id="alice",
        aliases=["ali"],
        public_0x="0x3333333333333333333333333333333333333333",
    )
    monkeypatch.setenv("GMAIL_ADDRESSBOOK_PATH", str(ab_path))

    with patch.object(EvmTxHandlerSkill, "_get_web3") as mock_web3, patch.object(
        EvmTxHandlerSkill, "_sign_and_send", return_value="0xabc"
    ), patch.object(
        EvmTxHandlerSkill,
        "_wait_receipt",
        return_value={"block_number": 1, "gas_used": 21000, "success": True},
    ):
        w3 = MagicMock()
        w3.eth.gas_price = 10**9
        w3.eth.get_transaction_count.return_value = 0
        w3.to_wei.side_effect = lambda val, unit: (
            int(val * 10**9) if unit == "gwei" else val
        )
        mock_web3.return_value = w3
        contract = MagicMock()
        contract.functions.balanceOf.side_effect = lambda _a: MagicMock(
            call=MagicMock(return_value=10**18)
        )
        contract.functions.transfer.return_value.build_transaction.return_value = {
            "to": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            "gas": 100000,
        }
        w3.eth.contract.return_value = contract
        w3.eth.get_balance = MagicMock(return_value=10**18)

        result = skill.execute(
            {
                "action": "transfer",
                "confirmed": True,
                "intent": {
                    "chain": "base",
                    "target_asset": "usdc",
                    "amount": 1,
                    "recipient": "ali",
                },
            }
        )
    assert result["status"] == "confirmed"
    assert result["recipient_source"] == "addressbook:alice"


def test_transfer_ambiguous_two_wallets(skill, tmp_path, monkeypatch):
    from skillware.core.mail_config import init_addressbook_file, add_addressbook_contact

    ab_path = tmp_path / "addressbook.yaml"
    init_addressbook_file(ab_path)
    add_addressbook_contact(
        ab_path,
        display_name="John Doe",
        contact_id="john_doe",
        aliases=["john"],
        public_0x="0x1111111111111111111111111111111111111111",
    )
    add_addressbook_contact(
        ab_path,
        display_name="John Smith",
        contact_id="john_smith",
        aliases=["john"],
        public_0x="0x2222222222222222222222222222222222222222",
    )
    monkeypatch.setenv("GMAIL_ADDRESSBOOK_PATH", str(ab_path))

    result = skill.execute(
        {
            "action": "transfer",
            "confirmed": True,
            "intent": {
                "chain": "base",
                "target_asset": "usdc",
                "amount": 1,
                "recipient": "john",
            },
        }
    )
    assert result["status"] == "needs_input"
    assert len(result["ambiguous_recipient"]["candidates"]) == 2


@patch.object(EvmTxHandlerSkill, "_get_web3")
def test_balances(mock_web3, skill):
    w3 = MagicMock()
    w3.eth.get_balance.return_value = 10**18
    mock_web3.return_value = w3
    erc20 = MagicMock()
    erc20.functions.balanceOf.side_effect = lambda _a: MagicMock(
        call=MagicMock(return_value=5_000_000)
    )
    w3.eth.contract.return_value = erc20

    result = skill.execute({"action": "balances", "intent": {"chain": "ethereum"}})
    assert result["status"] == "ready"
    assert "eth" in result["balances"]
