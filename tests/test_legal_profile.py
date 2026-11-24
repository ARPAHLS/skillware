# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

"""Unit tests for skillware.core.legal_profile."""

from __future__ import annotations

from skillware.core.legal_profile import (
    find_self_contact,
    format_iso_date,
    mask_legal_profile,
    mask_pii_value,
    normalize_country_code,
    normalize_country_name,
    resolve_profile_field,
    validate_is_self_uniqueness,
    validate_legal_profile,
)


def test_country_and_date_normalization() -> None:
    assert normalize_country_code("Greece") == "GR"
    assert normalize_country_code("UK") == "GB"
    assert normalize_country_name("GR", full_name=True) == "Greece"
    assert normalize_country_name("GR", full_name=False) == "GR"
    assert format_iso_date("1990-05-15", "MM-DD-YYYY") == "05-15-1990"
    assert format_iso_date("1990-05-15", "DD/MM/YYYY") == "15/05/1990"
    assert format_iso_date("1990-05-15", "YYYY-MM-DD") == "1990-05-15"


def test_multi_jurisdiction_tin_and_w9_slicing() -> None:
    contact = {
        "display_name": "Nikos Papadopoulos",
        "emails": ["nikos@example.com"],
        "legal_profile": {
            "type": "individual",
            "citizenship": "GR",
            "date_of_birth": "1988-11-03",
            "tax_residency": [
                {"country": "GR", "tin": "094123456", "tin_type": "AFM"},
                {"country": "GB", "tin": "1234567890", "tin_type": "UTR"},
            ],
            "tax_ids": {
                "US_SSN": "123-45-6789",
                "EU_VAT": "EL094123456",
            },
            "residence_address": {
                "street": "10 Ermou St",
                "street_line_2": "Floor 3",
                "city": "Athens",
                "state_province": "Attica",
                "postal_code": "10563",
                "country": "GR",
            },
        },
    }

    assert resolve_profile_field(contact, "legal_name") == "Nikos Papadopoulos"
    assert resolve_profile_field(contact, "email") == "nikos@example.com"
    assert resolve_profile_field(contact, "citizenship") == "Greece"
    assert (
        resolve_profile_field(contact, "date_of_birth", date_format="MM-DD-YYYY")
        == "11-03-1988"
    )
    # US form foreign TIN picks Greek AFM; UK form local TIN picks UK UTR
    assert (
        resolve_profile_field(contact, "tin.foreign", form_jurisdiction="US")
        == "094123456"
    )
    assert (
        resolve_profile_field(contact, "tin.local", form_jurisdiction="GB")
        == "1234567890"
    )
    assert resolve_profile_field(contact, "tin.eu_vat") == "EL094123456"
    # W-9 segmented SSN
    assert resolve_profile_field(contact, "tin.us_ssn.part1") == "123"
    assert resolve_profile_field(contact, "tin.us_ssn.part2") == "45"
    assert resolve_profile_field(contact, "tin.us_ssn.part3") == "6789"
    # Composite addresses
    assert (
        resolve_profile_field(contact, "residence_address.street_combined")
        == "10 Ermou St, Floor 3"
    )
    assert (
        resolve_profile_field(contact, "residence_address.city_state_postal")
        == "Athens, Attica 10563"
    )
    assert resolve_profile_field(contact, "residence_address.country") == "Greece"
    assert resolve_profile_field(contact, "entity_classification.individual") is True


def test_entity_profile_ein_slicing_and_signatory() -> None:
    contact = {
        "display_name": "Acme Ventures Ltd",
        "org": "Acme Group",
        "legal_profile": {
            "type": "entity",
            "tax_ids": {
                "US_EIN": "12-3456789",
                "GIIN": "ABCDEF.12345.LE.123",
                "LEI": "5493001KJTIIGC8Y1R12",
            },
            "company_registration": {
                "jurisdiction": "GB",
                "number": "09876543",
                "entity_classification": "c_corp",
            },
            "authorized_signatory": {
                "name": "Alice Example",
                "title": "Director",
            },
        },
    }

    assert resolve_profile_field(contact, "legal_name") == "Acme Ventures Ltd"
    assert resolve_profile_field(contact, "business_name") == "Acme Group"
    assert resolve_profile_field(contact, "tin.us_ein.part1") == "12"
    assert resolve_profile_field(contact, "tin.us_ein.part2") == "3456789"
    assert resolve_profile_field(contact, "tin.giin") == "ABCDEF.12345.LE.123"
    assert resolve_profile_field(contact, "tin.lei") == "5493001KJTIIGC8Y1R12"
    assert (
        resolve_profile_field(contact, "jurisdiction_of_incorporation")
        == "United Kingdom"
    )
    assert resolve_profile_field(contact, "entity_classification.c_corp") is True
    assert resolve_profile_field(contact, "entity_classification.corporation") is True
    assert resolve_profile_field(contact, "entity_classification.llc") is None
    assert (
        resolve_profile_field(contact, "authorized_signatory.name") == "Alice Example"
    )


