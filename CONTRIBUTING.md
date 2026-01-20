# Contributing to Skillware

Welcome to the Skillware project. We are building the definitive "App Store" for Agentic Capabilities.

This repository follows strict professional standards ("Corpo-Professional") to ensure every skill is safe, reliable, and model-agnostic.

---

## 🏗️ The Skill Package Standard

Every new skill must reside in its own directory under `skillware/skills/<category>/<skill_name>/`. It **must** contain the following files:

### 1. `manifest.yaml` (The Metadata)
Defines the interface and constitution.
*   **Must** have `name`, `version`, `description`.
*   **Must** have a valid JSON Schema in `parameters`.
*   **Must** include a `constitution` section defining safety boundaries.
*   **Must** include a `requirements` list if external packages are needed (e.g. `requests`, `pandas`).

```yaml
name: generic_hello
version: 1.0.0
description: A friendly greeting skill.
parameters:
  type: object
  properties:
    name:
      type: string
  required:
    - name
constitution: |
  1. Do not greet offensive names.
  2. Always maintain a polite tone.

requirements:
  - requests
  - pandas
```

### 2. `skill.py` (The Logic)
*   **Must** define a class inheriting from `BaseSkill` (planned) or follow the standard structure.
*   **Must** accept a dictionary of inputs and return a dictionary (JSON-serializable).
*   **Must** catch all internal errors and return a clean error report, not raise exceptions that crash the agent.
*   **Must NOT** print to stdout/stderr. Retrieve data only.

### 3. `instructions.md` (The Mind)
This is the most critical file. It is the "driver" for the LLM.
*   **Start** with "You are an agent equipped with [Skill Name]..."
*   **Explain** *when* to use the tool.
*   **Explain** how to interpret the output.
*   **Explain** edge cases given the tool's limitations.

### 4. `card.json` (The Presentation)
*   Defines how the skill state is rendered in a UI (optional but recommended for user-facing agents).

---

## 🚫 What to Avoid

*   **No "God Skills"**: Do not make one massive skill that does everything. Break it down.
*   **No Hardcoded Models**: Do not put prompts inside `skill.py`. Put them in `instructions.md`.
*   **No Vendor Lock-in**: Do not write code that only works with LangChain wrappers. Use standard Python.
*   **No Environment Leaks**: Never hardcode API keys. Use `os.environ` and document the required keys in `manifest.yaml`.

---

## 🔄 The Pull Request Process

1.  **Fork** the repository.
2.  **Create** your skill folder: `skillware/skills/<category>/<your_skill>/`.
3.  **Implement** the 4 required files.
4.  **Add** a test script in `examples/` demonstrating it works with at least one model (Gemini or Claude).
5.  **Submit** PR.

---

## 🛡️ Safety & Security

*   Skills that interact with real-world assets (wallets, email, etc.) must implement a "Dry Run" mode if possible.
*   Sanitize all inputs in `skill.py` before passing to external APIs.
*   **Malicious code in PRs will result in an immediate ban.**

---

*Thank you for helping us democratize Agent capabilities.*
