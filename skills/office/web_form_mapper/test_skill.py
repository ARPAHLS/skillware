"""Unit tests for office/web_form_mapper skill."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from skills.office.web_form_mapper.skill import WebFormMapperSkill

FIXTURES_DIR = Path(__file__).resolve().parent / "tests" / "fixtures"


@pytest.fixture
def aspnet_html() -> str:
    return (FIXTURES_DIR / "aspnet_legacy_form.html").read_text(encoding="utf-8")


@pytest.fixture
def spa_html() -> str:
    return (FIXTURES_DIR / "modern_spa_form.html").read_text(encoding="utf-8")


@pytest.fixture
def captcha_html() -> str:
    return (FIXTURES_DIR / "captcha_blocked_form.html").read_text(encoding="utf-8")


@pytest.fixture
def sample_addressbook(tmp_path: Path) -> Path:
    """Fixture creating addressbook.yaml with legal_profile support."""
    book = {
        "contacts": {
            "me": {
                "display_name": "Alice Example",
                "is_self": True,
                "emails": ["alice@example.com"],
                "org": "Example Corp",
                "phone": "+49 30 123456",
                "legal_profile": {
                    "type": "individual",
                    "legal_name": "Alice Marie Example",
                    "first_name": "Alice",
                    "last_name": "Example",
                    "tax_id": "DE-123456789",
                    "citizenship": "DE",
                    "tax_residence": "DE",
                    "dob": "1992-05-14",
                    "address": {
                        "street": "Friedrichstrasse 12",
                        "city": "Berlin",
                        "postal_code": "10117",
                        "country": "Germany",
                    },
                },
            },
            "acme_client": {
                "display_name": "Acme Holdings LLC",
                "emails": ["legal@acme.com"],
                "org": "Acme Holdings LLC",
                "legal_profile": {
                    "type": "entity",
                    "legal_name": "Acme Holdings LLC",
                    "ein": "12-3456789",
                    "address": {
                        "street": "1209 Orange Street",
                        "city": "Wilmington",
                        "state": "DE",
                        "postal_code": "19801",
                        "country": "US",
                    },
                },
            },
        }
    }
    path = tmp_path / "addressbook.yaml"
    path.write_text(yaml.safe_dump(book), encoding="utf-8")
    return path


def test_inspect_legacy_aspnet_form(aspnet_html: str):
    """Inspect must parse fields and preserve hidden ViewState / CSRF tokens."""
    skill = WebFormMapperSkill()
    res = skill.execute({"action": "inspect", "html_content": aspnet_html})

    assert res["status"] == "success"
    assert res["action"] == "inspect"
    assert res["form_id"] == "aspnetForm"
    assert res["form_action"] == "/TaxPortal/Submit.aspx"
    assert res["form_method"] == "POST"

    # Verify hidden fields preservation
    hidden = res["hidden_fields"]
    assert "__VIEWSTATE" in hidden
    assert "__EVENTVALIDATION" in hidden
    assert "__RequestVerificationToken" in hidden
    assert hidden["__RequestVerificationToken"] == "anti_csrf_token_xyz_998877"

    # Verify field extraction
    fields = {f["name"]: f for f in res["fields"]}
    assert "txtLegalName" in fields
    assert fields["txtLegalName"]["required"] is True
    assert "txtTaxID" in fields
    assert "ddlCountry" in fields
    assert fields["ddlCountry"]["type"] == "select"
    assert len(fields["ddlCountry"]["options"]) >= 4


def test_inspect_captcha_blocked_fail_closed(captcha_html: str):
    """Must immediately fail-closed when anti-bot or CAPTCHA signatures are found."""
    skill = WebFormMapperSkill()
    res = skill.execute({"action": "inspect", "html_content": captcha_html})

    assert res["status"] == "blocked"
    assert res["error"] == "CAPTCHA_DETECTED"
    assert "Turnstile" in res["message"] or "CAPTCHA" in res["message"]


def test_map_with_direct_payload(spa_html: str):
    """Direct payload maps accurately to input controls."""
    skill = WebFormMapperSkill()
    payload = {
        "first_name": "Bob",
        "last_name": "Smith",
        "email": "bob@example.com",
        "ssn": "000-11-2222",
        "phone": "+1 555 0199",
    }
    res = skill.execute(
        {
            "action": "map",
            "html_content": spa_html,
            "payload": payload,
        }
    )

    assert res["status"] == "success"
    assert len(res["unmapped_fields"]) == 0

    plan_by_name = {item["field_name"]: item for item in res["fill_plan"]}
    assert plan_by_name["first_name"]["proposed_value"] == "Bob"
    assert plan_by_name["last_name"]["proposed_value"] == "Smith"
    assert plan_by_name["contact_email"]["proposed_value"] == "bob@example.com"
    assert plan_by_name["ssn"]["proposed_value"] == "000-11-2222"


def test_map_with_addressbook_legal_profile(aspnet_html: str, sample_addressbook: Path):
    """Autofill form from addressbook.yaml operator legal_profile (use_self=True)."""
    skill = WebFormMapperSkill(addressbook_path=sample_addressbook)
    res = skill.execute(
        {
            "action": "map",
            "html_content": aspnet_html,
            "use_self": True,
        }
    )

    assert res["status"] == "success"
    assert len(res["unmapped_fields"]) == 0

    plan_by_name = {item["field_name"]: item for item in res["fill_plan"]}
    assert plan_by_name["txtLegalName"]["proposed_value"] == "Alice Marie Example"
    assert plan_by_name["txtTaxID"]["proposed_value"] == "DE-123456789"
    assert plan_by_name["txtEmail"]["proposed_value"] == "alice@example.com"
    assert plan_by_name["txtStreet"]["proposed_value"] == "Friedrichstrasse 12"
    assert plan_by_name["txtCity"]["proposed_value"] == "Berlin"
    assert plan_by_name["txtZip"]["proposed_value"] == "10117"
    # Country dropdown selection
    assert plan_by_name["ddlCountry"]["proposed_value"] == "DE"


def test_map_missing_required_returns_needs_input(spa_html: str):
    """Missing required fields return needs_input with unmapped list."""
    skill = WebFormMapperSkill()
    # Provide only first_name, missing last_name, email, and ssn
    res = skill.execute(
        {
            "action": "map",
            "html_content": spa_html,
            "payload": {"first_name": "OnlyName"},
        }
    )

    assert res["status"] == "needs_input"
    assert len(res["unmapped_fields"]) >= 2
    assert any("last" in f.lower() for f in res["unmapped_fields"])


def test_preview_diff_generation(aspnet_html: str, sample_addressbook: Path):
    """Preview produces a human-readable diff table with confidence scores."""
    skill = WebFormMapperSkill(addressbook_path=sample_addressbook)
    map_res = skill.execute(
        {
            "action": "map",
            "html_content": aspnet_html,
            "use_self": True,
        }
    )

    preview_res = skill.execute(
        {
            "action": "preview",
            "html_content": aspnet_html,
            "fill_plan": map_res["fill_plan"],
        }
    )

    assert preview_res["status"] == "success"
    table = preview_res["preview_table"]
    assert len(table) >= 5

    diff_by_sel = {d["selector"]: d for d in table}
    assert "#txtLegalName" in diff_by_sel
    assert diff_by_sel["#txtLegalName"]["proposed_value"] == "Alice Marie Example"
    assert diff_by_sel["#txtLegalName"]["confidence"] >= 0.85


def test_submit_dry_run_simulation(aspnet_html: str, tmp_path: Path):
    """Dry run simulates submission and writes payload receipt without network traffic."""
    skill = WebFormMapperSkill(scratch_dir=tmp_path)
    plan = [
        {
            "selector": "#txtLegalName",
            "field_name": "txtLegalName",
            "proposed_value": "Acme Corp",
            "source": "test",
            "confidence": 1.0,
        }
    ]

    res = skill.execute(
        {
            "action": "submit",
            "html_content": aspnet_html,
            "fill_plan": plan,
            "dry_run": True,
            "output_dir": str(tmp_path),
        }
    )

    assert res["status"] == "success"
    assert res["dry_run"] is True
    receipt_path = Path(res["submission_result"]["receipt_path"])
    assert receipt_path.is_file()

    saved_data = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert saved_data["simulated"] is True
    # Preserved hidden CSRF token must be in the payload
    assert (
        saved_data["payload"]["__RequestVerificationToken"]
        == "anti_csrf_token_xyz_998877"
    )
    assert saved_data["payload"]["txtLegalName"] == "Acme Corp"


def test_submit_without_confirmation_fails(aspnet_html: str):
    """Submitting with dry_run=False requires confirmed=True."""
    skill = WebFormMapperSkill()
    res = skill.execute(
        {
            "action": "submit",
            "html_content": aspnet_html,
            "fill_plan": [],
            "dry_run": False,
            "confirmed": False,
        }
    )

    assert res["status"] == "error"
    assert res["error"] == "CONFIRMATION_REQUIRED"


def test_submit_live_http_post_mocked(aspnet_html: str, tmp_path: Path):
    """Confirmed HTTP POST dispatches preserved tokens and writes response receipt."""
    skill = WebFormMapperSkill(scratch_dir=tmp_path)
    plan = [
        {
            "selector": "#txtLegalName",
            "field_name": "txtLegalName",
            "proposed_value": "Corp LLC",
            "source": "test",
            "confidence": 1.0,
        }
    ]

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = (
        b"<html><body>Filing Received: REF-990011</body></html>"
    )
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = skill.execute(
            {
                "action": "submit",
                "html_content": aspnet_html,
                "url": "https://taxportal.gov/TaxPortal/Submit.aspx",
                "fill_plan": plan,
                "dry_run": False,
                "confirmed": True,
                "output_dir": str(tmp_path),
            }
        )

    assert res["status"] == "success"
    assert res["dry_run"] is False
    assert res["submission_result"]["status_code"] == 200
    assert "REF-990011" in res["submission_result"]["response_snippet"]


@pytest.mark.asyncio
async def test_aexecute_async_parity(aspnet_html: str):
    """Async aexecute provides non-blocking execution parity."""
    skill = WebFormMapperSkill()
    res = await skill.aexecute(
        {
            "action": "inspect",
            "html_content": aspnet_html,
        }
    )

    assert res["status"] == "success"
    assert res["action"] == "inspect"
    assert "__VIEWSTATE" in res["hidden_fields"]
