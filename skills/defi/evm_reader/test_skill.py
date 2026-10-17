"""Unit tests for defi/evm_reader skill."""

from unittest.mock import MagicMock
import pytest
from pathlib import Path

from skills.defi.evm_reader.skill import EVMReaderSkill
from skills.defi.evm_reader.abis import get_preset_abi, ABI_PRESETS

ADDRESS_ALICE = "0x1111111111111111111111111111111111111111"
ADDRESS_BOB = "0x2222222222222222222222222222222222222222"
ADDRESS_USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
ADDRESS_DEGEN = "0x4ed4E862860beD51a9570b96d89aF5E1B0Efefed"
ADDRESS_ROUTER = "0x7a250d5630B4cF539739dF2C5dA4bF9C15291ECE"


@pytest.fixture
def mock_w3():
    w3 = MagicMock()
    contract_mock = MagicMock()
    w3.eth.contract.return_value = contract_mock
    return w3, contract_mock


@pytest.fixture
def sample_addressbook(tmp_path: Path) -> Path:
    book_file = tmp_path / "addressbook.yaml"
    book_content = """version: 1
contacts:
  alice:
    display_name: "Alice Smith"
    public_0x: "0x1111111111111111111111111111111111111111"
    aliases: ["alice_alias"]
  bob:
    display_name: "Bob Jones"
    public_0x: "0x2222222222222222222222222222222222222222"
  carol_1:
    display_name: "Carol Multi"
    public_0x: "0x3333333333333333333333333333333333333333"
    aliases: ["carol"]
  carol_2:
    display_name: "Carol Other"
    public_0x: "0x4444444444444444444444444444444444444444"
    aliases: ["carol"]
  no_wallet:
    display_name: "No Wallet User"
"""
    book_file.write_text(book_content, encoding="utf-8")
    return book_file


def test_abi_presets():
    assert "erc20" in ABI_PRESETS
    assert "erc721" in ABI_PRESETS
    assert "univ2_pair" in ABI_PRESETS
    assert "chainlink_feed" in ABI_PRESETS
    assert "multicall3" in ABI_PRESETS

    abi = get_preset_abi("erc20")
    assert isinstance(abi, list)
    with pytest.raises(ValueError):
        get_preset_abi("non_existent_preset")


def test_resolve_contract_address():
    skill = EVMReaderSkill()
    # Resolve token symbol from evm_defaults
    usdc_addr = skill._resolve_contract_address("ethereum", "usdc")
    assert usdc_addr.lower() == ADDRESS_USDC.lower()

    degen_addr = skill._resolve_contract_address("base", "degen")
    assert degen_addr.lower() == ADDRESS_DEGEN.lower()

    # Explicit 40-char hex
    addr = skill._resolve_contract_address("ethereum", ADDRESS_ALICE)
    assert addr == ADDRESS_ALICE

    # Invalid hex
    with pytest.raises(ValueError):
        skill._resolve_contract_address("ethereum", "0xinvalid")


def test_resolve_holder_explicit_and_addressbook(sample_addressbook: Path):
    skill = EVMReaderSkill(addressbook_path=sample_addressbook)

    # 1. Explicit hex
    res_exp = skill.execute("resolve_holder", holder=ADDRESS_ALICE)
    assert res_exp["status"] == "ok"
    assert res_exp["holder"] == ADDRESS_ALICE
    assert res_exp["holder_source"] == "explicit"

    # 2. Address book single match by contact_id
    res_ab = skill.execute("resolve_holder", holder="alice")
    assert res_ab["status"] == "ok"
    assert res_ab["holder"] == ADDRESS_ALICE
    assert "addressbook:alice" in res_ab["holder_source"]

    # 3. Address book single match by alias
    res_alias = skill.execute("resolve_holder", holder="alice_alias")
    assert res_alias["status"] == "ok"
    assert res_alias["holder"] == ADDRESS_ALICE

    # 4. Ambiguous match returns needs_input
    res_amb = skill.execute("resolve_holder", holder="carol")
    assert res_amb["status"] == "needs_input"
    assert res_amb["error_code"] == "ambiguous_recipient"
    assert "ambiguous_recipient" in res_amb

    # 5. Missing wallet in contact
    res_nowallet = skill.execute("resolve_holder", holder="no_wallet")
    assert res_nowallet["status"] == "error"

    # 6. Not found
    res_notfound = skill.execute("resolve_holder", holder="unknown_person_xyz")
    assert res_notfound["status"] == "error"


def test_erc20_metadata(mock_w3):
    w3, ct = mock_w3
    ct.functions.name.return_value.call.return_value = "USD Coin"
    ct.functions.symbol.return_value.call.return_value = "USDC"
    ct.functions.decimals.return_value.call.return_value = 6
    ct.functions.totalSupply.return_value.call.return_value = 25000000000000

    skill = EVMReaderSkill(web3_factory=lambda _: w3)
    out = skill.execute("erc20_metadata", chain="ethereum", contract=ADDRESS_USDC)

    assert out["status"] == "ok"
    assert out["name"] == "USD Coin"
    assert out["symbol"] == "USDC"
    assert out["decimals"] == 6
    assert out["total_supply"] == "25000000000000"


