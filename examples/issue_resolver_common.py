"""
Shared helpers for dev_tools/issue_resolver agent-loop examples.

The skill returns API URLs and checklists only. Example scripts fetch GitHub
issue context after ``prepare`` to demonstrate the two-phase pattern agents follow.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


def _github_get(url: str, token: Optional[str] = None) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "skillware-issue-resolver-example",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        return {"_fetch_error": exc.code, "_url": url}


def _raw_get(url: str, limit: int = 8000) -> str:
    request = urllib.request.Request(
        url, headers={"User-Agent": "skillware-issue-resolver-example"}
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode()[:limit]
    except urllib.error.HTTPError:
        return ""


def enrich_prepare_result(
    result: Dict[str, Any], token: Optional[str] = None
) -> Dict[str, Any]:
    """Attach issue body, comments, and README excerpt after action prepare."""
    if result.get("status") != "ready" or result.get("action") != "prepare":
        return result

    issue_api = result["issue"]["api_url"]
    issue_data = _github_get(issue_api, token)
    comments = _github_get(f"{issue_api}/comments", token)
    readme_excerpt = _raw_get(result["repository"]["readme_url"])

    enriched = dict(result)
    enriched["agent_fetched_context"] = {
        "issue": issue_data,
        "comments": comments if isinstance(comments, list) else [],
        "readme_excerpt": readme_excerpt,
        "note": (
            "Fetched by the example script after prepare. "
            "The skill itself does not call GitHub."
        ),
    }
    return enriched


def slim_for_local_model(
    result: Dict[str, Any],
    max_body: int = 4000,
    max_readme: int = 3000,
) -> Dict[str, Any]:
    """Trim large GitHub payloads for smaller local models."""
    if "agent_fetched_context" not in result:
        return result
    slim = dict(result)
    ctx = dict(slim["agent_fetched_context"])
    issue = ctx.get("issue")
    if isinstance(issue, dict) and isinstance(issue.get("body"), str):
        body = issue["body"]
        if len(body) > max_body:
            ctx["issue"] = {
                **issue,
                "body": body[:max_body] + "\n...[truncated for model context]...",
            }
    readme = ctx.get("readme_excerpt")
    if isinstance(readme, str) and len(readme) > max_readme:
        ctx["readme_excerpt"] = readme[:max_readme] + "\n...[truncated]..."
    slim["agent_fetched_context"] = ctx
    return slim


def execute_skill(
    skill: Any,
    arguments: Dict[str, Any],
    github_token: Optional[str] = None,
    *,
    slim: bool = False,
) -> Dict[str, Any]:
    """Run skill.execute and enrich prepare results like the agent loops do."""
    result = skill.execute(arguments)
    if result.get("action") == "prepare":
        result = enrich_prepare_result(result, github_token)
        if slim:
            result = slim_for_local_model(result)
    return result
