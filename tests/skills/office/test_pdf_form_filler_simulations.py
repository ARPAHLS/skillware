# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

"""Multi-turn simulation and stress tests for office/pdf_form_filler (v0.2.0 W-8BEN)."""

import os
import fitz
import pytest

from skillware.core.loader import SkillLoader


@pytest.fixture(scope="module")
def pdf_skill():
    bundle = SkillLoader.load_skill("office/pdf_form_filler")
    return bundle["class"]()


def test_w8ben_multiturn_progressive_fill_simulation(pdf_skill, tmp_path):
    """Simulate a full multi-turn agent session filling IRS Form W-8BEN."""
    # Turn 1: Discover templates
    listed = pdf_skill.execute(
        {"action": "list_templates", "category": "tax", "jurisdiction": "US"}
    )
    assert listed["status"] == "ok"
    assert any(t["template_id"] == "us_irs_w8ben" for t in listed["templates"])

    # Turn 2-4: Fetch each section individually (context-window friendly)
    collected_fields = []
    for sec_id in ("part_1_identification", "part_2_treaty", "part_3_certification"):
        sec = pdf_skill.execute(
            {
                "action": "get_template_schema",
                "template_id": "us_irs_w8ben",
                "section": sec_id,
            }
        )
        assert sec["status"] == "ok"
        assert "sections" not in sec
        collected_fields.extend(f["id"] for f in sec["fields"])

    assert len(collected_fields) == 23

    # Turn 5: Validate catches bad date before touching disk
    edits = {
        "beneficial_owner_name": "Maria Ioannou",
        "country_of_citizenship": "Cyprus",
        "permanent_residence_street": "15 Makarios Ave",
        "permanent_residence_city_state_postal": "Nicosia 1065",
        "permanent_residence_country": "Cyprus",
        "foreign_tin": "CY-10293847",
        "date_of_birth": "1988-09-01",
        "treaty_country": "Cyprus",
        "treaty_article_and_paragraph": "Article 10(2)",
        "treaty_withholding_rate_pct": "15",
        "treaty_income_type": "Dividends",
        "capacity_to_sign": True,
        "signature": "Maria Ioannou",
        "signer_name": "Maria Ioannou",
    }
    bad_val = pdf_skill.execute(
        {"action": "validate", "template_id": "us_irs_w8ben", "edits": edits}
    )
    assert bad_val["status"] == "error"
    assert bad_val["valid"] is False

    # Turn 6: Fix date and validate cleanly
    edits["date_of_birth"] = "09-01-1988"
    good_val = pdf_skill.execute(
        {"action": "validate", "template_id": "us_irs_w8ben", "edits": edits}
    )
    assert good_val["status"] == "ok"
    assert good_val["valid"] is True

    # Turn 7: Preview (confirmed=False) redacts PII
    preview = pdf_skill.execute(
        {
            "action": "fill",
            "template_id": "us_irs_w8ben",
            "edits": edits,
            "output_dir": str(tmp_path),
            "confirmed": False,
        }
    )
    assert preview["status"] == "needs_input"
    assert preview["preview"]["proposed_edits"]["foreign_tin"] == "***3847"
    assert preview["preview"]["proposed_edits"]["date_of_birth"] == "***1988"

    # Turn 8: Confirmed flattened fill
    filled = pdf_skill.execute(
        {
            "action": "fill",
            "template_id": "us_irs_w8ben",
            "edits": edits,
            "output_dir": str(tmp_path),
            "confirmed": True,
            "flatten": True,
        }
    )
    assert filled["status"] == "success"
    out_path = filled["output_path"]
    assert os.path.isfile(out_path)
    doc = fitz.open(out_path)
    page_text = doc[0].get_text()
    doc.close()
    assert "Maria Ioannou" in page_text
    assert "Nicosia 1065" in page_text
    assert "Dividends" in page_text


