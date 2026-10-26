# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

"""
Deterministic registry matching and discovery engine for Skillware.

Provides lexical and semantic intent matching, prerequisite readiness probing,
git commit freshness extraction, and action/parameter deep-inspection for
human operators, the CLI, and autonomous agents.
"""

from __future__ import annotations

import datetime
import difflib
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import yaml

from skillware.core.discovery import (
    existing_skill_root_paths,
    is_skill_dir,
)
from skillware.core.manifest_schema import normalize_manifest_v2
from skillware.core.secrets import audit_manifest_env_vars

# Common English question words and stop words to filter out during query parsing.
_STOPWORDS: Set[str] = {
    "a",
    "about",
    "also",
    "an",
    "and",
    "any",
    "are",
    "as",
    "at",
    "be",
    "by",
    "can",
    "could",
    "do",
    "does",
    "find",
    "for",
    "from",
    "has",
    "have",
    "help",
    "how",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "just",
    "like",
    "me",
    "my",
    "of",
    "on",
    "or",
    "our",
    "please",
    "search",
    "show",
    "skill",
    "skills",
    "some",
    "that",
    "the",
    "then",
    "there",
    "to",
    "tool",
    "tools",
    "us",
    "use",
    "using",
    "was",
    "we",
    "were",
    "what",
    "when",
    "which",
    "will",
    "with",
    "would",
    "you",
}


def _tokenize(text: str) -> List[str]:
    """Extract lowercase alphanumeric words and identifiers from text."""
    if not text:
        return []
    cleaned = re.sub(r"[^\w\s\-]", " ", text.lower())
    raw_tokens = re.findall(r"[a-z0-9]+", cleaned)
    return [t for t in raw_tokens if t]


def _stem(word: str) -> str:
    """Lightweight deterministic morphological suffix and trailing vowel stripper."""
    word = word.lower().strip()
    if len(word) > 4:
        for suffix in (
            "ing",
            "tion",
            "tions",
            "ment",
            "ments",
            "ers",
            "er",
            "es",
            "ed",
            "s",
        ):
            if word.endswith(suffix):
                word = word[: -len(suffix)]
                break
    return word.rstrip("e")


def _fuzzy_match(token: str, candidate: str, threshold: float = 0.80) -> bool:
    """Return True if token matches candidate directly, by stem, prefix/substring, or ratio."""
    token = token.lower()
    candidate = candidate.lower()
    if token == candidate:
        return True

    # Substring in compound candidate (e.g. 'orf' in 'find_orfs', 'email' in 'send_email')
    if len(token) >= 3 and token in candidate:
        return True
    # Substring in compound token (e.g. 'send' in 'send_email')
    if ("_" in token or "-" in token) and candidate in token:
        return True
    if (
        len(candidate) >= 4
        and len(token) >= 4
        and candidate in token
        and (len(candidate) / len(token) >= 0.75)
    ):
        return True

    # Check parts of compound candidate (e.g. 'attachment' in 'download_attachment')
    if "_" in candidate or "-" in candidate:
        for part in re.split(r"[_\-]+", candidate):
            if part and _fuzzy_match(token, part, threshold=threshold):
                return True

    stem_t = _stem(token)
    stem_c = _stem(candidate)
    if stem_t and stem_c:
        if stem_t == stem_c:
            return True
        if len(stem_t) >= 4 and len(stem_c) >= 4:
            if stem_c.startswith(stem_t) or stem_t.startswith(stem_c):
                return True

    if len(token) >= 4 and len(candidate) >= 4:
        ratio = difflib.SequenceMatcher(None, token, candidate).ratio()
        if ratio >= threshold:
            return True

    return False


