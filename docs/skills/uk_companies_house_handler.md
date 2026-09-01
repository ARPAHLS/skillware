# UK Companies House Handler Skill

**ID**: `finance/uk_companies_house_handler`
**Issuer**: [@Areen-09](https://github.com/Areen-09) ([@ARPAHLS](https://github.com/ARPAHLS))
<!-- skill-doc-meta:begin -->
**Version**: `1.2.0` — 24 Aug 2026
<!-- skill-doc-meta:end -->

**Recommended install:** `pip install "skillware[finance_uk_companies_house_handler]"`. See [Install extras](../usage/install_extras.md).
[Skill Library](README.md) · [Testing](../TESTING.md)

A deterministic UK Companies House API handler for agents. Provides structured operations for company search, profile lookup, officer and PSC listing, filing history, multi-step pipeline orchestration, and intent-to-operation mapping with UK corporate terminology translation. Returns status-based responses (`ready`, `partial`, `needs_input`, `error`) with disambiguation support.

## Capabilities

- **Company Search and Disambiguation**: Search by name, receive ranked candidates, handle ambiguous queries (e.g. "BP") with structured `needs_input` responses.
- **Company Profile**: Full profile by company number — status, type, SIC codes, registered address, charges, insolvency flags.
- **Officers (Directors and Secretaries)**: List current and past officers with optional `active_only` filtering (**default `true`**). Includes UK terminology notes when `role_hint` indicates executive roles (CEO → director).
- **Persons with Significant Control (PSC)**: List beneficial owners with natures of control, equivalent to the US concept of "beneficial owner" or "shareholder".
- **Filing History**: List filings (accounts, confirmation statements, incorporations) with optional category filtering and document metadata links.
- **Pipeline Orchestration (`run_pipeline`)**: Execute ordered steps sequentially, halting on disambiguation (`needs_input`) or `error`, and preserving execution progress in `pipeline`.
- **Composite Actions**: One-step resolution and extraction for common workflows (`resolve_and_get_officers`, `resolve_and_get_filings`).
- **Intent Mapping**: Translate common user intent keywords (CEO, owner, shareholder) to the correct UK Companies House actions and build suggested action pipelines.
- **State Tracking (Context)**: Automatically carries forward session state (like `company_number`, `company_name`, and active filters) between sequential tool calls to seamlessly link multi-step operations.

## Bundle layout

The skill is self-contained in `skills/finance/uk_companies_house_handler/`. [Skill anatomy](../introduction.md#skill-anatomy). **Contract** — see Manifest Details above. **Assurance** — `test_skill.py` in the bundle.

### Directive (`instructions.md`)
Skill-context instructions (registry ID opener, not a persona). The host agent:
- Passes **clean** `query` / `company_number` parameters and optional `role_hint` — the skill does not strip conversational prefixes.
- Handles disambiguation when search returns `needs_input`, then resumes with `context` / `run_pipeline`.
- Uses `terminology_map.yaml` as a reference lexicon; maps US/informal terms via reasoning plus `map_intent` hints.
- Renders full `officers[]` / `filings[]` lists, including `partial` previews (default limit 10).

### Effect (`skill.py`)
A single `execute()` entry point dispatches to nine action handlers:
- **Core actions**: `resolve_company`, `get_company_profile`, `get_officers`, `get_pscs`, `get_filing_history`.
- **Pipeline orchestration & composites**: `run_pipeline`, `map_intent`, `resolve_and_get_officers`, `resolve_and_get_filings`.
- **HTTP layer**: Authenticated requests using API key as HTTP Basic username.
- **Status envelope**: Every response includes `status` (ready/partial/needs_input/error), `fetched_at` (UTC ISO), and `source`.
- **Partial response previews**: Automatically previews the first 10 active officers or 10 recent filings with `partial` status and count hints when records exceed default limits.
- **State propagation**: Extracts and updates session `context` (such as `company_number`, `company_name`, `role_hint`, and `next_actions`) in every response, automatically falling back to these values if omitted in subsequent turns.
- **Error handling**: Catches HTTP errors (404, 429, 500), timeouts, and connection failures.

### 3. The Knowledge (`data/`)
Compact, bundled reference data (not a full OpenAPI dump):
- `api_index.json`: Endpoint index with methods, paths, parameter shapes, and rate limit info.
- `terminology_map.yaml`: UK corporate terminology mappings, role translations, and intent-to-action routing.

## Integration Guide

### Environment

| Variable | Required | Purpose |
| :--- | :--- | :--- |
| `COMPANIES_HOUSE_API_KEY` | Yes | API key from the [Companies House Developer Hub](https://developer.company-information.service.gov.uk/). Used as HTTP Basic username with empty password. |

Configure values per [API keys for skills](../usage/api_keys.md). This skill reads the names declared in `skills/finance/uk_companies_house_handler/manifest.yaml`.

Agent loops also need a provider API key (for example `GOOGLE_API_KEY` with Gemini); see [Gemini usage](../usage/gemini.md).

## Usage Examples

Guides: [Usage index](../usage/README.md) · [Agent loops](../usage/agent_loops.md) · [API keys](../usage/api_keys.md).


Use `bundle["class"]()` in the snippets below; explicit `bundle["module"].ClassName()` also works.

Sample user message: *Who is the CEO of BP?*

### Gemini

```python
import os
import google.genai as genai
from google.genai import types
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("finance/uk_companies_house_handler")
skill = bundle["class"](
    config={"COMPANIES_HOUSE_API_KEY": os.environ.get("COMPANIES_HOUSE_API_KEY")}
)
client = genai.Client()
tool = SkillLoader.to_gemini_tool(bundle)
tool_name = SkillLoader._sanitize_gemini_tool_name(bundle["manifest"]["name"])
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Who is the CEO of BP?",
    config=types.GenerateContentConfig(
        tools=[tool],
        system_instruction=bundle["instructions"],
    ),
)
for part in response.candidates[0].content.parts:
    if part.function_call and part.function_call.name == tool_name:
        result = skill.execute(dict(part.function_call.args))
        follow_up = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                "Use this tool result to answer the original request.",
                {
                    "function_response": {
                        "name": part.function_call.name,
                        "response": {"result": result},
                    }
                },
            ],
            config=types.GenerateContentConfig(
                tools=[tool],
                system_instruction=bundle["instructions"],
            ),
        )
        print(follow_up.text)
```

### Claude

```python
import os
import anthropic
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("finance/uk_companies_house_handler")
skill = bundle["class"](
    config={"COMPANIES_HOUSE_API_KEY": os.environ.get("COMPANIES_HOUSE_API_KEY")}
)
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
tools = [SkillLoader.to_claude_tool(bundle)]
# On tool_use, match name against bundle["manifest"]["name"]
# (finance/uk_companies_house_handler):
# skill.execute(tool_use.input), return tool_result
```

### OpenAI

```python
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("finance/uk_companies_house_handler")
skill = bundle["class"](
    config={"COMPANIES_HOUSE_API_KEY": os.environ.get("COMPANIES_HOUSE_API_KEY")}
)
openai_tool = SkillLoader.to_openai_tool(bundle)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
# Match tool_call.function.name to openai_tool["function"]["name"]
# (finance_uk_companies_house_handler)
```

### DeepSeek

```python
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("finance/uk_companies_house_handler")
skill = bundle["class"](
    config={"COMPANIES_HOUSE_API_KEY": os.environ.get("COMPANIES_HOUSE_API_KEY")}
)
deepseek_tool = SkillLoader.to_deepseek_tool(bundle)
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
# chat.completions.create(model="deepseek-chat", tools=[deepseek_tool], ...)
# Match tool_call.function.name to deepseek_tool["function"]["name"]
# (finance_uk_companies_house_handler)
```

### Ollama

Prompt mode via `SkillLoader.to_ollama_prompt(bundle)`; match `"tool": "finance/uk_companies_house_handler"` in the JSON block. See [Ollama usage](../usage/ollama.md) and [agent loops](../usage/agent_loops.md).

## Data Schema

### Input — resolve company (ambiguous name)

```json
{
  "action": "resolve_company",
  "query": "BP",
  "limit": 5
}
```

### Output — needs disambiguation

```json
{
  "status": "needs_input",
  "reason": "multiple_matches",
  "candidates": [
    {
      "company_number": "00102498",
      "title": "BP P.L.C.",
      "company_status": "active"
    },
    {
      "company_number": "01234567",
      "title": "BP ALTERNATIVE EXAMPLE LTD",
      "company_status": "dissolved"
    }
  ],
  "context": {
    "company_number": null,
    "company_name": null,
    "last_action": "resolve_company",
    "officer_filter": null,
    "selected_transaction_id": null
  },
  "agent_hint": "Ask the user which company they mean before calling get_officers.",
  "next_actions": ["get_company_profile", "get_officers"],
  "fetched_at": "2026-07-05T00:00:00+00:00"
}
```

### Input — get officers (after resolution)

```json
{
  "action": "get_officers",
  "company_number": "00102498",
  "active_only": true,
  "context": {
    "company_number": "00102498",
    "company_name": "BP P.L.C.",
    "last_action": "resolve_company",
    "officer_filter": null,
    "selected_transaction_id": null
  }
}
```

### Output — ready

```json
{
  "status": "ready",
  "company_number": "00102498",
  "context": {
    "company_number": "00102498",
    "company_name": "BP P.L.C.",
    "last_action": "get_officers",
    "officer_filter": null,
    "selected_transaction_id": null
  },
  "officers": [
    {
      "name": "SMITH, John",
      "officer_role": "director",
      "appointed_on": "2020-03-01"
    }
  ],
  "terminology_note": "UK companies use directors, not CEOs; this list includes statutory directors and secretaries.",
  "source": "companies_house_api",
  "fetched_at": "2026-07-05T00:00:00+00:00"
}
```

### Input — map intent

```json
{
  "action": "map_intent",
  "intent_keywords": "ceo, bp, director",
  "entities": {"company_query": "BP"}
}
```

### Output — suggested pipeline

```json
{
  "status": "ready",
  "suggested_pipeline": [
    {"action": "resolve_company", "params": {"query": "BP"}},
    {"action": "get_officers", "params": {"company_number": "<from_resolve>"}}
  ],
  "terminology_map": {"ceo": "director"},
  "relevant_endpoints": ["/company/{company_number}/officers"]
}
```

### Input — run pipeline (multi-step, one call)

```json
{
  "action": "run_pipeline",
  "steps": [
    {
      "action": "resolve_company",
      "params": {"query": "BP"}
    },
    {
      "action": "get_officers",
      "params": {"active_only": true}
    }
  ],
  "stop_on": ["needs_input", "error"]
}
```

### Output — pipeline stopped at disambiguation

```json
{
  "status": "needs_input",
  "reason": "multiple_matches",
  "candidates": [
    {
      "company_number": "00102498",
      "title": "BP P.L.C.",
      "company_status": "active"
    }
  ],
  "context": {
    "company_number": null,
    "company_name": null,
    "last_action": "run_pipeline",
    "officer_filter": null,
    "selected_transaction_id": null
  },
  "agent_hint": "Ask the user which company they mean before calling further actions.",
  "next_actions": ["get_officers"],
  "pipeline": {
    "completed_steps": 1,
    "total_steps": 2
  },
  "fetched_at": "2026-07-08T12:00:00+00:00"
}
```

### Input — resolve and get officers (composite)

```json
{
  "action": "resolve_and_get_officers",
  "query": "BP PLC",
  "active_only": true
}
```

### Output — composite ready

```json
{
  "status": "ready",
  "company_number": "00102498",
  "company_name": "BP P.L.C.",
  "total_results": 1,
  "active_count": 1,
  "officers": [
    {
      "name": "SMITH, John",
      "officer_role": "director",
      "appointed_on": "2020-03-01"
    }
  ],
  "terminology_note": "UK companies use directors, not CEOs; this list includes statutory directors and secretaries.",
  "pipeline": {
    "completed_steps": 2,
    "total_steps": 2
  },
  "context": {
    "company_number": "00102498",
    "company_name": "BP P.L.C.",
    "last_action": "resolve_and_get_officers",
    "officer_filter": null,
    "selected_transaction_id": null
  },
  "source": "companies_house_api",
  "fetched_at": "2026-07-08T12:00:00+00:00"
}
```

## Limitations

- **Scope**: Search, profile, officers, PSC, filing history, multi-step pipeline orchestration, and composite resolution. Charges, insolvency registers, and document downloads are planned for later v2 phases.
- **Read-only**: This skill cannot submit filings or modify Companies House records.
- **Rate limits**: Companies House API allows 600 requests per 5 minutes per key. The skill returns a structured `rate_limited` error when throttled.
- **Public data only**: Only publicly available information is returned.
- **Not legal advice**: Company information is provided as-is. This is not legal, accounting, or regulatory advice.

---

<!-- skill-history:begin -->
## Skill history

Commits that touched this skill bundle or its catalog page ([`finance/uk_companies_house_handler`](https://github.com/ARPAHLS/skillware/tree/main/skills/finance/uk_companies_house_handler)).

| Commit | Description | Date | Version | Contributors |
| :--- | :--- | :--- | :--- | :--- |
| [`01cd620`](https://github.com/ARPAHLS/skillware/commit/01cd620) | feat(uk_companies_house_handler): upgrade to v2b with pipeline orchestration and composites (#220) (#308) | 24 Aug 2026 | `1.2.0` | [@Areen-09](https://github.com/Areen-09), [@rosspeili](https://github.com/rosspeili) |
| [`84cd790`](https://github.com/ARPAHLS/skillware/commit/84cd790) | feat: complete uk companies house handler v2a (#220) (#255) | 22 Jul 2026 | `1.1.0` | [@Areen-09](https://github.com/Areen-09) |
| [`bca8181`](https://github.com/ARPAHLS/skillware/commit/bca8181) | Add category and per-skill pip extras with manifest sync (#236). (#256) | 16 Jul 2026 | `1.0.0` | [@rosspeili](https://github.com/rosspeili) |
| [`4814478`](https://github.com/ARPAHLS/skillware/commit/4814478) | Fix: to_gemini_tool to return types.Tool object. Fixes #223 (#229) | 10 Jul 2026 | `1.0.0` | [@Areen-09](https://github.com/Areen-09) |
| [`0d550d0`](https://github.com/ARPAHLS/skillware/commit/0d550d0) | docs: sweep vision, bundle class usage, and README Mermaid | 8 Jul 2026 | `1.0.0` | [@rosspeili](https://github.com/rosspeili) |
| [`8251e89`](https://github.com/ARPAHLS/skillware/commit/8251e89) | feat: add UK Companies House handler skill (#172) (#218) | 8 Jul 2026 | `1.0.0` | [@Areen-09](https://github.com/Areen-09) |
<!-- skill-history:end -->

## Enterprise disclaimer

This skill is provided for demonstration and integration purposes. It is intended as a starting point that you can adapt to your own data, schemas, and operational requirements. For an enterprise-grade version of this skill with dedicated support, SLAs, and customization, contact skills@arpacorp.net.
