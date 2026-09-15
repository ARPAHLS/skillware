# Integration Guide: Google Vertex AI (Gemini)

Vertex AI Gemini models use the **same tool schema** as the Gemini API. Use `SkillLoader.to_gemini_tool()` — no separate Skillware adapter. Auth and client init differ from the consumer API key path.

## Install

```bash
pip install "skillware[gemini]"
pip install "skillware[<category>_<skill>]"
```

## Client pattern

Use Application Default Credentials (ADC) on GCE, GKE, or Cloud Run, or set `GOOGLE_APPLICATION_CREDENTIALS` for a service account key file.

```python
import os

import google.genai as genai
from google.genai import types

from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()

bundle = SkillLoader.load_skill("finance/wallet_screening")
skill = bundle["class"](
    config={"ETHERSCAN_API_KEY": os.environ.get("ETHERSCAN_API_KEY")}
)
tool = SkillLoader.to_gemini_tool(bundle)

client = genai.Client(
    vertexai=True,
    project=os.environ["GOOGLE_CLOUD_PROJECT"],
    location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
)

response = client.models.generate_content(
    model=os.environ["VERTEX_GEMINI_MODEL"],
    contents="Screen wallet 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045.",
    config=types.GenerateContentConfig(
        tools=[tool],
        system_instruction=bundle["instructions"],
    ),
)
```

Handle `function_call` parts and `skill.execute()` as in [gemini.md](gemini.md).

## Environment

| Variable | Purpose |
| :--- | :--- |
| `GOOGLE_CLOUD_PROJECT` | GCP project ID |
| `GOOGLE_CLOUD_LOCATION` | Region (for example `us-central1`) |
| `VERTEX_GEMINI_MODEL` | Vertex model resource ID |
| Skill `env_vars` | Separate — see catalog page |

## Hosting

Run Skillware on Compute Engine, GKE, or Cloud Run — `pip install skillware`, attach a service account with Vertex access, use ADC. See [enterprise_cloud.md](enterprise_cloud.md).

## Related

- [Enterprise cloud overview](enterprise_cloud.md)
- [Gemini guide (API key path)](gemini.md)
- [Install extras](install_extras.md)
- [Vertex AI Gemini docs](https://cloud.google.com/vertex-ai/generative-ai/docs)