def test_validation_is_self_and_masking() -> None:
    assert (
        validate_legal_profile(
            "me", {"type": "individual", "date_of_birth": "1990-05-15"}
        )
        == []
    )
    errs = validate_legal_profile(
        "me", {"type": "robot", "date_of_birth": "05/15/1990"}
    )
    assert len(errs) == 2

    dup_errs = validate_is_self_uniqueness(
        {"a": {"is_self": True}, "b": {"is_self": True}}
    )
    assert len(dup_errs) == 1

    found = find_self_contact(
        {"contacts": {"alice": {"is_self": True, "display_name": "Alice"}}}
    )
    assert found is not None and found[0] == "alice"

    assert mask_pii_value("123-45-6789") == "***-**-6789"
    assert mask_pii_value("1990-05-15") == "****-**-15"
    masked = mask_legal_profile(
        {
            "type": "individual",
            "date_of_birth": "1990-05-15",
            "tax_ids": {"US_SSN": "123-45-6789"},
            "tax_residency": [{"country": "GR", "tin": "094123456", "tin_type": "AFM"}],
        }
    )
    assert masked["date_of_birth"] == "****-**-15"
    assert masked["tax_ids"]["US_SSN"] == "***-**-6789"
    assert masked["tax_residency"][0]["tin"] == "*****3456"


def test_mail_config_and_cli_legal_profile_end_to_end(tmp_path, monkeypatch) -> None:
    import json
    from rich.console import Console
    from skillware.cli_addressbook import (
        cmd_addressbook_list,
        cmd_addressbook_set_legal_profile,
        cmd_addressbook_show,
    )
    from skillware.core.mail_config import (
        add_addressbook_contact,
        init_addressbook_file,
        load_addressbook_yaml,
        set_addressbook_legal_profile,
        validate_addressbook_data,
    )

    ab_path = tmp_path / "addressbook.yaml"
    init_addressbook_file(ab_path)
    add_addressbook_contact(
        ab_path,
        display_name="Alice Example",
        email="alice@example.com",
        contact_id="me",
    )
    add_addressbook_contact(
        ab_path,
        display_name="Acme Ventures Ltd",
        email="ops@acme.example",
        org="Acme Group",
        contact_id="acme_corp",
    )

    monkeypatch.setenv("GMAIL_ADDRESSBOOK_PATH", str(ab_path))

    # Set self profile via CLI non-interactive flags
    out = Console(record=True)
    rc = cmd_addressbook_set_legal_profile(
        "me",
        console=out,
        profile_type="individual",
        is_self=True,
        citizenship="GR",
        tax_country="GR",
        tin="094123456",
        tin_type="AFM",
        dob="1990-05-15",
        street="10 Ermou St",
        city="Athens",
        postal="10563",
        country="GR",
    )
    assert rc == 0

    # Setting is_self=True on another contact clears previous is_self so uniqueness holds
    set_addressbook_legal_profile(
        ab_path,
        "acme_corp",
        {
            "type": "entity",
            "tax_ids": {"US_EIN": "12-3456789"},
            "company_registration": {
                "jurisdiction": "GB",
                "entity_classification": "c_corp",
            },
        },
        is_self=False,
    )
    data = load_addressbook_yaml(ab_path)
    assert validate_addressbook_data(data) == []

    # show masks PII by default, reveals with --unmask
    masked_console = Console(record=True)
    assert (
        cmd_addressbook_show(
            "me", console=masked_console, unmask=False, json_output=True
        )
        == 0
    )
    masked_json = json.loads(masked_console.export_text())
    assert masked_json["legal_profile"]["tax_residency"][0]["tin"] == "*****3456"
    assert masked_json["legal_profile"]["date_of_birth"] == "****-**-15"

    unmasked_console = Console(record=True)
    assert (
        cmd_addressbook_show(
            "me", console=unmasked_console, unmask=True, json_output=True
        )
        == 0
    )
    unmasked_json = json.loads(unmasked_console.export_text())
    assert unmasked_json["legal_profile"]["tax_residency"][0]["tin"] == "094123456"

    # list never dumps raw TINs even in JSON mode
    list_console = Console(record=True)
    assert cmd_addressbook_list(console=list_console, json_output=True) == 0
    list_text = list_console.export_text()
    assert "094123456" not in list_text
    assert "12-3456789" not in list_text
