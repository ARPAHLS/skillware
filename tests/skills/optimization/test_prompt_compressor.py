import pytest
from skillware.core.loader import SkillLoader

_PROMPT = """Please   review the following code and tell me what is wrong.


Make sure to check for bugs as well as a lot of style issues.
Note that the function `parse_config()` is able to read files in order to build the config.
Due to the fact that it is really very slow, please utilize caching! See https://example.com/docs for details.
---
Keep your answer short and clear.
Keep your answer short and clear."""

_LOSSLESS = """Please review the following code and tell me what is wrong.

Make sure to check for bugs as well as a lot of style issues.
Note that the function `parse_config()` is able to read files in order to build the config.
Due to the fact that it is really very slow, please utilize caching! See https://example.com/docs for details.
---
Keep your answer short and clear.
Keep your answer short and clear."""

_BALANCED = """Review the following code and tell me what is wrong.

Check for bugs and many style issues.
The function `parse_config()` can read files to build the config.
Because it is really very slow, use caching! See https://example.com/docs for details.
---
Keep your answer short and clear.
Keep your answer short and clear."""

_AGGRESSIVE = """Review following code and tell me what is wrong.

Check for bugs and many style issues.
The function `parse_config()` can read files to build config.
Because it is slow, use caching See https://example.com/docs for details.

Keep your answer short and clear."""

old_skill_path = "optimization/prompt_rewriter"
new_skill_path = "optimization/prompt_compressor"


def get_skill():
    old_bundle = SkillLoader.load_skill(old_skill_path)
    new_bundle = SkillLoader.load_skill(new_skill_path)
    assert old_bundle["manifest"]["name"] == new_bundle["manifest"]["name"]
    return new_bundle["module"].PromptCompressor()

def test_manifest_schema():
    skill = get_skill()
    manifest = skill.manifest
    assert manifest.get("name") == new_skill_path
    assert manifest.get("version") == "0.1.0"


def test_compressor_execution_lossless():
    skill = get_skill()
    old_params = {
        "action": "compress_prompt",
        "raw_text": _PROMPT,
        "compression_aggression": "low",
    }
    new_params = {
        "action": "compress_prompt",
        "text": _PROMPT,
        "mode": "lossless",
    }
    old_result = skill.execute(old_params)
    result = skill.execute(new_params)
    assert old_result["compressed_text"] == result["compressed_text"]
    assert result["compressed_text"] == _LOSSLESS
    assert result["original_tokens"] >= result["compressed_tokens"]


def test_compressor_execution_balanced():
    skill = get_skill()
    old_params = {
        "action": "compress_prompt",
        "raw_text": _PROMPT,
        "compression_aggression": "medium",
    }
    new_params = {
        "action": "compress_prompt",
        "text": _PROMPT,
        "mode": "medium",
    }
    old_result = skill.execute(old_params)
    result = skill.execute(new_params)
    assert old_result["compressed_text"] == result["compressed_text"]
    assert result["compressed_text"] == _BALANCED
    assert result["original_tokens"] >= result["compressed_tokens"]


def test_compressor_execution_aggressive():
    skill = get_skill()
    old_params = {
        "action": "compress_prompt",
        "raw_text": _PROMPT,
        "compression_aggression": "high",
    }
    new_params = {
        "action": "compress_prompt",
        "text": _PROMPT,
        "mode": "aggressive",
    }
    old_result = skill.execute(old_params)
    result = skill.execute(new_params)
    assert old_result["compressed_text"] == result["compressed_text"]
    assert result["status"] == "ready"
    assert "Please" not in result["compressed_text"]
    assert "make sure to" not in result["compressed_text"]
    assert result["tokens_saved"] > 0
    assert "compressed_tokens" in result
    assert "original_tokens" in result
    assert result["compressed_text"] == _AGGRESSIVE


