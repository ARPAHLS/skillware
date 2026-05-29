"""Resolution workflow definitions for dev_tools/issue_resolver."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

WORKFLOW_VERSION = "0.2"

# Ordered stages — agent must complete each before advancing.
STAGE_ORDER: List[str] = [
    "discover_issue",
    "discover_repository",
    "analyze",
    "plan",
    "implement",
    "verify",
    "pre_commit",
    "commit",
    "pull_request",
]

STAGES: Dict[str, Dict[str, Any]] = {
    "discover_issue": {
        "title": "Discover the issue",
        "summary": "Fetch and understand the GitHub issue before touching the repository.",
        "steps": [
            "Fetch the issue via the GitHub API using issue.api_url from the prepare payload.",
            "Extract title, body, labels, state, assignees, and milestone.",
            "Fetch issue comments and note decisions or acceptance criteria not in the body.",
            "Note linked pull requests, referenced issues, and blocking relationships.",
        ],
        "conditionals": [
            "If the issue is closed, confirm with the user before investing in a new fix.",
            "If labels imply type (bug, docs, enhancement), carry that into later analysis.",
            "If acceptance criteria are missing, infer verifiable criteria from the body and comments.",
        ],
        "next_stage": "discover_repository",
    },
    "discover_repository": {
        "title": "Discover the repository",
        "summary": "Learn how this project is organized and how it expects contributions.",
        "steps": [
            "Read README (repository.readme_url) for purpose, stack, and setup.",
            "Read CONTRIBUTING if present (repository.contributing_url); continue if 404.",
            "Fetch the repository tree (repository.tree_api_url) and map source, test, docs, and CI areas.",
            "Inspect files explicitly referenced by the issue.",
        ],
        "conditionals": [
            "If CONTRIBUTING is missing, infer conventions from README, CI config, and existing code.",
            "If the tree response is truncated, inspect relevant directories selectively.",
            "If the repository is private and no token is configured, stop and request authentication.",
            "If a root-level contributor workflow file exists (any name), read it before planning.",
        ],
        "next_stage": "analyze",
    },
    "analyze": {
        "title": "Analyze impact",
        "summary": "Produce a structured understanding before proposing a plan.",
        "steps": [
            "Write a clear problem statement tied to the issue.",
            "List verifiable acceptance criteria.",
            "List affected paths only after confirming they exist in the tree or issue.",
            "Identify ripple effects on dependents, APIs, or consumers.",
            "Draft up to three options with trade-offs and one recommendation.",
            "State explicit out-of-scope items and caveats.",
        ],
        "conditionals": [
            "If the issue touches public API surface, include compatibility and migration impact.",
            "If the issue mentions security, include threat and data-handling caveats.",
            "If multiple valid approaches exist, rank them; do not hide uncertainty.",
        ],
        "next_stage": "plan",
    },
    "plan": {
        "title": "Present plan and wait for approval",
        "summary": "Deliver the resolution plan and obtain explicit approval before coding.",
        "steps": [
            (
                "Present issue summary, acceptance criteria, affected files, "
                "options, recommendation, caveats, and out-of-scope."
            ),
            "Use the structured output contract from instructions.md.",
            "Wait for explicit user or operator approval of one option.",
        ],
        "conditionals": [
            "If the user narrows scope during review, update the plan before implementation.",
            "If approval is ambiguous, ask one clarifying question instead of guessing.",
            "Do not write implementation code until approval is explicit.",
        ],
        "next_stage": "implement",
    },
    "implement": {
        "title": "Implement the approved plan",
        "summary": "Make the minimal change set that satisfies the approved plan.",
        "steps": [
            "Implement only what the approved plan describes.",
            "Follow conventions observed in discover_repository.",
            "Avoid drive-by refactors, unrelated formatting, or scope creep.",
        ],
        "conditionals": [
            "If the approved plan proves wrong mid-implementation, stop and re-plan with the user.",
            "If new files are required, place them where similar files already live in this repository.",
            "If dependencies change, update whatever manifest or lockfile this project uses.",
        ],
        "next_stage": "verify",
    },
    "verify": {
        "title": "Verify the solution",
        "summary": "Prove the change meets acceptance criteria using this repository's own quality gates.",
        "steps": [
            "Map each acceptance criterion to a diff hunk, test, or observable outcome.",
            "Run verification commands appropriate to this repository and attach evidence.",
            "Re-read the diff for unrelated changes, secrets, and accidental artifacts.",
        ],
        "conditionals": [
            "If the repository defines automated tests, run them and report pass or fail output.",
            "If a linter or formatter is documented or configured, run it on touched paths.",
            (
                "If the project maintains release notes or a changelog and the "
                "change is user-visible, update the file this project uses."
            ),
            "If CI configuration exists, confirm the change is unlikely to break declared checks.",
            "If no automated tests exist, document manual verification steps performed.",
            "If verification fails, return to implement; do not advance to pre_commit.",
        ],
        "next_stage": "pre_commit",
    },
    "pre_commit": {
        "title": "Pre-commit gate",
        "summary": "Confirm the change set is safe to commit.",
        "steps": [
            "Confirm all verify-stage conditionals relevant to this repo are satisfied.",
            "Confirm no credentials, tokens, or .env content appear in the diff.",
            "Confirm the diff contains only files required by the approved plan.",
            "Draft the commit message; call validate_commit_message before committing.",
        ],
        "conditionals": [
            "If validate_commit_message returns violations, fix the message and validate again.",
            "If unrelated staged files exist, unstage them before commit.",
            "If the operator has not authorized commit, stop and hand off the validated message and diff summary.",
        ],
        "next_stage": "commit",
    },
    "commit": {
        "title": "Commit and push",
        "summary": "Create a clean git commit on the correct branch and push to the operator remote.",
        "steps": [
            "Confirm current branch name matches the issue (e.g. feat/issue-N-short-desc).",
            "Confirm push remote points at the operator fork when contributing via fork workflow.",
            "Run git status, scoped git add, git commit, git push -u origin <branch>.",
        ],
        "conditionals": [
            "If origin is the upstream canonical repo, confirm the operator intends to push there.",
            "If the branch tracks the wrong remote, fix upstream before push.",
            "Never force-push shared or default branches unless explicitly instructed.",
            "If commit hooks fail, fix issues and create a new commit; do not skip hooks unless instructed.",
        ],
        "next_stage": "pull_request",
    },
    "pull_request": {
        "title": "Open or update pull request",
        "summary": "Prepare a reviewable PR and support CI through merge.",
        "steps": [
            "Draft a PR description: why, what, how verified, link to the issue.",
            "Complete the repository's pull request template if one exists.",
            "Monitor CI; if checks fail, diagnose, fix, and push follow-up commits.",
            "Address review comments with focused commits.",
        ],
        "conditionals": [
            "If the repository uses Fixes #N or Closes #N linking, include the appropriate reference.",
            "If draft PR is preferred for early feedback, mark draft until verify evidence is attached.",
            "If CI is required and failing, do not declare the resolution complete.",
        ],
        "next_stage": None,
    },
}

# Patterns that indicate AI tooling in Co-authored-by trailers (case-insensitive).
AI_COAUTHOR_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"cursor", re.I),
    re.compile(r"cursoragent", re.I),
    re.compile(r"claude", re.I),
    re.compile(r"anthropic", re.I),
    re.compile(r"copilot", re.I),
    re.compile(r"openai", re.I),
    re.compile(r"chatgpt", re.I),
    re.compile(r"github-actions\[bot\]", re.I),
)

CO_AUTHOR_LINE = re.compile(r"^Co-authored-by:\s*(.+)$", re.I | re.M)

# Explicit code-point ranges (avoids CodeQL py/overly-large-range on wide regex spans).
_EMOJI_RANGES: Tuple[Tuple[int, int], ...] = (
    (0x1F300, 0x1F5FF),  # Misc Symbols and Pictographs
    (0x1F600, 0x1F64F),  # Emoticons
    (0x1F680, 0x1F6FF),  # Transport and Map
    (0x1F900, 0x1F9FF),  # Supplemental Symbols and Pictographs
    (0x2600, 0x26FF),  # Misc symbols
    (0x2700, 0x27BF),  # Dingbats
)


def _contains_emoji(text: str) -> bool:
    return any(
        start <= ord(char) <= end for char in text for start, end in _EMOJI_RANGES
    )


def get_stage_checklist(stage: str) -> Optional[Dict[str, Any]]:
    """Return checklist payload for a workflow stage, or None if unknown."""
    if stage not in STAGES:
        return None
    meta = STAGES[stage]
    index = STAGE_ORDER.index(stage)
    return {
        "status": "ready",
        "workflow_version": WORKFLOW_VERSION,
        "stage": stage,
        "stage_index": index + 1,
        "stage_count": len(STAGE_ORDER),
        "title": meta["title"],
        "summary": meta["summary"],
        "steps": list(meta["steps"]),
        "conditionals": list(meta["conditionals"]),
        "next_stage": meta["next_stage"],
        "must_complete_before": meta["next_stage"],
        "gate_rule": (
            "Do not advance to the next stage while blockers remain or "
            "required conditionals for this repository are unaddressed."
        ),
    }


def get_workflow_overview() -> Dict[str, Any]:
    """Return ordered stage list for agents starting a resolution."""
    return {
        "status": "ready",
        "workflow_version": WORKFLOW_VERSION,
        "stage_order": list(STAGE_ORDER),
        "stages": [
            {
                "stage": name,
                "title": STAGES[name]["title"],
                "next_stage": STAGES[name]["next_stage"],
            }
            for name in STAGE_ORDER
        ],
        "future_profiles_note": (
            "v3 may support a repository-root workflow file (e.g. ISSUE_RESOLVER.md) "
            "that extends these universal stages with project-specific checks."
        ),
    }


def validate_commit_message(
    message: str,
    *,
    allow_ai_coauthor: bool = False,
) -> Dict[str, Any]:
    """Validate a proposed commit message against universal contribution rules."""
    violations: List[str] = []
    msg = (message or "").strip()

    if not msg:
        violations.append("Commit message is empty.")
    else:
        subject = msg.splitlines()[0].strip()
        if not subject:
            violations.append("Commit subject line is empty.")
        if _contains_emoji(subject):
            violations.append("Commit subject must not contain emojis.")

        for match in CO_AUTHOR_LINE.finditer(msg):
            trailer_value = match.group(1).strip()
            if allow_ai_coauthor:
                continue
            for pattern in AI_COAUTHOR_PATTERNS:
                if pattern.search(trailer_value):
                    violations.append(
                        "Co-authored-by trailer appears to credit an AI tool or agent "
                        f"({trailer_value}). Remove unless allow_ai_coauthor is true."
                    )
                    break

    required = [
        "Imperative mood subject line (Add, Fix, Document, ...).",
        "Reference the issue when applicable (Fixes #N or Refs #N).",
        "No emojis in the subject.",
    ]
    if not allow_ai_coauthor:
        required.append(
            "No Co-authored-by trailers crediting AI agents unless allow_ai_coauthor is true."
        )

    ok = len(violations) == 0
    return {
        "status": "ready" if ok else "rejected",
        "ok": ok,
        "violations": violations,
        "required_before_commit": required,
    }
