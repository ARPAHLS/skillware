# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

"""
Multi-turn offline demo: filling IRS Form W-8BEN with office/pdf_form_filler v0.2.0.

Demonstrates:
1. list_templates -> discover curated static AcroForm templates
2. get_template_schema(section=...) -> context-safe section chunking
3. validate -> schema + date + required field verification
4. fill(confirmed=False) -> PII-redacted preview
5. fill(confirmed=True, flatten=True) -> auto-named flattened PDF output
"""

import json
import tempfile
from pathlib import Path

from skillware.core.loader import SkillLoader


def main() -> None:
    bundle = SkillLoader.load_skill("office/pdf_form_filler")
    skill = bundle["class"]()

    # 1. Discover curated templates
    templates = skill.execute({"action": "list_templates", "category": "tax"})
    print("1. list_templates:", json.dumps(templates, indent=2))

    # 2. Fetch Part I schema chunk only
    part1 = skill.execute(
        {
            "action": "get_template_schema",
            "template_id": "us_irs_w8ben",
            "section": "part_1_identification",
        }
    )
    print(
        "2. Part I fields:",
        [f["id"] for f in part1.get("fields", [])],
    )

    edits = {
        "beneficial_owner_name": "Elena Papadopoulou",
        "country_of_citizenship": "Greece",
        "permanent_residence_street": "24 Syntagma Sq",
        "permanent_residence_city_state_postal": "Athens 10563",
        "permanent_residence_country": "Greece",
        "foreign_tin": "EL-987654321",
        "date_of_birth": "04-15-1992",
        "treaty_country": "Greece",
        "treaty_article_and_paragraph": "Article 12(2)",
        "treaty_withholding_rate_pct": "5",
        "treaty_income_type": "Royalties",
        "capacity_to_sign": True,
        "signature": "Elena Papadopoulou",
        "signer_name": "Elena Papadopoulou",
    }

    # 3. Validate edits against schema + PDF widgets
    validation = skill.execute(
        {"action": "validate", "template_id": "us_irs_w8ben", "edits": edits}
    )
    print("3. validate:", json.dumps(validation, indent=2))

    with tempfile.TemporaryDirectory() as tmpdir:
        # 4. Redacted preview (confirmed=False)
        preview = skill.execute(
            {
                "action": "fill",
                "template_id": "us_irs_w8ben",
                "edits": edits,
                "output_dir": tmpdir,
                "confirmed": False,
            }
        )
        print("4. preview (PII redacted):", json.dumps(preview, indent=2))

        # 5. Confirmed & flattened generation
        filled = skill.execute(
            {
                "action": "fill",
                "template_id": "us_irs_w8ben",
                "edits": edits,
                "output_dir": tmpdir,
                "confirmed": True,
                "flatten": True,
            }
        )
        print("5. filled:", json.dumps(filled, indent=2))
        assert Path(filled["output_path"]).is_file()


if __name__ == "__main__":
    main()
