import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from token_limiter_common import simulate_budget_loop  # noqa: E402

from skillware.core.loader import SkillLoader  # noqa: E402


def run_demo() -> None:
    bundle = SkillLoader.load_skill("monitoring/token_limiter")
    skill = bundle["module"].TokenLimiterSkill()

    print("Simulating a runaway scrape task with a 100k token ceiling...")
    results = simulate_budget_loop(
        skill,
        task_id="scrape_amazon_listings_101",
        max_allowed_tokens=100_000,
        turn_deltas=[30_000, 30_000, 30_000, 20_000],
    )

    final = results[-1]
    assert final["action"] == "FORCE_TERMINATE"
    print("\nLoop stopped as expected:")
    print(final["reason"])


if __name__ == "__main__":
    run_demo()
