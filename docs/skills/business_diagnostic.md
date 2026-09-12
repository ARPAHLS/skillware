# Business Diagnostic

**Domain:** `monitoring`
**Skill ID:** `monitoring/business_diagnostic`
**Issuer:** [@mrmasa88](https://github.com/mrmasa88) ([AO](https://github.com/0x-AO-Protocol))
<!-- skill-doc-meta:begin -->
**Version**: `0.1.0` — 8 Sep 2026
<!-- skill-doc-meta:end -->
**Recommended install:** `pip install "skillware[monitoring_business_diagnostic]"`. See [Install extras](../usage/install_extras.md).

[Skill Library](README.md) · [Testing](../TESTING.md)

Deterministic **scenario ledger and calibration**: `{action, as_of, framework, marks, observations?, outcome?, marks_history?}` → `scenarios[]` + `calibration`. An operator-maintained framework (scenarios with an adjudication date, leading indicators with declared per-scenario weights) and the operator's probability marks are evaluated against dated indicator observations. `adjudicate` returns the model-implied probability of each scenario under the declared weights, its delta from the marks, which indicators fired, the next re-mark due date, and days to adjudication. `calibrate` returns Brier scores once an outcome is resolved. Strict checks on every input, a closed error registry, and one honest state (`insufficient_data` with a reason code). `execute()` is a pure function: no network, no clock, no side effects, identical input → identical output. Interface agreed in [issue #338](https://github.com/ARPAHLS/skillware/issues/338).

Where [`monitoring/kpi_gate`](kpi_gate.md) answers "did this period breach a rule?", this skill answers "across periods, which way has the balance of plausibility shifted, and how well calibrated were the operator's marks?". It is a **ledger, not a data source**: observations are recorded upstream by the host or the operator; the skill never collects them, never estimates an unobserved indicator, and never re-marks on the operator's behalf.

> **Skill chains:** Stateless and terminal in v0.1 — marks, observations, history, and outcome travel in the input and come back in the output. Run after the host records an observation; see [Skill chaining](../usage/skill_chaining.md).

## Three terms

- **Operator marks** — the probabilities the operator assigned on `marked_on`. Never overwritten.
- **Model-implied** — what the declared weights imply once observations are applied to the marks. Not a forecast and not a recommendation; always shown next to the operator marks, never in place of them.
- **insufficient_data** — the honest state: a computation the skill refuses to fake, with a reason code from a closed set.

## Design split

- **The framework is operator-owned, versioned, and strict-schema.** Scenario ids and indicator ids are closed sets declared by the framework; the skill ships no scenarios or indicators of its own.
- **The skill's closed error registry covers contract violations only** (schema failures, undeclared ids, marks that do not sum to 1, malformed or out-of-order dates). These codes are the skill's identity and never change per operator.
- **Unobserved indicators contribute 0; nothing is estimated.** With `exhaustive: true` the model-implied values are renormalized to sum to 1; with `false` each scenario updates independently.
- **The evaluation date is an input** (`as_of`). The skill never reads the clock, so staleness and days to adjudication are reproducible offline.

## Agent-loop contract

- Surface `scenarios[].delta` and `scenarios[].fired` next to `operator_mark`; never present `model_implied` on its own
- `marks_stale: true` → prompt the operator to re-mark; never re-mark for them
- `insufficient_data` non-empty → report the reason; the host must not substitute, estimate, or backfill
- Top-level booleans for chain conditions: `fired_any`, `marks_stale`, `insufficient`

## Arithmetic (v0.1)

- Observation signal `o_i`: `yes` → +1, `no` → −1, unobserved → 0.
- For each scenario *s*: `logit(p_s') = logit(p_s) + Σ_i w_{i,s} · o_i`, where `w_{i,s}` is `indicators[i].strengthens[s]` (undeclared → 0).
- Weights: an indicator observed `yes` adds +w to every scenario listed in its `strengthens`, `no` adds −w; scenarios not listed get 0; indicators without an observation contribute 0 — nothing is imputed.
- `exhaustive: true` → divide every `p_s'` by their sum. With `exhaustive: false` each scenario updates independently and model-implied values may not sum to 1. Example (the end-to-end framework and marks, `I01` observed `yes`, `exhaustive: false`): A 0.324 (+0.174), B 0.332 (−0.118), C 0.300 (0.000), D 0.100 (0.000), sum 1.056.
- `model_implied` and `delta` are rounded to 3 decimals after normalization.
- Multi-class Brier: `Σ_s (p_s − y_s)²` with one-hot `y` (1 for the resolved scenario, 0 otherwise), 3 decimals; `brier_trend` scores each `marks_history` set in ascending `marked_on` order.

## Validation order (fail-closed, deterministic)

The first contract violation found is returned: request envelope → `action` → `as_of` → framework shape → `strengthens` ids → marks (shape, undeclared ids, missing ids, range, sum) → observations (shape, undeclared ids, duplicates, dates) → outcome → `marks_history`.

## Bundle layout

The skill lives in `skills/monitoring/business_diagnostic/`. [Skill anatomy](../introduction.md#skill-anatomy). **Contract** — see Manifest Details below. **Assurance** — `test_skill.py` in the bundle.

### Effect (`skill.py`)

Pure Python evaluation: fail-closed validation in the order above, closed error registry, logit-space update, optional renormalization, Brier scoring. Standard library only; no clock, no network.

### Directive (`instructions.md`)

Registry ID, the three terms, agent-loop contract (deltas next to marks, re-mark prompts, `insufficient_data` never backfilled), when to invoke, and how to read completed runs vs contract errors.

### Reference (`schemas/`)

JSON Schemas for `framework`, `marks`, `observations`, `outcome`, and the `output` shape (documentation; runtime uses explicit stdlib checks). In-bundle `fixtures/` hold the end-to-end example and one minimal input per error code.

### Corpus (`kb/`)

Synthetic demo framework (`demo_scenarios.json`, timestamped and sourced): four scenarios and two indicators, identical to the end-to-end fixture.

## Manifest Details

**Parameters Schema:**
* `action` (string, required): `adjudicate` or `calibrate`.
* `as_of` (string, required): evaluation date `YYYY-MM-DD` supplied by the host.
* `framework` (object, required): `schema_version: 1`, `framework_id`, `adjudication_date`, `exhaustive`, `scenarios[]` (`id`, `label`, `criterion`), `indicators[]` (`id`, `label`, `strengthens` map). Ids match `^[A-Z][A-Z0-9_]*$`.
* `marks` (object, required): `marked_on`, `remark_every_days`, `values` covering every scenario, each in `[0.001, 0.999]`, summing to 1.
* `observations` (array, optional for `adjudicate`): `indicator`, `observed` (`yes` / `no`), `on`, optional `source`. One entry per indicator; `on` must be after `marked_on` and not after `adjudication_date`.
* `outcome` (object or null, required for `calibrate`): `resolved_on`, `scenario`.
* `marks_history` (array, optional for `calibrate`): earlier mark sets, same shape as `marks`.

Reference JSON Schemas ship under the bundle's `schemas/` directory. The skill enforces the same constraints with explicit stdlib checks (`requirements: []` is deliberate; no runtime `jsonschema` dependency).

**Outputs Schema:**
* `status` (string): `completed` for an evaluation run; `error` for a contract violation.
* `framework_id` (string), `as_of` (string): echoed from the input.
* `scenarios` (array): per declared scenario in declaration order — `id`, `operator_mark`, `fired`; for `adjudicate` also `model_implied` and `delta` (3 decimals, or `null` under `insufficient_data`).
* `calibration` (object): `next_remark_due`, `days_to_adjudication`, `brier` (`null` for `adjudicate`); for `calibrate` also `brier_trend` (array or `null`).
* `fired_any`, `marks_stale`, `insufficient` (boolean); `insufficient_data` (array of `reason` + `detail`).

Contract violations return `{"status": "error", "error": {"code", "detail"}}` instead — errors and the honest state never mix.

**Error registry (closed):** `INVALID_REQUEST`, `UNKNOWN_ACTION`, `INVALID_AS_OF`, `INVALID_FRAMEWORK_SCHEMA`, `INVALID_MARKS_SCHEMA`, `INVALID_OBSERVATIONS_SCHEMA`, `INVALID_OUTCOME_SCHEMA`, `UNKNOWN_SCENARIO_ID`, `UNKNOWN_INDICATOR_ID`, `DUPLICATE_OBSERVATION`, `MARK_OUT_OF_RANGE`, `MARKS_NOT_NORMALIZED`, `OBSERVATION_PREDATES_MARKS`, `OBSERVATION_AFTER_ADJUDICATION`.

**Honest state (closed):** `adjudication_date_passed` — `adjudicate` with `as_of` on or after `adjudication_date` returns the marks with `model_implied: null` and `delta: null`.

## Environment

No environment variables. Fully offline; all inputs are passed to `execute()`.

## Example Usage (Direct)

The bundle ships the end-to-end example from #338 with `as_of` added (`fixtures/example_adjudicate_params.json`, `fixtures/example_calibrate_params.json`, `kb/demo_scenarios.json` — all values synthetic):

```python
import json
import os

from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("monitoring/business_diagnostic")
skill = bundle["class"]()
root = os.path.join("skills", "monitoring", "business_diagnostic", "fixtures")

with open(os.path.join(root, "example_adjudicate_params.json")) as f:
    params = json.load(f)

result = skill.execute(params)
print(result["status"], result["framework_id"], result["as_of"])
for row in result["scenarios"]:
    print(row["id"], row["operator_mark"], row["model_implied"], row["delta"], row["fired"])
print(result["calibration"], result["marks_stale"])
```

Expected: A 0.307 (+0.157), B 0.314 (−0.136), C 0.284 (−0.016), D 0.095 (−0.005), `fired: ["I01"]` on A and B, `next_remark_due 2026-10-16`, `days_to_adjudication 485`. The calibrate fixture (outcome B) returns `brier: 0.425`.

## Usage Examples

Guides: [Usage index](../usage/README.md) · [Agent loops](../usage/agent_loops.md). No skill-specific API keys.

Use `bundle["class"]()` in the snippets below; explicit `bundle["module"].BusinessDiagnosticSkill()` also works.

Sample user messages: *Update the launch scenario ledger with this week's observation and tell me which way the balance moved.* — then, after resolution — *The outcome is in: scenario B resolved on 2027-12-31. Score the marks and the earlier mark sets.*

The provider snippets share this setup (the same values as the bundle's end-to-end fixtures and `kb/demo_scenarios.json`):

```python
AS_OF = "2026-09-02"
FRAMEWORK = {
    "schema_version": 1,
    "framework_id": "demo_launch_2026",
    "adjudication_date": "2027-12-31",
    "exhaustive": True,
    "scenarios": [
        {"id": "A", "label": "wired launch", "criterion": "Product launches through an existing partner channel before the adjudication date."},
        {"id": "B", "label": "branded launch", "criterion": "Product launches under its own brand before the adjudication date."},
        {"id": "C", "label": "no launch", "criterion": "No launch of any kind before the adjudication date."},
        {"id": "D", "label": "residual", "criterion": "Any outcome not covered by A, B, or C."},
    ],
    "indicators": [
        {"id": "I01", "label": "design document published", "strengthens": {"A": 1.0, "B": -0.5}},
        {"id": "I07", "label": "timing synchronized with market window", "strengthens": {"B": 1.0, "A": -0.5}},
    ],
}
MARKS = {
    "marked_on": "2026-07-18",
    "remark_every_days": 90,
    "values": {"A": 0.15, "B": 0.45, "C": 0.30, "D": 0.10},
}
OBSERVATIONS = [{"indicator": "I01", "observed": "yes", "on": "2026-08-20", "source": "ref-12"}]
OUTCOME = {"resolved_on": "2027-12-31", "scenario": "B"}
MARKS_HISTORY = [
    {"marked_on": "2026-04-19", "remark_every_days": 90, "values": {"A": 0.15, "B": 0.40, "C": 0.35, "D": 0.10}},
    {"marked_on": "2026-01-19", "remark_every_days": 90, "values": {"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25}},
]
ADJUDICATE_USER_MESSAGE = (
    f"Adjudicate this scenario ledger with the business diagnostic tool as of {AS_OF}. "
    f"framework={FRAMEWORK} marks={MARKS} observations={OBSERVATIONS}"
)
CALIBRATE_USER_MESSAGE = (
    f"The outcome is resolved. Calibrate these marks with the business diagnostic tool as of {AS_OF}. "
    f"framework={FRAMEWORK} marks={MARKS} outcome={OUTCOME} marks_history={MARKS_HISTORY}"
)


def show_adjudicate(result):
    # Deltas and fired indicators next to the operator marks, never model_implied alone.
    for row in result["scenarios"]:
        print(row["id"], row["operator_mark"], row["model_implied"], row["delta"], row["fired"])
    print("marks_stale:", result["marks_stale"], "insufficient_data:", result["insufficient_data"])


def show_calibrate(result):
    print("brier:", result["calibration"]["brier"])
    print("brier_trend:", result["calibration"]["brier_trend"])
```

Expected: adjudicate → A 0.307 (+0.157), B 0.314 (−0.136), C 0.284 (−0.016), D 0.095 (−0.005), `fired: ["I01"]` on A and B; calibrate → `brier: 0.425`, `brier_trend` 2026-01-19 0.75 then 2026-04-19 0.515.

### Full loop (adjudicate → calibrate)

Host rules for the two-action loop:

- (a) The host supplies `as_of` on every call; the skill never reads the clock.
- (b) Stateless: `marks`, `observations`, `marks_history`, and `outcome` travel in the JSON input and come back in the output. Keep the ledger on the host side.
- (c) Surface `delta` and `fired` next to `operator_mark`. **Never present `model_implied` on its own.**
- (d) `marks_stale: true` → prompt the operator to re-mark; the host never re-marks for them.
- (e) `insufficient_data` non-empty → report the reason code; do not substitute, estimate, or backfill.
- (f) Chain conditions use the top-level booleans `fired_any`, `marks_stale`, and `insufficient`.

The loop is two tool calls. After an observation is recorded, the host sends `ADJUDICATE_USER_MESSAGE`, the model calls the tool with `action: "adjudicate"`, and the host presents `scenarios[]` next to the operator marks. After the outcome resolves, the host sends `CALIBRATE_USER_MESSAGE`, the model calls the tool with `action: "calibrate"` (adding `marks_history` when earlier mark sets exist), and the host reports `calibration["brier"]` and `calibration["brier_trend"]`. Every provider block below runs both calls in sequence.

### Runnable examples

- Local execute: [`examples/business_diagnostic_demo.py`](../../examples/business_diagnostic_demo.py) — runs the in-bundle fixtures fully offline: adjudicate, calibrate, and one fail-closed contract error

### Gemini

```python
import google.genai as genai
from google.genai import types
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("monitoring/business_diagnostic")
skill = bundle["class"]()
client = genai.Client()
gemini_tool = SkillLoader.to_gemini_tool(bundle)
config = types.GenerateContentConfig(
    tools=[gemini_tool],
    system_instruction=bundle["instructions"],
)


def run_tool_call(user_message, show):
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite", contents=user_message, config=config
    )
    for part in response.candidates[0].content.parts:
        if part.function_call:
            show(skill.execute(dict(part.function_call.args)))


run_tool_call(ADJUDICATE_USER_MESSAGE, show_adjudicate)  # after the observation
run_tool_call(CALIBRATE_USER_MESSAGE, show_calibrate)  # after the outcome resolves
```

### Claude

```python
import os

import anthropic
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("monitoring/business_diagnostic")
skill = bundle["class"]()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
tools = [SkillLoader.to_claude_tool(bundle)]


def run_tool_call(user_message, show):
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=bundle["instructions"],
        tools=tools,
        messages=[{"role": "user", "content": user_message}],
    )
    for block in response.content:
        if block.type == "tool_use":
            show(skill.execute(dict(block.input)))


run_tool_call(ADJUDICATE_USER_MESSAGE, show_adjudicate)  # after the observation
run_tool_call(CALIBRATE_USER_MESSAGE, show_calibrate)  # after the outcome resolves
```

### OpenAI

```python
import json
import os

from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("monitoring/business_diagnostic")
skill = bundle["class"]()
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
tool = SkillLoader.to_openai_tool(bundle)


def run_tool_call(user_message, show):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": bundle["instructions"]},
            {"role": "user", "content": user_message},
        ],
        tools=[tool],
    )
    message = response.choices[0].message
    if message.tool_calls:
        args = json.loads(message.tool_calls[0].function.arguments)
        show(skill.execute(args))


run_tool_call(ADJUDICATE_USER_MESSAGE, show_adjudicate)  # after the observation
run_tool_call(CALIBRATE_USER_MESSAGE, show_calibrate)  # after the outcome resolves
```

### DeepSeek

```python
import json
import os

from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("monitoring/business_diagnostic")
skill = bundle["class"]()
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
tool = SkillLoader.to_deepseek_tool(bundle)


def run_tool_call(user_message, show):
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": bundle["instructions"]},
            {"role": "user", "content": user_message},
        ],
        tools=[tool],
    )
    message = response.choices[0].message
    if message.tool_calls:
        args = json.loads(message.tool_calls[0].function.arguments)
        show(skill.execute(args))


run_tool_call(ADJUDICATE_USER_MESSAGE, show_adjudicate)  # after the observation
run_tool_call(CALIBRATE_USER_MESSAGE, show_calibrate)  # after the outcome resolves
```

### Ollama (prompt mode)

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("monitoring/business_diagnostic")
skill = bundle["class"]()


def prompt_for(user_message):
    return (
        "You may call tools as JSON blocks.\n"
        f"Tool: {bundle['manifest']['name']}\n"
        f"Instructions:\n{bundle['instructions']}\n"
        f"User: {user_message}"
    )


print(prompt_for(ADJUDICATE_USER_MESSAGE))
# When the model emits JSON tool args for adjudicate, pass them to execute:
show_adjudicate(
    skill.execute(
        {
            "action": "adjudicate",
            "as_of": AS_OF,
            "framework": FRAMEWORK,
            "marks": MARKS,
            "observations": OBSERVATIONS,
        }
    )
)

print(prompt_for(CALIBRATE_USER_MESSAGE))
# After the outcome resolves, the calibrate tool args:
show_calibrate(
    skill.execute(
        {
            "action": "calibrate",
            "as_of": AS_OF,
            "framework": FRAMEWORK,
            "marks": MARKS,
            "outcome": OUTCOME,
            "marks_history": MARKS_HISTORY,
        }
    )
)
```

## Limitations (v0.1)

- **No data acquisition**: observations are recorded upstream; the skill never fetches, scrapes, or polls anything.
- **No estimation**: an unobserved indicator contributes 0; nothing is imputed.
- **No re-marking**: `marks_stale` prompts the operator; the skill never writes marks.
- **Operator marks only**: `observations` passed to `calibrate` are validated but not used: Brier scores use operator marks only.
- **No weight tuning**: `strengthens` weights come from the framework; the skill never adjusts them.
- One observation per indicator per call; the host de-duplicates before calling.

v0.1 is the ledger; projections against declared targets and a report skeleton are planned as Skill Upgrades.

---

<!-- skill-history:begin -->
## Skill history

Commits that touched this skill bundle or its catalog page ([`monitoring/business_diagnostic`](https://github.com/ARPAHLS/skillware/tree/main/skills/monitoring/business_diagnostic)).

| Commit | Description | Date | Version | Contributors |
| :--- | :--- | :--- | :--- | :--- |
| *(pending merge)* | Add monitoring/business_diagnostic v0.1.0 — scenario ledger and calibration (#338) | 8 Sep 2026 | `0.1.0` | [@mrmasa88](https://github.com/mrmasa88) |
<!-- skill-history:end -->

## Enterprise disclaimer

This skill is provided for demonstration and integration purposes. It is intended as a starting point that you can adapt to your own scenarios, indicators, and operational requirements. For an enterprise-grade version of this skill with dedicated support, SLAs, and customization, contact skills@arpacorp.net.
