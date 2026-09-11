#!/usr/bin/env python3
"""
Live host simulation for finance/uk_companies_house_handler.

Stress-tests natural-language queries through Gemini / Claude hosts (or a
deterministic ideal host), verifies Companies House API payloads, and checks
that the model answer addresses the user question.

Requires:
  COMPANIES_HOUSE_API_KEY
  GOOGLE_API_KEY    (gemini)
  ANTHROPIC_API_KEY (claude)

Usage (repo root):
  python scripts/uk_companies_house_host_simulation.py --provider all
  python scripts/uk_companies_house_host_simulation.py --provider gemini
  python scripts/uk_companies_house_host_simulation.py --provider host
  python scripts/uk_companies_house_host_simulation.py --scenario ceo_bp
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "examples"))

from skillware.core.env import load_env_file  # noqa: E402
from skillware.core.loader import SkillLoader  # noqa: E402
from uk_companies_house_handler_common import SKILL_ID, handle_tool_call  # noqa: E402

# Known registry anchors for disambiguation and API cross-checks
BP_PLC = "00102498"
TESCO_PLC = "00445790"
BARCLAYS_BANK = "01026167"
MONZO_BANK = "09446231"
HSBC_HOLDINGS = "00061707"
ARM_LTD = "02557590"

SCENARIOS: List[Dict[str, Any]] = [
    {
        "id": "ceo_bp",
        "query": "Who is the CEO of BP?",
        "follow_ups": [
            f"Use BP P.L.C. (company number {BP_PLC}) and list the current directors."
        ],
        "company_number": BP_PLC,
        "expect_actions": {
            "resolve_and_get_officers",
            "get_officers",
            "run_pipeline",
        },
        "expect_answer_any": ["director", "ceo", "chief executive", "officer"],
        "expect_tool_fields_any": ["officers"],
    },
    {
        "id": "last_filing_tesco",
        "query": "When was the last filing for Tesco?",
        "follow_ups": [f"Tesco PLC, company number {TESCO_PLC}."],
        "company_number": TESCO_PLC,
        "expect_actions": {
            "resolve_and_get_filings",
            "get_filing_history",
            "run_pipeline",
            "map_intent",
        },
        "expect_answer_any": ["202", "filing", "august", "filed", "accounts"],
        "expect_tool_fields_any": ["filings", "filing_history"],
    },
    {
        "id": "officer_name_barclays",
        "query": "Does Barclays Bank PLC have an officer named John Perkins?",
        "follow_ups": [
            f"Barclays Bank PLC only — company number {BARCLAYS_BANK}. "
            "Search the officer list and say yes or no."
        ],
        "company_number": BARCLAYS_BANK,
        "expect_actions": {"resolve_and_get_officers", "get_officers"},
        "expect_answer_any": ["no", "not", "perkins", "officer", "director"],
        "expect_tool_fields_any": ["officers"],
        "officer_must_not_contain": "PERKINS",
    },
    {
        "id": "multi_hsbc",
        "query": "Show me the directors and the most recent accounts filings for HSBC.",
        "follow_ups": [
            f"HSBC Holdings PLC, company number {HSBC_HOLDINGS}. "
            "I want both officers and recent account filings."
        ],
        "company_number": HSBC_HOLDINGS,
        "expect_actions": {
            "map_intent",
            "run_pipeline",
            "get_officers",
            "get_filing_history",
            "resolve_and_get_officers",
        },
        "expect_answer_any": ["director", "officer", "filing", "account", "hsbc"],
        "expect_tool_fields_any": ["officers", "filings"],
    },
    {
        "id": "conversational_monzo",
        "query": "Can you tell me who runs Monzo Bank Ltd please?",
        "follow_ups": [f"Monzo Bank Ltd, company number {MONZO_BANK}."],
        "company_number": MONZO_BANK,
        "expect_actions": {"resolve_and_get_officers", "get_officers"},
        "expect_answer_any": ["director", "monzo", "officer", "chief", "executive"],
        "expect_tool_fields_any": ["officers"],
    },
    {
        "id": "profile_by_number",
        "query": "What is the company profile for UK company number 00445790?",
        "company_number": TESCO_PLC,
        "expect_actions": {"get_company_profile"},
        "expect_answer_any": ["tesco", "00445790", "active", "company", "ltd", "plc"],
        "expect_tool_fields_any": ["company_name", "company_status"],
    },
    {
        "id": "ambiguous_barclays",
        "query": "Tell me about Barclays.",
        "follow_ups": [
            f"I mean Barclays Bank PLC, company number {BARCLAYS_BANK}. "
            "Give me the company profile summary."
        ],
        "company_number": BARCLAYS_BANK,
        "expect_actions": {
            "resolve_company",
            "get_company_profile",
            "resolve_and_get_officers",
        },
        "expect_answer_any": ["barclays", "bank", "company", "active", "london"],
        "expect_tool_fields_any": ["company_name", "company_status", "candidates"],
    },
    {
        "id": "psc_arm",
        "query": "Who are the persons with significant control for ARM Limited?",
        "follow_ups": [f"ARM Limited, company number {ARM_LTD}. List the PSCs."],
        "company_number": ARM_LTD,
        "expect_actions": {"get_pscs", "resolve_company", "run_pipeline", "map_intent"},
        "expect_answer_any": ["control", "psc", "significant", "arm", "holder"],
        "expect_tool_fields_any": ["pscs", "items"],
    },
    {
        "id": "complex_natural",
        "query": (
            "I'm researching UK energy majors — for BP P.L.C. (00102498), "
            "who sits on the board today and what was their most recent "
            "Companies House filing?"
        ),
        "company_number": BP_PLC,
        "expect_actions": {
            "get_officers",
            "get_filing_history",
            "run_pipeline",
            "map_intent",
            "resolve_and_get_officers",
        },
        "expect_answer_any": ["director", "filing", "bp", "202"],
        "expect_tool_fields_any": ["officers", "filings"],
    },
    {
        "id": "role_hint_chair",
        "query": "Who is the chairman of Tesco PLC?",
        "follow_ups": [f"Tesco PLC, company number {TESCO_PLC}."],
        "company_number": TESCO_PLC,
        "expect_actions": {"resolve_and_get_officers", "get_officers"},
        "expect_answer_any": ["chair", "director", "tesco", "officer"],
        "expect_tool_fields_any": ["officers"],
    },
]

CONVERSATIONAL_QUERY_RE = re.compile(
    r"^(who|what|when|does|can you|tell me|show me|is there|i'm|i am)\b", re.I
)


@dataclass
class ToolTrace:
    action: str
    params: Dict[str, Any]
    status: str
    result: Dict[str, Any] = field(default_factory=dict)
    error_code: Optional[str] = None


@dataclass
class ScenarioResult:
    scenario_id: str
    provider: str
    query: str
    passed: bool
    notes: List[str] = field(default_factory=list)
    traces: List[ToolTrace] = field(default_factory=list)
    final_text: str = ""
    turns: int = 0


def section(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


def load_skill_bundle() -> tuple[Any, Dict[str, Any], str]:
    bundle = SkillLoader.load_skill(SKILL_ID)
    skill = SkillLoader.get_skill_class(bundle)()
    tool_name = SkillLoader._sanitize_gemini_tool_name(bundle["manifest"]["name"])
    return skill, bundle, tool_name


def dirty_query_in_params(params: Dict[str, Any]) -> Optional[str]:
    for key in ("query", "company_query"):
        val = params.get(key)
        if isinstance(val, str) and CONVERSATIONAL_QUERY_RE.search(val.strip()):
            return f"{key}={val!r}"
    entities = params.get("entities")
    if isinstance(entities, dict):
        cq = entities.get("company_query")
        if isinstance(cq, str) and CONVERSATIONAL_QUERY_RE.search(cq.strip()):
            return f"entities.company_query={cq!r}"
    return None


def collect_result_fields(traces: Sequence[ToolTrace]) -> set[str]:
    keys: set[str] = set()
    for trace in traces:
        keys.update(trace.result.keys())
        if "officers" in trace.result:
            keys.add("officers")
        if "filings" in trace.result:
            keys.add("filings")
        if "items" in trace.result and trace.action in ("get_pscs", "resolve_company"):
            keys.add("items")
    return keys


def last_ready_result(traces: Sequence[ToolTrace]) -> Optional[Dict[str, Any]]:
    for trace in reversed(traces):
        if trace.status == "ready" and trace.result:
            return trace.result
    return None


def validate_api_payload(
    scenario: Dict[str, Any], traces: List[ToolTrace]
) -> List[str]:
    notes: List[str] = []
    cn = scenario.get("company_number")
    ready = last_ready_result(traces)

    if cn:
        matched = any(
            str(trace.result.get("company_number", "")).strip() == cn
            or trace.params.get("company_number") == cn
            for trace in traces
            if trace.result or trace.params.get("company_number")
        )
        if ready and str(ready.get("company_number", "")).strip() not in ("", cn):
            if str(ready.get("company_number", "")).strip() != cn:
                notes.append(
                    f"WARN: ready payload company_number={ready.get('company_number')!r} "
                    f"expected {cn!r}"
                )
        elif not matched and not any(t.status == "needs_input" for t in traces):
            notes.append(f"WARN: no tool call used expected company_number {cn}")

    officer_block = scenario.get("officer_must_not_contain")
    if officer_block:
        for trace in traces:
            officers = trace.result.get("officers") or []
            for officer in officers:
                name = str(officer.get("name", "")).upper()
                if officer_block.upper() in name:
                    notes.append(f"FAIL: unexpected officer match {name!r}")

    expected_fields = scenario.get("expect_tool_fields_any") or []
    if expected_fields:
        got = collect_result_fields(traces)
        if not set(expected_fields) & got:
            if not any(t.status == "needs_input" for t in traces[:-1]):
                notes.append(
                    f"FAIL: tool results missing any of {expected_fields}; got keys {sorted(got)}"
                )

    if ready:
        if "officers" in (scenario.get("expect_tool_fields_any") or []):
            officers = ready.get("officers") or []
            if not officers and ready.get("status") == "ready":
                notes.append("WARN: ready response has empty officers[]")
        if "filings" in (scenario.get("expect_tool_fields_any") or []):
            filings = ready.get("filings") or []
            if not filings and "filing" in scenario["id"]:
                notes.append("WARN: ready response has empty filings[]")

    return notes


def validate_answer(
    scenario: Dict[str, Any], final_text: str, provider: str
) -> List[str]:
    notes: List[str] = []
    if provider == "host":
        return notes

    text = final_text.lower().strip()
    if len(text) < 30:
        notes.append(f"FAIL: model answer too short ({len(text)} chars)")
        return notes

    needles = [s.lower() for s in scenario.get("expect_answer_any", [])]
    if needles and not any(n in text for n in needles):
        notes.append(
            f"FAIL: answer missing expected terms (any of {scenario.get('expect_answer_any')})"
        )

    return notes


def evaluate_scenario(
    scenario: Dict[str, Any],
    traces: List[ToolTrace],
    final_text: str,
    provider: str,
) -> tuple[bool, List[str]]:
    notes: List[str] = []

    if not traces:
        notes.append("FAIL: no tool calls")
        return False, notes

    actions = {t.action for t in traces if t.action}
    expected = scenario.get("expect_actions") or set()
    if expected and not (actions & expected):
        notes.append(
            f"FAIL: expected actions {sorted(expected)}, got {sorted(actions)}"
        )

    for trace in traces:
        dirty = dirty_query_in_params(trace.params)
        if dirty:
            notes.append(f"WARN: conversational text in skill params ({dirty})")
        if trace.status == "error" and trace.error_code == "rate_limited":
            notes.append("WARN: Companies House rate limit")

    notes.extend(validate_api_payload(scenario, traces))
    notes.extend(validate_answer(scenario, final_text, provider))

    if provider != "host" and any(t.status == "needs_input" for t in traces):
        if not final_text.strip():
            notes.append(
                "FAIL: stopped at needs_input without final user-facing answer"
            )

    failed = any(n.startswith("FAIL:") for n in notes)
    if not failed:
        notes.insert(0, "PASS: tools, API payload, and answer checks OK")
    return not failed, notes


def execute_and_trace(skill: Any, params: Dict[str, Any]) -> ToolTrace:
    result = handle_tool_call(skill, dict(params))
    return ToolTrace(
        action=str(params.get("action", "")),
        params=dict(params),
        status=str(result.get("status", "")),
        result=result if isinstance(result, dict) else {},
        error_code=result.get("error_code") if isinstance(result, dict) else None,
    )


def run_pipeline_to_completion(
    skill: Any, first_result: Dict[str, Any]
) -> List[ToolTrace]:
    traces: List[ToolTrace] = []
    result = first_result
    for _ in range(8):
        if result.get("status") != "partial":
            break
        steps = result.get("steps") or result.get("suggested_pipeline")
        params: Dict[str, Any] = {
            "action": "run_pipeline",
            "steps": steps,
            "pipeline": result.get("pipeline"),
            "context": result.get("context", {}),
        }
        trace = execute_and_trace(skill, params)
        traces.append(trace)
        result = trace.result
    return traces


def needs_disambiguation(traces: List[ToolTrace]) -> bool:
    return bool(traces) and traces[-1].status == "needs_input"


def host_disambiguate(
    skill: Any, scenario: Dict[str, Any], traces: List[ToolTrace]
) -> None:
    """Ideal host: pick intended company and continue."""
    cn = scenario.get("company_number")
    last = traces[-1].result if traces else {}
    sid = scenario["id"]

    if sid == "ceo_bp" or sid == "conversational_monzo" or sid == "role_hint_chair":
        traces.append(
            execute_and_trace(
                skill,
                {
                    "action": "get_officers",
                    "company_number": cn,
                    "role_hint": "ceo" if "ceo" in sid or "monzo" in sid else "chair",
                    "limit": 20,
                },
            )
        )
    elif sid in ("last_filing_tesco",):
        traces.append(
            execute_and_trace(
                skill,
                {"action": "get_filing_history", "company_number": cn, "limit": 5},
            )
        )
    elif sid == "officer_name_barclays":
        traces.append(
            execute_and_trace(
                skill,
                {
                    "action": "get_officers",
                    "company_number": cn,
                    "officer_filter": "John Perkins",
                    "limit": 100,
                },
            )
        )
    elif sid == "profile_by_number":
        traces.append(
            execute_and_trace(
                skill, {"action": "get_company_profile", "company_number": cn}
            )
        )
    elif sid == "ambiguous_barclays":
        traces.append(
            execute_and_trace(
                skill, {"action": "get_company_profile", "company_number": cn}
            )
        )
    elif sid == "psc_arm":
        traces.append(
            execute_and_trace(skill, {"action": "get_pscs", "company_number": cn})
        )
    elif sid == "multi_hsbc":
        traces.append(
            execute_and_trace(
                skill,
                {"action": "get_officers", "company_number": cn, "limit": 10},
            )
        )
        traces.append(
            execute_and_trace(
                skill,
                {
                    "action": "get_filing_history",
                    "company_number": cn,
                    "category": "accounts",
                    "limit": 5,
                },
            )
        )
    elif sid == "complex_natural":
        traces.append(
            execute_and_trace(
                skill,
                {"action": "get_officers", "company_number": cn, "limit": 15},
            )
        )
        traces.append(
            execute_and_trace(
                skill,
                {"action": "get_filing_history", "company_number": cn, "limit": 3},
            )
        )
    elif last.get("candidates") and cn:
        traces.append(
            execute_and_trace(
                skill,
                {"action": "get_company_profile", "company_number": cn},
            )
        )


def run_host_ideal(scenario: Dict[str, Any], skill: Any) -> ScenarioResult:
    sid = scenario["id"]
    traces: List[ToolTrace] = []
    cn = scenario.get("company_number")

    if sid == "ceo_bp":
        traces.append(
            execute_and_trace(
                skill,
                {
                    "action": "get_officers",
                    "company_number": BP_PLC,
                    "role_hint": "ceo",
                },
            )
        )
    elif sid == "last_filing_tesco":
        traces.append(
            execute_and_trace(
                skill,
                {
                    "action": "get_filing_history",
                    "company_number": TESCO_PLC,
                    "limit": 5,
                },
            )
        )
    elif sid == "officer_name_barclays":
        t = execute_and_trace(
            skill,
            {
                "action": "get_officers",
                "company_number": BARCLAYS_BANK,
                "limit": 100,
            },
        )
        traces.append(t)
        names = [o.get("name", "") for o in t.result.get("officers", [])]
        found = any("PERKINS" in n.upper() for n in names)
        summary = f"John Perkins present={found} (officers scanned={len(names)})"
    elif sid == "multi_hsbc":
        traces.append(
            execute_and_trace(
                skill,
                {
                    "action": "get_officers",
                    "company_number": HSBC_HOLDINGS,
                    "limit": 10,
                },
            )
        )
        traces.append(
            execute_and_trace(
                skill,
                {
                    "action": "get_filing_history",
                    "company_number": HSBC_HOLDINGS,
                    "category": "accounts",
                    "limit": 5,
                },
            )
        )
    elif sid == "conversational_monzo":
        traces.append(
            execute_and_trace(
                skill,
                {
                    "action": "get_officers",
                    "company_number": MONZO_BANK,
                    "role_hint": "ceo",
                },
            )
        )
    elif sid == "profile_by_number":
        traces.append(
            execute_and_trace(
                skill, {"action": "get_company_profile", "company_number": TESCO_PLC}
            )
        )
    elif sid == "ambiguous_barclays":
        traces.append(
            execute_and_trace(skill, {"action": "resolve_company", "query": "Barclays"})
        )
        if needs_disambiguation(traces):
            host_disambiguate(skill, scenario, traces)
    elif sid == "psc_arm":
        traces.append(
            execute_and_trace(skill, {"action": "get_pscs", "company_number": ARM_LTD})
        )
    elif sid == "complex_natural":
        traces.append(
            execute_and_trace(
                skill, {"action": "get_officers", "company_number": BP_PLC, "limit": 15}
            )
        )
        traces.append(
            execute_and_trace(
                skill,
                {"action": "get_filing_history", "company_number": BP_PLC, "limit": 3},
            )
        )
    elif sid == "role_hint_chair":
        traces.append(
            execute_and_trace(
                skill,
                {
                    "action": "get_officers",
                    "company_number": TESCO_PLC,
                    "role_hint": "chair",
                },
            )
        )
    else:
        return ScenarioResult(
            sid, "host", scenario["query"], False, ["unknown scenario"], traces
        )

    summary = locals().get("summary", "ideal host completed")
    ok, notes = evaluate_scenario(scenario, traces, summary, "host")
    return ScenarioResult(sid, "host", scenario["query"], ok, notes, traces, summary)


def _process_tool_result(
    skill: Any, args: Dict[str, Any], traces: List[ToolTrace]
) -> Dict[str, Any]:
    trace = execute_and_trace(skill, args)
    traces.append(trace)
    result = trace.result
    if args.get("action") == "run_pipeline" and result.get("status") == "partial":
        for extra in run_pipeline_to_completion(skill, result):
            traces.append(extra)
            result = extra.result
    return result


FINAL_ANSWER_NUDGE = (
    "Based on the skill results above, write your complete answer for the user "
    "in plain language. Do not call any tools. If Companies House returned no "
    "matching records, explain what you checked and ask one helpful follow-up "
    "question (company name, number, or officer criteria)."
)


def _request_final_synthesis_gemini(
    client: Any,
    model: str,
    chat_messages: List[Any],
    system_instruction: str,
) -> str:
    from google.genai import types

    chat_messages.append(FINAL_ANSWER_NUDGE)
    response = client.models.generate_content(
        model=model,
        contents=chat_messages,
        config=types.GenerateContentConfig(system_instruction=system_instruction),
    )
    if not response.candidates or not response.candidates[0].content.parts:
        return ""
    parts = response.candidates[0].content.parts
    function_calls = [p for p in parts if p.function_call]
    if function_calls:
        return response.text or ""
    return response.text or ""


def _request_final_synthesis_claude(
    client: Any,
    model: str,
    messages: List[Dict[str, Any]],
    system_instruction: str,
) -> str:
    messages.append({"role": "user", "content": FINAL_ANSWER_NUDGE})
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system=system_instruction,
        messages=messages,
    )
    return "".join(b.text for b in response.content if getattr(b, "text", None))


def _queue_follow_up(
    scenario: Dict[str, Any],
    follow_ups: List[str],
    pending_user: List[str],
) -> None:
    if follow_ups:
        pending_user.append(follow_ups.pop(0))
    elif scenario.get("company_number"):
        pending_user.append(
            f"Use company number {scenario['company_number']} and complete my original question."
        )


def run_model_loop(
    scenario: Dict[str, Any],
    skill: Any,
    bundle: Dict[str, Any],
    tool_name: str,
    provider: str,
    max_turns: int,
) -> ScenarioResult:
    pending_user: List[str] = [scenario["query"]]
    follow_ups: List[str] = list(scenario.get("follow_ups") or [])
    traces: List[ToolTrace] = []
    final_text = ""
    turns = 0

    if provider == "gemini":
        import google.genai as genai
        from google.genai import types

        client = genai.Client()
        tool = SkillLoader.to_gemini_tool(bundle)
        model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
        chat_messages: List[Any] = []

        while turns < max_turns:
            turns += 1
            if pending_user:
                chat_messages.append(pending_user.pop(0))

            for attempt in range(5):
                try:
                    response = client.models.generate_content(
                        model=model,
                        contents=chat_messages,
                        config=types.GenerateContentConfig(
                            tools=[tool],
                            system_instruction=bundle["instructions"],
                        ),
                    )
                    break
                except Exception as exc:
                    if "429" in str(exc) and attempt < 4:
                        time.sleep(20 * (attempt + 1))
                        continue
                    raise

            if not response.candidates or not response.candidates[0].content.parts:
                break

            parts = response.candidates[0].content.parts
            function_calls = [p for p in parts if p.function_call]
            if not function_calls:
                final_text = response.text or ""
                break

            chat_messages.append(response.candidates[0].content)
            fr_parts = []
            for part in function_calls:
                fc = part.function_call
                if fc.name != tool_name:
                    traces.append(ToolTrace("unknown_tool", {"name": fc.name}, "error"))
                    fr_parts.append(
                        types.Part.from_function_response(
                            name=fc.name,
                            response={"error": f"unknown tool {fc.name}"},
                        )
                    )
                    continue
                result = _process_tool_result(skill, dict(fc.args), traces)
                fr_parts.append(
                    types.Part.from_function_response(
                        name=fc.name, response={"result": result}
                    )
                )
            chat_messages.append(fr_parts)

            if needs_disambiguation(traces) and not pending_user:
                _queue_follow_up(scenario, follow_ups, pending_user)
            time.sleep(1.0)

        if not final_text.strip() and traces:
            final_text = _request_final_synthesis_gemini(
                client, model, chat_messages, bundle["instructions"]
            )

    elif provider == "claude":
        import anthropic

        client = anthropic.Anthropic()
        model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
        tools = [SkillLoader.to_claude_tool(bundle)]
        messages: List[Dict[str, Any]] = []

        while turns < max_turns:
            turns += 1
            if pending_user:
                messages.append({"role": "user", "content": pending_user.pop(0)})

            for attempt in range(5):
                try:
                    response = client.messages.create(
                        model=model,
                        max_tokens=2048,
                        system=bundle["instructions"],
                        tools=tools,
                        messages=messages,
                    )
                    break
                except Exception as exc:
                    if "429" in str(exc) and attempt < 4:
                        time.sleep(20 * (attempt + 1))
                        continue
                    raise

            if response.stop_reason != "tool_use":
                final_text = "".join(
                    b.text for b in response.content if getattr(b, "text", None)
                )
                break

            tool_uses = [b for b in response.content if b.type == "tool_use"]
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for tool_use in tool_uses:
                if tool_use.name != tool_name:
                    traces.append(
                        ToolTrace("unknown_tool", {"name": tool_use.name}, "error")
                    )
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": json.dumps({"error": "unknown tool"}),
                        }
                    )
                    continue
                result = _process_tool_result(skill, dict(tool_use.input), traces)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": json.dumps(result),
                    }
                )
            messages.append({"role": "user", "content": tool_results})

            if needs_disambiguation(traces) and not pending_user:
                _queue_follow_up(scenario, follow_ups, pending_user)
            time.sleep(1.0)

        if not final_text.strip() and traces:
            final_text = _request_final_synthesis_claude(
                client, model, messages, bundle["instructions"]
            )

    ok, notes = evaluate_scenario(scenario, traces, final_text, provider)
    return ScenarioResult(
        scenario["id"],
        provider,
        scenario["query"],
        ok,
        notes,
        traces,
        final_text,
        turns,
    )


def print_result(result: ScenarioResult) -> None:
    mark = "PASS" if result.passed else "FAIL"
    print(
        f"\n[{mark}] {result.provider} :: {result.scenario_id}  (turns={result.turns})"
    )
    print(f"  Q: {result.query}")
    for note in result.notes:
        print(f"  - {note}")
    for i, trace in enumerate(result.traces, 1):
        print(
            f"  tool#{i}: action={trace.action} status={trace.status}"
            f"{f' error={trace.error_code}' if trace.error_code else ''}"
        )
        print(f"         params={json.dumps(trace.params, default=str)[:180]}")
        if trace.result.get("company_name"):
            print(f"         company={trace.result.get('company_name')!r}")
        if trace.result.get("officers"):
            print(f"         officers={len(trace.result['officers'])} returned")
        if trace.result.get("filings"):
            print(f"         filings={len(trace.result['filings'])} returned")
    if result.final_text:
        snippet = result.final_text.replace("\n", " ")[:320]
        print(f"  answer: {snippet}...")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provider",
        choices=("host", "gemini", "claude", "all"),
        default="all",
    )
    parser.add_argument("--scenario", action="append")
    parser.add_argument("--max-turns", type=int, default=10)
    parser.add_argument(
        "--gemini-delay",
        type=float,
        default=15.0,
        help="Seconds between Gemini scenarios (free-tier RPM guard)",
    )
    args = parser.parse_args()

    load_env_file()
    if not os.environ.get("COMPANIES_HOUSE_API_KEY"):
        print("COMPANIES_HOUSE_API_KEY is required.", file=sys.stderr)
        return 1

    skill, bundle, tool_name = load_skill_bundle()
    scenarios = SCENARIOS
    if args.scenario:
        wanted = set(args.scenario)
        scenarios = [s for s in SCENARIOS if s["id"] in wanted]

    if args.provider == "all":
        providers = ["host"]
        if os.environ.get("GOOGLE_API_KEY"):
            providers.append("gemini")
        if os.environ.get("ANTHROPIC_API_KEY"):
            providers.append("claude")
    else:
        providers = [args.provider]

    section("UK Companies House host simulation")
    print(f"Manifest: {bundle['manifest'].get('version')}  tool={tool_name}")
    print(f"Providers: {', '.join(providers)}  scenarios: {len(scenarios)}")

    results: List[ScenarioResult] = []
    for provider in providers:
        if provider != "host":
            key = "GOOGLE_API_KEY" if provider == "gemini" else "ANTHROPIC_API_KEY"
            if not os.environ.get(key):
                print(f"\nSkipping {provider}: {key} not set")
                continue
        section(f"Provider: {provider}")
        for scenario in scenarios:
            try:
                if provider == "host":
                    result = run_host_ideal(scenario, skill)
                else:
                    result = run_model_loop(
                        scenario,
                        skill,
                        bundle,
                        tool_name,
                        provider,
                        args.max_turns,
                    )
            except Exception as exc:
                result = ScenarioResult(
                    scenario["id"],
                    provider,
                    scenario["query"],
                    False,
                    [f"FAIL: {type(exc).__name__}: {exc}"],
                )
            print_result(result)
            results.append(result)
            if provider == "gemini":
                time.sleep(args.gemini_delay)

    passed = sum(1 for r in results if r.passed)
    section("Summary")
    print(f"{passed}/{len(results)} passed")
    for r in results:
        print(f"  {'PASS' if r.passed else 'FAIL'}  {r.provider:6}  {r.scenario_id}")

    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
