import importlib.util
import os
import re
from typing import Any, Dict

from skillware.core.base_skill import BaseSkill


def _import_workflow():
    try:
        from . import workflow as wf  # type: ignore[import-not-found]
    except ImportError:
        wf_path = os.path.join(os.path.dirname(__file__), "workflow.py")
        spec = importlib.util.spec_from_file_location(
            "issue_resolver_workflow", wf_path
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load workflow module from {wf_path}")
        wf = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(wf)
    return wf


_wf = _import_workflow()
WORKFLOW_VERSION = _wf.WORKFLOW_VERSION
get_stage_checklist = _wf.get_stage_checklist
get_workflow_overview = _wf.get_workflow_overview
validate_commit_message = _wf.validate_commit_message


class IssueResolverSkill(BaseSkill):
    """
    Universal GitHub issue resolution assistant for any repository.

    The skill does not call GitHub, run git, or write code. It returns
    deterministic workflow payloads, stage checklists with conditional logic,
    and commit-message gates for the calling agent to execute in order.
    """

    _GITHUB_ISSUE_RE = re.compile(
        r"https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/issues/(?P<number>\d+)"
    )

    _VALID_ACTIONS = frozenset(
        {
            "prepare",
            "workflow_overview",
            "stage_checklist",
            "validate_commit_message",
        }
    )

    @property
    def manifest(self) -> Dict[str, Any]:
        manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
        if os.path.exists(manifest_path):
            import yaml

            with open(manifest_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {}

    def _parse_issue_url(self, url: str) -> Dict[str, str]:
        match = self._GITHUB_ISSUE_RE.match(url.strip())
        if not match:
            raise ValueError(
                f"issue_url does not match the expected GitHub issue URL pattern: {url!r}. "
                "Expected format: https://github.com/<owner>/<repo>/issues/<number>"
            )
        owner = match.group("owner")
        repo = match.group("repo")
        number = match.group("number")
        return {
            "owner": owner,
            "repo": repo,
            "number": number,
            "api_url": f"https://api.github.com/repos/{owner}/{repo}/issues/{number}",
            "raw_url": url.strip(),
            "repo_api_url": f"https://api.github.com/repos/{owner}/{repo}",
            "repo_html_url": f"https://github.com/{owner}/{repo}",
        }

    def _resolve_token(self, params: Dict[str, Any]) -> str:
        token = (params.get("github_token") or "").strip()
        if not token:
            token = (
                self.config.get("GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
            )
        return token

    def _action(self, params: Dict[str, Any]) -> str:
        action = (params.get("action") or "prepare").strip().lower()
        if action not in self._VALID_ACTIONS:
            return "__invalid__"
        return action

    def _prepare(self, params: Dict[str, Any]) -> Dict[str, Any]:
        issue_url = (params.get("issue_url") or "").strip()
        if not issue_url:
            return {
                "status": "error",
                "message": "issue_url is required for action prepare.",
            }

        try:
            parsed = self._parse_issue_url(issue_url)
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}

        token = self._resolve_token(params)
        extra_instructions = (params.get("extra_instructions") or "").strip()

        auth_header_note = (
            "Include the Authorization header: Bearer <GITHUB_TOKEN>."
            if token
            else (
                "No GITHUB_TOKEN is configured. The GitHub API will apply the "
                "unauthenticated rate limit (60 requests per hour). For private "
                "repositories or high-volume usage, set GITHUB_TOKEN."
            )
        )

        return {
            "status": "ready",
            "action": "prepare",
            "workflow_version": WORKFLOW_VERSION,
            "issue": {
                "url": parsed["raw_url"],
                "api_url": parsed["api_url"],
                "owner": parsed["owner"],
                "repo": parsed["repo"],
                "number": parsed["number"],
            },
            "repository": {
                "html_url": parsed["repo_html_url"],
                "api_url": parsed["repo_api_url"],
                "readme_url": (
                    f"https://raw.githubusercontent.com/{parsed['owner']}"
                    f"/{parsed['repo']}/HEAD/README.md"
                ),
                "contributing_url": (
                    f"https://raw.githubusercontent.com/{parsed['owner']}"
                    f"/{parsed['repo']}/HEAD/CONTRIBUTING.md"
                ),
                "tree_api_url": (
                    f"https://api.github.com/repos/{parsed['owner']}/{parsed['repo']}"
                    "/git/trees/HEAD?recursive=1"
                ),
            },
            "auth": {
                "token_provided": bool(token),
                "note": auth_header_note,
            },
            "extra_instructions": extra_instructions or None,
            "next_step": (
                "Call action workflow_overview or stage_checklist for discover_issue. "
                "Follow instructions.md stages in order; do not skip gates."
            ),
        }

    def _stage_checklist(self, params: Dict[str, Any]) -> Dict[str, Any]:
        stage = (params.get("stage") or "").strip().lower()
        if not stage:
            return {
                "status": "error",
                "message": "stage is required for action stage_checklist.",
            }
        payload = get_stage_checklist(stage)
        if payload is None:
            return {
                "status": "error",
                "message": f"Unknown stage {stage!r}. Call workflow_overview for valid names.",
            }
        payload["action"] = "stage_checklist"
        return payload

    def _validate_commit_message(self, params: Dict[str, Any]) -> Dict[str, Any]:
        message = params.get("message")
        if message is None or not str(message).strip():
            return {
                "status": "error",
                "message": "message is required for action validate_commit_message.",
            }
        allow = bool(params.get("allow_ai_coauthor", False))
        result = validate_commit_message(str(message), allow_ai_coauthor=allow)
        result["action"] = "validate_commit_message"
        return result

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        action = self._action(params)
        if action == "__invalid__":
            allowed = ", ".join(sorted(self._VALID_ACTIONS))
            return {
                "status": "error",
                "message": f"Unknown action. Supported actions: {allowed}.",
            }
        if action == "prepare":
            return self._prepare(params)
        if action == "workflow_overview":
            overview = get_workflow_overview()
            overview["action"] = "workflow_overview"
            return overview
        if action == "stage_checklist":
            return self._stage_checklist(params)
        if action == "validate_commit_message":
            return self._validate_commit_message(params)
        return {"status": "error", "message": "Unhandled action."}
