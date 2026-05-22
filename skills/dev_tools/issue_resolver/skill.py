import os
import re
from typing import Any, Dict

from skillware.core.base_skill import BaseSkill


class IssueResolverSkill(BaseSkill):
    """
    Parses and validates inputs for the Issue Resolver skill, then returns a
    structured prompt payload the calling agent uses to perform analysis.

    The skill itself does not call the GitHub API or write code. It normalises
    inputs, resolves credentials, builds a deterministic analysis context, and
    hands control back to the agent's own reasoning and tool-use capabilities.
    """

    _GITHUB_ISSUE_RE = re.compile(
        r"https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/issues/(?P<number>\d+)"
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
        """
        Extracts owner, repo, and issue number from a GitHub issue URL.
        Returns a dict with keys: owner, repo, number, api_url, raw_url.
        Raises ValueError if the URL does not match the expected pattern.
        """
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
        """
        Returns the GitHub token to use, preferring the runtime parameter over
        the environment variable. Returns an empty string if neither is set.
        """
        token = (params.get("github_token") or "").strip()
        if not token:
            token = (
                self.config.get("GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
            )
        return token

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validates inputs and returns a structured analysis context.

        The returned dict contains everything the calling agent needs to begin
        the resolution workflow using its own tools (HTTP fetching, file
        inspection, reasoning). The agent should follow the instructions in
        instructions.md when interpreting this payload.
        """
        issue_url = (params.get("issue_url") or "").strip()
        if not issue_url:
            return {
                "status": "error",
                "message": "issue_url is required and must not be empty.",
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
                "Follow the workflow in instructions.md. Fetch the issue, "
                "read the repository context, then produce the structured "
                "resolution plan as described."
            ),
        }