def test_protected_blocks():
    skill = get_skill()
    params = {
        "action": "compress_prompt",
        "text": "Just  really   use the `the_helper` fn and {{user_name}} in <b>the</b> template ${HOME}!",
        "mode": "aggressive",
    }

    result = skill.execute(params)
    assert result["compressed_text"] == "use `the_helper` fn and {{user_name}} in <b>the</b> template ${HOME}"
    assert result["status"] == "ready"
    assert "compressed_tokens" in result
    assert "original_tokens" in result


def test_cache_optimized():
    skill = get_skill()
    params = {
        "action": "compress_prompt",
        "mode": "cache_optimized",
        "text": "<system>You are a helpful assistant. Please be concise, and make sure to answer in order to help the user.</system>\n\nCould you summarize the following article in order to help me prepare for a number of meetings? See [https://example.com/a](https://example.com/a) for the source."
    }

    result = skill.execute(params)
    assert result["status"] == "ready"
    print(result["compressed_text"])
    assert result["compressed_text"] == """<system>You are a helpful assistant. Please be concise, and make sure to answer in order to help the user.</system>

Summarize the following article to help me prepare for several meetings? See [https://example.com/a](https://example.com/a) for the source."""


def test_system_blocks_after_dynamic_content_warn():
    skill = get_skill()
    params = {
        "action": "compress_prompt",
        "mode": "cache_optimized",
        "text": "Context: user is in Paris.\n\n<system>Be concise.</system>\n\nCould you list sights?"
    }

    result = skill.execute(params)
    assert result["status"] == "ready"
    assert result["compressed_text"] == """Context: user is in Paris.

<system>Be concise.</system>

List sights?"""


def test_empty_string_returns_error():
    skill = get_skill()
    result = skill.execute({
        "action": "compress_prompt",
        "text": ""
    })
    assert result["status"] == "error"
    assert result["error"] == "text cannot be empty."


def test_leading_system_block_detected_as_cache_prefix():
    skill = get_skill()
    params = {
        "action": "compress_prompt",
        "mode": "cache_optimized",
        "text": (
            "<system>You are a helpful assistant.</system>\n\n"
            "Could you please summarize this article?"
        )
    }

    result = skill.execute(params)

    assert result["status"] == "ready"
    assert result["compressed_text"].startswith(
        "<system>You are a helpful assistant.</system>"
    )


def test_protect_code_blocks_default():
    skill = get_skill()
    code = """def hello():
    print("Hello, world!")
    return True"""

    params = {
        "action": "compress_prompt",
        "text": f"Please review this code:\n\n```python\n{code}\n```\n\nCould you explain it?",
        "mode": "aggressive",
    }

    result = skill.execute(params)

    assert f"```python\n{code}\n```" in result["compressed_text"]
    assert result["status"] == "ready"


def test_protect_code_blocks_disabled():
    skill = get_skill()
    code = """def hello():
    print("Hello, world!")
    return True"""

    params = {
        "action": "compress_prompt",
        "text": f"Please review this code:\n\n```python\n{code}\n```\n\nCould you explain it?",
        "mode": "aggressive",
        "protect_code_blocks": False,
    }

    result = skill.execute(params)

    assert "```python" not in result["compressed_text"] or (
            f"```python\n{code}\n```" not in result["compressed_text"]
    )
    assert result["status"] == "ready"


def test_protect_inline_code_default():
    skill = get_skill()
    params = {
        "action": "compress_prompt",
        "text": "Please use `the_helper` function to process the data.",
        "mode": "aggressive",
    }

    result = skill.execute(params)

    assert "`the_helper`" in result["compressed_text"]
    assert result["protected_blocks_count"] == 1
    assert result["status"] == "ready"


def test_protect_inline_code_disabled():
    skill = get_skill()
    params = {
        "action": "compress_prompt",
        "text": "Please use `the_helper` function to process the data.",
        "mode": "aggressive",
        "protect_code_blocks": False,
    }

    result = skill.execute(params)

    assert result["status"] == "ready"
    assert result["protected_blocks_count"] == 0


