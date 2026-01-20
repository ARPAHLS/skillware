# Skillware vs. Anthropic Skills

While both Skillware and [Anthropic's Skills](https://github.com/anthropics/skills) repository share the goal of empowering AI agents with modular capabilities, they differ fundamentally in scope, architecture, and intent.

Skillware is designed to be a comprehensive, model-agnostic **Framework**, whereas Anthropic's repository is a collection of reference implementations specifically for Claude.

## Key Differences

### 1. Model Agnosticism
*   **Anthropic Skills**: Optimized specifically for the Claude family of models. The prompts and structures are tuned for Claude's specific attention patterns and context window behavior.
*   **Skillware**: Built from the ground up to be **Universal**.
    *   **Any Model**: Works with OpenAI (GPT-4), Google (Gemini), Anthropic (Claude), LLaMA, and custom local models.
    *   **Abstraction Layer**: We provide the "glue" code that adapts a skill's output to the specific formatting requirements of different models (e.g., function calling schemas vs. XML tools).

### 2. Cognitive Context & System Prompts
Anthropic's approach relies heavily on `SKILL.md` for context. Skillware adopts and extends this:
*   **Integrated Instruction Sets**: Every Skillware skill includes not just code, but also refined **Procedures** and **System Prompts**.
*   **Context Injection**: When a skill is loaded, our orchestrator automatically appends the necessary instructions to the model's system prompt, ensuring the model knows *exactly* how and when to use the tool, regardless of its underlying architecture.
*   **Safety "Constitution"**: We enforce safety rules (defined in the Manifest) at the prompt level, providing a layer of governance that travels with the skill.

### 3. Maps, Parsers, & Orchestration
Skillware is not just a library of folders; it is an active runtime environment.
*   **Orchestrators**: We provide the runtime logic to manage the lifecycle of a skill—from discovery to execution to cleanup.
*   **Parsers**: Our framework handles the "messy middle" of parsing model outputs into structured data that the Python code can execute, handling edge cases and errors gracefully.
*   **Cognitive Maps**: We map capabilities to semantic descriptions, allowing agents to "browse" for skills based on vague intent (e.g., "I need to analyze this dataset") rather than knowing exact function names.

## Summary

| Feature | Anthropic Skills | ARPA Skillware |
| :--- | :--- | :--- |
| **Scope** | Reference Library | Full Application Framework |
| **Target Model** | Claude Only | **Any LLM** (Model Agnostic) |
| **Execution** | Manual / Script-based | **Managed Runtime** (Orchestrators) |
| **Discovery** | File-system | **Semantic Registry** & Manifests |
| **Philosophy** | "Here is how to teach Claude" | "**`pip install` for Agent Capabilities**" |
