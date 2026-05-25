# Novelty Extractor Skill

**Domain:** `data_engineering`
**Skill ID:** `data_engineering/novelty_extractor`
**Issuer:** [@rizzoMartin](https://github.com/rizzoMartin)

[Skill Library](README.md) - [Testing](../TESTING.md)

A data engineering skill that filters large text datasets by semantic novelty,
retaining only chunks that carry genuinely new information above a configurable
similarity threshold. Useful for dataset curation, training data distillation,
and multi-turn corpus processing.

## Capabilities

- **Local embeddings**: Uses `fastembed` with the `BAAI/bge-small-en-v1.5` model.
  No API key required. No cloud dependency.
- **Configurable threshold**: The `novelty_threshold` parameter controls how
  strict the filtering is. Lower values mean stricter filtering.
- **Stateless multi-turn support**: Pass `distilled_content` from a previous
  call as `baseline_chunks` to filter consistently across turns without hidden
  global state.
- **Pluggable chunking**: Supports `paragraph` (default) and `sentence`
  strategies, with an extensible design for future strategies.

## Internal Architecture

The skill is located in `skills/data_engineering/novelty_extractor/`.

### 1. The Mind (`instructions.md`)
Explains when to invoke the skill, how to interpret outputs, and how to handle
multi-turn filtering by passing `distilled_content` as `baseline_chunks`.

### 2. The Body (`skill.py`)
- **Chunking**: Splits input text using the configured strategy before embedding.
- **Embedding**: Embeds all chunks in a single batch call using `fastembed`
  (`BAAI/bge-small-en-v1.5`, ~50 MB, downloaded on first use).
- **Filtering**: Computes cosine similarity between each chunk vector and all
  previously seen vectors. Chunks below `novelty_threshold` are kept.
- **Baseline**: Embeds `baseline_chunks` at the start of each call to seed
  the seen-vectors list for cross-turn deduplication.

## Integration Guide

### Dependencies

This skill requires `fastembed` and `numpy`. Install them before loading:

```bash
pip install fastembed numpy
```

On first use, `fastembed` downloads the `BAAI/bge-small-en-v1.5` model (~50 MB)
to a local cache. Subsequent calls reuse the cached model.

### Environment

This skill requires no API keys or environment variables.

## Usage Examples

Guides: [Usage index](../usage/README.md) - [Agent loops](../usage/agent_loops.md).

Sample user message: *Filter this dataset and keep only the chunks that contain new information.*

### Direct execute

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("data_engineering/novelty_extractor")
skill = bundle["module"].NoveltyExtractor()

result = skill.execute({
    "dataset_chunk": "Bitcoin is going to rise.\n\nBitcoin will increase.\n\nThe sky is blue.",
    "novelty_threshold": 0.85,
})
print(result["distilled_content"])
print(result["compression_ratio"])
print(result["redundant_chunks_dropped"])
```

### Multi-turn filtering

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("data_engineering/novelty_extractor")
skill = bundle["module"].NoveltyExtractor()

result1 = skill.execute({
    "dataset_chunk": "first batch of text...",
    "novelty_threshold": 0.85,
})

result2 = skill.execute({
    "dataset_chunk": "second batch of text...",
    "novelty_threshold": 0.85,
    "baseline_chunks": result1["distilled_content"],
})

full_distilled = result1["distilled_content"] + "\n\n" + result2["distilled_content"]
```

### Gemini

```python
import google.genai as genai
from google.genai import types
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("data_engineering/novelty_extractor")
skill = bundle["module"].NoveltyExtractor()
client = genai.Client()
tool = SkillLoader.to_gemini_tool(bundle)
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Filter this dataset and keep only novel chunks.",
    config=types.GenerateContentConfig(
        tools=[tool],
        system_instruction=bundle["instructions"],
    ),
)
for part in response.candidates[0].content.parts:
    if part.function_call:
        result = skill.execute(dict(part.function_call.args))
        print(result["distilled_content"])
```

### Claude

```python
import anthropic
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("data_engineering/novelty_extractor")
skill = bundle["module"].NoveltyExtractor()
client = anthropic.Anthropic()
tools = [SkillLoader.to_claude_tool(bundle)]
# On tool_use (name data_engineering/novelty_extractor): skill.execute(tool_use.input)
```

### OpenAI

```python
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("data_engineering/novelty_extractor")
skill = bundle["module"].NoveltyExtractor()
client = OpenAI()
openai_tool = SkillLoader.to_openai_tool(bundle)
# Match tool_call.function.name (data_engineering_novelty_extractor)
```

### DeepSeek

```python
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("data_engineering/novelty_extractor")
skill = bundle["module"].NoveltyExtractor()
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
deepseek_tool = SkillLoader.to_deepseek_tool(bundle)
```

### Ollama

`SkillLoader.to_ollama_prompt(bundle)`; match `"tool": "data_engineering/novelty_extractor"`.
See [Ollama usage](../usage/ollama.md).

## Output Schema

```json
{
  "distilled_content": "Novel chunks joined by double newline.",
  "compression_ratio": "33.3%",
  "redundant_chunks_dropped": 1
}
```

On error:

```json
{
  "error": "Description of what went wrong.",
  "distilled_content": "",
  "compression_ratio": "0%",
  "redundant_chunks_dropped": 0
}
```

## Limitations

- **First-run model download**: `fastembed` downloads `BAAI/bge-small-en-v1.5`
  (~50 MB) on first use. Subsequent calls use the local cache.
- **Stateless by design**: The skill does not accumulate results across calls.
  The caller is responsible for passing `distilled_content` as `baseline_chunks`
  and for concatenating results across turns.
- **English-optimized model**: `BAAI/bge-small-en-v1.5` performs best on English
  text. Results on other languages may vary.
- **Threshold sensitivity**: Results depend on the chosen `novelty_threshold`.
  A value between 0.80 and 0.90 works well for most corpora.