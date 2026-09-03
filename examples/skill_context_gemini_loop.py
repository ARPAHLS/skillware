"""
SkillContext multi-skill demo: offline registry context (Phase 1) and optional
Gemini tool loop (Phase 2).

Phase 1 runs without API keys. Phase 2 requires GOOGLE_API_KEY, pip install
"skillware[gemini]", and SKILL_CONTEXT_GEMINI_LIVE=1.
"""

from __future__ import annotations

import json
import os

from skillware import SkillContext
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

FIREWALL = "security/prompt_injection_firewall"
TOKEN_LIMITER = "monitoring/token_limiter"


def _gemini_tool_index(ctx: SkillContext) -> dict[str, str]:
    """Map sanitized Gemini function names to registry skill IDs."""
    index: dict[str, str] = {}
    for skill_id in ctx.skill_ids:
        prep = ctx.prepare(skill_id)
        gemini_name = SkillLoader._sanitize_gemini_tool_name(prep.manifest["name"])
        index[gemini_name] = skill_id
    return index


def run_offline_phase() -> SkillContext:
    print("Phase 1: SkillContext offline (no LLM)...")
    ctx = SkillContext(skills=[FIREWALL, TOKEN_LIMITER], mode="brief")
    print(f"  skills: {', '.join(ctx.skill_ids)}")
    system = ctx.merge_system("You are a bounded agent with Skillware tools.")
    print(f"  merge_system length: {len(system)} chars")
    print(f"  openai tool count: {len(ctx.tools('openai'))}")

    fw = ctx.execute(
        FIREWALL,
        {
            "source_text": "Summarize Q3 earnings highlights for the board.",
            "input_mode": "plain",
            "sensitivity": "balanced",
        },
    )
    print(f"  security/prompt_injection_firewall is_safe={fw.get('is_safe')}")
    return ctx


def run_gemini_phase(ctx: SkillContext) -> None:
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("\nSkipping Phase 2: GOOGLE_API_KEY is not set.")
        return

    try:
        import google.genai as genai
        from google.genai import types
        from google.genai.errors import ClientError
    except ImportError:
        print(
            '\nSkipping Phase 2: install gemini extra (pip install "skillware[gemini]").'
        )
        return

    print("\nPhase 2: Gemini multi-tool loop via SkillContext...")
    client = genai.Client()
    tools = ctx.tools("gemini")
    system = ctx.merge_system(
        "You are a bounded scrape agent. Call monitoring/token_limiter when asked "
        "about token budget; use security/prompt_injection_firewall only for "
        "untrusted user text."
    )
    tool_index = _gemini_tool_index(ctx)
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
    user_query = (
        "For task_id skill_context_demo, call the token budget tool with "
        "current_token_count 95000 and max_allowed_tokens 100000, then summarize "
        "whether the host should continue."
    )
    print(f"User: {user_query}")

    try:
        response = client.models.generate_content(
            model=model,
            contents=[user_query],
            config=types.GenerateContentConfig(
                tools=tools,
                system_instruction=system,
            ),
        )
    except ClientError as exc:
        print(f"Skipping Phase 2 live call: {exc}")
        return

    if not response.candidates or not response.candidates[0].content.parts:
        print("No model response.")
        return

    part = response.candidates[0].content.parts[0]
    if not part.function_call:
        print("Model did not request a tool.")
        print(response.text)
        return

    fn_name = part.function_call.name
    fn_args = dict(part.function_call.args)
    print(f"Gemini requested tool: {fn_name}")
    print(f"Input: {fn_args}")

    skill_id = tool_index.get(fn_name)
    if not skill_id:
        print(f"Unknown tool name {fn_name!r}; known: {sorted(tool_index)}")
        return

    result = ctx.execute(skill_id, fn_args)
    print(json.dumps(result, indent=2))


def run_demo(*, live_gemini: bool = False) -> None:
    load_env_file()
    ctx = run_offline_phase()
    if live_gemini:
        run_gemini_phase(ctx)


if __name__ == "__main__":
    live = os.environ.get("SKILL_CONTEXT_GEMINI_LIVE", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    run_demo(live_gemini=live)
