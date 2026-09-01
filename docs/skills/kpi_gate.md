# KPI Gate

**Domain:** `monitoring`
**Skill ID:** `monitoring/kpi_gate`
**Issuer:** [@mrmasa88](https://github.com/mrmasa88) ([AO](https://github.com/0x-AO-Protocol))
<!-- skill-doc-meta:begin -->
**Version**: `0.1.0` — 29 Aug 2026
<!-- skill-doc-meta:end -->
**Recommended install:** `pip install "skillware[monitoring_kpi_gate]"`. See [Install extras](../usage/install_extras.md).

[Skill Library](README.md) · [Testing](../TESTING.md)

Deterministic **business-KPI gate**: `{metrics, policy, benchmarks?}` → `findings[]`. A metrics snapshot (JSON) is evaluated against an operator-maintained policy charter (versioned YAML) and optional versioned benchmark data, returning findings with two severities (`error`, `warning`) and one honest third state (`insufficient_data` with reason codes). Strict schemas on all three inputs, a closed rule set, and fail-closed contract errors from a closed registry. `execute()` is a pure function: no network, no side effects, identical input → identical output. Interface frozen in [issue #317](https://github.com/ARPAHLS/skillware/issues/317).

Where [`monitoring/token_limiter`](token_limiter.md) covers resource-side monitoring, this skill adds business-metric monitoring to the category. It is an **auditor, not a data pipeline**: the snapshot is assembled upstream (exports, scripts, dashboards, or an agent that already gathered counts); the skill never fetches CRM, email, or analytics data.

## Design split

- **The skill's closed error registry covers contract violations only.** These codes are the skill's identity and never change per operator.
- **Finding codes come from the policy file**: each charter declares its own closed set of `UPPER_SNAKE_CASE` rule ids (for example `NO_BOOKING`), validated against a strict pattern. Another operator declares `NO_SIGNED_CONTRACT` instead; the skill needs no fork.
- **Benchmarks are optional.** A charter that references no benchmark runs fully self-contained. Demo data ships at `kb/benchmarks_demo.json` (timestamped, sourced, versioned); revisions land as ordinary data-only PRs.

## Agent-loop contract

- `error` → host blocks the dependent action until an operator override is recorded
- `warning` → surface to the operator, never block
- `insufficient_data` → treat the metric as absent; the host must not substitute or estimate

## Validation order (fail-closed, deterministic)

1. Schema-validate all three inputs → contract error on first failure
2. Cross-checks: rule metrics, denominator metrics, and snapshot keys must be declared by the policy; every `benchmark_ref` must resolve
3. Honesty floors → `insufficient_data` iff the declared floor is unmet, with the rule's declared reason code — checked against the declared metric only, never inferred
4. Rule evaluation in declared order

## Bundle layout

The skill lives in `skills/monitoring/kpi_gate/`. [Skill anatomy](../introduction.md#skill-anatomy). **Contract** — see Manifest Details below. **Assurance** — `test_skill.py` in the bundle.

### Effect (`skill.py`)

Pure Python evaluation: four-stage validation, closed error registry, and rule evaluation in charter order. No network calls; identical input returns identical output.

### Directive (`instructions.md`)

Registry ID, agent-loop contract (errors block, warnings surface, `insufficient_data` never backfilled), when to invoke, and how to read findings vs contract errors.

### Reference (`schemas/`)

JSON Schemas for metrics, policy, and benchmarks inputs (documentation; runtime uses explicit stdlib checks).

### Corpus (`kb/`)

Versioned benchmark demo data (`benchmarks_demo.json`) for rules that reference `benchmark_ref`.

## Manifest Details

**Parameters Schema:**
* `metrics` (object, required): Snapshot — `schema_version: 1`, `period` (`start`, `end`, `granularity`), and a map of `lower_snake_case` keys to non-negative numbers.
* `policy` (object, required): Charter — `schema_version: 2`, `policy_id`, closed `metrics` declaration, ordered `rules`. Typically versioned YAML, parsed by the host.
* `benchmarks` (object, optional): Versioned benchmark data — required only when a rule uses `benchmark_ref`.

Reference JSON Schemas for all three inputs ship under the bundle's `schemas/` directory. The skill enforces the same constraints with explicit stdlib checks (`requirements: []` is deliberate; no runtime `jsonschema` dependency).

**Outputs Schema:**
* `status` (string): `completed` for an evaluation run; `error` for a contract violation.
* `policy_id` (string): The evaluated charter's id.
* `benchmark_version` (string or null): Version of the supplied benchmark data, `null` when none was supplied.
* `findings` (array): Rule findings (`finding`, `severity`, `detail` with `metric`/`threshold`/`observed`, `action`) and refusals (`state: insufficient_data`, `detail.metric`, `reason`), in rule-declaration order.

Contract violations return `{"status": "error", "error": {"code", "detail"}}` instead — errors and honest non-computability never mix.

**Error registry (closed):** `INVALID_METRICS_SCHEMA`, `INVALID_POLICY_SCHEMA`, `INVALID_BENCHMARKS_SCHEMA`, `NO_METRICS_PROVIDED`, `UNKNOWN_METRIC_KEY`, `UNKNOWN_RULE_METRIC`, `UNKNOWN_DENOMINATOR_METRIC`, `BENCHMARK_VERSION_MISSING`, `BENCHMARK_REF_UNRESOLVED`.

### Reserved fields (v1)

`check.applies_to` is shape-validated and echoed into `detail.applies_to` on a finding, but carries **no evaluation semantics in v1** — do not assume it filters or scopes rule evaluation. `threshold` accepts the explicit literal `"unlimited"` only with `lte`/`lt` (an upper-bound rule with no cap always passes); `0` is never a sentinel.

## Environment

No environment variables. Fully offline; all inputs are passed to `execute()`.

## Example Usage (Direct)

The bundle ships the end-to-end example frozen in #317 (`fixtures/example_snapshot.json`, `fixtures/example_charter.yaml`, `kb/benchmarks_demo.json` — all values synthetic):

```python
import json
import os

import yaml
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("monitoring/kpi_gate")
skill = bundle["class"]()
root = os.path.join("skills", "monitoring", "kpi_gate")

with open(os.path.join(root, "fixtures", "example_snapshot.json")) as f:
    snapshot = json.load(f)
with open(os.path.join(root, "fixtures", "example_charter.yaml")) as f:
    charter = yaml.safe_load(f)
with open(os.path.join(root, "kb", "benchmarks_demo.json")) as f:
    benchmarks = json.load(f)

result = skill.execute(
    {"metrics": snapshot, "policy": charter, "benchmarks": benchmarks}
)
print(result["status"], result["policy_id"], result["benchmark_version"])
for finding in result["findings"]:
    print(finding)
```

## Usage Examples

Guides: [Usage index](../usage/README.md) · [Agent loops](../usage/agent_loops.md). No skill-specific API keys.

Use `bundle["class"]()` in the snippets below; explicit `bundle["module"].KpiGateSkill()` also works.

Sample user message: *Gate this week's funnel snapshot against the coaching charter and tell me what blocks.*

The provider snippets share this compact single-rule setup:

```python
SNAPSHOT = {
    "schema_version": 1,
    "period": {"start": "2026-08-17", "end": "2026-08-23", "granularity": "weekly"},
    "metrics": {"bookings": 0},
}
CHARTER = {
    "schema_version": 2,
    "policy_id": "weekly_gate_demo",
    "metrics": ["bookings"],
    "rules": [
        {
            "id": "NO_BOOKING",
            "metric": "bookings",
            "check": {"op": "gte", "threshold": 1},
            "severity": "error",
        }
    ],
}
USER_MESSAGE = (
    "Evaluate this KPI snapshot against the charter using the kpi gate tool. "
    f"metrics={SNAPSHOT} policy={CHARTER}"
)
```

### Runnable examples

- Local execute: [`examples/kpi_gate_demo.py`](../../examples/kpi_gate_demo.py) — runs the in-bundle fixtures fully offline: the end-to-end findings scenario (error, warning, and `insufficient_data` in one run) plus two fail-closed contract errors (empty metrics map, malformed charter)

### Gemini

```python
import google.genai as genai
from google.genai import types
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("monitoring/kpi_gate")
skill = bundle["class"]()
client = genai.Client()
gemini_tool = SkillLoader.to_gemini_tool(bundle)
response = client.models.generate_content(
    model="gemini-2.5-flash-lite",
    contents=USER_MESSAGE,
    config=types.GenerateContentConfig(
        tools=[gemini_tool],
        system_instruction=bundle["instructions"],
    ),
)
for part in response.candidates[0].content.parts:
    if part.function_call:
        result = skill.execute(dict(part.function_call.args))
        print(result["status"], result["findings"])
```

### Claude

```python
import os

import anthropic
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("monitoring/kpi_gate")
skill = bundle["class"]()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
tools = [SkillLoader.to_claude_tool(bundle)]
response = client.messages.create(
    model="claude-3-5-haiku-latest",
    max_tokens=1024,
    system=bundle["instructions"],
    tools=tools,
    messages=[{"role": "user", "content": USER_MESSAGE}],
)
for block in response.content:
    if block.type == "tool_use":
        result = skill.execute(dict(block.input))
        print(result["status"], result["findings"])
```

### OpenAI

```python
import json
import os

from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("monitoring/kpi_gate")
skill = bundle["class"]()
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
tool = SkillLoader.to_openai_tool(bundle)
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": bundle["instructions"]},
        {"role": "user", "content": USER_MESSAGE},
    ],
    tools=[tool],
)
message = response.choices[0].message
if message.tool_calls:
    args = json.loads(message.tool_calls[0].function.arguments)
    result = skill.execute(args)
    print(result["status"], result["findings"])
```

### DeepSeek

```python
import json
import os

from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("monitoring/kpi_gate")
skill = bundle["class"]()
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
tool = SkillLoader.to_deepseek_tool(bundle)
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": bundle["instructions"]},
        {"role": "user", "content": USER_MESSAGE},
    ],
    tools=[tool],
)
message = response.choices[0].message
if message.tool_calls:
    args = json.loads(message.tool_calls[0].function.arguments)
    result = skill.execute(args)
    print(result["status"], result["findings"])
```

### Ollama (prompt mode)

```python
import json

from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("monitoring/kpi_gate")
skill = bundle["class"]()
prompt = (
    "You may call tools as JSON blocks.\n"
    f"Tool: {bundle['manifest']['name']}\n"
    f"Instructions:\n{bundle['instructions']}\n"
    f"User: {USER_MESSAGE}"
)
print(prompt)
# When the model emits JSON tool args, pass them to execute:
result = skill.execute({"metrics": SNAPSHOT, "policy": CHARTER})
print(json.dumps(result, indent=2))
```

## Limitations (v1)

- **No data acquisition**: the snapshot must be assembled upstream; the skill never fetches, scrapes, or polls anything.
- **No causal inference**: findings report threshold breaches, not why they happened.
- **No threshold optimization**: thresholds come from the charter and benchmarks; the skill never tunes them.
- Derived-ratio metrics are declared and computed upstream like any other metric; the honesty floor (`requires.min_denominator`) gates them either way. Structured entity input is a possible v1.1 extension.
- `applies_to` is reserved (see above); a pricing-validation sibling and ledger-driven benchmark revisions are deferred per #317.

---

<!-- skill-history:begin -->
## Skill history

Commits that touched this skill bundle or its catalog page ([`monitoring/kpi_gate`](https://github.com/ARPAHLS/skillware/tree/main/skills/monitoring/kpi_gate)).

| Commit | Description | Date | Version | Contributors |
| :--- | :--- | :--- | :--- | :--- |
| [`0d01991`](https://github.com/ARPAHLS/skillware/commit/0d019913ad7b87ad5447b564133bb03b270237d9) | Add monitoring/kpi_gate v0.1.0 implementing the issue #317 interface (#318) | 1 Sep 2026 | `0.1.0` | [@mrmasa88](https://github.com/mrmasa88) |
<!-- skill-history:end -->

## Enterprise disclaimer

This skill is provided for demonstration and integration purposes. It is intended as a starting point that you can adapt to your own metrics, charters, and operational requirements. For an enterprise-grade version of this skill with dedicated support, SLAs, and customization, contact skills@arpacorp.net.
