# Telemetry Normalizer

**ID**: `data_engineering/telemetry_normalizer`  
**Issuer**: [@rin-katsuragi](https://github.com/rin-katsuragi) ([@ARPAHLS](https://github.com/ARPAHLS))  
<!-- skill-doc-meta:begin -->
**Version**: `0.1.0`
<!-- skill-doc-meta:end -->
<!-- skill-intent:begin -->
**Solves:** Standardize noisy heterogeneous sensor telemetry from robotics, IoT, and facilities into canonical SI units and W3C SOSA/SSN semantic observations.
**Works with:** Gemini, Claude, OpenAI, DeepSeek, Ollama, and Bedrock-compatible host loops.
**Runtime:** In-memory deterministic normalization; no external network or API key required.
<!-- skill-intent:end -->

**Recommended install:** `pip install "skillware[data_engineering_telemetry_normalizer]"`. See [Install extras](../../usage/install_extras.md).  
**Category**: Data Engineering

[Skill Library](../README.md) · [Data Engineering](README.md) · [Testing](../../TESTING.md)

Autonomous agents and cognitive host loops struggle when fed raw telemetry arrays directly from hardware sensors, microcontrollers, and IoT hubs. Timestamps arrive in arbitrary millisecond, microsecond, or local timezone formats; physical units mix imperial and custom scales (such as Fahrenheit, degrees per second, and inches of water column); and hardware faults introduce out-of-bounds readings, stuck values, or floating-point NaNs.

This skill provides a fast, deterministic, zero-hallucination data engineering pipeline. It harmonizes raw sensor streams into canonical SI units, strict UTC ISO-8601 timestamps, and W3C SOSA/SSN semantic observations using bundled, domain-specific schema profiles.

Normalization is 100% deterministic. Identical telemetry arrays and options always produce identical results, with zero generative model calls executed inside the skill.

## Capabilities

- **SI Unit Harmonization**: Deterministically converts raw vendor units (e.g. °F &rarr; °C, deg/s &rarr; rad/s, cfm &rarr; m3/h, in_wc &rarr; Pa, mV &rarr; V) into canonical SI equivalents via lookup rules.
- **Universal UTC Timestamp Normalizer**: Ingests epochs (seconds, milliseconds, microseconds, nanoseconds) and RFC/ISO date strings into strict UTC ISO-8601 timestamps.
- **Physical Boundary & Fault Guard**: Validates telemetry against domain-specific physical thresholds. Identifies out-of-bounds readings and sensor faults (NaN, inf, stuck sensor sentinels) without throwing unhandled exceptions.
- **W3C SOSA / SSN Semantic Export**: Transforms readings into W3C Sensor, Observation, Sample, and Actuation (SOSA) JSON-LD linked data graphs for enterprise knowledge graphs.
- **Offline & Air-gapped**: Runs entirely in-memory using bundled profile definitions in `data/profiles/`. Zero network requests or database connections.

## Bundled Profiles

1. `robotics_kinematics_imu`: Linear acceleration (`m/s2`), angular velocity (`rad/s`), orientation, temperature (`degC`), battery voltage (`V`).
2. `environmental_air_quality`: PM2.5 (`ug/m3`), PM10 (`ug/m3`), CO2 (`ppm`), ambient temperature (`degC`), relative humidity (`%`).
3. `energy_battery_fleet`: High-voltage pack voltage (`V`), current (`A`), state of charge (`%`), cell temperature (`degC`).
4. `smart_building_hvac`: Airflow (`m3/h`), static pressure (`Pa`), zone temperature (`degC`), damper position (`%`).

## Arguments

| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `action` | string | `normalize` | Operation to run: `normalize`, `list_profiles`, or `validate`. |
| `schema_profile` | string | - | Target schema profile name (e.g. `robotics_kinematics_imu`). |
| `raw_telemetry` | array/object | - | Raw sensor reading dictionary or list of reading dictionaries. |
| `unit_system` | string | `si` | Canonical unit standard (`si` or `canonical`). |
| `output_format` | string | `canonical` | Output envelope format: `canonical` or `jsonld`. |

## Output

| Field | Type | Description |
| :--- | :--- | :--- |
| `status` | string | `ready`, `warning`, `insufficient_data`, or `error`. |
| `schema_profile` | string | Applied schema profile. |
| `observations` | array | List of normalized observation records with canonical units and quality flags. |
| `quality_metrics` | object | Aggregate metrics: `total_readings`, `mapped_count`, `out_of_bounds_count`, `sensor_fault_count`, `coverage_score`. |
| `fields_unknown` | array | List of unrecognized telemetry keys. |
| `validation_errors` | array | Non-fatal structural issues or failure messages. |
| `agent_hint` | string | Deterministic, template-based operational hint for host agents. |
| `jsonld_payload` | object | W3C SOSA/SSN JSON-LD graph (when `output_format: "jsonld"`). |
| `error` | string | Failure reason or `null`. |

```json
{
  "status": "ready",
  "schema_profile": "robotics_kinematics_imu",
  "observations": [
    {
      "sensor_id": "imu_chassis_front",
      "observed_at_utc": "2026-10-11T12:00:00.120000Z",
      "phenomenon": "angular_velocity_z",
      "raw_value": 180.0,
      "raw_unit": "deg/s",
      "canonical_value": 3.14159,
      "canonical_unit": "rad/s",
      "quality": "valid"
    }
  ],
  "quality_metrics": {
    "total_readings": 1,
    "mapped_count": 1,
    "out_of_bounds_count": 0,
    "sensor_fault_count": 0,
    "coverage_score": 1.0
  },
  "fields_unknown": [],
  "validation_errors": [],
  "agent_hint": "All 1 telemetry observation(s) in 'robotics_kinematics_imu' are within nominal physical bounds (coverage: 1.0). Standardized to canonical SI units.",
  "jsonld_payload": null,
  "error": null
}
```

## Environment

This skill requires no environment variables, network access, or API keys. See [API keys for skills](../../usage/api_keys.md) for the general setup other skills use.

## Bundle layout

The skill lives in `skills/data_engineering/telemetry_normalizer/`. Roles: [Skill anatomy](../../introduction.md#skill-anatomy). Vocabulary: [glossary](../../glossary.md). **Contract** - see Arguments and Output above. **Assurance** - `test_skill.py` in the bundle.

### Effect (`skill.py`)

Parameter dispatch, profile resolution, envelope wrapping, and error isolation.

### Effect module (`normalizer.py`)

Pure unit transformation math, timestamp scale parsing, physical bounds validation, and SOSA JSON-LD serialization.

### Directive (`instructions.md`)

When to invoke, profile selection rules, status code interpretation, and chaining guidelines.

## Usage Examples

Guides: [Usage index](../../usage/README.md) · [Agent loops](../../usage/agent_loops.md) · [Skill chaining](../../usage/skill_chaining.md) · [Install extras](../../usage/install_extras.md)

### Direct execute

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("data_engineering/telemetry_normalizer")
skill = bundle["class"]()

result = skill.execute({
    "action": "normalize",
    "schema_profile": "robotics_kinematics_imu",
    "raw_telemetry": [
        {
            "node": "imu_chassis_front",
            "t": 1728648000120,
            "gyro_z_dps": 180.0,
            "temp_f": 113.0,
            "v_batt": 24.2,
        }
    ],
})

print(result["status"], result["agent_hint"])
for obs in result["observations"]:
    print(obs["phenomenon"], obs["canonical_value"], obs["canonical_unit"])
```

### Claude (Anthropic Tool Use)

```python
import os
import anthropic
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("data_engineering/telemetry_normalizer")
skill = bundle["class"]()
tool = SkillLoader.to_claude_tool(bundle)
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

response = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=1024,
    tools=[tool],
    messages=[{"role": "user", "content": "Normalize raw IMU telemetry with gyro_z_dps=180.0 and temp_f=113.0."}],
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
bundle = SkillLoader.load_skill("data_engineering/telemetry_normalizer")
skill = bundle["class"]()
openai_tool = SkillLoader.to_openai_tool(bundle)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

response = client.chat.completions.create(
    model="gpt-4o",
    tools=[openai_tool],
    messages=[{"role": "user", "content": "Normalize air quality station telemetry: pm25=18.5, co2_ppm=800.0."}],
)

for call in response.choices[0].message.tool_calls or []:
    result = skill.execute(json.loads(call.function.arguments))
    print(result["status"], result["quality_metrics"]["coverage_score"])
```

### DeepSeek

```python
import json
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("data_engineering/telemetry_normalizer")
skill = bundle["class"]()
deepseek_tool = SkillLoader.to_deepseek_tool(bundle)
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

response = client.chat.completions.create(
    model="deepseek-chat",
    tools=[deepseek_tool],
    messages=[{"role": "user", "content": "Validate HVAC building telemetry for zone 3 conference room."}],
)

for call in response.choices[0].message.tool_calls or []:
    print(skill.execute(json.loads(call.function.arguments))["status"])
```

### Ollama (prompt mode)

```python
import json
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("data_engineering/telemetry_normalizer")
skill = bundle["class"]()
prompt = (
    "You may call tools as JSON blocks.\n"
    f"Tool: {bundle['manifest']['name']}\n"
    f"Instructions:\n{bundle['instructions']}\n"
    "User: Normalize battery pack voltage 680V and current 45A."
)
print(prompt)
result = skill.execute({
    "action": "normalize",
    "schema_profile": "energy_battery_fleet",
    "raw_telemetry": {"voltage": 680.0, "current": 45.0, "time": "2026-10-12T09:15:00Z"},
})
print(json.dumps(result, indent=2))
```

### Gemini

```python
import os
import google.genai as genai
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("data_engineering/telemetry_normalizer")
tool = SkillLoader.to_gemini_tool(bundle)
skill = bundle["class"]()
client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Normalize robot chassis IMU telemetry: accel_z=9.81, gyro_z_dps=180.0.",
    config=genai.types.GenerateContentConfig(tools=[tool]),
)

tool_name = SkillLoader._sanitize_gemini_tool_name(bundle["manifest"]["name"])
for part in response.candidates[0].content.parts:
    if part.function_call and part.function_call.name == tool_name:
        print(skill.execute(dict(part.function_call.args))["status"])
```

---

<!-- skill-history:begin -->
## Skill history

Commits that touched this skill bundle or its catalog page ([`data_engineering/telemetry_normalizer`](https://github.com/ARPAHLS/skillware/tree/main/skills/data_engineering/telemetry_normalizer)).

| Commit | Description | Date | Version | Contributors |
| :--- | :--- | :--- | :--- | :--- |
| [`47f10a1`](https://github.com/ARPAHLS/skillware/commit/47f10a1) | feat(data_engineering): add telemetry_normalizer skill for sensor harmonization (#47) | 12 Oct 2026 | `0.1.0` | [@rin-katsuragi](https://github.com/rin-katsuragi) |
<!-- skill-history:end -->

## Enterprise disclaimer

This skill is provided for demonstration and integration purposes. It is intended as a starting point that you can adapt to your own data, schemas, and operational requirements. For an enterprise-grade version of this skill with dedicated support, SLAs, and customization, contact skills@arpacorp.net.