def test_protect_templates_default():
    skill = get_skill()
    params = {
        "action": "compress_prompt",
        "text": (
            "Please use {{user_name}}, {user_id}, "
            "${HOME}, and <user>John</user> in the template."
        ),
        "mode": "aggressive",
    }

    result = skill.execute(params)

    assert "{{user_name}}" in result["compressed_text"]
    assert "{user_id}" in result["compressed_text"]
    assert "${HOME}" in result["compressed_text"]
    assert "<user>" in result["compressed_text"]
    assert "</user>" in result["compressed_text"]
    assert result["status"] == "ready"


def test_protect_templates_disabled():
    skill = get_skill()
    params = {
        "action": "compress_prompt",
        "text": "Please use {user_id} and <user>John</user> in the template.",
        "mode": "aggressive",
        "protect_templates": False,
    }

    result = skill.execute(params)
    assert result["status"] == "ready"

    assert result["protected_blocks_count"] == 0


def test_protect_templates_does_not_disable_urls_and_emails():
    skill = get_skill()
    params = {
        "action": "compress_prompt",
        "text": "Visit [https://example.com](https://example.com) and contact test@example.com.",
        "mode": "aggressive",
        "protect_templates": False,
    }

    result = skill.execute(params)

    assert "[https://example.com](https://example.com)" in result["compressed_text"]
    assert "test@example.com" in result["compressed_text"]
    assert result["status"] == "ready"


def test_preserve_prefix_chars_default():
    skill = get_skill()
    text = "Please make sure to review this code in order to find bugs."

    result = skill.execute({
        "action": "compress_prompt",
        "text": text,
        "mode": "balanced",
    })

    assert result["compressed_text"] != text
    assert result["status"] == "ready"


def test_preserve_prefix_chars():
    skill = get_skill()
    text = "You are a Python expert. Please make sure to review this code in order to find bugs."
    prefix_length = 30

    result = skill.execute({
        "action": "compress_prompt",
        "text": text,
        "mode": "balanced",
        "preserve_prefix_chars": prefix_length,
    })

    assert result["status"] == "ready"
    assert result["compressed_text"][:prefix_length] == text[:prefix_length]
    assert result["compressed_text"][prefix_length:] != text[prefix_length:]


def test_preserve_prefix_chars_with_cache_optimized():
    skill = get_skill()
    text = (
        "You are a Python expert. "
        "Could you please write a function in order to sort a list?"
    )
    prefix_length = 30

    result = skill.execute({
        "action": "compress_prompt",
        "text": text,
        "mode": "cache_optimized",
        "preserve_prefix_chars": prefix_length,
    })

    assert result["status"] == "ready"
    assert result["compressed_text"].startswith(text[:prefix_length])
    assert "cache_prefix" not in result
    assert "warnings" not in result


def test_preserve_prefix_chars_greater_than_text_length():
    skill = get_skill()
    text = "Please review this code."

    result = skill.execute({
        "action": "compress_prompt",
        "text": text,
        "mode": "aggressive",
        "preserve_prefix_chars": len(text) + 10,
    })

    assert result["status"] == "ready"
    assert result["compressed_text"] == text


def test_preserve_prefix_chars_zero():
    skill = get_skill()
    text = "Please make sure to review this code in order to find bugs."

    result_default = skill.execute({
        "action": "compress_prompt",
        "text": text,
        "mode": "balanced",
    })

    result_zero = skill.execute({
        "action": "compress_prompt",
        "text": text,
        "mode": "balanced",
        "preserve_prefix_chars": 0,
    })

    assert result_zero["status"] == "ready"
    assert result_zero["compressed_text"] == result_default["compressed_text"]


