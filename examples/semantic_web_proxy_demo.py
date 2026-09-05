"""Offline demo for data_engineering/semantic_web_proxy.

Runs entirely against bundled fixture HTML: no network access and no API keys.
Shows the three behaviours a host agent cares about - boilerplate removal, opt-in
comments, and the JavaScript-render warning.
"""

from pathlib import Path

from skillware.core.loader import SkillLoader

FIXTURES = (
    Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "semantic_web_proxy"
)

CONTEXT_WINDOW = 200_000


def read(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def report(label, result):
    savings = result["token_savings"]
    print(f"\n[{label}] status: {result['status']}")
    print(f"  title: {result['metadata'].get('title')}")
    print(
        f"  tokens: {savings['original_tokens']} -> {savings['semantic_tokens']}"
        f" (saved {savings['tokens_saved']}, reduction {savings['reduction_pct']}%)"
    )
    print(
        f"  context saved: {savings['context_saved_pct']}% of {CONTEXT_WINDOW} tokens"
    )
    if result["warnings"]:
        print(f"  warnings: {', '.join(result['warnings'])}")
    if result["error"]:
        print(f"  error: {result['error']}")


def run_demo():
    print("Loading data_engineering/semantic_web_proxy...")
    bundle = SkillLoader.load_skill("data_engineering/semantic_web_proxy")
    skill = bundle["class"]()

    article = skill.execute(
        {"html_content": read("article.html"), "context_window": CONTEXT_WINDOW}
    )
    report("Article", article)
    print("  payload head:")
    for line in article["semantic_payload"].splitlines()[:4]:
        print(f"    {line}")

    thread = skill.execute(
        {
            "html_content": read("thread_with_comments.html"),
            "include_comments": True,
            "context_window": CONTEXT_WINDOW,
        }
    )
    report("Thread with comments", thread)

    shell = skill.execute(
        {"html_content": read("js_shell.html"), "context_window": CONTEXT_WINDOW}
    )
    report("Client-rendered dashboard", shell)

    blocked = skill.execute({"url": "http://169.254.169.254/latest/meta-data/"})
    report("SSRF guard", blocked)

    print("\nDemo complete.")


if __name__ == "__main__":
    run_demo()
