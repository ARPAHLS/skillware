import json
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
import yaml
from bs4 import BeautifulSoup
from skillware.core.base_skill import BaseSkill

try:
    import google.genai as genai
    from google.genai import types
except ImportError:  # pragma: no cover - dependency is optional at runtime
    genai = None
    types = None


class TOSEvaluatorSkill(BaseSkill):
    """
    Evaluates whether an automated website action appears permissible based on
    robots.txt and discovered legal policy pages.
    """

    WELL_KNOWN_POLICY_PATHS = [
        "/terms",
        "/terms-of-service",
        "/terms-of-use",
        "/tos",
        "/legal/terms",
        "/legal",
        "/conditions",
        "/policies/terms",
        "/acceptable-use",
        "/aup",
        "/developer-terms",
        "/api-terms",
    ]

    POLICY_KEYWORDS = {
        "terms": 8,
        "terms of service": 12,
        "terms of use": 12,
        "tos": 6,
        "legal": 5,
        "conditions": 4,
        "user agreement": 8,
        "acceptable use": 10,
        "developer terms": 8,
        "api terms": 10,
        "api policy": 9,
        "robots": 3,
    }

    ACTION_PATTERNS = {
        "scrape": [r"\bscrap", r"\bextract", r"\bharvest", r"\bcollect data\b"],
        "crawl": [r"\bcrawl", r"\bspider", r"\bbot\b", r"\bautomated access\b"],
        "index": [r"\bindex", r"\bsearch engine", r"\barchive", r"\bmirror"],
        "api_use": [r"\bapi\b", r"\bdeveloper\b", r"\bintegration\b"],
        "monitor": [r"\bmonitor", r"\bwatch", r"\btrack", r"\bcheck periodically\b"],
        "download": [r"\bdownload", r"\bexport", r"\bbulk\b"],
        "automated_access": [r"\bautomation\b", r"\bscript", r"\bprogrammatic\b"],
    }

    CLAUSE_PATTERNS = [
        {
            "label": "hard_block",
            "severity": "high",
            "weight": -45,
            "patterns": [
                r"may not scrape",
                r"must not scrape",
                r"no scraping",
                r"no crawlers",
                r"no robots",
                r"no automated means",
                r"prohibited automated access",
                r"automated means.*prohibited",
                r"harvest.*prohibited",
                r"crawl.*prohibited",
            ],
        },
        {
            "label": "soft_caution",
            "severity": "medium",
            "weight": -20,
            "patterns": [
                r"prior written consent",
                r"without our permission",
                r"reasonable rate",
                r"rate limit",
                r"commercial use.*restricted",
                r"access.*subject to",
                r"must comply with.*api",
                r"use the api",
            ],
        },
        {
            "label": "permission",
            "severity": "low",
            "weight": 18,
            "patterns": [
                r"permitted to access",
                r"you may use.*api",
                r"public api",
                r"developers may access",
                r"search engines may crawl",
            ],
        },
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Skillware-TOS-Evaluator/0.1 (+https://github.com/ARPAHLS/skillware)"
            }
        )

    @property
    def manifest(self) -> Dict[str, Any]:
        manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {}

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        normalized = self._normalize_input(params)
        if "error" in normalized:
            return normalized

        robots_assessment = self._evaluate_robots(
            normalized["origin"], normalized["target_url"], normalized["user_agent"]
        )
        policy_candidates = self._discover_policy_pages(
            normalized["origin"], robots_assessment, normalized["max_terms_pages"]
        )
        tos_assessment = self._evaluate_policy_pages(
            normalized, policy_candidates, normalized["max_terms_pages"]
        )

        llm_assessment = None
        if self._should_use_llm(normalized, robots_assessment, tos_assessment):
            llm_assessment = self._run_llm_evaluator(normalized, tos_assessment)

        return self._build_final_result(
            normalized,
            robots_assessment,
            tos_assessment,
            llm_assessment,
            policy_candidates,
        )

    def _normalize_input(self, params: Dict[str, Any]) -> Dict[str, Any]:
        target_url = params.get("target_url", "").strip()
        intended_action = params.get("intended_action", "").strip()
        if not target_url:
            return {"error": "target_url is required."}
        if not intended_action:
            return {"error": "intended_action is required."}

        parsed = urlparse(target_url)
        if not parsed.scheme or not parsed.netloc:
            return {"error": "target_url must be a fully qualified URL."}

        origin = f"{parsed.scheme}://{parsed.netloc}"
        action_type = self._classify_action(intended_action)
        user_agent = params.get("user_agent", self.session.headers["User-Agent"])

        return {
            "target_url": target_url,
            "intended_action": intended_action,
            "action_type": action_type,
            "origin": origin,
            "path": parsed.path or "/",
            "user_agent": user_agent,
            "fetch_mode": params.get("fetch_mode", "lightweight"),
            "use_llm_evaluator": bool(params.get("use_llm_evaluator", False)),
            "llm_provider": params.get("llm_provider", "gemini"),
            "llm_model": params.get("llm_model", "gemini-2.5-flash-lite"),
            "assume_authenticated_session": bool(
                params.get("assume_authenticated_session", False)
            ),
            "max_terms_pages": max(1, min(int(params.get("max_terms_pages", 5)), 10)),
        }

    def _classify_action(self, intended_action: str) -> str:
        lowered = intended_action.lower()
        for action, patterns in self.ACTION_PATTERNS.items():
            if any(re.search(pattern, lowered) for pattern in patterns):
                return action
        return "automated_access"

    def _evaluate_robots(
        self, origin: str, target_url: str, user_agent: str
    ) -> Dict[str, Any]:
        robots_url = f"{origin}/robots.txt"
        assessment = {
            "status": "unavailable",
            "robots_url": robots_url,
            "can_fetch": None,
            "matched_rule": "unknown",
            "crawl_delay": None,
            "request_rate": None,
            "sitemaps": [],
            "reason": "robots.txt could not be retrieved.",
        }

        try:
            response = self.session.get(robots_url, timeout=10)
            if response.status_code >= 400:
                assessment["reason"] = f"robots.txt returned HTTP {response.status_code}."
                return assessment

            parser = RobotFileParser()
            parser.set_url(robots_url)
            parser.parse(response.text.splitlines())

            can_fetch = parser.can_fetch(user_agent, target_url)
            assessment["status"] = "parsed"
            assessment["can_fetch"] = can_fetch
            assessment["matched_rule"] = "allowed" if can_fetch else "disallowed"
            assessment["crawl_delay"] = parser.crawl_delay(user_agent)
            assessment["request_rate"] = parser.request_rate(user_agent)
            assessment["sitemaps"] = parser.site_maps() or []
            assessment["reason"] = (
                "robots.txt allows the target path."
                if can_fetch
                else "robots.txt disallows the target path for the supplied user-agent."
            )
            return assessment
        except requests.RequestException as exc:
            assessment["reason"] = f"robots.txt request failed: {str(exc)}"
            return assessment

    def _discover_policy_pages(
        self, origin: str, robots_assessment: Dict[str, Any], max_terms_pages: int
    ) -> Dict[str, List[Dict[str, Any]]]:
        candidates: Dict[str, Dict[str, Any]] = {}

        for path in self.WELL_KNOWN_POLICY_PATHS:
            url = urljoin(origin, path)
            score = 50 if "terms" in path or "acceptable" in path else 35
            candidates[url] = {
                "url": url,
                "score": score,
                "source": "well_known_path",
                "label": path.strip("/") or "legal",
            }

        html_pages = [origin]
        for sitemap_url in robots_assessment.get("sitemaps", [])[:2]:
            html_pages.append(sitemap_url)

        for url in html_pages:
            discovered = self._extract_candidate_links(url, origin)
            for item in discovered:
                existing = candidates.get(item["url"])
                if existing:
                    existing["score"] = max(existing["score"], item["score"])
                    existing["source"] = f"{existing['source']},{item['source']}"
                else:
                    candidates[item["url"]] = item

        ordered = sorted(candidates.values(), key=lambda item: item["score"], reverse=True)
        return {"candidates": ordered[:max_terms_pages]}

    def _extract_candidate_links(self, page_url: str, origin: str) -> List[Dict[str, Any]]:
        links: List[Dict[str, Any]] = []
        response = self._safe_get(page_url, timeout=10)
        if not response or "html" not in response.headers.get("Content-Type", "").lower():
            return links

        soup = BeautifulSoup(response.text[:300000], "html.parser")
        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href", "").strip()
            text = " ".join(anchor.stripped_strings).strip().lower()
            if not href:
                continue

            absolute = urljoin(page_url, href)
            parsed = urlparse(absolute)
            if not parsed.scheme.startswith("http"):
                continue
            if f"{parsed.scheme}://{parsed.netloc}" != origin:
                continue

            score = self._score_policy_link(absolute.lower(), text)
            if score <= 0:
                continue

            links.append(
                {
                    "url": absolute,
                    "score": score,
                    "source": "link_discovery",
                    "label": text or parsed.path,
                }
            )

        return links

    def _score_policy_link(self, href: str, text: str) -> int:
        combined = f"{href} {text}".lower()
        score = 0
        for keyword, weight in self.POLICY_KEYWORDS.items():
            if keyword in combined:
                score += weight
        return score

    def _evaluate_policy_pages(
        self,
        normalized: Dict[str, Any],
        policy_candidates: Dict[str, List[Dict[str, Any]]],
        max_terms_pages: int,
    ) -> Dict[str, Any]:
        pages_evaluated = []
        clause_hits = []

        for candidate in policy_candidates.get("candidates", [])[:max_terms_pages]:
            url = candidate["url"]
            response = self._safe_get(url, timeout=12)
            if not response:
                continue

            content_type = response.headers.get("Content-Type", "").lower()
            if "html" not in content_type:
                pages_evaluated.append(
                    {
                        "url": url,
                        "status": "skipped",
                        "reason": f"Unsupported content type: {content_type or 'unknown'}",
                    }
                )
                continue

            extracted_sections = self._extract_policy_sections(response.text)
            page_hits = self._score_policy_sections(
                normalized["action_type"], extracted_sections, url
            )
            clause_hits.extend(page_hits)
            pages_evaluated.append(
                {
                    "url": url,
                    "status": "parsed",
                    "candidate_score": candidate["score"],
                    "matched_clauses": len(page_hits),
                }
            )

        clause_hits.sort(key=lambda item: abs(item["score_delta"]), reverse=True)
        aggregate_score = sum(item["score_delta"] for item in clause_hits)
        if not pages_evaluated:
            status = "insufficient_evidence"
            summary = "No candidate Terms or policy pages could be parsed."
        elif any(item["classification"] == "hard_block" for item in clause_hits):
            status = "blocked"
            summary = "Discovered policy text contains an explicit restriction on the requested automated behavior."
        elif aggregate_score <= -20:
            status = "caution"
            summary = "Discovered policy text suggests restrictions or conditions on the requested automated behavior."
        elif aggregate_score > 0:
            status = "allowed"
            summary = "Discovered policy text includes language that appears permissive for the requested behavior."
        else:
            status = "insufficient_evidence"
            summary = "Policy pages were found, but none produced strong action-specific evidence."

        return {
            "status": status,
            "summary": summary,
            "pages_evaluated": pages_evaluated,
            "matched_clauses": clause_hits[:10],
            "aggregate_score": aggregate_score,
        }

    def _extract_policy_sections(self, html: str) -> List[Dict[str, str]]:
        soup = BeautifulSoup(html[:400000], "html.parser")
        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()

        body = soup.body or soup
        sections: List[Dict[str, str]] = []
        current_heading = "General"

        for element in body.find_all(["h1", "h2", "h3", "p", "li"]):
            text = " ".join(element.stripped_strings)
            text = re.sub(r"\s+", " ", text).strip()
            if not text or len(text) < 20:
                continue

            if element.name in {"h1", "h2", "h3"}:
                current_heading = text[:160]
                continue

            sections.append({"heading": current_heading, "text": text[:1200]})

        return sections[:200]

    def _score_policy_sections(
        self, action_type: str, sections: List[Dict[str, str]], page_url: str
    ) -> List[Dict[str, Any]]:
        hits = []
        action_relevance_patterns = self.ACTION_PATTERNS.get(action_type, [])
        for section in sections:
            text_lower = section["text"].lower()
            heading_lower = section["heading"].lower()
            combined = f"{heading_lower} {text_lower}"

            if action_relevance_patterns and not any(
                re.search(pattern, combined) for pattern in action_relevance_patterns
            ):
                generic_automation = re.search(
                    r"automated|bot|crawl|scrap|harvest|api|programmatic", combined
                )
                if not generic_automation:
                    continue

            for clause in self.CLAUSE_PATTERNS:
                for pattern in clause["patterns"]:
                    if re.search(pattern, combined):
                        hits.append(
                            {
                                "url": page_url,
                                "heading": section["heading"],
                                "snippet": section["text"],
                                "classification": clause["label"],
                                "severity": clause["severity"],
                                "score_delta": clause["weight"],
                            }
                        )
                        break

        return hits

    def _should_use_llm(
        self,
        normalized: Dict[str, Any],
        robots_assessment: Dict[str, Any],
        tos_assessment: Dict[str, Any],
    ) -> bool:
        if not normalized.get("use_llm_evaluator"):
            return False
        if tos_assessment["status"] in {"blocked", "allowed"}:
            return False
        if robots_assessment.get("can_fetch") is False:
            return False
        return bool(tos_assessment.get("matched_clauses") or tos_assessment["status"] == "caution")

    def _run_llm_evaluator(
        self, normalized: Dict[str, Any], tos_assessment: Dict[str, Any]
    ) -> Dict[str, Any]:
        provider = normalized["llm_provider"].lower()
        if provider != "gemini":
            return {
                "status": "skipped",
                "reason": f"Unsupported llm_provider '{normalized['llm_provider']}'.",
            }
        if genai is None or types is None:
            return {"status": "skipped", "reason": "google-genai is not installed."}

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return {"status": "skipped", "reason": "GOOGLE_API_KEY is not configured."}

        prompt = {
            "target_url": normalized["target_url"],
            "intended_action": normalized["intended_action"],
            "action_type": normalized["action_type"],
            "matched_clauses": tos_assessment.get("matched_clauses", [])[:6],
            "task": (
                "Classify whether these policy snippets forbid, allow, or condition "
                "the requested action. Return strict JSON with keys: "
                "verdict, confidence_score, rationale."
            ),
        }

        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=normalized["llm_model"],
                contents=json.dumps(prompt, ensure_ascii=True),
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0,
                ),
            )
            parsed = json.loads(response.text)
            return {
                "status": "used",
                "provider": provider,
                "model": normalized["llm_model"],
                "verdict": parsed.get("verdict", "CAUTION"),
                "confidence_score": float(parsed.get("confidence_score", 0.5)),
                "rationale": parsed.get("rationale", "No rationale returned."),
            }
        except Exception as exc:
            return {"status": "error", "reason": f"LLM evaluator failed: {str(exc)}"}

    def _build_final_result(
        self,
        normalized: Dict[str, Any],
        robots_assessment: Dict[str, Any],
        tos_assessment: Dict[str, Any],
        llm_assessment: Optional[Dict[str, Any]],
        policy_candidates: Dict[str, List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        verdict = "INSUFFICIENT_EVIDENCE"
        confidence_score = 0.35
        reason = "Insufficient policy evidence to safely approve the requested action."
        recommended_next_step = "Review the discovered policy pages manually before proceeding."

        if robots_assessment.get("can_fetch") is False:
            verdict = "UNSAFE"
            confidence_score = 0.98
            reason = robots_assessment["reason"]
            recommended_next_step = (
                "Do not automate access to this path unless you have explicit permission."
            )
        elif tos_assessment["status"] == "blocked":
            verdict = "UNSAFE"
            confidence_score = 0.9
            reason = tos_assessment["summary"]
            recommended_next_step = "Avoid the requested action or obtain explicit written permission."
        elif tos_assessment["status"] == "caution":
            verdict = "CAUTION"
            confidence_score = 0.65
            reason = tos_assessment["summary"]
            recommended_next_step = "Prefer an official API or documented integration path if one exists."
        elif tos_assessment["status"] == "allowed" and robots_assessment.get("can_fetch") is not False:
            verdict = "SAFE"
            confidence_score = 0.72
            reason = tos_assessment["summary"]
            recommended_next_step = "Proceed conservatively and continue honoring crawl delays and rate limits."

        if llm_assessment and llm_assessment.get("status") == "used":
            verdict = llm_assessment.get("verdict", verdict)
            confidence_score = max(
                confidence_score,
                llm_assessment.get("confidence_score", confidence_score),
            )
            reason = llm_assessment.get("rationale", reason)

        evidence = []
        if robots_assessment.get("reason"):
            evidence.append(
                {
                    "source": robots_assessment.get("robots_url"),
                    "type": "robots",
                    "snippet": robots_assessment["reason"],
                }
            )
        for clause in tos_assessment.get("matched_clauses", [])[:5]:
            evidence.append(
                {
                    "source": clause["url"],
                    "type": clause["classification"],
                    "heading": clause["heading"],
                    "snippet": clause["snippet"],
                }
            )

        return {
            "is_safe_to_proceed": verdict == "SAFE",
            "confidence_score": round(float(confidence_score), 2),
            "verdict": verdict,
            "reason": reason,
            "recommended_next_step": recommended_next_step,
            "action_type": normalized["action_type"],
            "robots_assessment": robots_assessment,
            "tos_assessment": tos_assessment,
            "llm_assessment": llm_assessment or {"status": "not_used"},
            "discovered_policy_urls": {
                "candidates": [item["url"] for item in policy_candidates.get("candidates", [])]
            },
            "evidence": evidence,
        }

    def _safe_get(self, url: str, timeout: int = 10) -> Optional[requests.Response]:
        try:
            response = self.session.get(url, timeout=timeout, allow_redirects=True)
            if response.status_code >= 400:
                return None
            return response
        except requests.RequestException:
            return None