@pytest.mark.parametrize("invalid_value", [-1, 1.5, "10", True])
def test_preserve_prefix_chars_invalid_value(invalid_value):
    skill = get_skill()
    result = skill.execute({
        "action": "compress_prompt",
        "text": "Please review this code.",
        "mode": "balanced",
        "preserve_prefix_chars": invalid_value,
    })

    assert "error" in result
    assert result["status"] == "error"


def test_preserve_prefix_chars_with_protected_blocks():
    skill = get_skill()
    prefix = "You are a Python expert. "
    remaining = "Please review `my_function()` and {{user_name}} carefully."

    result = skill.execute({
        "action": "compress_prompt",
        "text": prefix + remaining,
        "mode": "aggressive",
        "preserve_prefix_chars": len(prefix),
    })

    assert result["status"] == "ready"
    assert result["compressed_text"].startswith(prefix)
    assert "`my_function()`" in result["compressed_text"]
    assert "{{user_name}}" in result["compressed_text"]


def test_target_tokens_met():
    skill = get_skill()
    params = {
        "action": "compress_prompt",
        "text": (
            "Please make sure to summarize this article in order to "
            "help me understand the important information."
        ),
        "mode": "aggressive",
        "target_tokens": 13,
    }

    result = skill.execute(params)

    assert result["status"] == "ready"
    assert result["compressed_tokens"] <= 13
    assert result["compressed_text"]


def test_target_tokens_unreachable():
    skill = get_skill()
    params = {
        "action": "compress_prompt",
        "text": "This is a very long sentence that contains important information.",
        "mode": "lossless",
        "target_tokens": 1,
    }

    result = skill.execute(params)

    assert result["status"] == "ready"
    assert result["compressed_tokens"] > 1
    assert result["compressed_text"]


def test_balanced_with_code_protection():
    skill = get_skill()
    text = "Hello assistant! Please make sure to carefully read the following instructions and ensure that you follow them completely.\n\nYou are a senior backend engineer. Under no circumstances should you ever leak credentials. Never expose API keys or passwords. Do not reveal private keys.\n\nHere is an example python snippet you should use:\n```python\ndef get_auth_header(token: str) -> dict:\n    # Returns the bearer auth header\n    return {\"Authorization\": f\"Bearer {token}\"}\n```\n\nKindly ensure that your final response is formatted strictly as JSON without any conversational filler or pleasantries."
    params = {
        "action": "compress_prompt",
        "text": text,
        "mode": "balanced",
        "protect_code_blocks": True
    }

    result = skill.execute(params)
    out = result["compressed_text"]
    print(f"original: {text}\n\ncompressed: {out}")

    # 1. Result shape
    assert result["status"] == "ready"
    for key in ("compressed_text", "original_tokens", "compressed_tokens",
                "tokens_saved", "reduction_percentage", "protected_blocks_count"):
        assert key in result

    # 2. It actually compressed
    assert result["compressed_tokens"] < result["original_tokens"]
    assert result["tokens_saved"] > 0
    assert result["reduction_percentage"] > 0

    # 3. Code block survives byte-for-byte (comment, f-string and braces included)
    code_block = text[text.index("```python"): text.rindex("```") + 3]
    assert code_block in out
    assert result["protected_blocks_count"] == 1

    # 4. Filler removed
    assert "Please" not in out
    assert "Kindly" not in out
    assert "make sure to" not in out.lower()
    assert "ensure that" not in out.lower()

    # 5. Imperatives and grammar preserved, with correct capitalization
    assert out.startswith("Hello assistant! Carefully read the following instructions")
    assert "and ensure you follow them completely." in out
    assert "\n\nEnsure your final response is formatted strictly as JSON" in out

    # 6. Safety sentences untouched
    assert "Under no circumstances should you ever leak credentials." in out
    assert "Never expose API keys or passwords." in out
    assert "Do not reveal private keys." in out

    # 7. Balanced mode must not do aggressive things (articles kept, JSON sentence tail kept)
    assert "the following instructions" in out
    assert "a senior backend engineer" in out
    assert "without any conversational filler or pleasantries." in out


