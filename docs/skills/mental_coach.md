# Mental Coach

**Domain:** `wellness`
**Skill ID:** `wellness/mental_coach`
**Issuer:** [@mrmasa88](https://github.com/mrmasa88) (AO) · **Contact:** masa88keith@gmail.com

[Skill Library](README.md) · [Testing](../TESTING.md)

Deterministic wellness coaching guardrail for host agents. Runs crisis triage before retrieval, blocks clinical overreach, retrieves grounded KB chunks with citations, and optionally runs a Gemini scope evaluator.

> **Health disclaimer:** This skill provides general wellness support and information only. It is not medical, psychological, or clinical advice and is not a substitute for care from a licensed professional. Use at your own discretion. Active safety guardrails (deterministic crisis gate and hard constraints) reduce risk but do not replace professional judgment; double-check results and treat output as everyday coping guidance, not medical advice. In a crisis or emergency, contact local emergency services or the crisis resources returned by the skill.

## What It Does

1. **Crisis gate (deterministic, first)** — detects danger signals and returns escalation guidance instead of coaching.
2. **Hard constraints** — blocks diagnosis, medication advice, and clinical interpretation requests.
3. **Grounded retrieval** — jurisdiction- and session-aware chunks from the embedded public KB.
4. **Optional evaluator** — lightweight Gemini audit when `run_evaluator` is enabled.

Supportive coaching and psychoeducation only. Not emergency services, telehealth, or licensed care.

## Parameters

| Parameter | Required | Notes |
| :--- | :--- | :--- |
| `user_prompt` | Yes | User message or coaching request |
| `user_jurisdiction` | No | `US`, `EU`, `UK`, `FR`, `DE`, `ES`, `IT`, `GLOBAL`, or `unknown` |
| `session_mode` | No | `coaching`, `information`, or `crisis_check` |
| `run_evaluator` | No | Optional LLM scope audit |
| `evaluator_model` | No | Default `gemini-2.5-flash-lite` |
| `max_chunks` | No | Max KB chunks (cap 15) |

## Environment

| Variable | Required | Purpose |
| :--- | :--- | :--- |
| `GOOGLE_API_KEY` | No | Optional scope evaluator when `run_evaluator` is enabled |

Configure values per [API keys for skills](../usage/api_keys.md). Core crisis and coaching paths do not require a cloud API key.

## Example Usage (Direct)

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("wellness/mental_coach")
skill = bundle["module"].MentalCoachSkill()

result = skill.execute(
    {
        "user_prompt": "I feel stressed at work and need coping strategies.",
        "user_jurisdiction": "US",
        "session_mode": "coaching",
        "run_evaluator": False,
    }
)

print(result["policy_status"])
print(result["citations"])
print(result["final_context_for_agent"])
```

## Runnable Example

See [examples/mental_coach_demo.py](../../examples/mental_coach_demo.py) for local execute demos (coaching, crisis, blocked clinical).

## Usage Examples

Guides: [Usage index](../usage/README.md) · [Agent loops](../usage/agent_loops.md) · [API keys](../usage/api_keys.md) (optional `GOOGLE_API_KEY` for evaluator).

Sample user message: *I feel stressed at work and need coping strategies.*

### Gemini

```python
import google.genai as genai
from google.genai import types
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("wellness/mental_coach")
skill = bundle["module"].MentalCoachSkill()
tool = SkillLoader.to_gemini_tool(bundle)
client = genai.Client()
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="I feel stressed at work and need coping strategies.",
    config=types.GenerateContentConfig(
        tools=[tool],
        system_instruction=bundle["instructions"],
    ),
)
for part in response.candidates[0].content.parts:
    if part.function_call:
        result = skill.execute(dict(part.function_call.args))
        print(result["policy_status"], result["final_context_for_agent"])
```

### Claude

```python
import anthropic
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("wellness/mental_coach")
skill = bundle["module"].MentalCoachSkill()
client = anthropic.Anthropic()
tools = [SkillLoader.to_claude_tool(bundle)]
# On tool_use (name wellness/mental_coach): skill.execute(tool_use.input)
```

### OpenAI

```python
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("wellness/mental_coach")
skill = bundle["module"].MentalCoachSkill()
client = OpenAI()
openai_tool = SkillLoader.to_openai_tool(bundle)
# Match tool_call.function.name (wellness_mental_coach)
```

### DeepSeek

```python
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("wellness/mental_coach")
skill = bundle["module"].MentalCoachSkill()
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
deepseek_tool = SkillLoader.to_deepseek_tool(bundle)
```

### Ollama

`SkillLoader.to_ollama_prompt(bundle)`; match `"tool": "wellness/mental_coach"`.
See [Ollama usage](../usage/ollama.md).

## Output Semantics

- `ESCALATE` — crisis signals detected; coaching suppressed; resources provided.
- `BLOCKED` — clinical request declined; non-clinical alternatives only.
- `CAUTION` — proceed gently with disclaimers and optional resources.
- `OK` — coaching path with grounded citations.

Always include `disclaimers_required` in the user-facing reply.

## Limitations

- English-first v0.1; non-English input routes to CAUTION with resources.
- Public KB only; no private corpus in the published package.
- Crisis gate uses conservative keyword signals; over-escalation is intentional.
