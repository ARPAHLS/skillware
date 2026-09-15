# Integration Guide: Azure OpenAI

Azure OpenAI deployments use the **OpenAI Chat Completions tools schema**. Use `SkillLoader.to_openai_tool()` — no separate Skillware adapter.

## Install

```bash
pip install "skillware[openai]"
pip install "skillware[<category>_<skill>]"
```

## Client pattern

```python
import os

from openai import AzureOpenAI

from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()

bundle = SkillLoader.load_skill("compliance/tos_evaluator")
skill = bundle["class"]()
tool = SkillLoader.to_openai_tool(bundle)

client = AzureOpenAI(
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
)

response = client.chat.completions.create(
    model=os.environ["AZURE_OPENAI_DEPLOYMENT"],
    messages=[
        {"role": "system", "content": bundle["instructions"]},
        {"role": "user", "content": "Check https://example.com/robots.txt compliance."},
    ],
    tools=[tool],
)
```

Handle `tool_calls` and `skill.execute()` as in [openai.md](openai.md) and [agent_loops.md](agent_loops.md).

## Environment

| Variable | Purpose |
| :--- | :--- |
| `AZURE_OPENAI_API_KEY` | API key (or use `DefaultAzureCredential` with Azure identity — configure in your host app) |
| `AZURE_OPENAI_ENDPOINT` | Resource endpoint URL |
| `AZURE_OPENAI_DEPLOYMENT` | Deployment name for your model |
| `AZURE_OPENAI_API_VERSION` | API version string |

Confirm your deployment supports **function / tool calling** in the Azure model catalog.

## Hosting

Run Skillware on Azure VM, App Service, or AKS the same way as any Python app — see [enterprise_cloud.md](enterprise_cloud.md).

## Related

- [Enterprise cloud overview](enterprise_cloud.md)
- [OpenAI guide](openai.md)
- [OpenAI-compatible hosts](openai_compatible.md)
- [Install extras](install_extras.md)
- [Microsoft Azure OpenAI documentation](https://learn.microsoft.com/en-us/azure/ai-services/openai/)
