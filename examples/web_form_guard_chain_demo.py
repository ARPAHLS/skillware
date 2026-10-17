"""
Chained execution demo: security/deceptive_ui_guard -> office/web_form_mapper (offline).

Demonstrates a secure preflight guardrail chain for web form automation:
1. security/deceptive_ui_guard screens the form HTML for deceptive UX, dark
   patterns, fake urgency countdowns, or hidden pre-checked recurring charges.
2. If and only if the surface is safe (is_safe == True), office/web_form_mapper
   proceeds to inspect form controls, map identity fields, and generate diffs.
3. If deceptive patterns are detected, the mapper is automatically skipped to
   prevent corporate identity leakage or unauthorized subscription commitments.

Usage:
    python examples/web_form_guard_chain_demo.py
"""

from __future__ import annotations

import os
import tempfile
import yaml

from skillware import SkillContext
from skillware.chains import run_chain, validate_chain
from skillware.core.chains_config import ChainDefinition, ChainStep, StepWhen

GUARD_SKILL = "security/deceptive_ui_guard"
MAPPER_SKILL = "office/web_form_mapper"

# Realistic benign enterprise corporate filing form
BENIGN_FORM_HTML = """
<!DOCTYPE html>
<html>
<head><title>Department of Revenue - Annual Corporate Tax Declaration</title></head>
<body>
  <h1>Official Business Entity Filing</h1>
  <form id="tax-form" action="/api/v1/filings/submit" method="POST">
    <input type="hidden" name="_csrf" value="csrf_token_prod_998811">
    <input type="hidden" name="__VIEWSTATE" value="wEPDwUKLTU4OTky">
    <label for="entity_name">Registered Legal Entity Name</label>
    <input type="text" id="entity_name" name="entity_name" required>

    <label for="tax_id">Tax Identification Number (EIN / Steuernummer)</label>
    <input type="text" id="tax_id" name="tax_id" required>

    <label for="contact_email">Official Signatory Email</label>
    <input type="email" id="contact_email" name="contact_email" required>

    <label for="jurisdiction">Country of Registration</label>
    <select id="jurisdiction" name="jurisdiction">
      <option value="US">United States</option>
      <option value="DE">Germany</option>
      <option value="GB">United Kingdom</option>
    </select>

    <button type="submit">Submit Declaration</button>
  </form>
</body>
</html>
"""

# Malicious/deceptive form with fake countdown urgency and hidden pre-checked billing subscription
DECEPTIVE_FORM_HTML = """
<!DOCTYPE html>
<html>
<head><title>Fast Filing Expedite Service</title></head>
<body>
  <div class="countdown-warning">
    <p>CRITICAL ALERT: You have only 00:59 seconds left before your corporate charter is REVOKED!</p>
  </div>
  <form id="expedite-form" action="/charge-card" method="POST">
    <label for="company">Company Name</label>
    <input type="text" id="company" name="company">

    <div style="opacity: 0.05; height: 1px; overflow: hidden;">
      <input type="checkbox" id="vip_sub" name="vip_sub" checked>
      <label for="vip_sub">Enroll in recurring VIP enterprise monitoring at $499/month automatically</label>
    </div>

    <button type="submit">Expedite Now</button>
  </form>
</body>
</html>
"""


def build_secure_form_intake_chain() -> ChainDefinition:
    """Builds a deterministic two-step preflight and inspection chain."""
    return ChainDefinition(
        name="secure_web_form_intake",
        description="Screen HTML for deceptive UI and dark patterns; inspect form controls only if safe.",
        steps=(
            ChainStep(
                skill=GUARD_SKILL,
                step_id="guard",
                params={
                    "sensitivity": "strict",
                    "intended_action": "fill corporate filing declaration",
                },
                input_from={"html_content": "host.html_content"},
            ),
            ChainStep(
                skill=MAPPER_SKILL,
                step_id="inspect_form",
                when=StepWhen(prior_step="guard", field="is_safe", equals=True),
                params={"action": "inspect"},
                input_from={"html_content": "host.html_content"},
            ),
        ),
    )