def test_erc20_balance(mock_w3, sample_addressbook: Path):
    w3, ct = mock_w3
    ct.functions.balanceOf.return_value.call.return_value = 1500000000  # 1500 USDC
    ct.functions.decimals.return_value.call.return_value = 6
    ct.functions.symbol.return_value.call.return_value = "USDC"

    skill = EVMReaderSkill(
        web3_factory=lambda _: w3, addressbook_path=sample_addressbook
    )
    # Using alias for holder
    out = skill.execute(
        "erc20_balance", chain="ethereum", contract="usdc", holder="alice"
    )

    assert out["status"] == "ok"
    assert out["chain"] == "ethereum"
    assert out["holder"] == ADDRESS_ALICE
    assert out["decimals"] == 6
    assert out["balance_raw"] == "1500000000"
    assert out["balance"] == "1500.000000"


def test_erc20_allowance(mock_w3):
    w3, ct = mock_w3
    ct.functions.allowance.return_value.call.return_value = 500000000
    ct.functions.decimals.return_value.call.return_value = 6

    skill = EVMReaderSkill(web3_factory=lambda _: w3)
    out = skill.execute(
        "erc20_allowance",
        chain="ethereum",
        contract=ADDRESS_USDC,
        owner=ADDRESS_ALICE,
        spender="router_v2",
    )

    assert out["status"] == "ok"
    assert out["owner"] == ADDRESS_ALICE
    assert out["spender"].lower() == ADDRESS_ROUTER.lower()
    assert out["allowance_raw"] == "500000000"
    assert out["allowance"] == "500.000000"


def test_erc721_metadata_and_balance_and_owner(mock_w3):
    w3, ct = mock_w3
    ct.functions.name.return_value.call.return_value = "CryptoPunks"
    ct.functions.symbol.return_value.call.return_value = "PUNK"
    ct.functions.totalSupply.return_value.call.return_value = 10000
    ct.functions.balanceOf.return_value.call.return_value = 3
    ct.functions.ownerOf.return_value.call.return_value = ADDRESS_BOB

    skill = EVMReaderSkill(web3_factory=lambda _: w3)
    c_addr = "0xb47e3cd837dDF8e4c57F05d70Ab865de6e193BBB"

    meta = skill.execute("erc721_metadata", chain="ethereum", contract=c_addr)
    assert meta["status"] == "ok"
    assert meta["name"] == "CryptoPunks"
    assert meta["symbol"] == "PUNK"
    assert meta["total_supply"] == "10000"

    bal = skill.execute(
        "erc721_balance", chain="ethereum", contract=c_addr, holder=ADDRESS_BOB
    )
    assert bal["status"] == "ok"
    assert bal["balance_count"] == 3

    owner = skill.execute(
        "erc721_owner_of", chain="ethereum", contract=c_addr, token_id=42
    )
    assert owner["status"] == "ok"
    assert owner["owner"] == ADDRESS_BOB


def test_call_view(mock_w3):
    w3, ct = mock_w3
    func_mock = MagicMock()
    func_mock.return_value.call.return_value = (1000000, 2000000, 1600000000)
    setattr(ct.functions, "getReserves", func_mock)

    skill = EVMReaderSkill(web3_factory=lambda _: w3)
    out = skill.execute(
        "call_view",
        chain="ethereum",
        contract=ADDRESS_DEGEN,
        method="getReserves",
        abi_preset="univ2_pair",
    )

    assert out["status"] == "ok"
    assert out["method"] == "getReserves"
    assert out["result"] == [1000000, 2000000, 1600000000]


def test_multicall(mock_w3):
    w3, ct = mock_w3
    ct.encodeABI.return_value = "0x12345678"
    ct.decode_function_output.return_value = 1000000000
    ct.functions.tryAggregate.return_value.call.return_value = [
        (
            True,
            bytes.fromhex(
                "000000000000000000000000000000000000000000000000000000003b9aca00"
            ),
        )
    ]

    skill = EVMReaderSkill(web3_factory=lambda _: w3)
    calls = [
        {
            "target": ADDRESS_USDC,
            "method": "balanceOf",
            "abi_preset": "erc20",
            "args": [ADDRESS_ALICE],
        }
    ]
    out = skill.execute("multicall", chain="ethereum", calls=calls)

    assert out["status"] == "ok"
    assert out["total_calls"] == 1
    assert len(out["results"]) == 1
    assert out["results"][0]["success"] is True


def test_multicall_batch_too_large():
    skill = EVMReaderSkill()
    calls = [{"target": ADDRESS_USDC, "method": "name"}] * 51
    out = skill.execute("multicall", chain="ethereum", calls=calls)
    assert out["status"] == "error"
    assert out["error_code"] == "batch_too_large"


def test_unsupported_action():
    skill = EVMReaderSkill()
    out = skill.execute("sign_transaction")
    assert out["status"] == "error"
    assert out["error_code"] == "unsupported_action"
