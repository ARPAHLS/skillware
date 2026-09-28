"""Bundle tests for linguistics/korean_slang.

Offline and deterministic. Locks the issue #34 interpret contract, pack
integrity, honorific gates, and toxic-term filtering.
"""

import json
import os

import yaml

from skillware.core.loader import SkillLoader

from .skill import KoreanSlangSkill

BUNDLE_DIR = os.path.dirname(__file__)
KB_DIR = os.path.join(BUNDLE_DIR, "kb")


def _load_json(name):
    with open(os.path.join(KB_DIR, name), "r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_manifest():
    with open(os.path.join(BUNDLE_DIR, "manifest.yaml"), encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_skill_manifest_consistency():
    skill = KoreanSlangSkill()
    manifest = _load_manifest()
    assert skill.manifest["name"] == manifest["name"] == "linguistics/korean_slang"
    assert skill.manifest["version"] == manifest["version"] == "0.1.0"
    assert manifest["requirements"] == []
    assert "output" not in manifest
    result = skill.execute({"text": "요즘 완전 폼 미쳤다"})
    for key in manifest["outputs"]:
        assert key in result


def test_skill_loader_can_import():
    bundle = SkillLoader.load_skill("linguistics/korean_slang")
    assert bundle["manifest"]["name"] == "linguistics/korean_slang"
    assert hasattr(bundle["module"], "KoreanSlangSkill")
    skill = bundle["class"]()
    result = skill.execute({"text": "알잘딱깔센"})
    assert result["status"] == "ok"


def test_issue_34_interpret_contract():
    skill = KoreanSlangSkill()
    result = skill.execute(
        {
            "text": "요즘 완전 폼 미쳤다",
            "context": "A comment on a YouTube video about a popular singer.",
            "action": "interpret",
        }
    )
    assert result["status"] == "ok"
    assert result["action"] == "interpret"
    assert result["translation"] == (
        "They are absolutely killing it right now / " "Their form is crazy these days"
    )
    assert result["slang_breakdown"]["폼 미쳤다"].startswith(
        "Slang directly translating to 'form is crazy'"
    )
    assert result["nuance"].startswith("Highly positive, trendy internet-friendly")
    assert "YouTube video" in result["nuance"]
    assert result["formality"] == "Informal / Slang"
    assert result["hit_count"] >= 1
    assert any(hit["id"] == "pom_michyeotda" for hit in result["hits"])


def test_compact_and_romanization_match():
    skill = KoreanSlangSkill()
    compact = skill.execute({"text": "폼미쳤다"})
    roman = skill.execute({"text": "pom michyeotda"})
    assert compact["hits"][0]["id"] == "pom_michyeotda"
    assert roman["hits"][0]["id"] == "pom_michyeotda"


def test_longest_match_gatsaengreo_then_gatsaeng():
    skill = KoreanSlangSkill()
    result = skill.execute({"text": "갓생러는 갓생 중"})
    ids = [hit["id"] for hit in result["hits"]]
    assert ids.count("gatsaengreo") == 1
    assert ids.count("gatsaeng") == 1


def test_lookup_and_unmatched():
    skill = KoreanSlangSkill()
    found = skill.execute({"action": "lookup", "text": "알잘딱깔센"})
    assert found["found"] is True
    assert found["entry"]["id"] == "aljaldakkkalsen"
    missing = skill.execute({"action": "lookup", "text": "없는신조어xyz"})
    assert missing["found"] is False
    unmatched = skill.execute({"text": "안녕하세요. 오늘 날씨가 좋습니다."})
    assert unmatched["unmatched"] is True
    assert unmatched["slang_breakdown"] == {}


def test_suggest_peers_praise_and_elders_gate():
    skill = KoreanSlangSkill()
    peers = skill.execute(
        {"action": "suggest", "intent": "praise", "audience": "peers"}
    )
    assert peers["status"] == "ok"
    blob = " ".join(item["text"] for item in peers["suggestions"])
    assert "폼 미쳤다" in blob
    assert "ㄹㅇ" in blob or "ㅋㅋ" in blob
    elders = skill.execute(
        {"action": "suggest", "intent": "praise", "audience": "elders"}
    )
    elder_blob = " ".join(item["text"] for item in elders["suggestions"])
    assert "폼 미쳤다" not in elder_blob
    assert "ㅋㅋ" not in elder_blob
    assert "ㄹㅇ" not in elder_blob
    assert "세요" in elder_blob or "습니다" in elder_blob


def test_constitution_blocks_and_vulgar_opt_in():
    skill = KoreanSlangSkill()
    blocked = skill.execute({"text": "저 사람은 테무인간 같아"})
    assert blocked["blocked_omitted"]
    assert "테무인간" not in json.dumps(
        blocked.get("slang_breakdown"), ensure_ascii=False
    )
    suggest_blocked = skill.execute(
        {"action": "suggest", "text": "테무인간처럼 놀려줘", "intent": "annoyed"}
    )
    assert suggest_blocked["suggestions"] == []
    default = skill.execute(
        {"action": "suggest", "intent": "food", "audience": "peers"}
    )
    food_blob = " ".join(item["text"] for item in default["suggestions"])
    assert "존나" not in food_blob
    assert "존맛탱" not in food_blob


def test_empty_text_and_unknown_action():
    skill = KoreanSlangSkill()
    empty = skill.execute({"action": "interpret", "text": "  "})
    assert empty["status"] == "error"
    assert empty["error"]["code"] == "EMPTY_TEXT"
    unknown = skill.execute({"action": "translate", "text": "폼 미쳤다"})
    assert unknown["status"] == "error"
    assert unknown["error"]["code"] == "UNKNOWN_ACTION"


def test_pack_entries_are_unique_and_lookupable():
    skill = KoreanSlangSkill()
    entries = _load_json("entries.json")
    ids = [entry["id"] for entry in entries]
    assert len(ids) == len(set(ids))
    assert len(entries) >= 70
    for entry in entries:
        surface = entry["surfaces"][0]
        result = skill.execute({"action": "lookup", "text": surface})
        assert result["found"] is True, surface
        assert result["entry"]["id"] == entry["id"]
