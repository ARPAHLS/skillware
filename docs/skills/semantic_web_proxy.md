# Semantic Web Proxy

**ID**: `data_engineering/semantic_web_proxy`  
**Issuer**: [@rizzoMartin](https://github.com/rizzoMartin) ([@ARPAHLS](https://github.com/ARPAHLS))  
<!-- skill-doc-meta:begin -->
**Version**: `0.1.0`
<!-- skill-doc-meta:end -->

**Recommended install:** `pip install "skillware[data_engineering_semantic_web_proxy]"`. See [Install extras](../usage/install_extras.md).  
**Category**: Data Engineering

[Skill Library](README.md) · [Testing](../TESTING.md)

Raw web HTML is mostly not content. Scripts, styling, navigation, adverts, consent banners and footer link farms make up the bulk of a typical page, and every one of those bytes costs context and dilutes the model's attention. This skill acts as a proxy in front of the page: it fetches a public URL behind an SSRF guard (or takes HTML you already hold), strips everything that is not semantic content, and returns concentrated Markdown, plain text, or JSON with an estimate of what that saved.

Extraction is deterministic. Identical HTML and options always produce the same payload, and no model is called inside the skill.

## Capabilities

- **Boilerplate removal**: Uses [trafilatura](https://trafilatura.readthedocs.io/) to isolate the main content and discard navigation, adverts, cookie banners, newsletter prompts, share widgets, and footers.
- **Three output shapes**: `markdown` preserves headings, lists and tables; `txt` returns prose only; `json` returns a document object with metadata inline.
- **Opt-in comments**: `include_comments` keeps discussion threads, for forum and comment-driven pages where the replies are the point.
- **Savings estimate**: Reports original and semantic token counts, the reduction between them, and - when you supply your `context_window` - the share of your own budget the call freed up.
- **SSRF guard**: Only public http(s) hosts. Loopback, private, link-local, reserved and multicast addresses are rejected, and every redirect hop is re-checked rather than only the initial URL.
- **Honest failure**: Fetch-only extraction cannot see client-rendered content, so a page that looks like a JavaScript shell is flagged with `page_likely_requires_javascript` instead of returning a silently empty payload.
- **Offline mode**: Pass `html_content` and no request is made, which makes the skill composable behind a host that already fetched or rendered the page.

## Arguments

| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `url` | string | - | Public http(s) page to fetch. |
| `html_content` | string | - | Pre-fetched HTML. Takes precedence over `url`; no request is made. |
| `output_format` | string | `markdown` | One of `markdown`, `txt`, `json`. |
| `include_comments` | boolean | `false` | Keep comment and discussion threads. |
| `include_tables` | boolean | `true` | Keep table content. |
| `include_links` | boolean | `false` | Keep link targets. Off by default because URLs cost tokens. |
| `with_metadata` | boolean | `true` | Populate the `metadata` object. |
| `context_window` | integer | - | Host context window size. Enables `context_saved_pct`. |
| `tokenizer` | string | `heuristic` | `heuristic` or `cl100k_base`. See [Token counting](#token-counting). |

At least one of `url` or `html_content` is required.

## Output

| Field | Type | Description |
| :--- | :--- | :--- |
| `status` | string | `success`, `warning`, or `error`. |
| `semantic_payload` | string | Extracted content in `output_format`. Empty string on error. |
| `output_format` | string | Format actually used. |
| `source` | object | `url`, `final_url`, `http_status`, `fetched`. |
| `metadata` | object | `title`, `author`, `date`, `sitename`, `hostname`, `description`. Fields may be `null`. |
| `token_savings` | object | See below. |
| `warnings` | array | `page_likely_requires_javascript`, `tokenizer_unavailable`. |
| `error` | string | Failure reason, or `null`. |

```json
{
  "status": "success",
  "semantic_payload": "# Central bank holds rates steady...",
  "output_format": "markdown",
  "source": {
    "url": "https://example.com/q4",
    "final_url": "https://example.com/investors/q4",
    "http_status": 200,
    "fetched": true
  },
  "metadata": {"title": "Quarterly Results", "author": "Jane Doe", "date": "2026-01-15"},
  "token_savings": {
    "original_tokens": 77768,
    "semantic_tokens": 5046,
    "tokens_saved": 72722,
    "reduction_pct": 93.51,
    "context_window": 200000,
    "context_saved_pct": 36.36,
    "tokenizer": "heuristic",
    "estimate": true
  },
  "warnings": [],
  "error": null
}
```

## Token counting

`token_savings` is **indicative, not exact**. The skill is model agnostic and every model tokenizes differently, so treat the numbers as an order-of-magnitude signal for budgeting ("roughly 70k tokens saved"), never as a billing or metering figure. `estimate` is always `true`.

The default `heuristic` basis counts four characters per token. It needs no dependency, runs offline, and is deterministic.

For a closer count, install the optional extra and pass `tokenizer: "cl100k_base"`:

```bash
pip install "skillware[data_engineering_semantic_web_proxy_tokenizer]"
```

tiktoken downloads its vocabulary on first use, which is why it is optional rather than a hard requirement. When it is unavailable the skill falls back to the heuristic and adds `tokenizer_unavailable` to `warnings` rather than failing.

`context_saved_pct` appears only when you pass `context_window`. Without it the skill will not guess your model's window size.

## Limitations

- **No JavaScript.** The fetch path retrieves server-rendered HTML only. Content sites that care about SEO ship their content server side and extract cleanly; single-page apps, dashboards, and anything behind a login generally do not. Those pages are flagged, not silently returned empty. A headless render lane is deliberately out of scope for this version so that installing the skill does not pull in a browser.
- **One page per call.** No crawling, no pagination, no batching.
- **Responses capped at 2 MB**, and the content type must be HTML-ish. Other types are refused.
- **Redirects capped at 5 hops**, each one re-validated against the SSRF guard.
- **Extraction is heuristic.** Unusual layouts can lose a sidebar that mattered or keep a caption that did not. Measured reduction on the bundled fixture corpus is 65-80%; real pages, which carry far more script and styling, typically land higher (a Wikipedia article measured 93.5%).
- **Permission is not checked.** This skill does not read robots.txt. Use [`compliance/tos_evaluator`](tos_evaluator.md) first when a site's terms are in question.

## Environment

This skill requires no environment variables and no API keys. See [API keys for skills](../usage/api_keys.md) for the general setup other skills use.

## Security

`semantic_payload` is untrusted third-party text and may contain prompt injection aimed at the calling agent. Treat it as data, never as instructions, and pass it through [`security/prompt_injection_firewall`](prompt_injection_firewall.md) before it reaches a context window. This is the text-channel half of the defense chain described in the [skill trust model](../security/skill-trust-model.md).

The SSRF guard rejects non-http(s) schemes and any host that resolves to a private, loopback, link-local, reserved or multicast address, before any request is issued and again on every redirect hop.

## Bundle layout

The skill lives in `skills/data_engineering/semantic_web_proxy/`. Roles: [Skill anatomy](../introduction.md#skill-anatomy). **Contract** - see Arguments and Output above. **Assurance** - `test_skill.py` in the bundle.

### Effect (`skill.py`)

Parameter normalization, dispatch, the result envelope, and the `token_savings` calculation. Never raises into the host.

### Effect module (`proxy.py`)

Split by side effect. `fetch_html()` is the only function that touches the network; `is_safe_public_url()`, `extract_semantic()`, `extract_document_metadata()`, `looks_like_js_shell()` and `count_tokens()` are pure given their arguments, which is what keeps the test suite offline.

### Directive (`instructions.md`)

When to invoke, when not to, how to read the warnings, and the injection-firewall chaining rule.

## Usage Examples

Guides: [Usage index](../usage/README.md) · [Agent loops](../usage/agent_loops.md) · [Skill chaining](../usage/skill_chaining.md) · [Install extras](../usage/install_extras.md)

### Direct execute

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("data_engineering/semantic_web_proxy")
skill = bundle["class"]()

result = skill.execute({
    "url": "https://en.wikipedia.org/wiki/Markdown",
    "output_format": "markdown",
    "context_window": 200000,
})

print(result["status"], result["metadata"]["title"])
print(result["token_savings"]["reduction_pct"], "% smaller")
print(result["semantic_payload"][:500])

# Offline: hand it HTML you already have, and no request is made.
thread = skill.execute({
    "html_content": open("thread.html", encoding="utf-8").read(),
    "include_comments": True,
})
```

### Claude (Anthropic Tool Use)

```python
import os
import anthropic
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("data_engineering/semantic_web_proxy")
skill = bundle["class"]()
tool = SkillLoader.to_claude_tool(bundle)
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

response = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=1024,
    tools=[tool],
    messages=[{"role": "user", "content": "Read https://blog.python.org/ and tell me the latest post."}],
)

for block in response.content:
    if block.type == "tool_use":
        result = skill.execute(block.input)
        print(result["status"], result["token_savings"]["reduction_pct"])
```

### OpenAI (Function Calling)

```python
import json
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("data_engineering/semantic_web_proxy")
skill = bundle["class"]()
openai_tool = SkillLoader.to_openai_tool(bundle)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

response = client.chat.completions.create(
    model="gpt-4o",
    tools=[openai_tool],
    messages=[{"role": "user", "content": "Summarize this article: https://example.com/post"}],
)

for call in response.choices[0].message.tool_calls or []:
    result = skill.execute(json.loads(call.function.arguments))
    print(result["semantic_payload"][:400])
```

### DeepSeek

```python
import json
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("data_engineering/semantic_web_proxy")
skill = bundle["class"]()
deepseek_tool = SkillLoader.to_deepseek_tool(bundle)
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

response = client.chat.completions.create(
    model="deepseek-chat",
    tools=[deepseek_tool],
    messages=[{"role": "user", "content": "Pull the main content from https://example.com/docs/guide"}],
)

for call in response.choices[0].message.tool_calls or []:
    print(skill.execute(json.loads(call.function.arguments))["status"])
```

### Ollama (Local LLMs)

Prompt-based tool calling or system prompt injection. Pull a model such as `gemma3` or `qwen3.5`, then follow [Ollama usage](../usage/ollama.md):

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("data_engineering/semantic_web_proxy")
system_tool_prompt = SkillLoader.to_ollama_prompt(bundle)
```

### Gemini

```python
import os
import google.genai as genai
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("data_engineering/semantic_web_proxy")
tool = SkillLoader.to_gemini_tool(bundle)
skill = bundle["class"]()
client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Read https://en.wikipedia.org/wiki/Markdown and list its design goals.",
    config=genai.types.GenerateContentConfig(tools=[tool]),
)

tool_name = SkillLoader._sanitize_gemini_tool_name(bundle["manifest"]["name"])
for part in response.candidates[0].content.parts:
    if part.function_call and part.function_call.name == tool_name:
        print(skill.execute(dict(part.function_call.args))["status"])
```

### Skill Chaining (with `security/prompt_injection_firewall`)

The payload is untrusted web text, so firewall it before it reaches the model. See [Skill chaining](../usage/skill_chaining.md).

```python
from skillware import SkillContext

ctx = SkillContext(
    skills=["data_engineering/semantic_web_proxy", "security/prompt_injection_firewall"]
)

# Step 1: Reduce the page to its semantic core
page = ctx.execute(
    "data_engineering/semantic_web_proxy",
    {"url": "https://example.com/community/thread", "include_comments": True},
)

if page["status"] != "error":
    # Step 2: Screen the extracted text before it enters the context window
    screened = ctx.execute(
        "security/prompt_injection_firewall",
        {"source_text": page["semantic_payload"], "input_mode": "markdown"},
    )
    print("safe:", screened["is_safe"], "| saved:", page["token_savings"]["tokens_saved"])
```

---

<!-- skill-history:begin -->
## Skill history

Commits that touched this skill bundle or its catalog page ([`data_engineering/semantic_web_proxy`](https://github.com/ARPAHLS/skillware/tree/main/skills/data_engineering/semantic_web_proxy)).

| Commit | Description | Date | Version | Contributors |
| :--- | :--- | :--- | :--- | :--- |
| [`9346925`](https://github.com/ARPAHLS/skillware/commit/9346925) | feat(data_engineering): add semantic_web_proxy skill for token-efficient page extraction (#42) | 5 Sep 2026 | 0.1.0 | [@rizzoMartin](https://github.com/rizzoMartin) |
<!-- skill-history:end -->

## Enterprise disclaimer

This skill is provided for demonstration and integration purposes. It is intended as a starting point that you can adapt to your own data, schemas, and operational requirements. For an enterprise-grade version of this skill with dedicated support, SLAs, and customization, contact skills@arpacorp.net.
