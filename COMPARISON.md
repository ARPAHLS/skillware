# Comparison: Skillware vs. Others

Skillware occupies a unique position in the AI ecosystem. It is often compared to **Antigravity Skills** (Agentic Coding) or **Anthropic's Skills** (Claude Reference). 

This document clarifies the differences, specifically focusing on **Model Agnosticism**, **Architecture**, and **Token Economy**.

---

## 1. Skillware vs. Anthropic Skills (Reference Implementations)

[Anthropic's Skills](https://github.com/anthropics/skills) repository is a collection of reference prompts and scripts optimized for Claude.

### Key Differences
*   **Model Agnosticism**: Anthropic skills are hyper-tuned for Claude. Skillware is **Universal**. We provide the abstraction layer (Loader) that adapts a single skill to work with OpenAI, Gemini, Claude, and Llama functions transparently.
*   **The "Managed" Runtime**: Anthropic skills are often standalone scripts. Skillware provides a `SkillLoader` that handles lifecycle, dependency checking (`requirements`), and error handling automatically.

---

## 2. Skillware vs. Antigravity ("Agentic" Skills)

Users familiar with **Antigravity** (Google DeepMind's Agentic Coding assistant) use `SKILL.md` files to teach their coding agent how to work in a specific repository.

### Key Differences
*   **Audience**: 
    *   **Antigravity Skills** are for the **Developer Agent** (the one writing code in your IDE). They are "Procedural Memory" (e.g., "How to run the build script").
    *   **Skillware Skills** are for the **Runtime Agent** (the application you are building). They are "Functional Capabilities" (e.g., "Check a crypto wallet").
*   **Analogy**:
    *   **Antigravity** is a **Recipe Book** (Instructions on how to cook).
    *   **Skillware** is a **New Knife** (A tool to actually do the work).

---

## 3. The Token Economy Advantage (Efficiency)

A critical architectural decision in Skillware is the use of **Native, Hardcoded Functions** over "Code-Generation" skills.

*   **The "Code Gen" Approach (Others)**: Some frameworks ask the LLM to write Python code on the fly to solve a problem (e.g., "Write a script to check this wallet").
    *   **Expensive**: You pay output tokens for the code generation *every single time*.
    *   **Slow**: Generating code takes time.
    *   **Risky**: The generated code might have syntax errors or security flaws.

*   **The Skillware Approach**: We provide **Pre-Compiled functions**.
    *   **Cheap**: You only pay for the *logical* tokens ("Call function `check_wallet` with arg `0x123`"). The heavy lifting happens in pure Python (0 cost).
    *   **Fast**: Instant execution.
    *   **Safe**: The code is reviewable and static.

---

## Summary Comparison

| Feature | Antigravity Skills | Anthropic Skills | ARPA Skillware |
| :--- | :--- | :--- | :--- |
| **Primary User** | The **Developer Agent** (IDE) | The **Claude Developer** | The **Runtime Agent** (End User) |
| **Format** | `SKILL.md` (Text/Markdown) | JS/Python Reference Code | `manifest.yaml` + Python Module |
| **Goal** | **Teach Procedure** ("How-to") | Show capabilities of Claude | **Install Capabilities** ("Can-do") |
| **Execution** | Agent reads docs, drives IDE | Script-based / Manual | **Managed Runtime** (`SkillLoader`) |
| **Token Cost** | **Standard** (RAG/Context) | **High** (Prompt engineering) | **Optimized** (Native Function calling) |
| **Analogy** | **The Recipe** | **The Experiment** | **The Knife** |

**Conclusion**: Use **Antigravity** to help you *build* your project. Use **Skillware** to give your project *superpowers* when it runs.
