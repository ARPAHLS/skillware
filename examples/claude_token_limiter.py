import json
import os
import sys
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).resolve().parent))
from token_limiter_common import simulate_budget_loop  # noqa: E402

from skillware.core.env import load_env_file  # noqa: E402
from skillware.core.loader import SkillLoader  # noqa: E402

SKILL_ID = "monitoring/token_limiter"


def run_local_simulation(skill) -> None:
    print("Phase 1: local deterministic budget loop (no LLM)...")
    simulate_budget_loop(
        skill,
        task_id="claude_scrape_demo",
        max_allowed_tokens=50_000,
        turn_deltas=[15_000, 15_000, 15_000, 10_000],
        model_id="claude-3-5-sonnet-latest",
    )


def run_claude_loop(skill, bundle) -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Skipping live Claude demo: ANTHROPIC_API_KEY is not set.")
        return

    print("\nPhase 2: Claude tool loop with budget check...")
    client = anthropic.Anthropic(api_key=api_key)
    tools = [SkillLoader.to_claude_tool(bundle)]
    system = bundle["instructions"]
    model = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")

    user_query = (
        "You are running a bounded scrape task with task_id claude_scrape_demo. "
        "Call monitoring/token_limiter with current_token_count 125000 and "
        "max_allowed_tokens 100000, then explain whether the loop should stop."
    )
    print(f"User: {user_query}")

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=system,
        tools=tools,
        messages=[{"role": "user", "content": user_query}],
    )

    tool_uses = [block for block in response.content if block.type == "tool_use"]
    if not tool_uses:
        print("Model did not request the budget tool.")
        for block in response.content:
            if hasattr(block, "text"):
                print(block.text)
        return

    tool_use = tool_uses[0]
    print(f"Claude requested tool: {tool_use.name}")
    print(f"Input: {tool_use.input}")
    result = skill.execute(dict(tool_use.input))
    print(json.dumps(result, indent=2))


def run_demo(live_claude: bool = True) -> None:
    load_env_file()
    bundle = SkillLoader.load_skill(SKILL_ID)
    skill = bundle["module"].TokenLimiterSkill()
    run_local_simulation(skill)
    if live_claude:
        run_claude_loop(skill, bundle)


if __name__ == "__main__":
    run_demo()
