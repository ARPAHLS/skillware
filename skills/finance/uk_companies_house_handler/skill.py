"""
UK Companies House Handler Skill

Deterministic skill that wraps the Companies House REST API into structured
actions with status-based responses. Supports company search, profile lookup,
officer and PSC listing, filing history, and intent-to-operation mapping with
UK corporate terminology translation.
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
    "map_intent",
    "run_pipeline",
    "resolve_and_get_officers",
    "resolve_and_get_filings",
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
        self.companies_house_api_key = os.environ.get("COMPANIES_HOUSE_API_KEY")

        if not self.companies_house_api_key and self.config:
            self.companies_house_api_key = self.config.get("COMPANIES_HOUSE_API_KEY")

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
            company_number = params.get("company_number") or context.get("company_number")
            if not company_number or not company_number.strip():
                return self._error_response(
                    "missing_company_number",
                    f"Action '{action}' requires a 'company_number' "
                    "parameter. Use 'resolve_company' first to find "
                    "the correct company number.",
                    context=context,
                )

        dispatch = {
            "resolve_company": self._resolve_company,
            "get_company_profile": self._get_company_profile,
            "get_officers": self._get_officers,
            "get_pscs": self._get_pscs,
            "get_filing_history": self._get_filing_history,
            "map_intent": self._map_intent,
            "run_pipeline": self._run_pipeline,
            "resolve_and_get_officers": self._resolve_and_get_officers,
            "resolve_and_get_filings": self._resolve_and_get_filings,
        }

        try:
            result = dispatch[action](params)

            # Carry forward and merge context
            company_number = (
                result.get("company_number")
                or params.get("company_number")
                or context.get("company_number")
            )
            company_name = (
                result.get("company_name")
                or params.get("company_name")
                or context.get("company_name")
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
            "before calling further actions."
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

    def _get_officers(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List officers (directors, secretaries) for a company."""
        company_number = params["company_number"].strip()
        active_only = params.get("active_only", True)
        limit = params.get("limit", 10)
        officer_name = params.get("officer_name", "").lower()
        role_hint = params.get("role_hint", "").lower()
        start_index = params.get("start_index", 0)

        request_params: Dict[str, Any] = {
            "items_per_page": min(limit, 100),
            "start_index": start_index
        }

        data = self._request(
            "GET",
            f"/company/{company_number}/officers",
            params=request_params,
        )

        officers = []
        for item in data.get("items", []):
            officer = {
                "name": item.get("name", ""),
                "officer_role": item.get("officer_role", ""),
                "appointed_on": item.get("appointed_on", ""),
                "resigned_on": item.get("resigned_on"),
                "nationality": item.get("nationality", ""),
                "occupation": item.get("occupation", ""),
                "country_of_residence": item.get("country_of_residence", ""),
            }

            # Filter resigned officers when active_only is requested
            if active_only and officer.get("resigned_on"):
                continue

            if officer_name and officer_name not in officer.get("name", "").lower():
                continue

            officers.append(officer)
            if len(officers) >= limit:
                break

        company_name = params.get("context", {}).get("company_name", "")

        if any(
            term in role_hint
            for term in ("ceo", "chief_executive", "president", "coo", "cfo")
        ):
            terminology_note = (
                "UK companies use directors, not CEOs; this list "
                "includes statutory directors and secretaries."
            )
        else:
            terminology_note = (
                "Statutory company officers in the UK comprise directors "
                "and secretaries."
            )

        total_results = data.get("total_results")
        active_count = data.get("active_count")

        result = {
            "company_number": company_number,
            "company_name": company_name,
            "total_results": total_results,
            "active_count": active_count,
            "officers": officers,
            "terminology_note": terminology_note,
        }

        return self._ready_response(
            result,
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
        """List filing history for a company."""
        company_number = params["company_number"].strip()
        limit = params.get("limit", 10)

        request_params: Dict[str, Any] = {"items_per_page": limit}
        category = params.get("category")
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

        company_name = params.get("context", {}).get("company_name", "")

        total_results = data.get("total_count")
        result = {
            "company_number": company_number,
            "company_name": company_name,
            "total_results": total_results,
            "filing_history_status": data.get("filing_history_status", ""),
            "filings": filings,
        }

        return self._ready_response(
            result,
            source="companies_house_api",
        )

    def _map_intent(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Map user intent keywords to a suggested action pipeline."""
        keywords_raw = params.get("intent_keywords", "")
        if isinstance(keywords_raw, list):
            keywords = keywords_raw
        else:
            keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]
        entities = dict(params.get("entities") or {})
        action_params = dict(params.get("action_params") or {})

        if not keywords and not entities and not action_params:
            return self._error_response(
                "missing_intent",
                "Provide 'intent_keywords', 'entities', or 'action_params' for intent mapping.",
            )

        role_map = self.terminology_map.get("role_mappings", {})
        intent_map = self.terminology_map.get("intent_to_action", {})
        document_types = self.terminology_map.get("document_types", {})
        entity_types = self.terminology_map.get("entity_types", {})
        status_mappings = self.terminology_map.get("status_mappings", {})

        terminology_translations: Dict[str, str] = {}
        filing_categories: List[str] = []
        for kw in keywords:
            normalized = self._normalize_keyword(kw)
            role = self._lookup_terminology(normalized, role_map)
            if role:
                terminology_translations[kw] = role
            doc_type = self._lookup_terminology(normalized, document_types)
            if doc_type:
                terminology_translations[kw] = doc_type
                if doc_type not in filing_categories:
                    filing_categories.append(doc_type)
            entity = self._lookup_terminology(normalized, entity_types)
            if entity:
                terminology_translations[kw] = entity
            status = self._lookup_terminology(normalized, status_mappings)
            if status:
                terminology_translations[kw] = status

        suggested_actions: List[str] = []
        seen_actions: set = set()
        for kw in keywords:
            normalized = self._normalize_keyword(kw)
            action = self._lookup_terminology(normalized, intent_map)
            if action and action not in seen_actions:
                suggested_actions.append(action)
                seen_actions.add(action)

        company_query = str(entities.get("company_query") or "").strip()
        # Also consider actions mentioned in action_params if not already present
        for act in action_params:
            if act not in seen_actions and act != "resolve_company":
                suggested_actions.append(act)
                seen_actions.add(act)

        needs_resolve = any(
            action in _ACTIONS_REQUIRING_COMPANY_NUMBER for action in suggested_actions
        )

        if needs_resolve and not company_query:
            return self._needs_input_response(
                "missing_company_query",
                [],
                agent_hint=(
                    "Ask the user which UK company they mean, then call "
                    "map_intent again with entities.company_query or call "
                    "resolve_company / a composite action with a clean query."
                )
            )

        role_hint = action_params.get("get_officers", {}).get("role_hint")
        officer_name = action_params.get("get_officers", {}).get("officer_name")
        active_officers = action_params.get("get_officers", {}).get("active_only")
        active_pscs = action_params.get("get_pscs", {}).get("active_only")
        officers_limit = action_params.get("get_officers", {}).get("limit")
        filings_limit = action_params.get("get_filing_history", {}).get("limit")
        companies_limit = action_params.get("resolve_company", {}).get("limit")
        category = action_params.get("get_filing_history", {}).get("category")

        pipeline: List[Dict[str, Any]] = []
        if company_query or needs_resolve:
            res_params: Dict[str, Any] = {"query": company_query}
            res_params.update({"query": company_query})
            if companies_limit is not None:
                res_params["limit"] = companies_limit
            pipeline.append(
                {
                    "action": "resolve_company",
                    "params": res_params,
                }
            )

        for action in suggested_actions:
            if action == "resolve_company":
                continue
            step_params: Dict[str, Any] = {}
            if action in _ACTIONS_REQUIRING_COMPANY_NUMBER:
                step_params["company_number"] = "<from_resolve>"

            if action == "get_officers":
                if role_hint is not None:
                    step_params["role_hint"] = role_hint
                if officer_name is not None:
                    step_params["officer_name"] = officer_name
                if active_officers is not None:
                    step_params["active_only"] = active_officers
                if officers_limit is not None:
                    step_params["limit"] = officers_limit

            elif action == "get_pscs":
                if active_pscs is not None:
                    step_params["active_only"] = active_pscs

            elif action == "get_filing_history":
                if category is not None:
                    step_params["category"] = category
                if filings_limit is not None:
                    step_params["limit"] = filings_limit

            if action in action_params and isinstance(action_params[action], dict):
                step_params.update(action_params[action])

            pipeline.append({"action": action, "params": step_params})

        if not pipeline and company_query:
            pipeline.append(
                {
                    "action": "resolve_company",
                    "params": res_params,
                }
            )

        endpoint_index = self.api_index.get("endpoints", {})
        relevant_endpoints = []
        for action in suggested_actions:
            ep = endpoint_index.get(action, {})
            if ep.get("path"):
                relevant_endpoints.append(ep["path"])

        return self._ready_response(
            {
                "steps": pipeline,
                "pipeline": {
                    "completed_steps": 0,
                    "total_steps": len(pipeline),
                },
                "terminology_map": terminology_translations,
                "relevant_endpoints": relevant_endpoints,
            },
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

        # Clone steps list so caller's object is not mutated unexpectedly
        steps = [dict(s) for s in steps]

        company_number = (
            params.get("company_number")
            or context.get("company_number")
        )

        incoming_pipeline = dict(params.get("pipeline") or {})
        prior_completed = int(incoming_pipeline.get("completed_steps") or 0)
        prior_total = int(incoming_pipeline.get("total_steps") or (len(steps) + prior_completed))

        # Pop the current step from the stack
        step = steps.pop(0)
        step_action = step.get("action")
        step_params = dict(step.get("params") or {})
        
        # Resolve parameters (e.g. company_number from context / previous step)
        if (
            not step_params.get("company_number")
            or step_params.get("company_number") in ("<from_resolve>", "<from resolve>", "<from-resolve>")
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
        resolved_number = (
            result.get("company_number")
            or company_number
            or context.get("company_number")
        )
        if resolved_number:
            for rem_step in steps:
                rem_params = rem_step.setdefault("params", {})
                if (
                    not rem_params.get("company_number")
                    or rem_params.get("company_number") in ("<from_resolve>", "<from resolve>", "<from-resolve>")
                ):
                    if rem_step.get("action") in _ACTIONS_REQUIRING_COMPANY_NUMBER:
                        rem_params["company_number"] = resolved_number

        pipeline_info: Dict[str, Any] = {
            "completed_steps": completed_steps,
            "total_steps": total_steps,
        }
        if steps:
            result["steps"] = steps

        result["pipeline"] = pipeline_info

        # Stop on needs_input
        if result.get("status") == "needs_input":
            orig_hint = result.get("agent_hint", "")
            result["agent_hint"] = (
                f"{orig_hint} Once the user specifies the company, resume run_pipeline "
                f"with the selected company_number, remaining steps, context, and pipeline."
            ).strip()
        
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
        """Resolve company and fetch officers in an orchestrated pipeline."""
        context = dict(params.get("context") or {})
        company_number = str(
            params.get("company_number")
            or context.get("company_number")
            or ""
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

        # Branch YES: User query has company number -> get_company_profile -> get_officers
        if company_number:
            profile_res = self._get_company_profile({
                "company_number": company_number,
                "context": context,
            })
            if profile_res.get("status") == "error":
                return profile_res

            company_name = profile_res.get("company_name", "")
            officer_params = dict(params)
            officer_params["company_number"] = company_number
            officer_params["company_name"] = company_name
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

        officer_params = dict(params)
        officer_params["company_number"] = resolved_number
        officer_params["company_name"] = resolved_name
        officer_params["action"] = "get_officers"
        return self.execute(officer_params)

    def _resolve_and_get_filings(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve company and fetch filing history in an orchestrated pipeline."""
        context = dict(params.get("context") or {})
        company_number = str(
            params.get("company_number")
            or context.get("company_number")
            or ""
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

        if company_number:
            profile_res = self._get_company_profile({
                "company_number": company_number,
                "context": context,
            })
            if profile_res.get("status") == "error":
                return profile_res

            company_name = profile_res.get("company_name", "")
            filing_params = dict(params)
            filing_params["company_number"] = company_number
            filing_params["company_name"] = company_name
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

        filing_params = dict(params)
        filing_params["company_number"] = resolved_number
        filing_params["company_name"] = resolved_name
        filing_params["action"] = "get_filing_history"
        return self.execute(filing_params)
        
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

    def _partial_response(
        self,
        data: Dict[str, Any],
        source: str = "companies_house_api",
        context: Optional[Dict[str, Any]] = None,
        pipeline: Optional[Dict[str, int]] = None,
        agent_hint: str = "",
    ) -> Dict[str, Any]:
        """Build a partial status response envelope."""
        response = {
            "status": "partial",
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
    def _normalize_keyword(keyword: str) -> str:
        """Normalize intent/terminology keywords for YAML map lookup."""
        return keyword.lower().strip().replace(" ", "_").replace("-", "_")

    @staticmethod
    def _lookup_terminology(normalized: str, mapping: Dict[str, str]) -> str:
        """Look up a normalized keyword in a terminology map with alias tolerance."""
        if normalized in mapping:
            return mapping[normalized]
        compact = normalized.replace("_", "")
        if compact in mapping:
            return mapping[compact]
        return ""

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
