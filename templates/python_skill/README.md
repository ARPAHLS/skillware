# Skillware Starter Bundle Template

This directory (`templates/python_skill/`) is the canonical starter template for creating new skills in the Skillware registry under `skills/<category>/<skill_name>/`. Copy this folder to your target path and replace all placeholders before opening a Pull Request.

Skills in Skillware are modular, deterministic agent capabilities loaded across runtimes and LLM providers. Each skill adheres to a strict architectural anatomy separating contract, implementation, prompt directives, assurance tests, and UI presentation.

---

## Skill Anatomy

Every skill bundle implements five core roles. For deep-dive architectural context, see [Skill Anatomy](../../docs/introduction.md#skill-anatomy) and the [Glossary](../../docs/glossary.md).

| Role | File / Asset | Purpose | Required |
| :--- | :--- | :--- | :---: |
| **Contract** | `manifest.yaml` | Declares the public tool interface, JSON Schema parameters, output contract, safety constitution, runtime requirements, and issuer attribution. | **Yes** |
| **Effect** | `skill.py` | Implements deterministic Python logic. Must define exactly one concrete `BaseSkill` subclass. | **Yes** |
| **Directive** | `instructions.md` | Provides append-only prompt instructions for the host LLM regarding when and how to invoke the tool. | **Yes** |
| **Assurance** | `test_skill.py` | Co-located offline unit tests validating parameter schema compliance, execution outputs, and error handling. | **Yes** |
| **Presentation** | `card.json` | Defines visual card UI schema (badges, metrics, labels) and author attribution. | Recommended |
| **Corpus** | `data/`, `kb/` | *(Optional)* Versioned local data, lookup tables, or offline knowledge bases read by the Effect. | Optional |
| **Reference** | `schemas/`, fixtures | *(Optional)* Specs, JSON schemas, or spec fixtures used by the Effect or tests. | Optional |

> **Note on Helpers**: Additional Python modules co-located in the skill folder (e.g. `utils.py`, `helpers.py`, `workflow.py`) are considered **Effect modules**. They must be imported only by `skill.py`.

---

## Step-by-Step Creation Guide

### 1. Choose Category and Skill ID
* Skill IDs must follow the `category/skill_name` convention in **snake_case** (e.g. `office/pdf_form_filler`, `security/prompt_injection_firewall`, `defi/evm_reader`).
* Check existing categories in [Skill Library](../../docs/skills/README.md) or the root [README.md](../../README.md).

### 2. Copy the Template Folder
Copy `templates/python_skill/` to your target directory:
```bash
cp -r templates/python_skill skills/<category>/<skill_name>
```

### 3. Packaging & Dependencies
1. **Packaging Inits**: Ensure an empty `__init__.py` exists in `skills/<category>/` (if creating a new category) and inside `skills/<category>/<skill_name>/`.
2. **Requirements**: If your skill requires third-party packages, declare them under `requirements:` in `manifest.yaml` using PEP 508 strings. Pin with `>=` when depending on a minimum version:
   ```yaml
   requirements:
     - "pydantic>=2.0.0"
   ```
3. **Sync Extras**: Run the sync script from the repository root to regenerate optional extras in `pyproject.toml`:
   ```bash
   python scripts/sync_extras.py
   ```
4. **Documentation**: If new dependencies were added, update the tables in [Install Extras](../../docs/usage/install_extras.md). CI verifies this with `tests/test_extras_sync.py`.

### 4. Author the Contract (`manifest.yaml`)
* **`name`**: Full registry ID matching the directory path (`category/skill_name`). CI enforces that folder path and `name` match via `tests/test_registry_identity.py`.
* **`version`**: Semantic version string (start at `0.1.0` for new skills).
* **`issuer`**: Real author attribution (`name` and `email` are required; `github` and `org` are optional). Replace placeholders (`Your Name`, `you@example.com`) before submitting. See [CONTRIBUTING.md#issuer-attribution](../../CONTRIBUTING.md#issuer-attribution).
* **`short_description`**: One-line summary (~80 chars) displayed in `skillware list`.
* **`parameters`**: Valid JSON Schema defining tool arguments for LLM tool calling.
* **`outputs`**: Map of named output fields returned by `execute()` (never use legacy singular `output:`).
* **`constitution`**: Safety principles and boundaries enforced at the prompt level.
* **`env_vars`**: Declare any environment variables or API keys needed.
* **`presentation`**: Icon and color tokens matching `card.json`.

### 5. Implement the Effect (`skill.py`)
* Define **exactly one** subclass of `BaseSkill`. `SkillLoader` discovers this class as `bundle["class"]`.
* Call `super().__init__(config=config)` in `__init__`.
* Read secrets with `self.credential("KEY_NAME")` (checks host-injected `config` first, then falls back to `os.environ`). See [API Keys for Skills](../../docs/usage/api_keys.md).
* Validate arguments against manifest JSON schema using `self.validate_params(payload)`.
* Keep execution **purely deterministic**. Never embed open-ended LLM generation inside `skill.py`.
* Do **not** print to `stdout` or `stderr` in production paths.
* Catch internal errors gracefully and return structured JSON reports (e.g. `{"status": "error", "error": "..."}`) rather than crashing the host agent.

### 6. Author the Directive (`instructions.md`)
* Provide concise, append-only instructions for the host LLM.
* Detail when to invoke the tool and when NOT to invoke it (anti-patterns).
* Explain how to interpret output fields and errors.
* **Avoid persona starters**: Never start with "You are an expert..." or narrative agent personas. Instructions should focus purely on the skill context.

### 7. Configure Presentation (`card.json`) & Add CI Fixture
* Ensure `card.json` fields mirror `manifest.yaml` (`name`, `description`, `issuer`, `icon`, `color`).
* In `ui_schema.fields`, every `key` must correspond to a field or dot-path in the JSON returned by `execute()`.
* **Mandatory CI Fixture**: Whenever `ui_schema.type == "card"` is present, you **must** add a sample output fixture file at:
  ```text
  tests/fixtures/card_ui_schema/<category>__<skill_name>.json
  ```
  Example fixture content (matching the keys declared in `ui_schema.fields`):
  ```json
  {
    "status": "success",
    "result": "Sample execution output"
  }
  ```
  This is validated automatically in CI by `tests/test_card_ui_schema.py`.

### 8. Write Assurance Tests (`test_skill.py`)
* Co-locate unit tests in `skills/<category>/<skill_name>/test_skill.py`.
* Tests **must run offline**. Mock all external HTTP requests, APIs, database calls, and first-run model downloads.
* Test normal execution, output dictionary schema compliance, parameter validation failures, and dynamic loading via `SkillLoader.load_skill()`.

### 9. Create Catalog Documentation
Create `docs/skills/<category>/<skill_name>.md` following [Skill Usage Template](../../docs/usage/skill_usage_template.md):
1. **Header Metadata**: ID, Issuer, Version, and Recommended Install (`pip install "skillware[<category>_<skill>]"`).
2. **Intent Block**:
   ```markdown
   <!-- skill-intent:begin -->
   - **Solves**: [Problem summary]
   - **Works with**: [Host agents, LLM providers]
   - **Runtime**: [Local/Python requirements, API keys]
   <!-- skill-intent:end -->
   ```
3. **Usage Examples**: Provide runnable code snippets for 5 providers: **Gemini**, **Claude**, **OpenAI**, **DeepSeek**, and **Ollama**.
4. **Skill History**: Add a table of notable commits with commit SHAs and linked GitHub contributors (`[@username](https://github.com/username)`).

### 10. Register in Hubs and Sitemap
* Add a row in `docs/skills/<category>/README.md`.
* Add a row in `docs/skills/README.md`.
* Add the catalog page link in `docs/sitemap.md`.
* If introducing a new category, add a row to the root `README.md` category table.

---

## Do's and Don'ts

| Do | Don't |
| :--- | :--- |
| **Do** use `snake_case` for skill directories and IDs (`utility/my_skill`). | **Don't** use hyphens (`utility/my-skill`) or uppercase letters. |
| **Do** inherit from `BaseSkill` and call `super().__init__(config=config)`. | **Don't** write a standalone class or omit calling `super().__init__`. |
| **Do** resolve credentials with `self.credential("KEY_NAME")`. | **Don't** read `os.environ` directly or hardcode secrets in code. |
| **Do** validate arguments using `self.validate_params(payload)`. | **Don't** assume input types without validating against the schema. |
| **Do** return structured JSON-serializable dictionaries (`dict`). | **Don't** print to `stdout`/`stderr` or return raw text / non-serializable objects. |
| **Do** catch internal exceptions and return structured errors. | **Don't** allow unhandled exceptions to crash the host agent loop. |
| **Do** provide an output fixture in `tests/fixtures/card_ui_schema/`. | **Don't** define a card `ui_schema` without adding the sample fixture. |
| **Do** mock all network and model downloads in `test_skill.py`. | **Don't** make real network requests in CI tests. |
| **Do** use real issuer attribution in your final PR. | **Don't** commit placeholder text (`Your Name`, `you@example.com`). |
| **Do** keep `instructions.md` concise and append-only. | **Don't** add persona starters ("You are an AI assistant..."). |
| **Do** put category hubs in `docs/skills/<category>/README.md`. | **Don't** create `skills/<category>/README.md` inside the registry code path. |

---

## Local Verification Commands

Run these checks locally before opening your pull request:

```bash
# 1. Run the skill bundle test
pytest skills/<category>/<skill_name>/test_skill.py
# Or using the Skillware CLI:
skillware test <category>/<skill_name>

# 2. Verify issuer attribution rules
pytest tests/test_skill_issuer.py

# 3. Verify registry identity (manifest.name matches path)
pytest tests/test_registry_identity.py

# 4. Verify card UI schema matches output fixture
pytest tests/test_card_ui_schema.py

# 5. Verify packaging extras and docs synchronization
python scripts/sync_extras.py
pytest tests/test_extras_sync.py

# 6. Verify documentation and provider snippet guards
pytest tests/test_registry_docs.py
pytest tests/test_skill_docs.py

# 7. Check environment health
skillware doctor
```

---

## Helpful References

* **Contributing Guidelines**: [CONTRIBUTING.md](../../CONTRIBUTING.md)
* **AI Agent Workflow**: [Agent Contribution Workflow](../../docs/contributing/ai_native_workflow.md)
* **Testing Guide**: [TESTING.md](../../docs/TESTING.md)
* **Catalog Page Standard & Usage Examples**: [Skill Usage Template](../../docs/usage/skill_usage_template.md)
* **Skill Library & Category Hubs**: [Skill Library](../../docs/skills/README.md) and [Sitemap](../../docs/sitemap.md)
* **Agent Loops & Host Integration**: [Agent Loops Guide](../../docs/usage/agent_loops.md)
* **Multi-Skill Orchestration**: [Skill Chaining Guide](../../docs/usage/skill_chaining.md)
* **Runnable Example Scripts**: [Examples Directory](../../examples/README.md)
* **Packaging & Optional Extras**: [Install Extras Guide](../../docs/usage/install_extras.md)
* **API Keys & Secrets Architecture**: [API Keys for Skills](../../docs/usage/api_keys.md)
* **Skill Trust Model**: [Skill Trust Model](../../docs/security/skill-trust-model.md)
