# Unit Normalizer

**ID**: `data_engineering/unit_normalizer`  
**Issuer**: [@rizzoMartin](https://github.com/rizzoMartin) ([@ARPAHLS](https://github.com/ARPAHLS))  
<!-- skill-doc-meta:begin -->
- **Version**: `0.1.0`
- **Tier**: `core`
- **Shape**: `atomic`
- **Target**: `software`, `hardware`
- **Tags**: `units`, `normalization`, `conversion`, `measurement`, `data_cleaning`, `si_units`, `engineering`
<!-- skill-doc-meta:end -->
<!-- skill-intent:begin -->
**Solves:** Normalize mixed units across whole batches and tables, parse compound quantity strings, and declare every ambiguous reading instead of guessing.
**Works with:** Gemini, Claude, OpenAI, DeepSeek, Ollama, and Bedrock-compatible host loops.
**Runtime:** Pure Python, offline, no API key, no dependencies.
<!-- skill-intent:end -->

**Recommended install:** `pip install "skillware[data_engineering_unit_normalizer]"`. See [Install extras](../../usage/install_extras.md).  
**Category**: Data Engineering

[Skill Library](../README.md) · [Data Engineering](README.md) · [Testing](../../TESTING.md)

Models convert `10 km` to miles without trouble. They fail where unit work actually happens in pipelines. A 1,500-row supplier sheet in mixed units either burns thousands of output tokens or takes 1,500 tool round trips. `5 ft 11 in` gets read as `5.11 ft`, a 14% error. `20 tons` gets converted with a reading that is silently picked from three that are up to 12% apart. This skill does the arithmetic locally and deterministically, in one call per batch, and records every choice it had to make.

## Capabilities

- **One equation for every unit**: each unit is a `{factor, offset}` row against the SI base of its dimension (`si = (value + offset) * factor`), so Celsius, Fahrenheit, Kelvin and Rankine use the same path as meters and pounds with no special cases.
- **Batch and table modes**: `normalize_batch` converts a list of records and `normalize_table` converts named columns of a row list or a columnar object. A bad record becomes an error keyed by its `id`; the other rows still convert.
- **Compound string parsing**: `parse_quantity` reads `5 ft 11 in`, `5'11"`, `1/4 lb`, `3 1/2 gal`, `120 km/h`, `45.2 psi`, `15 knots` and `3.5 MPa`, and returns the components it summed.
- **Assume-and-declare**: ambiguous units (`ton`, `gal`, `pt`, `qt`, `oz`, `'`, `"`) convert with a documented default and carry `assumed`, `assumption`, `alternatives` and `risk_variance`. The `assume` parameter locks a reading for the whole call, and locked rows come back clean.
- **Hard dimension guard**: `kg` to `m` is a `dimension_mismatch` error, never a number. Angles have their own dimension, so `deg` never validates against a dimensionless quantity, and `rpm` and `dps` compose as angle per time.
- **SI canonicalization**: `canonicalize`, or simply omitting `to_unit`, converts to the SI unit of each value's dimension (m, kg, s, K, Pa, J, W, N, rad, rad/s and so on).
- **Strict SI prefixes**: `n`, `u`/`µ`, `m`, `c`, `k`, `M`, `G` apply only to an allowlist of base units, and case is never folded on symbols: `MPa` and `mPa` are 10⁹ apart.
- **Context-safe output**: `compact: true` returns per-unit statistics, five sample results and every error instead of the full result list.

## Arguments

| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `action` | string | `normalize` | `normalize`, `normalize_batch`, `canonicalize`, `parse_quantity`, or `normalize_table`. |
| `value` | number | - | Value for `normalize` and single `canonicalize`. |
| `from_unit` | string | - | Unit of `value`. |
| `to_unit` | string | SI unit | Target unit. Omit for the canonical SI unit. |
| `id` | string | `0` | Identifier echoed on a single result. |
| `records` | array | - | `normalize_batch` / `canonicalize`: objects with `value`, `from_unit`, optional `to_unit` and `id`. |
| `text` | string | - | `parse_quantity` input. |
| `target_unit` | string | SI unit | `parse_quantity` target. |
| `table` | array or object | - | `normalize_table`: row objects, or column name to list of values. |
| `columns` | object | - | `normalize_table`: column name to `{from_unit, to_unit}`. |
| `assume` | object | - | Locks ambiguous readings, e.g. `{"ton": "us_short_ton"}`. |
| `precision` | integer | `6` | Decimals in `display_value` (0 to 12). |
| `compact` | boolean | `false` | Summary statistics and samples instead of every result. |

In tables, empty cells (`null`, blank strings, NaN) are skipped and counted in `summary.skipped`. Numeric strings such as `"12.5"` are accepted as values, because CSV readers return text. Strings with units are not; use `parse_quantity` for those.

## Output

| Field | Type | Description |
| :--- | :--- | :--- |
| `status` | string | `ready`, `warning`, `insufficient_data`, or `error`. |
| `action` | string | Action that produced the envelope. |
| `result` | object | The single record for `normalize` and `parse_quantity`, else `null`. |
| `results` | array | Converted records: `id`, `value`, `display_value`, `from_unit`, `to_unit`, `dimension`, plus the assumption fields when a reading was assumed. |
| `errors` | array | `id`, `code`, `detail`, and the units when known. Table errors add `column`. |
| `summary` | object | `total`, `converted`, `assumed`, `errors`, `skipped`. |
| `precision` | integer | Decimals used for `display_value`. |
| `agent_hint` | string | One-line summary for the host agent. |
| `error` | string | Request-level failure reason, or `null`. |
| `table` | array or object | `normalize_table` only, same shape as the input (omitted under `compact`). |
| `compact`, `results_omitted`, `stats` | - | Present only when `compact` is `true`. `stats` is keyed by target unit with `count`, `min`, `max`. |

```json
{
  "status": "warning",
  "action": "normalize_batch",
  "result": null,
  "results": [
    {"id": "r1", "value": 62.13711922373339, "display_value": "62.137119",
     "from_unit": "km", "to_unit": "miles", "dimension": "length"},
    {"id": "r3", "value": 20000.0, "display_value": "20000.000000",
     "from_unit": "ton", "to_unit": "kg", "dimension": "mass",
     "assumed": true, "assumption": "ton interpreted as metric_ton",
     "alternatives": ["us_short_ton", "imperial_long_ton"], "risk_variance": "12.0%"}
  ],
  "errors": [
    {"id": "r7", "code": "dimension_mismatch",
     "detail": "kg (mass) cannot convert to m (length)", "from_unit": "kg", "to_unit": "m"}
  ],
  "summary": {"total": 3, "converted": 2, "assumed": 1, "errors": 1, "skipped": 0},
  "precision": 6,
  "agent_hint": "Converted 2 of 3 record(s); 1 assumed; 1 error(s).",
  "error": null
}
```

### Statuses and error codes

`ready` means every record converted with no assumption. `warning` means at least one record failed or was assumed; the rest are still valid. `insufficient_data` means nothing was supplied. `error` means the request itself is invalid: unknown action, bad `assume` (`invalid_assumption`), bad `precision`, or a bad `columns` spec.

Record error codes are stable strings: `unknown_unit`, `dimension_mismatch`, `unparseable`, `invalid_value` (booleans, NaN, infinity, non-numeric text), and `invalid_record`.

## Ambiguity policy

| Token | Default | Alternatives | `risk_variance` |
| :--- | :--- | :--- | :--- |
| `ton` | `metric_ton` | `us_short_ton`, `imperial_long_ton` | `12.0%` |
| `gal` | `us_gallon` | `imperial_gallon` | `20.1%` |
| `pt` | `us_pint` | `imperial_pint` | `20.1%` |
| `qt` | `us_quart` | `imperial_quart` | `20.1%` |
| `oz` | `oz_mass` | `oz_fluid_us`, `oz_fluid_imperial` | - (fluid readings are another dimension) |
| `'` | `ft` | `arcmin` | - |
| `"` | `in` | `arcsec` | - |

When the target unit settles the dimension, the reading follows it: `8 oz` to `mL` uses `oz_fluid_us`, and is still declared. Plural and long forms (`tons`, `gallons`, `ounces`) belong to the same groups. Pass `assume` to lock a reading; locked rows carry no assumption fields and do not raise the status to `warning`.

## Limitations

- **No unit products** such as `oz-in` or `N*m`, and no ambiguous units inside rates (`gal/min` is `unknown_unit`).
- **No caller-defined units** in this version.
- **Compound strings need whitespace between pairs** (`5 ft 11 in`), except after quote marks and the degree sign (`5'11"`, `40°26'46"`). Later components follow the first one's dimension, so `45° 30'` reads the `'` as arcminutes. Sums are refused across dimensions or with temperature scales (`20 C 5 F` is `unparseable`).
- **Commas are refused**, not guessed as thousands or decimal separators.
- **Fractions with a decimal denominator** (`1/2.3"`) are refused: they are optical sensor-format designations, not lengths. Integer fractions of an inch (`1/2"`) are read literally.
- **Static constants only.** No currencies or other time-varying rates.

## Environment

This skill requires no environment variables and no API keys. See [API keys for skills](../../usage/api_keys.md) for the general setup other skills use.

Because the manifest targets `hardware` as well as `software`, `SkillContext` emits `SkillwareHardwareSafetyWarning` unless the host sets `allow_hardware_execution=True`. The skill itself never actuates anything; the warning exists because its output may feed controllers that do.

## Bundle layout

The skill lives in `skills/data_engineering/unit_normalizer/`. Roles: [Skill anatomy](../../introduction.md#skill-anatomy). Vocabulary: [glossary](../../glossary.md). **Contract** - see Arguments and Output above. **Assurance** - `test_skill.py` in the bundle.

### Effect (`skill.py`)

Parameter validation, action dispatch, batch and table loops, compact statistics, and the result envelope. Never raises into the host.

### Effect modules (`units.py`, `parser.py`)

`units.py` holds the unit table, the ambiguity table, and resolution: exact alias, then SI prefix against the allowlist, then case-insensitive long names, then exponent suffixes, then `a/b` quotients. `parser.py` reads compound quantity strings into components. Both are pure.

### Directive (`instructions.md`)

When to invoke, the boundary with `telemetry_normalizer`, how to read assumed rows, and the limits.

## Usage Examples

Guides: [Usage index](../../usage/README.md) · [Agent loops](../../usage/agent_loops.md) · [Skill chaining](../../usage/skill_chaining.md) · [Install extras](../../usage/install_extras.md)

### Direct execute

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("data_engineering/unit_normalizer")
skill = bundle["class"]()

batch = skill.execute({
    "action": "normalize_batch",
    "assume": {"ton": "metric_ton"},
    "records": [
        {"id": "a", "value": 100, "from_unit": "km", "to_unit": "miles"},
        {"id": "b", "value": 450, "from_unit": "kPa", "to_unit": "psi"},
        {"id": "c", "value": 3000, "from_unit": "rpm", "to_unit": "rad/s"},
        {"id": "d", "value": 20, "from_unit": "ton", "to_unit": "kg"},
    ],
})
print(batch["status"], [r["display_value"] for r in batch["results"]])

height = skill.execute({"action": "parse_quantity", "text": "5 ft 11 in", "target_unit": "m"})
print(height["result"]["value"])  # 1.8034

table = skill.execute({
    "action": "normalize_table",
    "table": [{"sku": "A1", "speed": "60"}, {"sku": "B2", "speed": 30}],
    "columns": {"speed": {"from_unit": "mph", "to_unit": "km/h"}},
})
print(table["table"])
```

### Claude (Anthropic Tool Use)

```python
import os
import anthropic
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("data_engineering/unit_normalizer")
skill = bundle["class"]()
tool = SkillLoader.to_claude_tool(bundle)
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

response = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=1024,
    system=bundle["instructions"],
    tools=[tool],
    messages=[{"role": "user", "content": "The shipment is 20 tons and the crate is 5 ft 11 in tall. Give me both in SI."}],
)

for block in response.content:
    if block.type == "tool_use":
        result = skill.execute(block.input)
        print(result["status"], result["agent_hint"])
```

### OpenAI (Function Calling)

```python
import json
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("data_engineering/unit_normalizer")
skill = bundle["class"]()
openai_tool = SkillLoader.to_openai_tool(bundle)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

response = client.chat.completions.create(
    model="gpt-4o",
    tools=[openai_tool],
    messages=[
        {"role": "system", "content": bundle["instructions"]},
        {"role": "user", "content": "Convert these motor speeds to rad/s: 1200 rpm, 3000 rpm, 4500 rpm."},
    ],
)

for call in response.choices[0].message.tool_calls or []:
    result = skill.execute(json.loads(call.function.arguments))
    print([r["display_value"] for r in result["results"]])
```

### DeepSeek

```python
import json
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("data_engineering/unit_normalizer")
skill = bundle["class"]()
deepseek_tool = SkillLoader.to_deepseek_tool(bundle)
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

response = client.chat.completions.create(
    model="deepseek-chat",
    tools=[deepseek_tool],
    messages=[
        {"role": "system", "content": bundle["instructions"]},
        {"role": "user", "content": "The datasheet says 45.2 psi and 3.5 MPa. Which is higher?"},
    ],
)

for call in response.choices[0].message.tool_calls or []:
    print(skill.execute(json.loads(call.function.arguments))["status"])
```

### Ollama (prompt mode)

```python
import json
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("data_engineering/unit_normalizer")
skill = bundle["class"]()
prompt = (
    "You may call tools as JSON blocks.\n"
    f"Tool: {bundle['manifest']['name']}\n"
    f"Instructions:\n{bundle['instructions']}\n"
    "User: Normalize 3 1/2 gal of coolant to liters."
)
print(prompt)
result = skill.execute({"action": "parse_quantity", "text": "3 1/2 gal", "target_unit": "L"})
print(json.dumps(result, indent=2))
```

### Gemini

```python
import os
import google.genai as genai
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("data_engineering/unit_normalizer")
tool = SkillLoader.to_gemini_tool(bundle)
skill = bundle["class"]()
client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

response = client.models.generate_content(
    model="gemini-3.5-flash",
    contents="Canonicalize these readings to SI: 98.6 F, 15 knots, 1 atm.",
    config=genai.types.GenerateContentConfig(
        system_instruction=bundle["instructions"], tools=[tool]
    ),
)

tool_name = SkillLoader._sanitize_gemini_tool_name(bundle["manifest"]["name"])
for part in response.candidates[0].content.parts:
    if part.function_call and part.function_call.name == tool_name:
        print(skill.execute(dict(part.function_call.args))["results"])
```

### Skill Chaining (with `data_engineering/semantic_web_proxy`)

Pull a spec sheet into text, then normalize the quantities the host extracted from it. See [Skill chaining](../../usage/skill_chaining.md).

```python
from skillware import SkillContext

ctx = SkillContext(
    skills=["data_engineering/semantic_web_proxy", "data_engineering/unit_normalizer"],
    allow_hardware_execution=True,
)

page = ctx.execute(
    "data_engineering/semantic_web_proxy",
    {"url": "https://example.com/products/pump-x200/specs"},
)

if page["status"] != "error":
    # Quantities the host model pulled out of page["semantic_payload"]
    specs = ["120 psi", "3 1/2 gal", "1750 rpm"]
    normalized = [
        ctx.execute("data_engineering/unit_normalizer", {"action": "parse_quantity", "text": s})
        for s in specs
    ]
    print([(n["result"]["display_value"], n["result"]["to_unit"]) for n in normalized])
```

---

<!-- skill-history:begin -->
## Skill history

Commits that touched this skill bundle or its catalog page ([`data_engineering/unit_normalizer`](https://github.com/ARPAHLS/skillware/tree/main/skills/data_engineering/unit_normalizer)).

| Commit | Description | Date | Version | Contributors |
| :--- | :--- | :--- | :--- | :--- |
| [`8f485a6`](https://github.com/ARPAHLS/skillware/commit/8f485a6cb336172e1f9f1882518d868a39ed1152) | feat(data_engineering): add unit_normalizer skill (#167) | 1 Nov 2026 | `0.1.0` | [@rizzoMartin](https://github.com/rizzoMartin) |
<!-- skill-history:end -->

## Enterprise disclaimer

This skill is provided for demonstration and integration purposes. It is intended as a starting point that you can adapt to your own data, schemas, and operational requirements. For an enterprise-grade version of this skill with dedicated support, SLAs, and customization, contact skills@arpacorp.net.