def _batch_git_commit_dates(roots: Sequence[Path]) -> Dict[str, str]:
    """
    Attempt to extract the latest git commit date (%cs, YYYY-MM-DD) for all
    discovered skill folders in one fast batch call.
    """
    dates: Dict[str, str] = {}
    try:
        cmd = [
            "git",
            "log",
            "-n",
            "300",
            "--format=COMMIT:%cs",
            "--name-only",
            "skills/",
        ]
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
            timeout=2.0,
        )
        if proc.returncode == 0 and proc.stdout:
            current_date: Optional[str] = None
            for line in proc.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                if line.startswith("COMMIT:"):
                    current_date = line.split(":", 1)[1].strip()
                elif current_date and line.startswith("skills/"):
                    parts = line.split("/")
                    if len(parts) >= 3:
                        skill_id = f"{parts[1]}/{parts[2]}"
                        if skill_id not in dates:
                            dates[skill_id] = current_date
    except Exception:
        pass
    return dates


@dataclass(frozen=True)
class SkillMatchResult:
    """Ranked discovery result for a matched skill."""

    skill_id: str
    category: str
    confidence_pct: int
    summary: str
    issuer: str
    last_updated: str
    is_ready: bool
    missing_prerequisites: List[str]
    matched_actions: List[str]
    shape: str = "atomic"
    tier: str = "core"
    target: str = "software"
    tags: List[str] = field(default_factory=list)
    matched_terms: List[str] = field(default_factory=list)
    agent_hint: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert the result to a clean dictionary representation."""
        return {
            "skill_id": self.skill_id,
            "category": self.category,
            "confidence_pct": self.confidence_pct,
            "summary": self.summary,
            "issuer": self.issuer,
            "last_updated": self.last_updated,
            "is_ready": self.is_ready,
            "missing_prerequisites": list(self.missing_prerequisites),
            "matched_actions": list(self.matched_actions),
            "shape": self.shape,
            "tier": self.tier,
            "target": self.target,
            "tags": list(self.tags),
            "matched_terms": list(self.matched_terms),
            "agent_hint": self.agent_hint,
        }


class SkillMatcher:
    """
    In-memory registry index and relevance matcher.

    Indexes skills across manifest.yaml, card.json, and instructions.md.
    Supports query normalization, multi-field weighted scoring, operational
    readiness verification, and detail inspection.
    """

    def __init__(
        self,
        roots: Optional[Sequence[Path | str]] = None,
        *,
        autoload: bool = True,
    ) -> None:
        if roots is not None:
            self.roots = [Path(r).expanduser().resolve() for r in roots]
        else:
            self.roots = existing_skill_root_paths()

        self._index: List[Dict[str, Any]] = []
        self._index_by_id: Dict[str, Dict[str, Any]] = {}
        if autoload:
            self.build_index()

    def refresh(self) -> None:
        """Rebuild the registry index."""
        self.build_index()

    def build_index(self) -> List[Dict[str, Any]]:
        """Walk all skill roots and index manifest, card, and instructions metadata."""
        git_dates = _batch_git_commit_dates(self.roots)
        indexed: List[Dict[str, Any]] = []
        seen_ids: Set[str] = set()

        for root in self.roots:
            if not root.is_dir():
                continue
            for manifest_path in sorted(root.glob("*/*/manifest.yaml")):
                skill_dir = manifest_path.parent
                if not is_skill_dir(skill_dir):
                    continue

                category = skill_dir.parent.name
                skill_name = skill_dir.name
                skill_id = f"{category}/{skill_name}"

                if skill_id in seen_ids:
                    # First root in resolution order wins (shadowing semantics)
                    continue
                seen_ids.add(skill_id)

                try:
                    raw_manifest = (
                        yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
                    )
                except Exception:
                    raw_manifest = {}

                # Apply Manifest v2 normalizer (tier, shape, target, tags)
                manifest = normalize_manifest_v2(raw_manifest)

                # Card metadata
                card_data: Dict[str, Any] = {}
                card_path = skill_dir / "card.json"
                if card_path.is_file():
                    try:
                        card_data = (
                            json.loads(card_path.read_text(encoding="utf-8")) or {}
                        )
                    except Exception:
                        card_data = {}

                # Instructions text
                instructions_path = skill_dir / "instructions.md"
                instructions_text = ""
                if instructions_path.is_file():
                    try:
                        instructions_text = instructions_path.read_text(
                            encoding="utf-8"
                        )
                    except Exception:
                        instructions_text = ""

                # Summary determination
                card_summary = card_data.get("description", "").strip()
                manifest_short = manifest.get("short_description", "").strip()
                manifest_desc = manifest.get("description", "").strip()
                summary = card_summary or manifest_short or manifest_desc

                # Truncate summary for single-line display if needed
                if len(summary) > 140:
                    dot_idx = summary.find(". ")
                    if dot_idx != -1 and dot_idx <= 140:
                        summary = summary[: dot_idx + 1]
                    else:
                        summary = summary[:137] + "…"

                # Issuer string
                issuer_val = manifest.get("issuer") or card_data.get("issuer") or ""
                if isinstance(issuer_val, dict):
                    issuer_str = (
                        issuer_val.get("github")
                        or issuer_val.get("name")
                        or issuer_val.get("org")
                        or ""
                    )
                else:
                    issuer_str = str(issuer_val).strip()

                # Freshness: git date fallback to manifest mtime
                if skill_id in git_dates:
                    last_updated = git_dates[skill_id]
                else:
                    try:
                        mtime = os.path.getmtime(manifest_path)
                        last_updated = datetime.datetime.fromtimestamp(
                            mtime, datetime.timezone.utc
                        ).strftime("%Y-%m-%d")
                    except Exception:
                        last_updated = "unknown"

                # Operational Readiness Probing
                envs_status, envs_detail = audit_manifest_env_vars(manifest)
                is_ready = envs_status != "fail"
                missing_prerequisites: List[str] = []
                if not is_ready and envs_detail.startswith("missing: "):
                    missing_prerequisites = [
                        k.strip()
                        for k in envs_detail.replace("missing: ", "").split(",")
                        if k.strip()
                    ]

                # Actions & parameters extraction
                actions_dict, param_names = self._extract_actions_and_params(manifest)

                record: Dict[str, Any] = {
                    "skill_id": skill_id,
                    "category": category,
                    "name": skill_name,
                    "title": manifest.get("name") or card_data.get("name") or skill_id,
                    "version": str(manifest.get("version", "0.1.0")),
                    "description": manifest_desc,
                    "summary": summary,
                    "issuer": issuer_str,
                    "last_updated": last_updated,
                    "is_ready": is_ready,
                    "missing_prerequisites": missing_prerequisites,
                    "actions": actions_dict,
                    "action_names": sorted(list(actions_dict.keys())),
                    "parameters": sorted(list(param_names)),
                    "shape": manifest.get("shape", "atomic"),
                    "tier": manifest.get("tier", "core"),
                    "target": manifest.get("target") or ["software"],
                    "tags": manifest.get("tags") or [],
                    "requirements": manifest.get("requirements") or [],
                    "instructions_text": instructions_text,
                    "skill_dir": str(skill_dir),
                    "manifest_path": str(manifest_path),
                    "card_path": str(card_path) if card_path.is_file() else None,
                }
                indexed.append(record)

        self._index = indexed
        self._index_by_id = {r["skill_id"]: r for r in indexed}
        return self._index

    @staticmethod
    def _extract_actions_and_params(
        manifest: Dict[str, Any],
    ) -> Tuple[Dict[str, str], Set[str]]:
        """Extract declared actions and parameter names from a manifest."""
        actions: Dict[str, str] = {}
        param_names: Set[str] = set()

        raw_actions = manifest.get("actions")
        if isinstance(raw_actions, list):
            for item in raw_actions:
                if isinstance(item, dict):
                    act_name = item.get("name")
                    if act_name:
                        actions[str(act_name)] = str(item.get("description", ""))
                elif isinstance(item, str):
                    actions[item] = ""
        elif isinstance(raw_actions, dict):
            for act_name, meta in raw_actions.items():
                if isinstance(meta, dict):
                    actions[str(act_name)] = str(meta.get("description", ""))
                else:
                    actions[str(act_name)] = str(meta or "")

        # Also inspect parameters schema for action enums
        params_schema = manifest.get("parameters") or {}
        if isinstance(params_schema, dict):
            props = params_schema.get("properties")
            if not isinstance(props, dict):
                props = {
                    k: v
                    for k, v in params_schema.items()
                    if k not in ("type", "required", "properties", "$schema")
                }
            for p_name, p_meta in props.items():
                param_names.add(str(p_name))
                if p_name == "action" and isinstance(p_meta, dict):
                    enum_acts = p_meta.get("enum")
                    if isinstance(enum_acts, list):
                        for ea in enum_acts:
                            if str(ea) not in actions:
                                actions[str(ea)] = str(p_meta.get("description", ""))

        return actions, param_names

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        category: Optional[str] = None,
        ready_only: bool = False,
        shape: Optional[str] = None,
        tier: Optional[str] = None,
        target: Optional[str] = None,
        tag: Optional[str] = None,
        min_confidence: int = 0,
        min_score: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[SkillMatchResult]:
        """
        Search and score skills against a query.

        Args:
            query: Natural language query, task description, or skill identifier.
            top_k: Maximum number of skills to return (default: 5).
            category: Filter to a specific category (e.g. 'bio', 'defi').
            ready_only: If True, only include skills with all prerequisites met.
            shape: Filter by Manifest v2 shape ('atomic', 'workflow', 'middleware', 'stream').
            tier: Filter by Manifest v2 tier ('core', 'cloud', 'enterprise').
            target: Filter by Manifest v2 substrate ('software', 'hardware', 'bioware').
            tag: Filter by domain tag.
            min_confidence: Minimum score percentage threshold (0-100).
            min_score: Alias for min_confidence.
            limit: Alias for top_k.
        """
        if limit is not None:
            top_k = limit
        if min_score is not None:
            min_confidence = min_score

        clean_query = query.strip()
        if not clean_query:
            return []

        all_query_tokens = _tokenize(clean_query)
        if not all_query_tokens:
            return []

        content_tokens = [t for t in all_query_tokens if t not in _STOPWORDS]
        if not content_tokens:
            # Query contains exclusively English stopwords with no actionable intent keywords.
            return []

        tokens_to_match = content_tokens
        norm_query_str = " ".join(all_query_tokens)

        results: List[SkillMatchResult] = []

        for record in self._index:
            # 1. Structural Filters
            if category and record["category"].lower() != category.lower():
                continue
            if ready_only and not record["is_ready"]:
                continue
            if shape and record["shape"].lower() != shape.lower():
                continue
            if tier and record["tier"].lower() != tier.lower():
                continue
            if target:
                record_targets = [str(t).lower() for t in record["target"]]
                if target.lower() not in record_targets:
                    continue
            if tag:
                record_tags = [str(t).lower() for t in record["tags"]]
                if tag.lower() not in record_tags:
                    continue

            # 2. Relevance Scoring
            confidence_pct, matched_terms, matched_actions = self._score_record(
                record,
                clean_query,
                norm_query_str,
                all_query_tokens,
                tokens_to_match,
            )

            if confidence_pct <= 0 or confidence_pct < min_confidence:
                continue

            agent_hint = self._build_agent_hint(record, confidence_pct, matched_actions)

            res = SkillMatchResult(
                skill_id=record["skill_id"],
                category=record["category"],
                confidence_pct=confidence_pct,
                summary=record["summary"],
                issuer=record["issuer"],
                last_updated=record["last_updated"],
                is_ready=record["is_ready"],
                missing_prerequisites=record["missing_prerequisites"],
                matched_actions=matched_actions,
                shape=record["shape"],
                tier=record["tier"],
                target=(
                    record["target"][0]
                    if isinstance(record["target"], list) and record["target"]
                    else "software"
                ),
                tags=record["tags"],
                matched_terms=matched_terms,
                agent_hint=agent_hint,
            )
            results.append(res)

        # Sort descending by confidence, then ascending by skill_id
        results.sort(key=lambda r: (-r.confidence_pct, r.skill_id))
        return results[:top_k]

    def _score_record(
        self,
        record: Dict[str, Any],
        raw_query: str,
        norm_query: str,
        all_tokens: List[str],
        content_tokens: List[str],
    ) -> Tuple[int, List[str], List[str]]:
        """Compute match confidence (0-100) and identify matched terms/actions."""
        skill_id = record["skill_id"].lower()
        name = record["name"].lower()
        category = record["category"].lower()
        title = record["title"].lower()
        summary = record["summary"].lower()
        desc = record["description"].lower()
        tags = [t.lower() for t in record["tags"]]
        actions = {a.lower(): d.lower() for a, d in record["actions"].items()}
        params = [p.lower() for p in record["parameters"]]
        instr = record["instructions_text"].lower()

        # Direct exact matches
        clean_raw = raw_query.lower().strip()
        if clean_raw in (skill_id, name):
            return 100, [raw_query], list(record["actions"].keys())[:3]

        if clean_raw in category:
            base_score = 65.0
        else:
            base_score = 0.0

        score = base_score
        matched_tokens: Set[str] = set()
        matched_actions: Set[str] = set()

        # Check full query substring in key fields
        if norm_query in desc or norm_query in summary:
            score += 25.0
            matched_tokens.update(content_tokens)
        elif norm_query in instr:
            score += 15.0
            matched_tokens.update(content_tokens)

        # Evaluate individual tokens
        for token in content_tokens:
            token_matched = False

            # Skill ID / name component
            if token in name or token in skill_id:
                score += 35.0
                token_matched = True

            # Action name exact or fuzzy
            for act_name, act_desc in actions.items():
                if _fuzzy_match(token, act_name):
                    score += 30.0
                    token_matched = True
                    matched_actions.add(act_name)
                elif token in act_desc:
                    score += 12.0
                    token_matched = True
                    matched_actions.add(act_name)

            # Domain tags
            for t in tags:
                if _fuzzy_match(token, t):
                    score += 25.0
                    token_matched = True

            # Category
            if _fuzzy_match(token, category):
                score += 20.0
                token_matched = True

            # Title
            if token in title:
                score += 18.0
                token_matched = True

            # Summary & Description
            if token in summary or token in desc:
                score += 12.0
                token_matched = True

            # Parameters
            if any(_fuzzy_match(token, p) for p in params):
                score += 8.0
                token_matched = True

            # Instructions text
            if token in instr:
                score += 5.0
                token_matched = True

            if token_matched:
                matched_tokens.add(token)

        # Token coverage calculation
        num_query_tokens = max(len(content_tokens), 1)
        coverage_ratio = len(matched_tokens) / num_query_tokens

        if coverage_ratio == 0:
            return 0, [], []

        # Coverage weighting: penalize partial token coverage
        score = score * (coverage_ratio**1.8)

        # Full coverage bonus
        if coverage_ratio >= 1.0:
            score += 20.0

        # Substring in skill_id bonus
        if any(token in skill_id for token in content_tokens):
            score += 12.0

        # Normalization to 0-100 percentage
        confidence = int(min(max(score, 0.0), 98.0))

        # Clamp single-token weak matches
        if len(content_tokens) == 1 and coverage_ratio == 1.0:
            if any(_fuzzy_match(content_tokens[0], a) for a in actions):
                confidence = max(confidence, 85)
            elif content_tokens[0] in skill_id or any(
                _fuzzy_match(content_tokens[0], t) for t in tags
            ):
                confidence = max(confidence, 82)
            elif content_tokens[0] in summary:
                confidence = min(max(confidence, 40), 72)

        return confidence, sorted(list(matched_tokens)), sorted(list(matched_actions))

    @staticmethod
    def _build_agent_hint(
        record: Dict[str, Any],
        confidence_pct: int,
        matched_actions: List[str],
    ) -> str:
        """Synthesize actionable advice for host LLMs and agent frameworks."""
        skill_id = record["skill_id"]
        is_ready = record["is_ready"]
        missing_prereqs = record["missing_prerequisites"]
        actions = matched_actions or record["action_names"][:2]
        act_hint = (
            f"Recommended action(s): {', '.join(actions)}."
            if actions
            else "Inspect action schema before calling."
        )

        if not is_ready:
            missing_str = ", ".join(missing_prereqs)
            return (
                f"Candidate '{skill_id}' matches with {confidence_pct}% confidence, "
                f"but missing required environment variable(s): {missing_str}. "
                "Advise operator to configure credentials or select an offline alternative."
            )

        if confidence_pct >= 80:
            return (
                f"High confidence match on '{skill_id}' ({confidence_pct}%). "
                f"Skill is verified ready for immediate execution. {act_hint}"
            )
        elif confidence_pct >= 50:
            return (
                f"Moderate match on '{skill_id}' ({confidence_pct}%). "
                f"Verify intent with operator. {act_hint}"
            )
        return (
            f"Low confidence match on '{skill_id}' ({confidence_pct}%). "
            "Confirm task parameters before invocation."
        )

    def inspect(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """
        Deep-inspect a skill by ID.

        Returns comprehensive metadata including parameter schemas,
        taxonomy badges, readiness, and referenced example scripts.
        """
        record = self._index_by_id.get(skill_id)
        if not record:
            return None

        # Discover associated examples from examples/README.md
        examples: List[str] = []
        try:
            repo_root = Path(__file__).resolve().parent.parent.parent
            readme_path = repo_root / "examples" / "README.md"
            if readme_path.is_file():
                for line in readme_path.read_text(encoding="utf-8").splitlines():
                    if line.startswith("| `") and skill_id in line:
                        script_match = re.search(r"\|\s*`([^`]+)`", line)
                        if script_match:
                            examples.append(f"examples/{script_match.group(1)}")
        except Exception:
            pass

        return {
            "skill_id": record["skill_id"],
            "category": record["category"],
            "name": record["name"],
            "title": record["title"],
            "version": record["version"],
            "summary": record["summary"],
            "description": record["description"],
            "issuer": record["issuer"],
            "last_updated": record["last_updated"],
            "is_ready": record["is_ready"],
            "missing_prerequisites": record["missing_prerequisites"],
            "shape": record["shape"],
            "tier": record["tier"],
            "target": record["target"],
            "tags": record["tags"],
            "actions": record["actions"],
            "parameters": record["parameters"],
            "examples": examples,
            "manifest_path": record["manifest_path"],
            "skill_dir": record["skill_dir"],
        }

    def list_categories(self) -> Dict[str, int]:
        """Return counts of skills indexed per category."""
        counts: Dict[str, int] = {}
        for r in self._index:
            cat = r["category"]
            counts[cat] = counts.get(cat, 0) + 1
        return dict(sorted(counts.items()))

    def get_skill(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """Return the raw index document for a skill ID."""
        return self._index_by_id.get(skill_id)


def find_skills(
    query: str,
    roots: Optional[Sequence[Path | str] | Path | str] = None,
    skills_root: Optional[Sequence[Path | str] | Path | str] = None,
    **kwargs: Any,
) -> List[SkillMatchResult]:
    """Convenience helper to search the local Skillware registry."""
    effective_roots = roots or skills_root
    if isinstance(effective_roots, (Path, str)):
        effective_roots = [effective_roots]
    matcher = SkillMatcher(roots=effective_roots)
    return matcher.search(query, **kwargs)


def inspect_skill(
    skill_id: str,
    roots: Optional[Sequence[Path | str] | Path | str] = None,
    skills_root: Optional[Sequence[Path | str] | Path | str] = None,
    raise_if_not_found: bool = False,
) -> Optional[Dict[str, Any]]:
    """Convenience helper to inspect a specific skill."""
    effective_roots = roots or skills_root
    if isinstance(effective_roots, (Path, str)):
        effective_roots = [effective_roots]
    matcher = SkillMatcher(roots=effective_roots)
    details = matcher.inspect(skill_id)
    if details is None and raise_if_not_found:
        raise FileNotFoundError(f"Skill '{skill_id}' not found in registry.")
    return details
