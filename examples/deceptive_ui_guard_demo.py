"""Local execute demo for security/deceptive_ui_guard (v0.2.0).

Loads sanitized HTML recreations of documented dark patterns (confirm shaming,
drip pricing, forced continuity, mislabeled CTAs, anti-agent hidden text).
Demonstrates v2 capabilities: DOM zone weighting, session nag tracking,
mobile profile heuristics, and zone summary breakdowns.

Demo fixtures live under examples/fixtures/deceptive_ui/. For the expanded
23-fixture golden test corpus categorized across 8 sub-domains, see
tests/fixtures/deceptive_ui/.
"""

from pathlib import Path

from skillware.core.loader import SkillLoader

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "deceptive_ui"


def _load_fixture(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def run_demo():
    print("Loading security/deceptive_ui_guard (v0.2.0)...")
    bundle = SkillLoader.load_skill("security/deceptive_ui_guard")
    skill = bundle["module"].DeceptiveUiGuardSkill()

    scenarios = [
        (
            "Confirm shaming with session nag tracking (newsletter modal)",
            {
                "html_content": _load_fixture("confirm_shaming_newsletter.html"),
                "sensitivity": "balanced",
                "intended_action": "browse storefront",
                "session_fingerprint": "session_usr_98231_checkout",
            },
        ),
        (
            "Drip pricing & zone weighting (late fee disclosure in checkout zone)",
            {
                "html_content": _load_fixture("drip_pricing_checkout.html"),
                "sensitivity": "balanced",
                "intended_action": "complete checkout payment",
            },
        ),
        (
            "Forced continuity (free trial auto-renew signup)",
            {
                "html_content": _load_fixture("forced_continuity_trial.html"),
                "sensitivity": "balanced",
                "intended_action": "start subscription trial",
            },
        ),
        (
            "Mislabeled CTA (visible vs aria-label mismatch)",
            {
                "html_content": _load_fixture("mislabeled_subscription_cta.html"),
                "sensitivity": "balanced",
            },
        ),
        (
            "Hidden imperative anti-agent text (display:none override)",
            {
                "html_content": _load_fixture("hidden_imperative_anti_agent.html"),
                "sensitivity": "balanced",
                "intended_action": "complete checkout",
                "render_mode": "off",
            },
        ),
        (
            "Clean control (neutral product documentation with zone summary)",
            {
                "html_content": _load_fixture("clean_product_docs.html"),
                "sensitivity": "balanced",
                "surface_profile": "desktop",
            },
        ),
    ]

    for label, params in scenarios:
        print(f"\n=== {label} ===")
        result = skill.execute(params)
        print(f"status: {result.get('status')}")
        print(f"trust_score: {result.get('trust_score')}")
        print(f"is_safe: {result.get('is_safe')}")
        print(f"risk_level: {result.get('risk_level')}")
        print(f"findings: {len(result.get('findings') or [])}")
        if result.get("findings"):
            for finding in result["findings"][:3]:
                print(
                    f"  - {finding.get('type')}/{finding.get('subtype')} "
                    f"({finding.get('severity')}) [zone={finding.get('zone')}]"
                )
        if result.get("zone_summary"):
            active_zones = {
                z: data["findings_count"]
                for z, data in result["zone_summary"].items()
                if data["findings_count"] > 0
            }
            if active_zones:
                print(f"zone_findings: {active_zones}")
        if result.get("session_recommendation"):
            print(f"session_recommendation: {result.get('session_recommendation')}")
        print(f"sanitized_excerpt: {result.get('sanitized_excerpt')!r}")
        guidance = result.get("agent_guidance") or {}
        print(f"verify_before_payment: {guidance.get('verify_before_payment')}")
        if guidance.get("do_not_click"):
            print(f"do_not_click: {guidance.get('do_not_click')}")


if __name__ == "__main__":
    run_demo()