def run_demo() -> None:
    print("=== Secure Web Form Intake Chain Demo (Local / Offline) ===\n")
    chain = build_secure_form_intake_chain()
    validate_chain(chain, strict=True)

    scenarios = [
        ("Benign Corporate Filing Portal", BENIGN_FORM_HTML),
        ("Deceptive / Dark-Pattern Portal", DECEPTIVE_FORM_HTML),
    ]

    for label, html in scenarios:
        print(f"--- Running Scenario: {label} ---")
        result = run_chain(chain, host_input={"html_content": html})
        print(f"Overall Chain Status: {result.status}")
        if result.errors:
            print(f"Errors: {result.errors}")

        for step in result.steps:
            print(f"  > Step {step.index} ({step.skill_id}): status={step.status}")
            if step.skill_id == GUARD_SKILL and step.output:
                print(
                    f"    - Surface Trust Score: {step.output.get('trust_score')}/100"
                )
                print(f"    - Posture Status:      {step.output.get('status')}")
                print(f"    - Safe to Proceed:     {step.output.get('is_safe')}")
                findings = step.output.get("findings", [])
                if findings:
                    print(f"    - Findings Detected:   {len(findings)} dark pattern(s)")
                    for f in findings[:2]:
                        desc = f.get("description") or f.get("category") or str(f)
                        print(f"      * {desc}")
            elif step.skill_id == MAPPER_SKILL:
                if step.status == "ok" and step.output:
                    form_action = step.output.get("form_action")
                    fields = step.output.get("fields", [])
                    hidden = step.output.get("hidden_fields", {})
                    print(f"    - Form Target Action:  {form_action}")
                    print(f"    - Controls Extracted:  {len(fields)} fields")
                    print(f"    - Hidden CSRF Tokens:  {list(hidden.keys())}")
                elif step.status == "skipped":
                    print(
                        "    - [SAFETY HALT] Inspection safely aborted due to deceptive UI detection."
                    )
        print()

    print("--- Multi-Skill Host Orchestration (SkillContext: Mapper + AddressBook) ---")
    with tempfile.TemporaryDirectory() as tmp_dir:
        book_path = os.path.join(tmp_dir, "addressbook.yaml")
        with open(book_path, "w", encoding="utf-8") as f:
            yaml.dump(
                {
                    "contacts": {
                        "self": {
                            "display_name": "Acme Holdings LLC",
                            "emails": ["filings@acme.corp"],
                            "legal_profile": {
                                "legal_name": "Acme Holdings International LLC",
                                "tax_id": "DE-998877665",
                                "jurisdiction": "DE",
                            },
                        }
                    }
                },
                f,
            )

        ctx = SkillContext(skills=[MAPPER_SKILL])
        # 1. Map fields with operator legal_profile
        mapped = ctx.execute(
            MAPPER_SKILL,
            {
                "action": "map",
                "html_content": BENIGN_FORM_HTML,
                "use_self": True,
                "addressbook_path": book_path,
            },
        )
        fill_plan = mapped.get("fill_plan", [])
        print(f"Mapped {len(fill_plan)} fields against corporate legal_profile:")
        for item in fill_plan:
            print(
                f"  * {item.get('field_name')} -> "
                f"'{item.get('proposed_value')}' "
                f"(conf: {item.get('confidence')})"
            )

        # 2. Generate side-by-side human review diff table
        diff = ctx.execute(
            MAPPER_SKILL,
            {
                "action": "preview",
                "html_content": BENIGN_FORM_HTML,
                "fill_plan": fill_plan,
            },
        )
        print("\nHuman Review Preview Diff:")
        print(f"  | {'Field Label':<30} | {'Proposed Value':<32} | Conf |")
        print(f"  |{'-' * 32}|{'-' * 34}|------|")
        for row in diff.get("preview_table", []):
            label = (row.get("label") or row.get("field_name") or "")[:28]
            val = str(row.get("proposed_value") or "")[:30]
            conf = float(row.get("confidence", 0.0))
            print(f"  | {label:<30} | {val:<32} | {conf:.2f} |")
        print()

    print("Demo completed successfully.")


if __name__ == "__main__":
    run_demo()