def test_w8ben_batch_stress_mixed_profiles(pdf_skill, tmp_path):
    """Stress test: generate 10 distinct W-8BEN PDFs (treaty & non-treaty)."""
    for idx in range(10):
        name = f"Applicant Number {idx}"
        edits = {
            "beneficial_owner_name": name,
            "country_of_citizenship": "Germany" if idx % 2 == 0 else "Japan",
            "permanent_residence_street": f"{100 + idx} Friedrichstrasse",
            "permanent_residence_city_state_postal": (
                "Berlin 10117" if idx % 2 == 0 else "Tokyo 100-0001"
            ),
            "permanent_residence_country": "Germany" if idx % 2 == 0 else "Japan",
            "capacity_to_sign": True,
            "signer_name": name,
        }
        if idx % 2 == 0:
            edits["foreign_tin"] = f"DE-9988776{idx}"
            edits["treaty_country"] = "Germany"
            edits["treaty_article_and_paragraph"] = "Article 12(1)"
            edits["treaty_withholding_rate_pct"] = "0"
            edits["treaty_income_type"] = "Royalties"
        else:
            edits["ftin_not_legally_required"] = True

        res = pdf_skill.execute(
            {
                "action": "fill",
                "template_id": "us_irs_w8ben",
                "edits": edits,
                "output_dir": str(tmp_path),
                "filler_name": f"applicant_{idx}",
                "confirmed": True,
                "flatten": idx % 2 == 0,
            }
        )
        assert res["status"] == "success", f"Batch item {idx} failed: {res}"
        assert os.path.isfile(res["output_path"])
        doc = fitz.open(res["output_path"])
        assert len(doc) == 1
        doc.close()


def test_w8ben_scenario_audit_matrix(pdf_skill, tmp_path):
    """Audit all W-8BEN edge cases: full, partial/missing required, bad date, unknown field, unconfirmed."""
    audit_log = []

    # 1. Partial / missing required fields -> must fail closed and tell agent what to ask
    partial_res = pdf_skill.execute(
        {
            "action": "validate",
            "template_id": "us_irs_w8ben",
            "edits": {"beneficial_owner_name": "Alex Mercer"},
        }
    )
    audit_log.append(
        {
            "scenario": "partial_missing_required",
            "status": partial_res["status"],
            "errors": len(partial_res["errors"]),
        }
    )
    assert partial_res["status"] == "error"
    missing_ids = {e["field"] for e in partial_res["errors"]}
    assert {
        "country_of_citizenship",
        "permanent_residence_street",
        "capacity_to_sign",
        "signer_name",
    } <= missing_ids

    # 2. Unknown field injection -> must fail closed
    unknown_res = pdf_skill.execute(
        {
            "action": "validate",
            "template_id": "us_irs_w8ben",
            "edits": {
                "beneficial_owner_name": "Alex Mercer",
                "country_of_citizenship": "Canada",
                "permanent_residence_street": "10 Bay St",
                "permanent_residence_city_state_postal": "Toronto ON M5J 2R8",
                "permanent_residence_country": "Canada",
                "capacity_to_sign": True,
                "signer_name": "Alex Mercer",
                "injected_unknown_field": "malicious",
            },
        }
    )
    audit_log.append(
        {"scenario": "unknown_field_injection", "status": unknown_res["status"]}
    )
    assert unknown_res["status"] == "error"
    assert any(e["field"] == "injected_unknown_field" for e in unknown_res["errors"])

    # 3. Unconfirmed fill -> must redact PII and NOT write any PDF to disk
    valid_edits = {
        "beneficial_owner_name": "Alex Mercer",
        "country_of_citizenship": "Canada",
        "permanent_residence_street": "10 Bay St",
        "permanent_residence_city_state_postal": "Toronto ON M5J 2R8",
        "permanent_residence_country": "Canada",
        "us_tin": "123-45-6789",
        "foreign_tin": "CA-55443322",
        "date_of_birth": "07-04-1985",
        "capacity_to_sign": True,
        "signer_name": "Alex Mercer",
    }
    preview_res = pdf_skill.execute(
        {
            "action": "fill",
            "template_id": "us_irs_w8ben",
            "edits": valid_edits,
            "output_dir": str(tmp_path),
            "confirmed": False,
        }
    )
    audit_log.append(
        {
            "scenario": "unconfirmed_preview",
            "status": preview_res["status"],
            "redacted": preview_res["preview"]["redacted_fields"],
        }
    )
    assert preview_res["status"] == "needs_input"
    assert not os.path.exists(preview_res["preview"]["output_path"])
    assert preview_res["preview"]["proposed_edits"]["us_tin"] == "***6789"
    assert preview_res["preview"]["proposed_edits"]["foreign_tin"] == "***3322"
    assert preview_res["preview"]["proposed_edits"]["date_of_birth"] == "***1985"

    # 4. Confirmed fill with auto_date -> writes readable PDF and verifies all widgets/text
    fill_res = pdf_skill.execute(
        {
            "action": "fill",
            "template_id": "us_irs_w8ben",
            "edits": valid_edits,
            "output_dir": str(tmp_path),
            "confirmed": True,
            "flatten": False,
        }
    )
    audit_log.append(
        {
            "scenario": "confirmed_fill_auto_date",
            "status": fill_res["status"],
            "filled_count": len(fill_res["filled_fields"]),
        }
    )
    assert fill_res["status"] == "success"
    doc = fitz.open(fill_res["output_path"])
    widgets = {w.field_name: w.field_value for w in doc[0].widgets()}
    doc.close()
    assert widgets["topmostSubform[0].Page1[0].f_1[0]"] == "Alex Mercer"
    assert widgets["topmostSubform[0].Page1[0].f_9[0]"] == "123-45-6789"
    assert widgets["topmostSubform[0].Page1[0].f_10[0]"] == "CA-55443322"
    assert widgets["topmostSubform[0].Page1[0].Date[0]"]  # auto-populated MM-DD-YYYY
    assert len(audit_log) == 4


