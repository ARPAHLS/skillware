import json
import os
import sys
from pathlib import Path
import google.genai as genai
from google.genai import types

sys.path.insert(0, str(Path(__file__).resolve().parent))
from token_limiter_common import simulate_budget_loop  # noqa: E402

from skillware.core.env import load_env_file  # noqa: E402
from skillware.core.loader import SkillLoader  # noqa: E402

SKILL_ID = "monitoring/token_limiter"


def run_local_simulation(skill) -> None:
    print("Phase 1: local deterministic budget loop (no LLM)...")
    simulate_budget_loop(
        skill,
        task_id="gemini_scrape_demo",
        max_allowed_tokens=50_000,
        turn_deltas=[15_000, 15_000, 15_000, 10_000],
        model_id="gemini-2.5-flash",
    )


def run_gemini_loop(skill, bundle) -> None:
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("Skipping live Gemini demo: GOOGLE_API_KEY is not set.")
        return

    print("\nPhase 2: Gemini tool loop with budget check...")
    client = genai.Client()
    gemini_tool = SkillLoader.to_gemini_tool(bundle)
    system_instruction = bundle["instructions"]
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")

    user_query = (
        "You are running a bounded scrape task with task_id gemini_scrape_demo. "
        "Call monitoring/token_limiter with current_token_count 125000 and "
        "max_allowed_tokens 100000, then explain whether the loop should stop."
    )
    print(f"User: {user_query}")

    response = client.models.generate_content(
        model=model,
        contents=[user_query],
        config=types.GenerateContentConfig(
            tools=[gemini_tool],
            system_instruction=system_instruction,
        ),
    )

    part = response.candidates[0].content.parts[0]
    if not part.function_call:
        print("Model did not request the budget tool.")
        print(response.text)
        return

    fn_args = dict(part.function_call.args)
    print(f"Gemini requested tool: {part.function_call.name}")
    print(f"Input: {fn_args}")
    result = skill.execute(fn_args)
    print(json.dumps(result, indent=2))


def run_demo(live_gemini: bool = True) -> None:
    load_env_file()
    bundle = SkillLoader.load_skill(SKILL_ID)
    skill = bundle["module"].TokenLimiterSkill()
    run_local_simulation(skill)
    if live_gemini:
        run_gemini_loop(skill, bundle)


if __name__ == "__main__":
    run_demo()
