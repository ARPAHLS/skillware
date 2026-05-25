from unittest.mock import patch, MagicMock
from skillware.core.loader import SkillLoader


def get_skill():
    bundle = SkillLoader.load_skill("finance/wallet_screening")
    # Initialize without needing real API keys
    return bundle["module"].WalletScreeningSkill()


@patch("skills.finance.wallet_screening.skill.requests.get")
def test_wallet_screening_success(mock_get):
    skill = get_skill()
    skill.etherscan_api_key = "dummy_key"

    # Mock responses
    mock_eth_balance = MagicMock()
    mock_eth_balance.json.return_value = {
        "status": "1",
        "result": "1000000000000000000",
    }  # 1 ETH

    mock_txs = MagicMock()
    mock_txs.json.return_value = {
        "status": "1",
        "result": [
            {
                "from": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045".lower(),
                "to": "0x123",
                "value": "500000000000000000",
                "isError": "0",
                "gasUsed": "21000",
                "gasPrice": "1000000000",
            }
        ],
    }

    mock_price = MagicMock()
    mock_price.json.return_value = {"ethereum": {"usd": 2000.0, "eur": 1800.0}}

    # Configure mock side_effect based on URL/params
    def get_side_effect(url, **kwargs):
        if "action" in kwargs.get("params", {}):
            if kwargs["params"]["action"] == "balance":
                return mock_eth_balance
            elif kwargs["params"]["action"] == "txlist":
                return mock_txs
        return mock_price

    mock_get.side_effect = get_side_effect

    result = skill.execute({"address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"})

    assert "error" not in result
    assert "summary" in result
    assert result["summary"]["balance_eth"] == 1.0
    assert result["summary"]["balance_usd"] == 2000.0
    assert "financial_analysis" in result
    assert result["financial_analysis"]["value_out_eth"] == 0.5


def test_wallet_screening_invalid_address():
    skill = get_skill()
    result = skill.execute({"address": "invalid_addr"})
    assert "error" in result
    assert "Invalid Ethereum address" in result["error"]


def test_wallet_screening_missing_key():
    skill = get_skill()
    skill.etherscan_api_key = None
    result = skill.execute({"address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"})
    assert "error" in result
    assert "Missing ETHERSCAN_API_KEY" in result["error"]


# Known ETH vector from entities.ftm.json (properties.publicKey)
SANCTIONED_ETH = "0x7eab248c014d1043e54e96ac4f31ec7d9a97ffd3"


def _mock_etherscan_empty(mock_get):
    mock_eth_balance = MagicMock()
    mock_eth_balance.json.return_value = {"status": "1", "result": "0"}
    mock_txs = MagicMock()
    mock_txs.json.return_value = {"status": "1", "result": []}
    mock_price = MagicMock()
    mock_price.json.return_value = {"ethereum": {"usd": 2000.0, "eur": 1800.0}}

    def get_side_effect(url, **kwargs):
        params = kwargs.get("params") or {}
        if params.get("action") == "balance":
            return mock_eth_balance
        if params.get("action") == "txlist":
            return mock_txs
        return mock_price

    mock_get.side_effect = get_side_effect


@patch("skills.finance.wallet_screening.skill.requests.get")
def test_ftm_publickey_eth_sanctions_match(mock_get):
    skill = get_skill()
    skill.etherscan_api_key = "dummy_key"
    skill.sanctions_entities = [
        {
            "id": "test-ftm-wallet",
            "schema": "CryptoWallet",
            "caption": "sanctioned-test-wallet",
            "properties": {
                "publicKey": [SANCTIONED_ETH],
                "topics": ["crime.terror"],
            },
        }
    ]
    skill.additional_datasets = []
    skill.malicious_contracts = []
    skill._build_sanctions_index()
    _mock_etherscan_empty(mock_get)

    result = skill.execute({"address": SANCTIONED_ETH})

    assert "error" not in result
    assert result["summary"]["sanctioned_entity_match"] is True
    assert len(result["risk_details"]["sanctions_hits"]) >= 1


@patch("skills.finance.wallet_screening.skill.requests.get")
def test_publickey_comma_separated_eth_match(mock_get):
    skill = get_skill()
    skill.etherscan_api_key = "dummy_key"
    target = "0xc8fe1c81e927540fcc99ebb3c880a840082293da"
    skill.sanctions_entities = [
        {
            "caption": "multi-chain-wallet",
            "properties": {
                "publicKey": [
                    "0xc8fe1c81e927540fcc99ebb3c880a840082293da, TR2nTb64cQMx6tqFwisoC6o7barFWHhPiw"
                ],
            },
        }
    ]
    skill.additional_datasets = []
    skill.malicious_contracts = []
    skill._build_sanctions_index()
    _mock_etherscan_empty(mock_get)

    result = skill.execute({"address": target})

    assert result["summary"]["sanctioned_entity_match"] is True


def test_normalize_eth_address_strips_zero_width():
    skill = get_skill()
    raw = "0x" + "\u200b" + "7eab248c014d1043e54e96ac4f31ec7d9a97ffd3"
    assert skill.normalize_eth_address(raw) == SANCTIONED_ETH


def test_sanctions_index_real_ftm_publickey_vector():
    skill = get_skill()
    assert SANCTIONED_ETH in skill._sanctions_index
    hits = skill._lookup_sanctions_hits(SANCTIONED_ETH)
    assert len(hits) >= 1
    assert hits[0]["__source_file__"] == "entities.ftm.json"
    assert SANCTIONED_ETH in hits[0].get("properties", {}).get("publicKey", [])