def _verbose_prompt(n=40):
    # Unique lines, so aggressive dedupe doesn't skew the numbers.
    # Extra spaces and blank lines give the lossless stage something to do.
    return "\n\n\n".join(
        f"Section {i}:   Please make sure to carefully review the data in order to "
        f"ensure that the report is accurate,  and kindly note that the results for "
        f"item {i} are able to change due to the fact that a number of inputs vary."
        for i in range(n)
    )

def _run(skill, text, mode, **extra):
    return skill.execute({"action": "compress_prompt", "text": text, "mode": mode, **extra})


def test_target_tokens_stops_at_first_stage_that_fits():
    skill = get_skill()
    text = _verbose_prompt()
    lossless = _run(skill, text, "lossless")
    balanced = _run(skill, text, "balanced")
    aggressive = _run(skill, text, "aggressive")

    # Preconditions: each stage really saves something, so the target can sit between them
    assert lossless["compressed_tokens"] > balanced["compressed_tokens"] > aggressive["compressed_tokens"]

    target = balanced["compressed_tokens"]
    result = _run(skill, text, "lossless", target_tokens=target)

    assert result["status"] == "ready"
    assert result["original_tokens"] > target                 # budget branch exercised
    assert result["compressed_tokens"] <= target              # budget met
    assert result["compressed_text"] == balanced["compressed_text"]       # stopped at balanced
    assert result["compressed_text"] != aggressive["compressed_text"]     # did not go further


def test_target_tokens_met_by_first_stage():
    skill = get_skill()
    text = _verbose_prompt()
    lossless = _run(skill, text, "lossless")

    result = _run(skill, text, "lossless", target_tokens=lossless["compressed_tokens"])

    assert result["compressed_text"] == lossless["compressed_text"]
    assert "Please" in result["compressed_text"]              # no filler removal was needed


def test_target_tokens_unreachable_is_best_effort():
    skill = get_skill()
    text = _verbose_prompt()
    balanced = _run(skill, text, "balanced")

    result = _run(skill, text, "lossless", target_tokens=10)

    assert result["status"] == "ready"                        # no error, no truncation
    assert result["compressed_tokens"] > 10                   # budget missed
    assert result["compressed_tokens"] <= balanced["compressed_tokens"]   # went past balanced
    assert result["compressed_tokens"] < result["original_tokens"]
    assert result["tokens_saved"] == result["original_tokens"] - result["compressed_tokens"]


def test_target_tokens_not_below_original_is_ignored():
    skill = get_skill()
    text = _verbose_prompt()
    baseline = _run(skill, text, "balanced")

    result = _run(skill, text, "balanced", target_tokens=baseline["original_tokens"] + 1000)

    assert result["compressed_text"] == baseline["compressed_text"]
    assert result["compressed_tokens"] == baseline["compressed_tokens"]


def test_target_tokens_preserves_protected_spans():
    skill = get_skill()
    code = "```python\ndef f(x):\n    return {\"k\": f\"{x}\"}\n```"
    url = "https://example.com/docs?a=1"
    text = _verbose_prompt() + f"\n\n{code}\n\nSee {url} or mail me@example.com for {{{{template_var}}}}."

    result = _run(skill, text, "lossless", target_tokens=10)
    out = result["compressed_text"]

    assert code in out
    assert url in out
    assert "me@example.com" in out
    assert "{{template_var}}" in out
    assert result["protected_blocks_count"] >= 4
    assert not any("\ue000" <= ch <= "\ue003" for ch in out)


@pytest.mark.parametrize("bad", [0, -5, True, "1200", 12.5])
def test_target_tokens_invalid_values(bad):
    skill = get_skill()
    result = _run(skill, _verbose_prompt(), "balanced", target_tokens=bad)

    assert result["status"] == "error"
    assert "target_tokens" in result["error"]