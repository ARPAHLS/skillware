"""Offline OFAC SDN.CSV projection tests for wallet screening (#287)."""

import importlib.util
import json
import os

import pytest

from .skill import WalletScreeningSkill

_SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
_PARSER_PATH = os.path.join(_SKILL_DIR, "maintenance", "normalize_ofac_sdn.py")

SHELBIT_ETH = (
    "0xe05f529f5284d75624eba386cb716928c3b54a2a",
    "0x6b69e2a7545c166417a80c61a77562052bffa9c5",
)


def _load_parser():
    spec = importlib.util.spec_from_file_location("normalize_ofac_sdn", _PARSER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


parser = _load_parser()


def _row(uid, name, program, remarks):
    cols = [uid, name, "-0-", program] + ["-0-"] * 7 + [remarks]
    return ",".join(f'"{col}"' for col in cols)


def _csv(*lines):
    return "\n".join(lines) + "\n"


def test_broken_program_quotes_are_repaired():
    text = _csv(
        _row(
            "4632",
            "BANK",
            "IRAN] [SDGT] [IRGC] [IFSR",
            "Digital Currency Address - ETH 0x" + "ab" * 20,
        )
    )
    parsed = parser.parse_sdn_csv(text)
    assert parsed["records"][0]["reason"] == "[IRAN] [SDGT] [IRGC] [IFSR]"


def test_eth_identifier_is_lowercased_and_indexed():
    text = _csv(
        _row(
            "1",
            "SHPS SHELBIT",
            "SDGT",
            "Digital Currency Address - ETH 0xE05F529F5284D75624EBA386CB716928C3B54A2A",
        )
    )
    parsed = parser.parse_sdn_csv(text)
    assert parsed["empty_wallet_set"] is False
    record = parsed["records"][0]
    assert record["address"] == "0xe05f529f5284d75624eba386cb716928c3b54a2a"
    assert record["extra"]["literal_identifier"].startswith("0xE05F")
    assert record["extra"]["match_transform"] == "eth_lowercase"
    assert record["extra"]["indexed_for_eth_screening"] is True


def test_duplicate_identifiers_stay_separate_observations():
    text = _csv(
        _row("1", "ONE", "SDGT", "Digital Currency Address - ETH 0x" + "ab" * 20),
        _row("2", "TWO", "SDGT", "Digital Currency Address - ETH 0x" + "AB" * 20),
    )
    parsed = parser.parse_sdn_csv(text)
    assert len(parsed["records"]) == 2
    assert {row["extra"]["uid"] for row in parsed["records"]} == {"1", "2"}
    assert parsed["distinct_typed_wallets"] == 1


def test_non_eth_0x_is_not_an_ethereum_match_key():
    usdt = "0x" + "cd" * 20
    text = _csv(_row("9", "STABLE", "SDGT", f"Digital Currency Address - USDT {usdt}"))
    parsed = parser.parse_sdn_csv(text)
    record = parsed["records"][0]
    assert "address" not in record
    assert record["network"] == "USDT"
    assert record["extra"]["literal_identifier"] == usdt
    assert record["extra"]["indexed_for_eth_screening"] is False


def test_snapshot_omission_drops_unobserved_identifier():
    eth_a = "0x" + "11" * 20
    eth_b = "0x" + "22" * 20
    first = parser.parse_sdn_csv(
        _csv(
            _row(
                "1",
                "NET",
                "SDGT",
                f"Digital Currency Address - ETH {eth_a}; alt. Digital Currency Address - ETH {eth_b}",
            )
        )
    )
    second = parser.parse_sdn_csv(
        _csv(_row("1", "NET", "SDGT", f"Digital Currency Address - ETH {eth_b}"))
    )
    first_keys = {row["address"] for row in first["records"]}
    second_keys = {row["address"] for row in second["records"]}
    assert first_keys == {eth_a, eth_b}
    assert second_keys == {eth_b}
    assert all("delisted" not in row for row in second["records"])


def test_malformed_eth_is_quarantined_not_published():
    text = _csv(_row("3", "BAD", "SDGT", "Digital Currency Address - ETH 0x123"))
    parsed = parser.parse_sdn_csv(text)
    assert parsed["records"] == []
    assert parsed["quarantine"][0]["reason"] == "invalid_eth_identifier"
    assert parsed["empty_wallet_set"] is False


def test_empty_wallet_set_is_not_a_parse_failure():
    text = _csv(_row("4", "NO WALLET", "SDGT", "Passport AB123."))
    parsed = parser.parse_sdn_csv(text)
    assert parsed["records"] == []
    assert parsed["empty_wallet_set"] is True


def test_unrecognized_file_is_a_parse_error():
    with pytest.raises(parser.OfacParseError):
        parser.parse_sdn_csv("this is not an sdn csv\n")


def test_bundled_snapshot_hits_shelbit_eth():
    skill = WalletScreeningSkill()
    manifest_path = os.path.join(skill.data_dir, "ofac_sdn_manifest.json")
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    assert manifest["parser_version"] == "1"
    assert manifest["sha256"]
    assert manifest["eth_indexed"] >= 2
    assert any("not a delisting" in note for note in manifest["notes"])

    for address in SHELBIT_ETH:
        hits = skill._lookup_sanctions_hits("0x" + address[2:].upper())
        assert hits, address
        assert any(hit.get("source") == "OFAC SDN" for hit in hits)
        assert any(
            (hit.get("extra") or {}).get("literal_currency") == "ETH" for hit in hits
        )


def test_non_eth_rows_are_not_ethereum_index_keys():
    skill = WalletScreeningSkill()
    path = os.path.join(skill.data_dir, "normalized_ofac_sdn.json")
    with open(path, encoding="utf-8") as handle:
        rows = json.load(handle)
    non_eth = [row for row in rows if row.get("network") != "ETH"]
    assert non_eth
    assert all("address" not in row for row in non_eth)
    usdt = next(row for row in non_eth if row["network"] == "USDT")
    literal = usdt["extra"]["literal_identifier"]
    if skill.normalize_eth_address(literal):
        hits = skill._lookup_sanctions_hits(literal)
        assert all(hit.get("source") != "OFAC SDN" for hit in hits)
