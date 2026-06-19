from skillware.core.loader import SkillLoader


def run_demo():
    print("Loading wellness/mental_coach...")
    bundle = SkillLoader.load_skill("wellness/mental_coach")
    skill = bundle["module"].MentalCoachSkill()

    scenarios = [
        (
            "Coaching",
            {
                "user_prompt": "I feel stressed at work and need coping strategies.",
                "user_jurisdiction": "US",
                "session_mode": "coaching",
                "run_evaluator": False,
            },
        ),
        (
            "Crisis escalation",
            {
                "user_prompt": "I want to kill myself tonight.",
                "user_jurisdiction": "US",
            },
        ),
        (
            "Blocked clinical request",
            {
                "user_prompt": "Can you diagnose me with depression?",
                "user_jurisdiction": "US",
            },
        ),
    ]

    for label, params in scenarios:
        print(f"\n=== {label} ===")
        result = skill.execute(params)
        print(f"policy_status: {result.get('policy_status')}")
        print(f"scope: {result.get('scope')}")
        print(
            f"chunks: {result.get('privacy_metadata', {}).get('kb_chunks_retrieved')}"
        )
        print(f"context preview: {result.get('final_context_for_agent', '')[:240]}...")


if __name__ == "__main__":
    run_demo()
