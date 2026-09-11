# UK Companies House Handler Skill

**ID**: `finance/uk_companies_house_handler`
**Issuer**: [@Areen-09](https://github.com/Areen-09) ([@ARPAHLS](https://github.com/ARPAHLS))
<!-- skill-doc-meta:begin -->
**Version**: `1.2.1` — 11 Sep 2026
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
- **State Tracking (Context)**: Automatically carries forward session state (like `company_number`, `company_name`, `last_action`, and `selected_transaction_id`) between sequential tool calls to seamlessly link multi-step operations.

## Bundle layout

The skill is self-contained in `skills/finance/uk_companies_house_handler/`. [Skill anatomy](../introduction.md#skill-anatomy). **Contract** — see Manifest Details above. **Assurance** — `test_skill.py` in the bundle.

### Directive (`instructions.md`)
Skill-context instructions (registry ID opener, not a persona). The host agent:
- Passes **clean** `query` / `company_number` parameters and optional `role_hint` — the skill does not strip conversational prefixes.
- Handles disambiguation when search returns `needs_input`, then resumes with `context` / `run_pipeline`.
- Uses `terminology_map.yaml` as a reference lexicon; maps US/informal terms via reasoning plus `map_intent` hints.
- Renders full `officers[]` / `filings[]` lists, including truncated results (default limit 10) with active count hints.
- **Always replies in plain language** — never ends with an empty or one-word answer; explains empty registry results and asks focused follow-ups when data is missing.

### Effect (`skill.py`)
A single `execute()` entry point dispatches to nine action handlers:
- **Core actions**: `resolve_company`, `get_company_profile`, `get_officers`, `get_pscs`, `get_filing_history`.
- **Pipeline orchestration & composites**: `run_pipeline`, `map_intent`, `resolve_and_get_officers`, `resolve_and_get_filings`.
- **HTTP layer**: Authenticated requests using API key as HTTP Basic username.
- **Status envelope**: Every response includes `status` (ready/partial/needs_input/error), `fetched_at` (UTC ISO), and `source`. The `partial` status is used exclusively during multi-step `run_pipeline` execution when steps remain.
- **Record limits and truncation**: Returns up to 10 active officers or recent filings by default (configurable via `limit`), with `total_results` and `active_count` metadata indicating truncation when more records exist, while maintaining `status: "ready"`.
- **State propagation**: Extracts and updates session `context` (such as `company_number`, `company_name`, `last_action`, and `selected_transaction_id`) in every response, automatically falling back to these values if omitted in subsequent turns.
- **Error handling**: Catches HTTP errors (404, 429, 500), timeouts, and connection failures.
- **Empty-result hints**: When `officers[]` or `filings[]` is empty on a successful call, includes an `agent_hint` so the host explains the gap and asks a focused follow-up.

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

Agent loops also need a provider API key — for example `GOOGLE_API_KEY` ([Gemini](../usage/gemini.md)) or `ANTHROPIC_API_KEY` ([Claude](../usage/claude.md)).

### Rate limits and API reference

Companies House enforces **600 requests per 5 minutes per API key**. See the official [rate limiting](https://developer.company-information.service.gov.uk/documentation/rate-limiting) and [Getting started](https://developer.company-information.service.gov.uk/) guides. When throttled, the skill returns `status: "error"` with `error_code: "rate_limited"`.

**Host guidance (from live agent-loop testing):**

- Pass **clean** `query` / `company_number` values — not full conversational sentences inside skill params.
- Short names (`BP`, `Tesco`, `Barclays`) often return `needs_input`; resume with a `company_number` or explicit candidate choice and carry `context` forward.
- Officer lists default to 10 active records; standalone actions return `ready` with `total_results` / `active_count` when truncated — render all returned rows. `partial` is reserved for in-flight `run_pipeline` only.
- For stress testing NLP hosts, see `scripts/uk_companies_house_host_simulation.py` (`--provider host|gemini|claude|all`). Gemini free tier may need `--gemini-delay 15` between scenarios.

## Direct execute — pipeline and composites (v2b)

Use these patterns when calling `skill.execute()` directly (no LLM) or when building deterministic hosts. Mocked flows: [`examples/uk_companies_house_handler_demo.py`](../../examples/uk_companies_house_handler_demo.py). Interactive agent loops: [`examples/gemini_uk_companies_house_handler.py`](../../examples/gemini_uk_companies_house_handler.py), [`examples/claude_uk_companies_house_handler.py`](../../examples/claude_uk_companies_house_handler.py).

**Composite (single intent):**

```python
result = skill.execute(
    {
        "action": "resolve_and_get_officers",
        "query": "Barclays",
        "role_hint": "ceo",
    }
)
```

**Multi-step pipeline:**

```python
intent = skill.execute(
    {
        "action": "map_intent",
        "intent_keywords": "officers, filings",
        "entities": {"company_query": "BP"},
    }
)
result = skill.execute(
    {
        "action": "run_pipeline",
        "steps": intent["steps"],
        "context": intent.get("context", {}),
    }
)
while result.get("status") == "partial":
    result = skill.execute(
        {
            "action": "run_pipeline",
            "steps": result["steps"],
            "pipeline": result["pipeline"],
            "context": result["context"],
        }
    )
```

**Resume after disambiguation:**

```python
result = skill.execute(
    {
        "action": "get_officers",
        "company_number": "01026167",
        "role_hint": "ceo",
        "context": prior_result["context"],
    }
)
```

Status envelopes (`ready`, `partial`, `needs_input`, `error`) and host reply expectations are defined in `instructions.md` (Directive). In agent loops, pass **`bundle["instructions"]`** as system context so the model passes clean `query` values, handles `needs_input`, and always produces a user-facing answer — including when registry rows are empty.

## Usage Examples

Guides: [Usage index](../usage/README.md) · [Agent loops](../usage/agent_loops.md) · [API keys](../usage/api_keys.md).


Use `bundle["class"]()` in the snippets below; explicit `bundle["module"].ClassName()` also works.

Sample user message: *Who is the CEO of BP?*

### Gemini

Runnable interactive loop: [`examples/gemini_uk_companies_house_handler.py`](../../examples/gemini_uk_companies_house_handler.py).

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
model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
response = client.models.generate_content(
    model=model,
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
            model=model,
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

Runnable interactive loop: [`examples/claude_uk_companies_house_handler.py`](../../examples/claude_uk_companies_house_handler.py).

```python
import json
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
tool_name = tools[0]["name"]
model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
messages = [{"role": "user", "content": "Who is the CEO of BP?"}]

response = client.messages.create(
    model=model,
    max_tokens=2048,
    system=bundle["instructions"],
    tools=tools,
    messages=messages,
)
while response.stop_reason == "tool_use":
    tool_use = next(b for b in response.content if b.type == "tool_use")
    result = skill.execute(dict(tool_use.input)) if tool_use.name == tool_name else {"error": "unknown tool"}
    messages.extend(
        [
            {"role": "assistant", "content": response.content},
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": json.dumps(result),
                    }
                ],
            },
        ]
    )
    if result.get("status") == "needs_input":
        messages.append(
            {
                "role": "user",
                "content": "Use BP P.L.C. (company number 00102498) and list current directors.",
            }
        )
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system=bundle["instructions"],
        tools=tools,
        messages=messages,
    )
print("".join(b.text for b in response.content if getattr(b, "text", None)))
```

### OpenAI

```python
import json
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("finance/uk_companies_house_handler")
skill = bundle["class"](
    config={"COMPANIES_HOUSE_API_KEY": os.environ.get("COMPANIES_HOUSE_API_KEY")}
)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
tool = SkillLoader.to_openai_tool(bundle)
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": bundle["instructions"]},
        {"role": "user", "content": "Who is the CEO of BP?"},
    ],
    tools=[tool],
)
message = response.choices[0].message
if message.tool_calls:
    args = json.loads(message.tool_calls[0].function.arguments)
    result = skill.execute(args)
    print(result["status"])
```
### DeepSeek

```python
import json
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("finance/uk_companies_house_handler")
skill = bundle["class"](
    config={"COMPANIES_HOUSE_API_KEY": os.environ.get("COMPANIES_HOUSE_API_KEY")}
)
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
tool = SkillLoader.to_deepseek_tool(bundle)
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": bundle["instructions"]},
        {"role": "user", "content": "Who is the CEO of BP?"},
    ],
    tools=[tool],
)
message = response.choices[0].message
if message.tool_calls:
    args = json.loads(message.tool_calls[0].function.arguments)
    result = skill.execute(args)
    print(result["status"])
```
### Ollama (prompt mode)

```python
import json
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("finance/uk_companies_house_handler")
skill = bundle["class"](
    config={"COMPANIES_HOUSE_API_KEY": os.environ.get("COMPANIES_HOUSE_API_KEY")}
)
prompt = (
    "You may call tools as JSON blocks.\n"
    f"Tool: {bundle['manifest']['name']}\n"
    f"Instructions:\n{bundle['instructions']}\n"
    f"User: Who is the CEO of BP?"
)
print(prompt)
result = skill.execute({
    "action": "resolve_company",
    "company_name": "BP",
})
print(json.dumps(result, indent=2))
```
## Data Schema

### Input — resolve company (ambiguous name)

```json
{
  "action": "resolve_company",
  "query": "Tesco",
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
      "company_number": "00445790",
      "title": "TESCO PLC",
      "company_status": "active",
      "company_type": "plc",
      "address_snippet": "Tesco House, Shire Park, Kestrel Way, Welwyn Garden City, United Kingdom, AL7 1GA",
      "date_of_creation": "1947-11-27",
      "snippet": "TESCO STORES (HOLDINGS) PUBLIC LIMITED COMPANY"
    },
    {
      "company_number": "09384423",
      "title": "KFORD TYRES (GORNAL) LTD",
      "company_status": "active",
      "company_type": "ltd",
      "address_snippet": "2 Dawley Brook Road, Kingswinford, England, DY6 7BD",
      "date_of_creation": "2015-01-12",
      "snippet": "TESCO TYRES LTD"
    }
  ],
  "context": {
    "company_number": null,
    "company_name": "Tesco",
    "selected_transaction_id": null,
    "last_action": "resolve_company"
  },
  "agent_hint": "Ask the user which company they mean before calling further actions.",
  "fetched_at": "2026-09-10T18:33:09+00:00"
}
```

### Input — get officers (after resolution)

```json
{
  "action": "get_officers",
  "company_number": "00445790",
  "active_only": true,
  "context": {
    "company_number": "00445790",
    "company_name": "TESCO PLC",
    "selected_transaction_id": null,
    "last_action": "resolve_company"
  }
}
```

### Output — ready

```json
{
  "status": "ready",
  "company_number": "00445790",
  "company_name": "TESCO PLC",
  "context": {
    "company_number": "00445790",
    "company_name": "TESCO PLC",
    "selected_transaction_id": null,
    "last_action": "get_officers"
  },
  "total_results": 74,
  "active_count": 11,
  "officers": [
    {
      "name": "MURPHY, Ken",
      "officer_role": "director",
      "appointed_on": "2020-10-01",
      "resigned_on": null,
      "nationality": "Irish",
      "occupation": "",
      "country_of_residence": "United Kingdom"
    }
  ],
  "terminology_note": "UK companies use directors, not CEOs; this list includes statutory directors and secretaries.",
  "source": "companies_house_api",
  "fetched_at": "2026-09-10T18:33:16+00:00"
}
```

### Input — map intent

```json
{
  "action": "map_intent",
  "intent_keywords": "ceo, 10k, officers, filings, accounts",
  "entities": {"company_query": "Tesco"}
}
```

### Output — planned steps

```json
{
  "status": "ready",
  "source": "companies_house_api",
  "fetched_at": "2026-09-10T18:33:07+00:00",
  "steps": [
    {
      "action": "resolve_company",
      "params": {
        "query": "Tesco"
      }
    },
    {
      "action": "get_officers",
      "params": {
        "company_number": "<from_resolve>"
      }
    },
    {
      "action": "get_filing_history",
      "params": {
        "company_number": "<from_resolve>"
      }
    }
  ],
  "pipeline": {
    "completed_steps": 0,
    "total_steps": 3
  },
  "terminology_map": {
    "ceo": "director",
    "10k": "accounts"
  },
  "relevant_endpoints": [
    "/company/{company_number}/officers",
    "/company/{company_number}/filing-history"
  ],
  "context": {
    "company_number": null,
    "company_name": null,
    "selected_transaction_id": null,
    "last_action": "map_intent"
  }
}
```

### Input — run pipeline (turn-by-turn orchestration)

```json
{
  "action": "run_pipeline",
  "steps": [
    {
      "action": "resolve_company",
      "params": {"query": "Tesco"}
    },
    {
      "action": "get_officers",
      "params": {"company_number": "<from_resolve>"}
    },
    {
      "action": "get_filing_history",
      "params": {"company_number": "<from_resolve>"}
    }
  ],
  "pipeline": {
    "completed_steps": 0,
    "total_steps": 3
  },
  "stop_on": ["needs_input", "error"]
}
```

### Output — pipeline paused on disambiguation (Turn 1)

```json
{
  "status": "needs_input",
  "reason": "multiple_matches",
  "candidates": [
    {
      "company_number": "00445790",
      "title": "TESCO PLC",
      "company_status": "active",
      "company_type": "plc",
      "address_snippet": "Tesco House, Shire Park, Kestrel Way, Welwyn Garden City, United Kingdom, AL7 1GA",
      "date_of_creation": "1947-11-27",
      "snippet": "TESCO STORES (HOLDINGS) PUBLIC LIMITED COMPANY"
    },
    {
      "company_number": "09384423",
      "title": "KFORD TYRES (GORNAL) LTD",
      "company_status": "active",
      "company_type": "ltd",
      "address_snippet": "2 Dawley Brook Road, Kingswinford, England, DY6 7BD",
      "date_of_creation": "2015-01-12",
      "snippet": "TESCO TYRES LTD"
    }
  ],
  "fetched_at": "2026-09-10T18:33:09+00:00",
  "agent_hint": "Ask the user which company they mean before calling further actions. Once the user specifies the company, resume run_pipeline with the selected company_number, remaining steps, context, and pipeline.",
  "context": {
    "company_number": null,
    "company_name": "Tesco",
    "selected_transaction_id": null,
    "last_action": "run_pipeline"
  },
  "steps": [
    {
      "action": "get_officers",
      "params": {
        "company_number": "<from_resolve>"
      }
    },
    {
      "action": "get_filing_history",
      "params": {
        "company_number": "<from_resolve>"
      }
    }
  ],
  "pipeline": {
    "completed_steps": 1,
    "total_steps": 3
  }
}
```

### Input — resolve and get officers (composite)

```json
{
  "action": "resolve_and_get_officers",
  "query": "Tesco",
  "role_hint": "ceo",
  "active_only": true
}
```

### Output — composite ready

```json
{
  "status": "ready",
  "company_number": "00445790",
  "company_name": "TESCO PLC",
  "total_results": 74,
  "active_count": 11,
  "officers": [
    {
      "name": "MURPHY, Ken",
      "officer_role": "director",
      "appointed_on": "2020-10-01",
      "resigned_on": null,
      "nationality": "Irish",
      "occupation": "",
      "country_of_residence": "United Kingdom"
    }
  ],
  "terminology_note": "UK companies use directors, not CEOs; this list includes statutory directors and secretaries.",
  "context": {
    "company_number": "00445790",
    "company_name": "TESCO PLC",
    "selected_transaction_id": null,
    "last_action": "resolve_and_get_officers"
  },
  "source": "companies_house_api",
  "fetched_at": "2026-09-10T18:33:16+00:00"
}
```

## Limitations

- **Scope**: Search, profile, officers, PSC, filing history, multi-step pipeline orchestration, and composite resolution. Charges, insolvency registers, and document downloads are planned for later v2 phases.
- **Read-only**: This skill cannot submit filings or modify Companies House records.
- **Rate limits**: Companies House API allows [600 requests per 5 minutes per key](https://developer.company-information.service.gov.uk/documentation/rate-limiting). The skill returns a structured `rate_limited` error when throttled. Batch or pipeline hosts should backoff and retry.
- **Public data only**: Only publicly available information is returned.
- **Not legal advice**: Company information is provided as-is. This is not legal, accounting, or regulatory advice.

---

<!-- skill-history:begin -->
## Skill history

Commits that touched this skill bundle or its catalog page ([`finance/uk_companies_house_handler`](https://github.com/ARPAHLS/skillware/tree/main/skills/finance/uk_companies_house_handler)).

| Commit | Description | Date | Version | Contributors |
| :--- | :--- | :--- | :--- | :--- |
| *(pending merge)* | fix(uk_companies_house_handler): stabilize multi-turn pipelines and lean context (#341) | 10 Sep 2026 | `1.2.1` | [@Areen-09](https://github.com/Areen-09) |
| [`12fbd1a`](https://github.com/ARPAHLS/skillware/commit/12fbd1a11bdf66250008afc59df7048935eafc73) | docs: adopt Skill anatomy vocabulary on catalog page (#319) | 1 Sep 2026 | `1.2.0` | [@rosspeili](https://github.com/rosspeili) |
| [`01cd620`](https://github.com/ARPAHLS/skillware/commit/01cd620) | feat(uk_companies_house_handler): upgrade to v2b with pipeline orchestration and composites (#220) (#308) | 24 Aug 2026 | `1.2.0` | [@Areen-09](https://github.com/Areen-09), [@rosspeili](https://github.com/rosspeili) |
| [`84cd790`](https://github.com/ARPAHLS/skillware/commit/84cd790) | feat: complete uk companies house handler v2a (#220) (#255) | 22 Jul 2026 | `1.1.0` | [@Areen-09](https://github.com/Areen-09) |
| [`bca8181`](https://github.com/ARPAHLS/skillware/commit/bca8181) | Add category and per-skill pip extras with manifest sync (#236). (#256) | 16 Jul 2026 | `1.0.0` | [@rosspeili](https://github.com/rosspeili) |
| [`4814478`](https://github.com/ARPAHLS/skillware/commit/4814478) | Fix: to_gemini_tool to return types.Tool object. Fixes #223 (#229) | 10 Jul 2026 | `1.0.0` | [@Areen-09](https://github.com/Areen-09) |
| [`0d550d0`](https://github.com/ARPAHLS/skillware/commit/0d550d0) | docs: sweep vision, bundle class usage, and README Mermaid | 8 Jul 2026 | `1.0.0` | [@rosspeili](https://github.com/rosspeili) |
| [`8251e89`](https://github.com/ARPAHLS/skillware/commit/8251e89) | feat: add UK Companies House handler skill (#172) (#218) | 8 Jul 2026 | `1.0.0` | [@Areen-09](https://github.com/Areen-09) |
<!-- skill-history:end -->

## Enterprise disclaimer

This skill is provided for demonstration and integration purposes. It is intended as a starting point that you can adapt to your own data, schemas, and operational requirements. For an enterprise-grade version of this skill with dedicated support, SLAs, and customization, contact skills@arpacorp.net.
