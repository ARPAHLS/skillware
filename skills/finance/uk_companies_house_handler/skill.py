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

        # Fallback parameters from context if not explicitly provided or if set to placeholder
        if (
            "company_number" not in params
            or not params["company_number"]
            or str(params["company_number"]).strip().startswith("<")
        ):
            if (
                "company_number" in context
                and context["company_number"]
                and not str(context["company_number"]).strip().startswith("<")
            ):
                params["company_number"] = context["company_number"]

        if "officer_filter" not in params and "officer_filter" in context:
            params["officer_filter"] = context["officer_filter"]
        if "role_hint" not in params and "role_hint" in context:
            params["role_hint"] = context["role_hint"]
        if (
            "selected_transaction_id" not in params
            and "selected_transaction_id" in context
        ):
            params["selected_transaction_id"] = context["selected_transaction_id"]

        # Validate company_number is present when required
        if action in _ACTIONS_REQUIRING_COMPANY_NUMBER:
            company_number = params.get("company_number")
            if not company_number or not company_number.strip():
                return self._error_response(
                    "missing_company_number",
                    f"Action '{action}' requires a 'company_number' "
                    "parameter. Use 'resolve_company' first to find "
                    "the correct company number.",
                    next_actions=["resolve_company"],
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
            new_context = {
                "company_number": context.get("company_number"),
                "company_name": context.get("company_name"),
                "last_action": action,
                "officer_filter": context.get("officer_filter"),
                "role_hint": context.get("role_hint"),
                "next_actions": context.get("next_actions"),
                "selected_transaction_id": context.get("selected_transaction_id"),
            }
            if "context" in result and isinstance(result["context"], dict):
                for k, v in result["context"].items():
                    if v is not None:
                        new_context[k] = v
            if result.get("company_number"):
                new_context["company_number"] = result["company_number"]
            if result.get("company_name"):
                new_context["company_name"] = result["company_name"]
            if "officer_filter" in params:
                new_context["officer_filter"] = params["officer_filter"]
            if "role_hint" in params:
                new_context["role_hint"] = params["role_hint"]
            if result.get("next_actions"):
                new_context["next_actions"] = result["next_actions"]
            if "selected_transaction_id" in params:
                new_context["selected_transaction_id"] = params[
                    "selected_transaction_id"
                ]
            new_context["last_action"] = action

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
                    "Companies House API rate limit exceeded. " "Wait and retry.",
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
                context=context,
            )
        except requests.exceptions.ConnectionError:
            return self._error_response(
                "connection_error",
                "Could not connect to the Companies House API.",
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
        if not query or not query.strip():
            return self._error_response(
                "missing_query",
                "The 'query' parameter is required for " "resolve_company.",
            )

        limit = min(params.get("limit", 5), 20)

        data = self._request(
            "GET",
            "/search/companies",
            params={"q": query.strip(), "items_per_page": limit},
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
            }

            # Compute a simple relevance indicator based on
            # snippet_type and match quality from the API
            snippet_type = item.get("snippet_type", "")
            match_snippet = item.get("snippet", "")
            candidate["snippet_type"] = snippet_type
            candidate["snippet"] = match_snippet
            candidates.append(candidate)

        # If exactly one active company, return ready
        active_candidates = [
            c for c in candidates if c.get("company_status") == "active"
        ]

        if len(active_candidates) == 1 and len(candidates) <= 3:
            match = active_candidates[0]
            return self._ready_response(
                {
                    "company_number": match["company_number"],
                    "company_name": match["title"],
                    "company_status": match["company_status"],
                    "company_type": match.get("company_type", ""),
                    "date_of_creation": match.get("date_of_creation", ""),
                    "address_snippet": match.get("address_snippet", ""),
                    "all_candidates": candidates,
                },
                next_actions=[
                    "get_company_profile",
                    "get_officers",
                    "get_pscs",
                ],
            )

        # Multiple or ambiguous matches — return needs_input
        return self._needs_input_response(
            "multiple_matches",
            candidates,
            agent_hint="Ask the user which company they mean "
            "before calling further actions.",
            next_actions=[
                "get_company_profile",
                "get_officers",
            ],
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

        return self._ready_response(
            profile,
            next_actions=[
                "get_officers",
                "get_pscs",
                "get_filing_history",
            ],
        )

    def _get_officers(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List officers (directors, secretaries) for a company."""
        company_number = params["company_number"].strip()
        active_only = params.get("active_only", True)
        limit = params.get("limit", 10)

        request_params: Dict[str, Any] = {
            "items_per_page": min(limit * 3 if active_only else limit, 100)
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

            officers.append(officer)
            if len(officers) >= limit:
                break

        company_name = data.get("company_name", "")
        # Fallback to context first
        if not company_name:
            company_name = params.get("context", {}).get("company_name", "")

        # Fetch company profile to get the name if the officers endpoint omitted it
        if not company_name:
            try:
                profile = self._get_company_profile({"company_number": company_number})
                if profile.get("status") in ("ready", "partial"):
                    company_name = profile.get("company_name", "")
            except Exception:
                pass

        officer_filter = str(params.get("officer_filter") or "").lower()
        role_hint = str(
            params.get("role_hint") or params.get("context", {}).get("role_hint") or ""
        ).lower()
        query_hint = str(
            params.get("query")
            or params.get("company_query")
            or params.get("intent_keywords")
            or params.get("context", {}).get("query")
            or ""
        ).lower()

        if any(
            term in officer_filter or term in role_hint or term in query_hint
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

        total_results = data.get("total_results", len(officers))
        active_count = data.get("active_count", len(officers) if active_only else 0)

        result = {
            "company_number": company_number,
            "company_name": company_name,
            "total_results": total_results,
            "active_count": active_count,
            "officers": officers,
            "terminology_note": terminology_note,
        }

        # Return partial status if more officers exist on file than returned in the preview
        is_partial = (active_only and active_count > len(officers)) or (
            not active_only and total_results > len(officers)
        )

        if is_partial:
            agent_hint = (
                f"Showing {len(officers)} active officers out of {active_count} active "
                f"({total_results} total on file). Specify 'limit' or 'active_only=False' for more."
            )
            return self._partial_response(
                result,
                next_actions=["get_pscs", "get_filing_history"],
                agent_hint=agent_hint,
                source="companies_house_api",
            )

        return self._ready_response(
            result,
            next_actions=["get_pscs", "get_filing_history"],
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

        result = {
            "company_number": company_number,
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
            next_actions=[
                "get_officers",
                "get_filing_history",
            ],
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

        total_results = data.get("total_count", len(filings))
        result = {
            "company_number": company_number,
            "total_results": total_results,
            "filing_history_status": data.get("filing_history_status", ""),
            "filings": filings,
        }

        # Return partial status if more filings exist on record
        if total_results > len(filings):
            agent_hint = (
                f"Showing {len(filings)} filings out of {total_results}. "
                "Specify 'limit' or 'category' to inspect more."
            )
            return self._partial_response(
                result,
                agent_hint=agent_hint,
                source="companies_house_api",
            )

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
        entities = params.get("entities", {})

        if not keywords and not entities:
            return self._error_response(
                "missing_intent",
                "Provide 'intent_keywords' or 'entities' " "for intent mapping.",
            )

        role_map = self.terminology_map.get("role_mappings", {})
        intent_map = self.terminology_map.get("intent_to_action", {})

        # Build terminology translations
        terminology_translations = {}
        for kw in keywords:
            normalized = kw.lower().strip().replace(" ", "_")
            if normalized in role_map:
                terminology_translations[kw] = role_map[normalized]

        # Determine suggested actions from keywords
        suggested_actions = []
        seen_actions = set()
        for kw in keywords:
            normalized = kw.lower().strip().replace(" ", "_")
            action = intent_map.get(normalized)
            if action and action not in seen_actions:
                suggested_actions.append(action)
                seen_actions.add(action)

        # Build a suggested pipeline
        pipeline = []
        company_query = entities.get("company_query", "")

        # Check if any suggested action requires a company number
        needs_resolve = any(
            action in _ACTIONS_REQUIRING_COMPANY_NUMBER for action in suggested_actions
        )

        # If we have a company query, or if any action needs a resolve, always start with resolve
        if company_query or needs_resolve:
            pipeline.append(
                {
                    "action": "resolve_company",
                    "params": {"query": company_query or "<insert_company_name_here>"},
                }
            )

        # Add the unique suggested actions
        for action in suggested_actions:
            if action == "resolve_company":
                continue  # Already added above (or handled)
            step = {"action": action, "params": {}}
            if action in _ACTIONS_REQUIRING_COMPANY_NUMBER:
                step["params"]["company_number"] = "<from_resolve>"
            pipeline.append(step)

        # If no pipeline could be built, suggest a generic search
        if not pipeline and company_query:
            pipeline.append(
                {
                    "action": "resolve_company",
                    "params": {"query": company_query},
                }
            )

        # Build relevant endpoints list
        endpoint_index = self.api_index.get("endpoints", {})
        relevant_endpoints = []
        for action in suggested_actions:
            ep = endpoint_index.get(action, {})
            if ep.get("path"):
                relevant_endpoints.append(ep["path"])

        return self._ready_response(
            {
                "suggested_pipeline": pipeline,
                "terminology_map": terminology_translations,
                "relevant_endpoints": relevant_endpoints,
            },
        )

    def _run_pipeline(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute ordered steps; stop on needs_input / error; merge context and results."""
        steps = params.get("steps")
        context = dict(params.get("context") or {})
        stop_on = params.get("stop_on", ["needs_input", "error"])

        # Fallback to next_actions if steps was omitted by caller
        if not steps:
            next_acts = params.get("next_actions") or context.get("next_actions")
            if next_acts and isinstance(next_acts, list):
                steps = [{"action": act, "params": {}} for act in next_acts]

        if not steps or not isinstance(steps, list):
            return self._error_response(
                "missing_steps",
                "Action 'run_pipeline' requires a non-empty list of 'steps'.",
                context=context,
            )

        # Merge top-level company_number if provided
        top_company_number = params.get("company_number")
        if top_company_number and not str(top_company_number).strip().startswith("<"):
            context["company_number"] = str(top_company_number).strip()

        # Track pipeline progress across multi-turn continuations
        incoming_pipeline = params.get("pipeline") or context.get("pipeline") or {}
        prior_completed = int(incoming_pipeline.get("completed_steps") or 0)
        prior_total = int(incoming_pipeline.get("total_steps") or 0)

        # If caller passed full pipeline on resumption, skip already-completed steps
        if prior_completed > 0 and len(steps) == prior_total:
            steps_to_run = steps[prior_completed:]
        else:
            steps_to_run = steps

        total_steps = (
            prior_total
            if prior_total >= (prior_completed + len(steps_to_run))
            else (prior_completed + len(steps_to_run))
        )

        combined_result: Dict[str, Any] = {
            "status": "ready",
            "source": "companies_house_api",
            "fetched_at": self._fetched_at(),
        }
        terminology_notes: List[str] = []
        has_partial = False

        for idx, step in enumerate(steps_to_run):
            if not isinstance(step, dict) or not step.get("action"):
                return self._error_response(
                    "invalid_step",
                    f"Step {prior_completed + idx + 1} must be an object with a valid 'action'.",
                    context=context,
                    pipeline={
                        "completed_steps": prior_completed + idx,
                        "total_steps": total_steps,
                    },
                )

            step_action = step["action"]
            step_params = dict(step.get("params") or {})

            # Auto-substitute company_number placeholder if resolved in context
            step_co_num = step_params.get("company_number")
            if (
                not step_co_num or str(step_co_num).strip().startswith("<")
            ) and context.get("company_number"):
                step_params["company_number"] = context["company_number"]

            # Pass role_hint from context if not already in step_params
            if "role_hint" not in step_params and context.get("role_hint"):
                step_params["role_hint"] = context["role_hint"]

            # Set action and pass current accumulated context
            step_params["action"] = step_action
            step_params["context"] = dict(context)

            # Execute step
            step_result = self.execute(step_params)

            # Merge step result context into accumulated context
            if "context" in step_result and isinstance(step_result["context"], dict):
                for k, v in step_result["context"].items():
                    if v is not None:
                        context[k] = v

            status = step_result.get("status")

            # Stop early if status matches stop_on and there are remaining steps
            if status in stop_on and idx < len(steps_to_run) - 1:
                step_result["pipeline"] = {
                    "completed_steps": prior_completed + idx + 1,
                    "total_steps": total_steps,
                }
                remaining_actions = [
                    s.get("action")
                    for s in steps_to_run[idx + 1 :]
                    if isinstance(s, dict) and s.get("action")
                ]
                if remaining_actions:
                    step_result["next_actions"] = remaining_actions
                step_result["context"] = context
                return step_result

            if status == "partial":
                has_partial = True

            # Collect terminology notes
            note = step_result.get("terminology_note")
            if note and note not in terminology_notes:
                terminology_notes.append(note)

            # Merge step data into combined_result
            for k, v in step_result.items():
                if k not in (
                    "status",
                    "source",
                    "fetched_at",
                    "pipeline",
                    "next_actions",
                    "terminology_note",
                ):
                    combined_result[k] = v

            if status not in ("ready", "partial"):
                combined_result["status"] = status

        if terminology_notes:
            combined_result["terminology_note"] = " ".join(terminology_notes)

        if combined_result.get("status") == "ready" and has_partial:
            combined_result["status"] = "partial"

        # Final step reached
        combined_result["pipeline"] = {
            "completed_steps": prior_completed + len(steps_to_run),
            "total_steps": total_steps,
        }
        combined_result["context"] = context
        return combined_result

    def _resolve_and_get_officers(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve company and fetch officers in an orchestrated pipeline."""
        context = dict(params.get("context") or {})
        company_number = params.get("company_number") or context.get("company_number")
        officer_params: Dict[str, Any] = {}
        if "active_only" in params:
            officer_params["active_only"] = params["active_only"]
        if "limit" in params:
            officer_params["limit"] = params["limit"]
        if "officer_filter" in params:
            officer_params["officer_filter"] = params["officer_filter"]
        if "role_hint" in params:
            officer_params["role_hint"] = params["role_hint"]
            context["role_hint"] = params["role_hint"]
        elif context.get("role_hint"):
            officer_params["role_hint"] = context["role_hint"]

        if company_number:
            officer_params["action"] = "get_officers"
            officer_params["company_number"] = company_number
            officer_params["context"] = context
            return self.execute(officer_params)

        query = (
            params.get("query") or params.get("company_query") or context.get("query")
        )
        if not query or not str(query).strip():
            return self._error_response(
                "missing_query",
                "Action 'resolve_and_get_officers' requires "
                "'query' or 'company_number'.",
                context=context,
            )

        query_str = str(query).strip()
        lower_query = query_str.lower()
        for prefix in (
            "who is the ceo of ",
            "who is the cfo of ",
            "who is the chairman of ",
            "who is the director of ",
            "ceo of ",
            "cfo of ",
            "chairman of ",
            "director of ",
            "officers of ",
            "directors of ",
        ):
            if lower_query.startswith(prefix):
                query_str = query_str[len(prefix) :].strip()
                if "ceo" in prefix:
                    officer_params["role_hint"] = "ceo"
                    context["role_hint"] = "ceo"
                elif "cfo" in prefix:
                    officer_params["role_hint"] = "cfo"
                    context["role_hint"] = "cfo"
                elif "chairman" in prefix:
                    officer_params["role_hint"] = "chairman"
                    context["role_hint"] = "chairman"
                elif "director" in prefix:
                    officer_params["role_hint"] = "director"
                    context["role_hint"] = "director"
                break

        resolve_params: Dict[str, Any] = {"query": query_str}
        if "limit" in params:
            resolve_params["limit"] = params["limit"]

        steps = [
            {"action": "resolve_company", "params": resolve_params},
            {"action": "get_officers", "params": officer_params},
        ]

        return self._run_pipeline(
            {
                "steps": steps,
                "context": context,
                "stop_on": ["needs_input", "error"],
            }
        )

    def _resolve_and_get_filings(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve company and fetch filing history in an orchestrated pipeline."""
        context = dict(params.get("context") or {})
        company_number = params.get("company_number") or context.get("company_number")
        filing_params: Dict[str, Any] = {}
        if "category" in params:
            filing_params["category"] = params["category"]
        if "limit" in params:
            filing_params["limit"] = params["limit"]

        if company_number:
            filing_params["action"] = "get_filing_history"
            filing_params["company_number"] = company_number
            filing_params["context"] = context
            return self.execute(filing_params)

        query = (
            params.get("query") or params.get("company_query") or context.get("query")
        )
        if not query or not str(query).strip():
            return self._error_response(
                "missing_query",
                "Action 'resolve_and_get_filings' requires "
                "'query' or 'company_number'.",
                context=context,
            )

        resolve_params: Dict[str, Any] = {"query": str(query).strip()}
        if "limit" in params:
            resolve_params["limit"] = params["limit"]

        steps = [
            {"action": "resolve_company", "params": resolve_params},
            {"action": "get_filing_history", "params": filing_params},
        ]

        return self._run_pipeline(
            {
                "steps": steps,
                "context": context,
                "stop_on": ["needs_input", "error"],
            }
        )

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
        next_actions: Optional[List[str]] = None,
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
        if next_actions:
            response["next_actions"] = next_actions
        return response

    def _partial_response(
        self,
        data: Dict[str, Any],
        next_actions: Optional[List[str]] = None,
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
        if next_actions:
            response["next_actions"] = next_actions
        return response

    def _needs_input_response(
        self,
        reason: str,
        candidates: List[Dict[str, Any]],
        agent_hint: str = "",
        next_actions: Optional[List[str]] = None,
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
        if next_actions:
            response["next_actions"] = next_actions
        return response

    def _error_response(
        self,
        error_code: str,
        message: str,
        agent_hint: str = "",
        next_actions: Optional[List[str]] = None,
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
        if next_actions:
            response["next_actions"] = next_actions
        return response

    # --- Data Loaders ---

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
