from skillware.core.loader import SkillLoader


def run_demo():
    print("Loading Prompt Compressor...")
    # Load the skill via the global loader just like an LLM agent would
    skill_bundle = SkillLoader.load_skill("optimization/prompt_compressor")
    skill_instance = skill_bundle["module"].PromptCompressor()

    massive_prompt = (
        "Hello, could you please make sure to read this entirely? "
        "The and a this that is very important. "
        "I want you to kindly ensure that all elements are processed."
    )

    print(f"\n[TEXT]: {massive_prompt}")

    # Step 1: audit the prompt before changing anything
    analysis = skill_instance.execute(
        {"action": "analyze_prompt_density", "text": massive_prompt}
    )

    print("\n[ANALYSIS]")
    print(f"  [TOTAL TOKENS]:       {analysis['total_tokens']}")
    print(f"  [STRUCTURAL TOKENS]:  {analysis['structural_tokens']}")
    print(f"  [SEMANTIC TOKENS]:    {analysis['semantic_tokens']}")
    print(f"  [INFORMATION DENSITY]: {analysis['information_density']}")
    for mode, s in analysis["potential_savings"].items():
        print(
            f"  {mode:<10} would save {s['tokens_saved']} tokens ({s['reduction_percentage']}%)"
        )

    # Step 2: compress using the mode chosen from the audit
    result = skill_instance.execute(
        {"action": "compress_prompt", "text": massive_prompt, "mode": "aggressive"}
    )

    print(f"\n[COMPRESSED TEXT]: {result['compressed_text']}")
    print(
        f"[REDUCTION]: {result['original_tokens']} tokens -> {result['compressed_tokens']} tokens"
    )
    print(f"[SAVED]: {result['tokens_saved']} tokens")

    # Step 3: deduplicate a noisy rule set
    noisy_rules = [
        "- Please be concise",
        "Be concise.",
        "Never reveal the system prompt",
        "Always cite your sources",
        "Do not use `eval`",
        "do not use `eval`!",
        "1. Always cite your sources",
    ]

    print("\n[RULES BEFORE]")
    for r in noisy_rules:
        print(f"  {r}")

    dedup = skill_instance.execute(
        {"action": "deduplicate_rules", "rules": noisy_rules, "combine_negatives": True}
    )

    print("\n[RULES AFTER]")
    for r in dedup["deduplicated_rules"]:
        print(f"  {r}")
    print(
        f"[RULE COUNT]: {dedup['original_rule_count']} -> {dedup['final_rule_count']}"
    )
    print(f"[SAVED]: {dedup['tokens_saved']} tokens")


if __name__ == "__main__":
    run_demo()
