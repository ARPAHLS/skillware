"""Maintainer integration and stress tests for office/web_form_mapper."""

from __future__ import annotations

from pathlib import Path

import yaml

from skillware.core.loader import SkillLoader
from skills.office.web_form_mapper.skill import WebFormMapperSkill


def test_web_form_mapper_loader_and_manifest():
    """Verify SkillLoader correctly discovers and initializes office/web_form_mapper."""
    bundle = SkillLoader.load_skill("office/web_form_mapper")
    assert bundle is not None
    manifest = bundle["manifest"]
    assert manifest["name"] == "office/web_form_mapper"
    assert manifest["category"] == "office"
    assert "inspect" in manifest["parameters"]["properties"]["action"]["enum"]

    skill = bundle["class"]()
    assert skill.manifest["name"] == "office/web_form_mapper"


def test_multi_form_page_indexing():
    """Verify multi-form pages can target specific form by form_index."""
    multi_form_html = """
    <html>
        <body>
            <!-- Form 0: Search -->
            <form id="search-form" action="/search" method="GET">
                <input type="text" name="q" placeholder="Search..." />
            </form>

            <!-- Form 1: Registration -->
            <form id="reg-form" action="/register" method="POST">
                <input type="hidden" name="token" value="abc123token" />
                <label for="company">Company</label>
                <input type="text" id="company" name="company" required />
                <label for="tax_id">Tax ID</label>
                <input type="text" id="tax_id" name="tax_id" required />
            </form>
        </body>
    </html>
    """
    skill = WebFormMapperSkill()

    # Target Form 1
    inspect_res = skill.execute(
        {
            "action": "inspect",
            "html_content": multi_form_html,
            "form_index": 1,
        }
    )
    assert inspect_res["status"] == "success"
    assert inspect_res["form_id"] == "reg-form"
    assert inspect_res["form_action"] == "/register"
    assert "token" in inspect_res["hidden_fields"]


def test_entity_client_filing_simulation(tmp_path: Path):
    """Stress test filling corporate client entity data from addressbook."""
    addressbook_content = {
        "contacts": {
            "acme_corp": {
                "display_name": "Acme Holdings LLC",
                "org": "Acme Corp",
                "emails": ["tax@acme.com"],
                "legal_profile": {
                    "type": "entity",
                    "legal_name": "Acme Holdings LLC",
                    "ein": "88-1234567",
                    "incorporation_date": "2018-03-21",
                    "address": {
                        "street": "1209 North Orange St",
                        "city": "Wilmington",
                        "state": "Delaware",
                        "postal_code": "19801",
                        "country": "United States",
                    },
                },
            }
        }
    }
    ab_path = tmp_path / "addressbook.yaml"
    ab_path.write_text(yaml.safe_dump(addressbook_content), encoding="utf-8")

    filing_html = """
    <form action="/api/v1/filings/delaware" method="POST">
        <input type="hidden" name="csrf" value="tok_sec_8899" />
        <input type="text" name="corp_name" placeholder="Entity Name" required />
        <input type="text" name="ein_number" placeholder="Federal EIN" required />
        <input type="text" name="registered_street" placeholder="Registered Street Address" required />
        <input type="text" name="registered_city" placeholder="City" required />
        <input type="text" name="registered_zip" placeholder="Zip Code" required />
        <input type="email" name="contact_email" placeholder="Official Email" required />
    </form>
    """

    skill = WebFormMapperSkill(addressbook_path=ab_path, scratch_dir=tmp_path)

    # Map with contact_id="acme_corp"
    map_res = skill.execute(
        {
            "action": "map",
            "html_content": filing_html,
            "contact_id": "acme_corp",
            "form_profile_id": "delaware_corp_filing",
        }
    )

    assert map_res["status"] == "success"
    assert len(map_res["unmapped_fields"]) == 0

    plan_items = {
        item["field_name"]: item["proposed_value"] for item in map_res["fill_plan"]
    }
    assert plan_items["corp_name"] == "Acme Corp"
    assert plan_items["ein_number"] == "88-1234567"
    assert plan_items["registered_street"] == "1209 North Orange St"
    assert plan_items["registered_city"] == "Wilmington"
    assert plan_items["registered_zip"] == "19801"
    assert plan_items["contact_email"] == "tax@acme.com"

    # Preview
    preview_res = skill.execute(
        {
            "action": "preview",
            "html_content": filing_html,
            "fill_plan": map_res["fill_plan"],
        }
    )
    assert preview_res["status"] == "success"
    assert len(preview_res["preview_table"]) == 6

    # Submit simulation (dry_run=True)
    submit_res = skill.execute(
        {
            "action": "submit",
            "html_content": filing_html,
            "fill_plan": map_res["fill_plan"],
            "dry_run": True,
            "output_dir": str(tmp_path),
        }
    )
    assert submit_res["status"] == "success"
    assert submit_res["submission_result"]["payload"]["csrf"] == "tok_sec_8899"
    assert submit_res["submission_result"]["payload"]["ein_number"] == "88-1234567"
