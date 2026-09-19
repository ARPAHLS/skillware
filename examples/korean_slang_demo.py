"""
Local execute demo for linguistics/korean_slang.

Runs the deterministic Korean slang pack entirely offline: the issue #34
YouTube-comment interpret contract, peer-register suggest(), lookup, an
unmatched formal sentence, and a blocked-term filter. No API keys, no network.
Hangul is printed via JSON ascii escapes so Windows cp1252 pipes do not crash.
"""

import json

from skillware.core.loader import SkillLoader


def _dump(value):
    return json.dumps(value, ensure_ascii=True)


def _print_interpret(title, result):
    print(f"\n{title}")
    print(f"  status: {result['status']}")
    if result["status"] != "ok":
        print(f"  error: {_dump(result.get('error'))}")
        return
    print(f"  formality: {result['formality']}")
    print(f"  translation: {result.get('translation')}")
    print(f"  slang_breakdown: {_dump(result.get('slang_breakdown'))}")
    if result.get("warnings"):
        print(f"  warnings: {_dump(result['warnings'])}")


def run_demo() -> None:
    print("Loading linguistics/korean_slang...")
    bundle = SkillLoader.load_skill("linguistics/korean_slang")
    skill = bundle["class"]()

    _print_interpret(
        "Scenario 1: issue #34 YouTube comment",
        skill.execute(
            {
                "text": "요즘 완전 폼 미쳤다",
                "context": "A comment on a YouTube video about a popular singer.",
                "action": "interpret",
            }
        ),
    )

    print("\nScenario 2: suggest praise for peers")
    suggested = skill.execute(
        {"action": "suggest", "intent": "praise", "audience": "peers"}
    )
    print(f"  status: {suggested['status']}")
    for item in suggested.get("suggestions") or []:
        print(f"  suggestion: {_dump(item['text'])}")

    print("\nScenario 3: lookup aljaldakkkalsen")
    looked = skill.execute({"action": "lookup", "text": "알잘딱깔센"})
    entry = looked.get("entry") or {}
    print(f"  found: {looked.get('found')} id={entry.get('id')}")

    _print_interpret(
        "Scenario 4: unmatched formal Korean",
        skill.execute({"text": "오늘 날씨가 좋습니다."}),
    )

    _print_interpret(
        "Scenario 5: blocked appearance slur is omitted",
        skill.execute({"text": "그 댓글에 테무인간이라고 써 있음"}),
    )

    print("\nDemo complete.")


if __name__ == "__main__":
    run_demo()
