"""
UK Companies House Handler Skill

Deterministic skill that wraps the Companies House REST API into structured
actions with status-based responses. Supports company search, profile lookup,
officer and PSC listing with role/name filters, filing history with helpers,
turn-by-turn pipeline orchestration, and composite shortcuts.
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
import yaml
from skillware.core.base_skill import BaseSkill

_SKILL_DIR = os.path.dirname(__file__)
_BASE_URL = "https://api.company-information.service.gov.uk"

_VALID_ACTIONS = {
    "resolve_company",
    "get_company_profile",
    "get_officers",
    "get_pscs",
    "get_filing_history",
    "run_pipeline",
    "resolve_and_get_officers",
    "resolve_and_get_filings",
    "resolve_company_officer",
}

_ACTIONS_REQUIRING_COMPANY_NUMBER = {
    "get_company_profile",
    "get_officers",
    "get_pscs",
    "get_filing_history",
}

_OPERATIONAL_RETRY_HINT = (
    "Retry after a short backoff. Companies House allows 600 requests per "
    "5 minutes per API key. If you know the 8-character company_number, "
    "pass it directly. Otherwise check spelling and pass a clean company "
    "name in query (no conversational prefixes)."
)


class UkCompaniesHouseHandlerSkill(BaseSkill):
    """Deterministic UK Companies House API handler for agents."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.companies_house_api_key = self.credential("COMPANIES_HOUSE_API_KEY")

        if not self.companies_house_api_key:
            raise ValueError(
                "COMPANIES_HOUSE_API_KEY must be provided "
                "through environment variables or config."
            )

        # Load bundled reference data
        self.api_index = self._load_json(
            os.path.join(_SKILL_DIR, "data", "api_index.json")
        )
        self.terminology_map = self._load_yaml(
            os.path.join(_SKILL_DIR, "data", "terminology_map.yaml")
        )

    @property
    def manifest(self) -> Dict[str, Any]:
        path = os.path.join(_SKILL_DIR, "manifest.yaml")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    # --- Main Entry Point ---

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch to the appropriate action handler."""
        action = params.get("action")
        context = params.get("context", {})

        if not action:
            return self._error_response(
                "missing_action",
                "The 'action' parameter is required.",
                context=context,
            )

        if action not in _VALID_ACTIONS:
            return self._error_response(
                "invalid_action",
                f"Unknown action '{action}'. "
                f"Valid actions: {sorted(_VALID_ACTIONS)}",
                context=context,
            )

        if action in _ACTIONS_REQUIRING_COMPANY_NUMBER:
            company_number = params.get("company_number") or context.get(
                "company_number"
            )
            if not company_number or not company_number.strip():
                return self._error_response(
                    "missing_company_number",
                    f"Action '{action}' requires a 'company_number' "
                    "parameter. Use 'resolve_company' first to find "
                    "the correct company number.",
                    context=context,
                )
            params["company_number"] = company_number.strip()

        dispatch = {
            "resolve_company": self._resolve_company,
            "get_company_profile": self._get_company_profile,
            "get_officers": self._get_officers,
            "get_pscs": self._get_pscs,
            "get_filing_history": self._get_filing_history,
            "run_pipeline": self._run_pipeline,
            "resolve_and_get_officers": self._resolve_and_get_officers,
            "resolve_and_get_filings": self._resolve_and_get_filings,
            "resolve_company_officer": self._resolve_company_officer,
        }

        try:
            result = dispatch[action](params)

            # Carry forward and merge context
            ctx_num = context.get("company_number")
            company_number = (
                result.get("company_number") or params.get("company_number") or ctx_num
            )
            # Only inherit context company_name if company_number matches context
            inherited_name = (
                context.get("company_name")
                if (not ctx_num or not company_number or ctx_num == company_number)
                else None
            )
            company_name = (
                result.get("company_name")
                or params.get("company_name")
                or inherited_name
            )

            if not company_name and company_number:
                try:
                    profile_data = self._request("GET", f"/company/{company_number}")
                    company_name = profile_data.get("company_name", "")
                    result["company_name"] = company_name
                except Exception:
                    pass

            new_context = {
                "company_number": company_number,
                "company_name": company_name,
                "selected_transaction_id": (
                    result.get("selected_transaction_id")
                    or params.get("selected_transaction_id")
                    or context.get("selected_transaction_id")
                ),
                "last_action": action,
            }

            result["context"] = new_context
            return result

        except requests.exceptions.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code == 404:
                return self._error_response(
                    "not_found",
                    "The requested resource was not found at "
                    "Companies House. Check the company number.",
                    context=context,
                )
            if status_code == 429:
                return self._error_response(
                    "rate_limited",
                    "Companies House API rate limit exceeded. Wait and retry.",
                    agent_hint=_OPERATIONAL_RETRY_HINT,
                    context=context,
                )
            return self._error_response(
                "api_error",
                f"Companies House API returned HTTP {status_code}.",
                context=context,
            )
        except requests.exceptions.Timeout:
            return self._error_response(
                "timeout",
                "Companies House API request timed out.",
                agent_hint=_OPERATIONAL_RETRY_HINT,
                context=context,
            )
        except requests.exceptions.ConnectionError:
            return self._error_response(
                "connection_error",
                "Could not connect to the Companies House API.",
                agent_hint=_OPERATIONAL_RETRY_HINT,
                context=context,
            )
        except Exception as exc:
            return self._error_response(
                "internal_error",
                f"Unexpected error: {type(exc).__name__}: {exc}",
                context=context,
            )

    # --- Action Handlers ---

    def _resolve_company(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Search for companies by name and return ranked candidates."""
        query = params.get("query")
        if not query or not str(query).strip():
            return self._error_response(
                "missing_query",
                "The 'query' parameter is required for " "resolve_company.",
            )

        query = self._normalize_company_query(str(query))
        if not query:
            return self._error_response(
                "missing_query",
                "The 'query' parameter is required for " "resolve_company.",
            )

        limit = min(params.get("limit", 5), 20)

        data = self._request(
            "GET",
            "/search/companies",
            params={"q": query, "items_per_page": limit},
        )

        items = data.get("items", [])
        if not items:
            return self._error_response(
                "no_results",
                f"No companies found matching '{query}'.",
                agent_hint="Ask the user to refine their search "
                "query or check spelling.",
            )

        candidates = []
        for item in items:
            candidate = {
                "company_number": item.get("company_number", ""),
                "title": item.get("title", ""),
                "company_status": item.get("company_status", ""),
                "company_type": item.get("company_type", ""),
                "address_snippet": item.get("address_snippet", ""),
                "date_of_creation": item.get("date_of_creation", ""),
                "snippet": item.get("snippet", ""),
            }

            candidates.append(candidate)

        # If exactly one company, return ready
        if len(candidates) == 1:
            match = candidates[0]
            return self._ready_response(
                {
                    "company_number": match["company_number"],
                    "company_name": match["title"],
                    "company_status": match["company_status"],
                    "company_type": match.get("company_type", ""),
                    "date_of_creation": match.get("date_of_creation", ""),
                    "address_snippet": match.get("address_snippet", ""),
                    "all_candidates": candidates,
                }
            )

        # Multiple or ambiguous matches — return needs_input
        return self._needs_input_response(
            "multiple_matches",
            candidates,
            agent_hint="Ask the user which company they mean "
            "before calling further actions.",
        )

    def _get_company_profile(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch the full profile for a company by number."""
        company_number = params["company_number"].strip()

        data = self._request(
            "GET",
            f"/company/{company_number}",
        )

        profile = {
            "company_number": company_number,
            "company_name": data.get("company_name", ""),
            "company_status": data.get("company_status", ""),
            "company_type": data.get("type", ""),
            "date_of_creation": data.get("date_of_creation", ""),
            "date_of_cessation": data.get("date_of_cessation"),
            "registered_office_address": data.get("registered_office_address", {}),
            "sic_codes": data.get("sic_codes", []),
            "has_charges": data.get("has_charges", False),
            "has_insolvency_history": data.get("has_insolvency_history", False),
            "can_file": data.get("can_file", False),
            "jurisdiction": data.get("jurisdiction", ""),
            "accounts": data.get("accounts", {}),
            "confirmation_statement": data.get("confirmation_statement", {}),
        }

        return self._ready_response(profile)

    def _match_officer_role(self, officer_role: str, target_role: str) -> bool:
        """Deterministically match an officer role against a requested role/category."""
        if not target_role:
            return True
        if not officer_role:
            return False

        norm_officer = str(officer_role).strip().lower().replace("_", "-")
        norm_target = str(target_role).strip().lower()

        # Check role_mappings first for synonyms / US terms (e.g. "ceo" -> "director")
        role_map = self.terminology_map.get("role_mappings", {})
        norm_key = norm_target.replace("-", "_")
        mapped_target = role_map.get(norm_key, norm_target)
        mapped_target_norm = str(mapped_target).strip().lower().replace("_", "-")

        # Canonical role categories from terminology_map
        role_categories = self.terminology_map.get("role_categories", {})

        # Check category match (allowing singular or plural)
        if mapped_target_norm in ("director", "directors") or norm_target in (
            "director",
            "directors",
        ):
            if norm_officer in role_categories.get("directors", []):
                return True
        elif mapped_target_norm in ("secretary", "secretaries") or norm_target in (
            "secretary",
            "secretaries",
        ):
            if norm_officer in role_categories.get("secretaries", []):
                return True
        elif mapped_target_norm == "corporate" or norm_target == "corporate":
            if norm_officer in role_categories.get(
                "corporate", []
            ) or norm_officer.startswith("corporate-"):
                return True

        # Check exact role match
        target_exact = norm_target.replace("_", "-")
        if norm_officer == target_exact or norm_officer == mapped_target_norm:
            return True

        return False

    def _get_officers(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List officers (directors, secretaries) for a company with deterministic filtering."""
        company_number = params["company_number"].strip()
        active_only = params.get("active_only", True)
        officer_name = (
            (params.get("officer_name") or params.get("officer_filter") or "")
            .strip()
            .lower()
        )
        officer_role = (params.get("officer_role") or "").strip().lower()
        role_hint = (params.get("role_hint") or "").strip().lower()
        start_index = int(params.get("start_index") or 0)
        limit_param = params.get("limit")

        has_filter = bool(officer_name or officer_role)

        if has_filter:
            limit = int(limit_param) if limit_param is not None else 100
            max_pages = 10
            page_size = 100
            current_start = start_index
            officers = []
            matched_count = 0
            total_results = None
            active_count = None

            for _ in range(max_pages):
                req_params = {
                    "items_per_page": page_size,
                    "start_index": current_start,
                }
                data = self._request(
                    "GET",
                    f"/company/{company_number}/officers",
                    params=req_params,
                )
                if total_results is None:
                    total_results = data.get("total_results")
                    active_count = data.get("active_count")

                items = data.get("items", [])
                if not items:
                    break

                for item in items:
                    resigned = bool(item.get("resigned_on"))
                    if active_only and resigned:
                        continue

                    role = item.get("officer_role", "")
                    if officer_role and not self._match_officer_role(
                        role, officer_role
                    ):
                        continue

                    name = item.get("name", "")
                    if officer_name:
                        name_lower = name.lower()
                        if not all(
                            part in name_lower
                            for part in officer_name.replace(",", " ").split()
                        ):
                            continue

                    matched_count += 1
                    if len(officers) < limit:
                        officers.append(
                            {
                                "name": name,
                                "officer_role": role,
                                "appointed_on": item.get("appointed_on", ""),
                                "resigned_on": item.get("resigned_on"),
                                "nationality": item.get("nationality", ""),
                                "occupation": item.get("occupation", ""),
                                "country_of_residence": item.get(
                                    "country_of_residence", ""
                                ),
                            }
                        )

                current_start += len(items)
                if total_results is not None and current_start >= total_results:
                    break
                if len(items) < page_size:
                    break
                if len(officers) >= limit:
                    break

            items_per_page = page_size
        else:
            limit = int(limit_param) if limit_param is not None else 10
            page_size = min(limit, 100)
            req_params = {
                "items_per_page": page_size,
                "start_index": start_index,
            }
            data = self._request(
                "GET",
                f"/company/{company_number}/officers",
                params=req_params,
            )
            total_results = data.get("total_results")
            active_count = data.get("active_count")
            items = data.get("items", [])
            officers = []
            matched_count = 0
            for item in items:
                resigned = bool(item.get("resigned_on"))
                if active_only and resigned:
                    continue
                matched_count += 1
                if len(officers) < limit:
                    officers.append(
                        {
                            "name": item.get("name", ""),
                            "officer_role": item.get("officer_role", ""),
                            "appointed_on": item.get("appointed_on", ""),
                            "resigned_on": item.get("resigned_on"),
                            "nationality": item.get("nationality", ""),
                            "occupation": item.get("occupation", ""),
                            "country_of_residence": item.get(
                                "country_of_residence", ""
                            ),
                        }
                    )
            items_per_page = page_size

        company_name = params.get("context", {}).get("company_name", "")

        if any(
            term in role_hint or term in officer_role
            for term in ("ceo", "chief_executive", "president", "coo", "cfo")
        ):
            terminology_note = (
                "UK companies use directors, not CEOs; this list "
                "includes statutory directors and secretaries."
            )
        elif not active_only:
            terminology_note = (
                "Statutory company officers in the UK comprise directors and "
                "secretaries. Includes both active and resigned officers on record."
            )
        else:
            terminology_note = (
                "Statutory company officers in the UK comprise directors "
                "and secretaries."
            )

        result = {
            "company_number": company_number,
            "company_name": company_name,
            "total_results": total_results,
            "active_count": active_count,
            "matched_count": matched_count,
            "officers": officers,
            "terminology_note": terminology_note,
            "start_index": start_index,
            "items_per_page": items_per_page,
            "active_only": active_only,
        }

        empty_hint = ""
        if not officers:
            empty_hint = (
                "Registry call succeeded but officers[] is empty for this company_number "
                "and filters. Tell the user what was queried and ask whether they meant "
                "a different entity or broader officer criteria."
            )

        return self._ready_response(
            result,
            agent_hint=empty_hint,
            source="companies_house_api",
        )

    def _get_pscs(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List persons with significant control for a company."""
        company_number = params["company_number"].strip()
        active_only = params.get("active_only", False)

        request_params = {}
        if active_only:
            request_params["register_view"] = "true"

        data = self._request(
            "GET",
            f"/company/{company_number}/persons-with-significant-control",
            params=request_params if request_params else None,
        )

        pscs = []
        for item in data.get("items", []):
            psc = {
                "name": item.get("name", ""),
                "kind": item.get("kind", ""),
                "notified_on": item.get("notified_on", ""),
                "ceased_on": item.get("ceased_on"),
                "natures_of_control": item.get("natures_of_control", []),
                "nationality": item.get("nationality", ""),
                "country_of_residence": item.get("country_of_residence", ""),
            }

            if active_only and psc.get("ceased_on"):
                continue

            pscs.append(psc)

        company_name = params.get("context", {}).get("company_name", "")

        result = {
            "company_number": company_number,
            "company_name": company_name,
            "total_results": data.get("total_results", len(pscs)),
            "pscs": pscs,
            "terminology_note": (
                "PSC = Person with Significant Control. In UK law, "
                "this is equivalent to beneficial owner — someone "
                "who holds >25% shares or voting rights, or has "
                "significant influence or control."
            ),
        }

        return self._ready_response(
            result,
            source="companies_house_api",
        )

    def _get_filing_history(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List filing history for a company with deterministic date sort and helpers."""
        company_number = params["company_number"].strip()
        limit = params.get("limit", 10)
        category = params.get("category")
        latest_only = bool(params.get("latest_only", False))
        latest_per_category = bool(params.get("latest_per_category", False))
        start_index = int(params.get("start_index") or 0)

        if latest_per_category or latest_only or (limit is not None and limit > 10):
            items_per_page = 100
        else:
            items_per_page = min(limit, 100) if limit is not None else 10

        request_params: Dict[str, Any] = {
            "items_per_page": items_per_page,
            "start_index": start_index,
        }
        if category:
            request_params["category"] = category

        data = self._request(
            "GET",
            f"/company/{company_number}/filing-history",
            params=request_params,
        )

        filings = []
        for item in data.get("items", []):
            filing = {
                "date": item.get("date", ""),
                "category": item.get("category", ""),
                "type": item.get("type", ""),
                "description": item.get("description", ""),
                "description_values": item.get("description_values", {}),
                "barcode": item.get("barcode", ""),
                "transaction_id": item.get("transaction_id", ""),
            }

            # Include document metadata link if available
            links = item.get("links", {})
            if links.get("document_metadata"):
                filing["document_metadata_url"] = links["document_metadata"]

            filings.append(filing)

        # Deterministic newest-first sort by date
        filings.sort(key=lambda x: str(x.get("date", "")), reverse=True)

        if latest_only:
            filings = filings[:1]
        elif latest_per_category:
            deduped = []
            seen_categories = set()
            for f in filings:
                cat = f.get("category", "")
                if cat not in seen_categories:
                    seen_categories.add(cat)
                    deduped.append(f)
            filings = deduped
            if limit is not None:
                filings = filings[:limit]
        else:
            if limit is not None:
                filings = filings[:limit]

        company_name = params.get("context", {}).get("company_name", "")
        total_results = data.get("total_count")

        result = {
            "company_number": company_number,
            "company_name": company_name,
            "total_results": total_results,
            "filing_history_status": data.get("filing_history_status", ""),
            "filings": filings,
            "start_index": start_index,
            "items_per_page": items_per_page,
            "latest_only": latest_only,
            "latest_per_category": latest_per_category,
        }

        empty_hint = ""
        if not filings:
            empty_hint = (
                "Registry call succeeded but filings[] is empty for this company_number "
                "and category filter. Explain that to the user and suggest confirming "
                "the entity or trying a different filing category."
            )

        return self._ready_response(
            result,
            agent_hint=empty_hint,
            source="companies_house_api",
        )

    def _run_pipeline(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute ordered steps as a stack (single-step execution); pause on needs_input / error."""
        steps = params.get("steps")
        context = dict(params.get("context") or {})
        stop_on = params.get("stop_on", ["needs_input", "error"])

        if not steps or not isinstance(steps, list):
            return self._error_response(
                "missing_steps",
                "Action 'run_pipeline' requires a non-empty list of 'steps'.",
                context=context,
            )

        for s in steps:
            if not isinstance(s, dict) or not s.get("action"):
                return self._error_response(
                    "invalid_step",
                    "Each step in 'steps' must be an object with an 'action' field.",
                    context=context,
                )

        # Clone steps list so caller's object is not mutated unexpectedly
        steps = [dict(s) for s in steps]

        company_number = params.get("company_number") or context.get("company_number")

        incoming_pipeline = dict(params.get("pipeline") or {})
        prior_completed = int(incoming_pipeline.get("completed_steps") or 0)
        prior_total = int(
            incoming_pipeline.get("total_steps") or (len(steps) + prior_completed)
        )

        # Pop the current step from the stack
        step = steps.pop(0)
        step_action = step.get("action")
        step_params = dict(step.get("params") or {})

        # Resolve parameters (e.g. company_number from context / previous step)
        if (
            not step_params.get("company_number")
            or step_params.get("company_number")
            in ("<from_resolve>", "<from resolve>", "<from-resolve>")
        ) and company_number:
            step_params["company_number"] = company_number

        if "company_name" not in step_params and context.get("company_name"):
            step_params["company_name"] = context.get("company_name")

        step_params["action"] = step_action
        step_params["context"] = context

        # Execute single atomic step
        result = self.execute(params=step_params)

        completed_steps = prior_completed + 1
        total_steps = max(prior_total, completed_steps + len(steps))

        # As soon as company_number is resolved, update all remaining steps in the stack
        # up until the next company resolution step.
        resolved_number = (
            result.get("company_number")
            or company_number
            or context.get("company_number")
        )
        if resolved_number:
            for rem_step in steps:
                if rem_step.get("action") in (
                    "resolve_company",
                    "resolve_and_get_officers",
                    "resolve_and_get_filings",
                    "resolve_company_officer",
                ):
                    break
                rem_params = rem_step.setdefault("params", {})
                if not rem_params.get("company_number") or rem_params.get(
                    "company_number"
                ) in ("<from_resolve>", "<from resolve>", "<from-resolve>"):
                    if rem_step.get("action") in _ACTIONS_REQUIRING_COMPANY_NUMBER:
                        rem_params["company_number"] = resolved_number

        pipeline_info: Dict[str, Any] = {
            "completed_steps": completed_steps,
            "total_steps": total_steps,
        }
        if steps:
            result["steps"] = steps

        result["pipeline"] = pipeline_info

        # Stop on stop_on statuses (needs_input, error, etc.)
        if result.get("status") in stop_on:
            if result.get("status") == "needs_input":
                orig_hint = result.get("agent_hint", "")
                result["agent_hint"] = (
                    f"{orig_hint} Once the user specifies the company, resume run_pipeline "
                    f"with the selected company_number, remaining steps, context, and pipeline."
                ).strip()
            return result

        if result.get("status") == "error":
            return result

        # Status: 'partial' if more steps remain in pipeline, 'ready' if final step
        if steps:
            result["status"] = "partial"
            if not result.get("agent_hint"):
                result["agent_hint"] = (
                    f"Step '{step_action}' completed ({completed_steps}/{total_steps}). "
                    "Call run_pipeline with remaining steps, context, and pipeline to continue."
                )
        else:
            result["status"] = "ready"

        return result

    def _resolve_and_get_officers(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve company and fetch officers in an orchestrated composite action."""
        context = dict(params.get("context") or {})
        company_number = str(
            params.get("company_number") or context.get("company_number") or ""
        ).strip()
        query = (
            params.get("query")
            or params.get("company_query")
            or context.get("company_name")
        )

        if not company_number and not query:
            return self._error_response(
                "missing_company",
                "No company_number or query provided.",
                context=context,
            )

        # Branch YES: User query has company number -> get_officers directly
        if company_number:
            officer_params = dict(params)
            officer_params["company_number"] = company_number
            officer_params["action"] = "get_officers"
            return self._get_officers(officer_params)

        # Branch NO: User query does not have company number -> resolve_company
        resolve_limit = params.get("resolve_limit", 5)
        resolve_params = {
            "action": "resolve_company",
            "query": query,
            "limit": resolve_limit,
            "context": context,
        }
        resolve_res = self.execute(resolve_params)

        if resolve_res.get("status") == "needs_input":
            return resolve_res

        if resolve_res.get("status") == "error":
            return resolve_res

        # Single match -> get_officers
        resolved_number = resolve_res.get("company_number", "")
        resolved_name = resolve_res.get("company_name", "")

        officer_context = dict(context)
        if resolved_name:
            officer_context["company_name"] = resolved_name

        officer_params = dict(params)
        officer_params["company_number"] = resolved_number
        officer_params["context"] = officer_context
        officer_params["action"] = "get_officers"
        return self._get_officers(officer_params)

    def _resolve_and_get_filings(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve company and fetch filing history in an orchestrated composite action."""
        context = dict(params.get("context") or {})
        company_number = str(
            params.get("company_number") or context.get("company_number") or ""
        ).strip()
        query = (
            params.get("query")
            or params.get("company_query")
            or context.get("company_name")
        )

        if not company_number and not query:
            return self._error_response(
                "missing_company",
                "No company_number or query provided.",
                context=context,
            )

        # Branch YES: User query has company number -> get_filing_history directly
        if company_number:
            filing_params = dict(params)
            filing_params["company_number"] = company_number
            filing_params["action"] = "get_filing_history"
            return self._get_filing_history(filing_params)

        resolve_limit = params.get("resolve_limit", 5)
        resolve_params = {
            "action": "resolve_company",
            "query": query,
            "limit": resolve_limit,
            "context": context,
        }
        resolve_res = self.execute(resolve_params)

        if resolve_res.get("status") == "needs_input":
            return resolve_res

        if resolve_res.get("status") == "error":
            return resolve_res

        resolved_number = resolve_res.get("company_number", "")
        resolved_name = resolve_res.get("company_name", "")

        filing_context = dict(context)
        if resolved_name:
            filing_context["company_name"] = resolved_name

        filing_params = dict(params)
        filing_params["company_number"] = resolved_number
        filing_params["context"] = filing_context
        filing_params["action"] = "get_filing_history"
        return self._get_filing_history(filing_params)

    def _resolve_company_officer(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve company and filter officers by role and/or name in an orchestrated composite action."""
        context = dict(params.get("context") or {})
        company_number = str(
            params.get("company_number") or context.get("company_number") or ""
        ).strip()
        query = (
            params.get("query")
            or params.get("company_query")
            or context.get("company_name")
        )

        if not company_number and not query:
            return self._error_response(
                "missing_company",
                "No company_number or query provided.",
                context=context,
            )

        # Branch YES: User query has company number -> get_officers directly
        if company_number:
            officer_params = dict(params)
            officer_params["company_number"] = company_number
            officer_params["action"] = "get_officers"
            return self._get_officers(officer_params)

        # Branch NO: User query does not have company number -> resolve_company
        resolve_limit = params.get("resolve_limit", 5)
        resolve_params = {
            "action": "resolve_company",
            "query": query,
            "limit": resolve_limit,
            "context": context,
        }
        resolve_res = self.execute(resolve_params)

        if resolve_res.get("status") == "needs_input":
            return resolve_res

        if resolve_res.get("status") == "error":
            return resolve_res

        # Single match -> get_officers
        resolved_number = resolve_res.get("company_number", "")
        resolved_name = resolve_res.get("company_name", "")

        officer_context = dict(context)
        if resolved_name:
            officer_context["company_name"] = resolved_name

        officer_params = dict(params)
        officer_params["company_number"] = resolved_number
        officer_params["context"] = officer_context
        officer_params["action"] = "get_officers"
        return self._get_officers(officer_params)

    # --- HTTP Layer ---

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make an authenticated request to the Companies House API."""
        clean_params = None
        if params:
            clean_params = {
                key: value for key, value in params.items() if value is not None
            }

        response = requests.request(
            method,
            f"{_BASE_URL}{endpoint}",
            auth=(self.companies_house_api_key, ""),
            params=clean_params,
            timeout=15,
        )

        response.raise_for_status()
        return response.json()

    # --- Output Helpers ---

    @staticmethod
    def _fetched_at() -> str:
        """Return current UTC timestamp in ISO format."""
        return datetime.now(timezone.utc).isoformat()

    def _ready_response(
        self,
        data: Dict[str, Any],
        source: str = "companies_house_api",
        context: Optional[Dict[str, Any]] = None,
        pipeline: Optional[Dict[str, int]] = None,
        agent_hint: str = "",
    ) -> Dict[str, Any]:
        """Build a ready status response envelope."""
        response = {
            "status": "ready",
            "source": source,
            "fetched_at": self._fetched_at(),
        }
        if context is not None:
            response["context"] = context
        if pipeline is not None:
            response["pipeline"] = pipeline
        if agent_hint:
            response["agent_hint"] = agent_hint
        response.update(data)
        return response

    def _needs_input_response(
        self,
        reason: str,
        candidates: List[Dict[str, Any]],
        agent_hint: str = "",
        context: Optional[Dict[str, Any]] = None,
        pipeline: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """Build a disambiguation response envelope."""
        response = {
            "status": "needs_input",
            "reason": reason,
            "candidates": candidates,
            "fetched_at": self._fetched_at(),
        }
        if context is not None:
            response["context"] = context
        if pipeline is not None:
            response["pipeline"] = pipeline
        if agent_hint:
            response["agent_hint"] = agent_hint
        return response

    def _error_response(
        self,
        error_code: str,
        message: str,
        agent_hint: str = "",
        context: Optional[Dict[str, Any]] = None,
        pipeline: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """Build a structured error response envelope."""
        response = {
            "status": "error",
            "error_code": error_code,
            "message": message,
            "fetched_at": self._fetched_at(),
        }
        if context is not None:
            response["context"] = context
        if pipeline is not None:
            response["pipeline"] = pipeline
        if agent_hint:
            response["agent_hint"] = agent_hint
        return response

    # --- Data Loaders ---

    @staticmethod
    def _normalize_company_query(query: str) -> str:
        """Strip whitespace and trailing punctuation from a company search query."""
        normalized = str(query).strip()
        while normalized and normalized[-1] in "?.,!;:":
            normalized = normalized[:-1].strip()
        return normalized

    @staticmethod
    def _load_json(path: str) -> Dict[str, Any]:
        """Load a JSON file, returning empty dict on failure."""
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    @staticmethod
    def _load_yaml(path: str) -> Dict[str, Any]:
        """Load a YAML file, returning empty dict on failure."""
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}
