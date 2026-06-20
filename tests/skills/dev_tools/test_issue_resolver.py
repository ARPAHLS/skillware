from skillware.core.loader import SkillLoader

VALID_ISSUE_URL = "https://github.com/ARPAHLS/skillware/issues/56"


def get_skill():
    bundle = SkillLoader.load_skill("dev_tools/issue_resolver")
    return bundle, bundle["module"].IssueResolverSkill()


def test_issue_resolver_manifest_loads():
    bundle, _ = get_skill()
    manifest = bundle["manifest"]

    assert manifest["name"] == "dev_tools/issue_resolver"
    assert "issue_url" in manifest["parameters"]["properties"]
    assert "action" in manifest["parameters"]["properties"]


def test_issue_resolver_prepare_uses_loader_path():
    _, skill = get_skill()

    result = skill.execute({"issue_url": VALID_ISSUE_URL})

    assert result["status"] == "ready"
    assert result["action"] == "prepare"
    assert result["issue"] == {
        "url": VALID_ISSUE_URL,
        "api_url": "https://api.github.com/repos/ARPAHLS/skillware/issues/56",
        "owner": "ARPAHLS",
        "repo": "skillware",
        "number": "56",
    }
    assert result["repository"]["html_url"] == "https://github.com/ARPAHLS/skillware"


def test_issue_resolver_workflow_overview_uses_loader_path():
    _, skill = get_skill()

    result = skill.execute({"action": "workflow_overview"})

    assert result["status"] == "ready"
    assert result["workflow_version"] == "0.2"
    assert result["stage_order"][0] == "discover_issue"
    assert result["stage_order"][-1] == "pull_request"


def test_issue_resolver_stage_checklist_uses_loader_path():
    _, skill = get_skill()

    result = skill.execute({"action": "stage_checklist", "stage": "verify"})

    assert result["status"] == "ready"
    assert result["stage"] == "verify"
    assert result["next_stage"] == "pre_commit"
    assert any("Run verification commands" in step for step in result["steps"])


def test_issue_resolver_rejects_ai_coauthor_via_loader_path():
    _, skill = get_skill()

    result = skill.execute(
        {
            "action": "validate_commit_message",
            "message": "Fix issue workflow\n\nCo-authored-by: Claude <noreply@example.com>",
        }
    )

    assert result["status"] == "rejected"
    assert result["ok"] is False
    assert result["violations"]