def test_session_restart_resilience_and_batch_stress(pdf_skill, tmp_path):
    """Simulate process-restart session resume and 5-session concurrent/batch isolation."""
    from skillware.core.loader import SkillLoader

    sdir = str(tmp_path / "sessions")
    session_ids = []

    # Create 5 independent sessions
    for i in range(5):
        init_res = pdf_skill.execute(
            {
                "action": "session_init",
                "template_id": "us_irs_w8ben",
                "session_dir": sdir,
            }
        )
        assert init_res["status"] == "ok"
        sid = init_res["session_id"]
        session_ids.append(sid)

        upd = pdf_skill.execute(
            {
                "action": "session_update",
                "session_id": sid,
                "session_dir": sdir,
                "values": {
                    "beneficial_owner_name": f"Session User {i}",
                    "country_of_citizenship": "Greece",
                    "permanent_residence_street": f"{i} Ermou St",
                    "permanent_residence_city_state_postal": "Athens 10563",
                    "permanent_residence_country": "Greece",
                    "capacity_to_sign": True,
                    "signature": f"Session User {i}",
                    "signer_name": f"Session User {i}",
                },
                "skip_fields": ["us_tin"],
            }
        )
        assert upd["status"] == "ready"

    # Simulate fresh SkillLoader instance (process restart)
    fresh_skill = SkillLoader.load_skill("office/pdf_form_filler")["class"]()
    for i, sid in enumerate(session_ids):
        out_pdf = str(tmp_path / f"session_{i}.pdf")
        fin = fresh_skill.execute(
            {
                "action": "session_finalize",
                "session_id": sid,
                "session_dir": sdir,
                "output_path": out_pdf,
                "confirmed": True,
            }
        )
        assert fin["status"] == "success"
        doc = fitz.open(out_pdf)
        text = doc[0].get_text()
        doc.close()
        assert f"Session User {i}" in text
        assert f"/s/ Session User {i}" in text
