#!/usr/bin/env python3
"""Offline stress harness for linguistics/korean_slang (safe to run in CI).

Walks a simulated group-chat plus every generation intent/audience pair.
Exits 1 if any scenario fails. No network.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from skillware.core.loader import SkillLoader  # noqa: E402

CHAT = [
    "요즘 완전 폼 미쳤다 ㄹㅇ",
    "점메추 ㄱㄱ",
    "내일 내또출이라 현타 옴",
    "알잘딱깔센으로 해줘",
    "추구미 그잡채",
    "킹받네 에바참치",
    "오운완 ㅋㅋ",
    "불금인데 치맥?",
    "최애 직캠 소름",
    "워라밸 글렀고 야근각",
    "억텐 모드로 회식 가는 중",
    "스불재로 밤새고 멘붕",
    "주불 호캉스 ㄱㄱ",
    "만반잘부 ㅎㅇ",
    "이건 별다줄 그 자체",
    "폼미쳤다",
    "pom michyeotda",
    "갓생러는 갓생 중",
    "ㄹㅇㅋㅋ ㅇㅈ",
    "안녕하세요. 오늘 날씨가 좋습니다.",
]

INTENTS = [
    "praise",
    "food",
    "work",
    "tired",
    "annoyed",
    "agree",
    "greeting",
    "bye",
    "thanks",
    "workout",
    "weekend",
    "dating",
    "fandom",
    "competence",
]
AUDIENCES = ("peers", "mixed", "work", "elders")


def main() -> int:
    bundle = SkillLoader.load_skill("linguistics/korean_slang")
    skill = bundle["class"]()
    failures = 0

    print("korean slang stress sim")
    print(f"pack entries: {skill.execute({'text': '폼 미쳤다'}).get('entry_count')}")

    for line in CHAT:
        result = skill.execute({"text": line})
        if result.get("status") != "ok":
            print(f"FAIL interpret {ascii(line)}: {result.get('error')}")
            failures += 1
            continue
        print(
            "ok interpret hit_count="
            f"{result['hit_count']} unmatched={result['unmatched']} {ascii(line)}"
        )

    for intent in INTENTS:
        for audience in AUDIENCES:
            result = skill.execute(
                {"action": "suggest", "intent": intent, "audience": audience}
            )
            if result.get("status") != "ok":
                print(f"FAIL suggest {intent}/{audience}: {result}")
                failures += 1
                continue
            blob = json.dumps(result, ensure_ascii=False)
            if "존나" in blob or "테무인간" in blob:
                print(f"FAIL leak {intent}/{audience}")
                failures += 1
                continue
            print(f"ok suggest {intent}/{audience} n={result.get('hit_count')}")

    empty = skill.execute({"action": "interpret", "text": ""})
    if empty.get("status") != "error":
        print("FAIL empty text should error")
        failures += 1
    else:
        print("ok empty-text contract error")

    if failures:
        print(f"stress sim failed: {failures}")
        return 1
    print("stress sim passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
