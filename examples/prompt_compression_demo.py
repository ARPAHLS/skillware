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

    # Execute the offline compression logic
    result = skill_instance.execute(
        {"text": massive_prompt, "mode": "aggressive"}
    )

    print(f"\n[COMPRESSED TEXT]: {result['compressed_text']}")
    print(
        f"[REDUCTION]: {result['original_tokens']} tokens -> {result['compressed_tokens']} tokens"
    )
    print(f"[SAVED]: {result['tokens_saved']} tokens")


if __name__ == "__main__":
    run_demo()
