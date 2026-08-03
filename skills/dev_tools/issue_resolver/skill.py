import importlib.util
import os
import re
from typing import Any, Dict, List, Optional

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


_ATX_HEADING_RE = re.compile(r"^ {0,3}(?P<marks>#{1,6})(?:[ \t]+(?P<text>.*)|[ \t]*)$")
_FENCE_RE = re.compile(r"^ {0,3}(?P<marker>`{3,}|~{3,})(?P<rest>.*)$")
_CLOSING_HASHES_RE = re.compile(r"[ \t]+#+[ \t]*$")


def _trim_blank_lines(lines: List[str]) -> str:
    """Join lines after removing only outer blank lines."""
    start = 0
    end = len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return "\n".join(lines[start:end])


def _parse_profile_markdown(markdown: str) -> Dict[str, Any]:
    """Parse a small, deterministic Markdown subset without semantic mapping."""
    title: Optional[str] = None
    preamble_lines: List[str] = []
    sections: List[Dict[str, Any]] = []
    current_section: Optional[Dict[str, Any]] = None
    current_lines: List[str] = []
    first_heading_seen = False
    fence_char: Optional[str] = None
    fence_length = 0

    for line in markdown.splitlines():
        fence_match = _FENCE_RE.match(line)
        if fence_char is not None:
            if current_section is None:
                preamble_lines.append(line)
            else:
                current_lines.append(line)
            if fence_match:
                marker = fence_match.group("marker")
                if (
                    marker[0] == fence_char
                    and len(marker) >= fence_length
                    and not fence_match.group("rest").strip()
                ):
                    fence_char = None
                    fence_length = 0
            continue

        if fence_match:
            marker = fence_match.group("marker")
            fence_char = marker[0]
            fence_length = len(marker)
            if current_section is None:
                preamble_lines.append(line)
            else:
                current_lines.append(line)
            continue

        heading_match = _ATX_HEADING_RE.match(line)
        if not heading_match:
            if current_section is None:
                preamble_lines.append(line)
            else:
                current_lines.append(line)
            continue

        if current_section is not None:
            current_section["content"] = _trim_blank_lines(current_lines)
            sections.append(current_section)
            current_section = None
            current_lines = []

        level = len(heading_match.group("marks"))
        heading = heading_match.group("text") or ""
        heading = _CLOSING_HASHES_RE.sub("", heading).strip()

        if not first_heading_seen and level == 1:
            while preamble_lines and not preamble_lines[-1].strip():
                preamble_lines.pop()
            title = heading
        else:
            current_section = {
                "level": level,
                "heading": heading,
            }
        first_heading_seen = True

    if current_section is not None:
        current_section["content"] = _trim_blank_lines(current_lines)
        sections.append(current_section)

    return {
        "format": "markdown",
        "title": title,
        "preamble": _trim_blank_lines(preamble_lines),
        "sections": sections,
    }


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
            "load_repository_profile",
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
                "profile_urls": [
                    (
                        f"https://raw.githubusercontent.com/{parsed['owner']}"
                        f"/{parsed['repo']}/HEAD/.github/ISSUE_RESOLVER.md"
                    ),
                    (
                        f"https://raw.githubusercontent.com/{parsed['owner']}"
                        f"/{parsed['repo']}/HEAD/ISSUE_RESOLVER.md"
                    ),
                ],
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

    def _load_repository_profile(self, params: Dict[str, Any]) -> Dict[str, Any]:
        profile_source = params.get("profile_source")
        if not isinstance(profile_source, str) or not profile_source.strip():
            return {
                "status": "error",
                "message": "profile_source is required for action load_repository_profile.",
            }

        profile_markdown = params.get("profile_markdown")
        if not isinstance(profile_markdown, str) or not profile_markdown.strip():
            return {
                "status": "error",
                "message": (
                    "profile_markdown is required for action "
                    "load_repository_profile."
                ),
            }

        return {
            "status": "ready",
            "action": "load_repository_profile",
            "workflow_version": WORKFLOW_VERSION,
            "profile_context": {
                "label": "Repository ISSUE_RESOLVER.md profile",
                "provenance": {
                    "kind": "caller_fetched_repository_profile",
                    "source": profile_source,
                },
                "authority": {
                    "classification": "repository_context_only",
                    "can_override_constitution": False,
                    "can_grant_authority": False,
                },
                "document": _parse_profile_markdown(profile_markdown),
            },
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
        if action == "load_repository_profile":
            return self._load_repository_profile(params)
        if action == "workflow_overview":
            overview = get_workflow_overview()
            overview["action"] = "workflow_overview"
            return overview
        if action == "stage_checklist":
            return self._stage_checklist(params)
        if action == "validate_commit_message":
            return self._validate_commit_message(params)
        return {"status": "error", "message": "Unhandled action."}
