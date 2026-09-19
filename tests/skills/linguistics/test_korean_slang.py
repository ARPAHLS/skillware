"""Maintainer depth and stress simulations for linguistics/korean_slang."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skillware.core.loader import SkillLoader


def _skill_class():
    return SkillLoader.load_skill("linguistics/korean_slang")["module"].KoreanSlangSkill


CHAT_SIMULATION = [
    ("요즘 완전 폼 미쳤다 ㄹㅇ", ["pom_michyeotda", "real_abbrev"]),
    ("점메추 ㄱㄱ", ["jeommechu", "gogo"]),
    ("내일 내또출이라 현타 옴", ["naettochul", "hyeonta"]),
    ("알잘딱깔센으로 해줘", ["aljaldakkkalsen"]),
    ("추구미 그잡채", ["chugumi", "geujapchae"]),
    ("킹받네 에바참치", ["kingbatda", "ebachamchi"]),
    ("오운완 ㅋㅋ", ["ounwan", "kk_laugh"]),
    ("불금인데 치맥?", ["bulgeum", "chimaek"]),
    ("최애 직캠 소름", ["choiae", "jikcam", "soreum"]),
    ("워라밸 글렀고 야근각", ["worlabel", "yageun"]),
    ("억텐 모드로 회식 가는 중", ["eokten"]),
    ("스불재로 밤새고 멘붕", ["seubuljae", "menbung"]),
    ("주불 호캉스 ㄱㄱ", ["jubuol", "hokangseu", "gogo"]),
    ("만반잘부 ㅎㅇ", ["manbanjalbu", "hi_abbrev"]),
    ("이건 별다줄 그 자체", ["byeoldajul"]),
]


def _skill():
    return _skill_class()()


def test_loader_and_class_are_the_same_pack():
    bundle = SkillLoader.load_skill("linguistics/korean_slang")
    loaded = bundle["class"]()
    native = _skill_class()()
    sample = "느좋 바이브"
    assert (
        loaded.execute({"text": sample})["hits"][0]["id"]
        == native.execute({"text": sample})["hits"][0]["id"]
    )


@pytest.mark.parametrize("line,expected_ids", CHAT_SIMULATION)
def test_group_chat_simulation_hits(line, expected_ids):
    result = _skill().execute({"text": line, "action": "interpret"})
    assert result["status"] == "ok"
    got = {hit["id"] for hit in result["hits"]}
    missing = set(expected_ids) - got
    assert not missing, f"{line!r} missing {missing}; got {got}"


def test_suggest_roundtrip_interpret():
    skill = _skill()
    suggested = skill.execute({"action": "suggest", "intent": "competence"})
    assert suggested["status"] == "ok"
    text = suggested["suggestions"][0]["text"]
    interpreted = skill.execute({"text": text})
    assert interpreted["hit_count"] >= 1
    assert "알잘딱" in json.dumps(interpreted["slang_breakdown"], ensure_ascii=False)


def test_suggest_never_emits_blocked_or_default_vulgar():
    skill = _skill()
    module = SkillLoader.load_skill("linguistics/korean_slang")["module"]
    pack_path = Path(module.__file__).resolve().parent / "kb" / "constitution.json"
    blocked_terms = json.loads(pack_path.read_text(encoding="utf-8"))[
        "blocked_substrings"
    ]
    intents = [
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
    for intent in intents:
        for audience in ("peers", "mixed", "work", "elders"):
            result = skill.execute(
                {"action": "suggest", "intent": intent, "audience": audience}
            )
            assert result["status"] == "ok", (intent, audience, result)
            blob = json.dumps(result, ensure_ascii=False)
            for term in blocked_terms:
                assert term not in blob
            assert "존나" not in blob
            assert "ㅈㄴ" not in blob


def test_style_hint_on_formal_prose():
    result = _skill().execute(
        {
            "text": "오늘 공연을 보았습니다. 정말 훌륭합니다.",
            "audience": "peers",
        }
    )
    assert result.get("style_hint")


def test_jamo_particles_in_comment_thread():
    result = _skill().execute({"text": "ㄹㅇㅋㅋ ㅇㅈ"})
    ids = {hit["id"] for hit in result["hits"]}
    assert "real_abbrev" in ids
    assert "kk_laugh" in ids
    assert "injeong" in ids


def test_max_hits_and_invalid_audience():
    skill = _skill()
    capped = skill.execute(
        {"text": "ㄹㅇ ㅇㅈ ㄱㄱ ㄴㄴ ㅎㅇ ㅂㅂ ㄱㅅ ㅊㅋ ㄷㄷ", "max_hits": 2}
    )
    assert capped["hit_count"] <= 2
    bad = skill.execute({"text": "폼 미쳤다", "audience": "boss"})
    assert bad["status"] == "error"
    assert bad["error"]["code"] == "UNKNOWN_AUDIENCE"


def test_identical_input_is_bit_stable():
    skill = _skill()
    params = {"text": "헤드림 직캠 폼 미쳤다 ㄹㅇ", "context": "fancam"}
    first = skill.execute(params)
    second = skill.execute(params)
    assert json.dumps(first, sort_keys=True, ensure_ascii=False) == json.dumps(
        second, sort_keys=True, ensure_ascii=False
    )
