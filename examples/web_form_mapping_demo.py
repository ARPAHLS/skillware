"""Local execute and offline demo for office/web_form_mapper.

Demonstrates:
1. Inspecting web form HTML to discover fields and preserve hidden CSRF tokens.
2. Mapping contact identity from addressbook.yaml (legal_profile) or direct payload.
3. Generating a human-review preview diff table with confidence scores.
4. Executing a safe dry-run submission generating a receipt artifact.

Run offline:
    python examples/web_form_mapping_demo.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from skillware.core.loader import SkillLoader  # noqa: E402

SAMPLE_FORM_HTML = """<!DOCTYPE html>
<html>
<head><title>Business Tax Declaration Portal</title></head>
<body>
    <form id="tax-form" action="/api/v1/tax/declaration" method="POST">
        <input type="hidden" name="_csrf" value="tok_sec_secure_998877" />
        <input type="hidden" name="__VIEWSTATE" value="/wEPDwULLTE4MzQ5MzY4NzAPZBYCZg9kFgICAQ88KwANAwAPFgIeC18hSXR" />

        <label for="txtLegalName">Legal Entity / Full Name</label>
        <input type="text" id="txtLegalName" name="txtLegalName" required />

        <label for="txtTaxID">Tax Identification Number (TIN / EIN)</label>
        <input type="text" id="txtTaxID" name="txtTaxID" placeholder="XX-XXXXXXX" required />

        <label for="txtEmail">Official Notification Email</label>
        <input type="email" id="txtEmail" name="txtEmail" required />

        <label for="txtStreet">Registered Physical Address</label>
        <input type="text" id="txtStreet" name="txtStreet" />

        <label for="txtCity">City</label>
        <input type="text" id="txtCity" name="txtCity" />

        <label for="txtZip">Postal / ZIP Code</label>
        <input type="text" id="txtZip" name="txtZip" />

        <label for="ddlCountry">Country</label>
        <select id="ddlCountry" name="ddlCountry">
            <option value="">-- Select Country --</option>
            <option value="US">United States</option>
            <option value="DE">Germany</option>
            <option value="GR">Greece</option>
        </select>

        <button type="submit" id="btnSubmit">Submit Declaration</button>
    </form>
</body>
</html>
"""


def main() -> None:
    print("=== office/web_form_mapper Demo (Local / Offline) ===")
    bundle = SkillLoader.load_skill("office/web_form_mapper")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # 1. Create a sample addressbook.yaml with operator legal_profile
        addressbook = {
            "contacts": {
                "me": {
                    "display_name": "Alice Example",
                    "is_self": True,
                    "emails": ["alice@example.com"],
                    "org": "Example GmbH",
                    "legal_profile": {
                        "type": "individual",
                        "legal_name": "Alice Marie Example",
                        "tax_id": "DE-998877665",
                        "citizenship": "DE",
                        "address": {
                            "street": "Friedrichstrasse 12",
                            "city": "Berlin",
                            "postal_code": "10117",
                            "country": "Germany",
                        },
                    },
                }
            }
        }
        ab_path = tmp_path / "addressbook.yaml"
        ab_path.write_text(yaml.safe_dump(addressbook), encoding="utf-8")

        skill = bundle["class"](addressbook_path=ab_path, scratch_dir=tmp_path)

        # Step 1: Inspect form
        print("\n1. Inspecting web form HTML:")
        inspect_res = skill.execute(
            {"action": "inspect", "html_content": SAMPLE_FORM_HTML}
        )
        print(
            f"   Form ID: {inspect_res['form_id']} | Action: {inspect_res['form_action']}"
        )
        print(f"   Detected Fields: {len(inspect_res['fields'])}")
        print(
            f"   Preserved Hidden Tokens: {list(inspect_res['hidden_fields'].keys())}"
        )

        # Step 2: Map with addressbook profile
        print("\n2. Mapping fields against operator legal_profile (use_self=True):")
        map_res = skill.execute(
            {
                "action": "map",
                "html_content": SAMPLE_FORM_HTML,
                "use_self": True,
            }
        )
        print(f"   Mapping Status: {map_res['status']}")
        print(
            f"   Mapped Fields: {len(map_res['fill_plan'])} | Unmapped: {map_res['unmapped_fields']}"
        )
        for item in map_res["fill_plan"]:
            print(
                f"     - {item['field_name']}: {item['proposed_value']!r} (confidence: {item['confidence']})"
            )

        # Step 3: Preview diff table
        print("\n3. Generating Human-Review Preview Diff:")
        preview_res = skill.execute(
            {
                "action": "preview",
                "html_content": SAMPLE_FORM_HTML,
                "fill_plan": map_res["fill_plan"],
            }
        )
        print("   " + "-" * 65)
        print(f"   {'Field Label':<28} | {'Proposed Value':<20} | {'Confidence':<10}")
        print("   " + "-" * 65)
        for row in preview_res["preview_table"]:
            print(
                f"   {row['label'][:28]:<28} | {row['proposed_value'][:20]:<20} | {row['confidence']:<10.2f}"
            )
        print("   " + "-" * 65)

        # Step 4: Dry-run submission simulation
        print("\n4. Executing Safe Dry-Run Submission:")
        submit_res = skill.execute(
            {
                "action": "submit",
                "html_content": SAMPLE_FORM_HTML,
                "fill_plan": map_res["fill_plan"],
                "dry_run": True,
                "output_dir": str(tmp_path),
            }
        )
        print(
            f"   Submit Status: {submit_res['status']} (Dry-Run: {submit_res['dry_run']})"
        )
        print(f"   Receipt Artifact: {submit_res['submission_result']['receipt_path']}")
        payload = submit_res["submission_result"]["payload"]
        print(f"   Preserved _csrf: {payload.get('_csrf')}")
        print(f"   Submitted Legal Name: {payload.get('txtLegalName')}")

    print("\nDemo completed successfully.")


if __name__ == "__main__":
    main()
