"""Unit tests for skillware.core.ui_schema helpers."""

from skillware.core.ui_schema import (
    extract_card_field_keys,
    is_output_card_ui_schema,
    missing_keys_for_samples,
    normalize_fixture_samples,
    path_exists,
    resolve_dot_path,
    validate_card_ui_schema,
)


def test_resolve_dot_path_nested():
    data = {"metadata": {"wallet_address": "0xabc"}, "summary": {"risk_flag": True}}
    assert resolve_dot_path(data, "metadata.wallet_address") == "0xabc"
    assert resolve_dot_path(data, "summary.risk_flag") is True


def test_path_exists_false_on_missing_segment():
    data = {"status": "ready"}
    assert path_exists(data, "preview.you_pay") is False


def test_is_output_card_ui_schema():
    assert is_output_card_ui_schema({"type": "card", "fields": [{"key": "status"}]})
    assert not is_output_card_ui_schema({"dataset_chunk": {"ui:widget": "textarea"}})
    assert not is_output_card_ui_schema({"type": "card", "fields": []})


def test_validate_card_ui_schema_across_samples():
    ui_schema = {
        "type": "card",
        "fields": [
            {"key": "preview.you_pay"},
            {"key": "tx_hash"},
        ],
    }
    samples = [
        {"status": "ready", "preview": {"you_pay": {"asset": "ETH"}}},
        {"status": "confirmed", "tx_hash": "0x1"},
    ]
    assert validate_card_ui_schema(ui_schema, samples) == []


def test_validate_card_ui_schema_reports_missing_keys():
    ui_schema = {"type": "card", "fields": [{"key": "missing.path"}]}
    samples = [{"status": "ready"}]
    assert validate_card_ui_schema(ui_schema, samples) == ["missing.path"]


def test_normalize_fixture_samples_accepts_wrapper_or_object():
    single = {"status": "success"}
    assert normalize_fixture_samples(single) == [single]
    wrapped = normalize_fixture_samples({"samples": [single, {"status": "error"}]})
    assert len(wrapped) == 2


def test_extract_card_field_keys_skips_blank_entries():
    ui_schema = {
        "type": "card",
        "fields": [{"key": " status "}, {"label": "No key"}, {"key": ""}],
    }
    assert extract_card_field_keys(ui_schema) == ["status"]


def test_missing_keys_for_samples():
    samples = [{"a": {"b": 1}}, {"c": 2}]
    assert missing_keys_for_samples(samples, ["a.b", "c", "missing"]) == ["missing"]
