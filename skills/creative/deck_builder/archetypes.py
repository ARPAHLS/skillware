"""Deck archetypes and outline suggestions for creative/deck_builder."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

ARCHETYPES = {
    "investor_pitch": {
        "name": "Investor Pitch Deck",
        "description": (
            "Seed through Series B investor overview focusing on problem, solution, market size, traction, and team."
        ),
        "recommended_slides": 11,
        "default_template": "pitch_v1",
        "skeleton": [
            {
                "type": "title",
                "title": "{topic}",
                "subtitle": "Investor Presentation",
                "speaker_notes": "Introduce the vision and founding story.",
            },
            {
                "type": "bullets",
                "title": "The Problem",
                "bullets": [
                    "Inefficient manual workflows stall growth",
                    "Existing tooling lacks deterministic guarantees",
                    "High infrastructure and operational costs",
                ],
            },
            {
                "type": "bullets",
                "title": "The Solution",
                "bullets": [
                    "Autonomous, policy-governed architecture",
                    "Sub-millisecond local execution",
                    "Universal interoperability across providers",
                ],
            },
            {
                "type": "section",
                "title": "Market Opportunity",
                "subtitle": "Expanding total addressable market",
            },
            {
                "type": "metrics",
                "title": "Key Traction Metrics",
                "metrics": [
                    {
                        "value": "$1.2M",
                        "label": "ARR",
                        "trend": "up",
                        "delta": "+140% YoY",
                    },
                    {
                        "value": "45k",
                        "label": "Active Users",
                        "trend": "up",
                        "delta": "+85%",
                    },
                    {"value": "99.9%", "label": "Uptime", "trend": "neutral"},
                ],
            },
            {
                "type": "two_column",
                "title": "Competitive Advantage",
                "left": ["Legacy Solutions", "Fragile JSON parsing", "Vendor lock-in"],
                "right": [
                    "Our Platform",
                    "Deterministic contracts",
                    "Universal host runtime",
                ],
            },
            {
                "type": "timeline",
                "title": "Execution Milestones",
                "items": [
                    {
                        "date": "Q1 2026",
                        "title": "Core Engine Launch",
                        "status": "completed",
                    },
                    {
                        "date": "Q2 2026",
                        "title": "Enterprise Pilot",
                        "status": "in_progress",
                    },
                    {
                        "date": "Q3 2026",
                        "title": "Global Registry",
                        "status": "planned",
                    },
                ],
            },
            {
                "type": "quote",
                "quote": "This platform transformed our operational throughput within days.",
                "attribution": "VP of Technology",
            },
            {
                "type": "bullets",
                "title": "Business Model",
                "bullets": [
                    "Open-source developer adoption",
                    "Enterprise cloud subscription tiers",
                    "Dedicated SLA and customization support",
                ],
            },
            {
                "type": "bullets",
                "title": "The Ask & Growth Runway",
                "bullets": [
                    "$10M Series A financing",
                    "18-month execution runway",
                    "Scale engineering and enterprise go-to-market",
                ],
            },
            {
                "type": "blank",
                "speaker_notes": "Thank the partners and open for discussion.",
            },
        ],
    },
    "technical_brief": {
        "name": "Technical Architecture Brief",
        "description": "Engineering and architectural deep dive for technical stakeholders, reviews, or RFCs.",
        "recommended_slides": 7,
        "default_template": "corporate_v1",
        "skeleton": [
            {
                "type": "title",
                "title": "{topic}",
                "subtitle": "System Architecture & Engineering Specification",
            },
            {
                "type": "section",
                "title": "Part 1: Architectural Foundations",
                "subtitle": "Design principles and boundaries",
            },
            {
                "type": "bullets",
                "title": "Core Principles",
                "bullets": [
                    "Deterministic, offline-first execution",
                    "Strict JSON Schema validation at boundary",
                    "Fail-closed safety guarantees",
                ],
            },
            {
                "type": "two_column",
                "title": "Subsystem Topology",
                "left": ["Host Runtime", "Context assembly", "Tool dispatch"],
                "right": ["Skill Boundary", "Isolated execution", "Auditable results"],
            },
            {
                "type": "timeline",
                "title": "Implementation Roadmap",
                "items": [
                    {
                        "date": "Sprint 1",
                        "title": "Core Contracts",
                        "status": "completed",
                    },
                    {
                        "date": "Sprint 2",
                        "title": "Integration Testing",
                        "status": "in_progress",
                    },
                    {
                        "date": "Sprint 3",
                        "title": "Production Deployment",
                        "status": "planned",
                    },
                ],
            },
            {
                "type": "table",
                "title": "Benchmark Latency",
                "columns": ["Module", "v0.1 (Legacy)", "v0.2 (Optimized)", "Delta"],
                "rows": [
                    ["Validation", "4.2 ms", "0.8 ms", "-81%"],
                    ["Assembly", "18.1 ms", "3.4 ms", "-81%"],
                    ["Total Pipeline", "22.3 ms", "4.2 ms", "-81%"],
                ],
            },
            {
                "type": "blank",
                "speaker_notes": "Technical Q&A with engineering leadership.",
            },
        ],
    },
    "quarterly_review": {
        "name": "Quarterly Executive Review",
        "description": "Executive review of OKRs, KPIs, financial metrics, and operational highlights.",
        "recommended_slides": 8,
        "default_template": "corporate_v1",
        "skeleton": [
            {
                "type": "title",
                "title": "{topic}",
                "subtitle": "Quarterly Performance Review",
            },
            {
                "type": "section",
                "title": "Quarterly Highlights",
                "subtitle": "Key achievements and milestones",
            },
            {
                "type": "metrics",
                "title": "Topline Performance",
                "metrics": [
                    {
                        "value": "$4.8M",
                        "label": "Quarterly Revenue",
                        "trend": "up",
                        "delta": "+24%",
                    },
                    {
                        "value": "94%",
                        "label": "CSAT Score",
                        "trend": "up",
                        "delta": "+3%",
                    },
                    {
                        "value": "< 1 hr",
                        "label": "Time to Resolution",
                        "trend": "down",
                        "delta": "-45%",
                    },
                ],
            },
            {
                "type": "bullets",
                "title": "Operational Wins",
                "bullets": [
                    "Exceeded retention targets across all customer cohorts",
                    "Reduced cloud infrastructure spend by 18%",
                    "Shipped three major customer-requested capabilities",
                ],
            },
            {
                "type": "timeline",
                "title": "Key Project Milestones",
                "items": [
                    {
                        "date": "Month 1",
                        "title": "Architecture Sign-off",
                        "status": "completed",
                    },
                    {
                        "date": "Month 2",
                        "title": "Beta Availability",
                        "status": "completed",
                    },
                    {
                        "date": "Month 3",
                        "title": "General Release",
                        "status": "completed",
                    },
                ],
            },
            {
                "type": "two_column",
                "title": "Challenges & Mitigations",
                "left": [
                    "Identified Headwinds",
                    "Extended enterprise sales cycles",
                    "Third-party dependency latency",
                ],
                "right": [
                    "Mitigation Strategies",
                    "Standardized proof-of-value pilots",
                    "In-memory response caching",
                ],
            },
            {
                "type": "bullets",
                "title": "Next Quarter Priorities",
                "bullets": [
                    "Accelerate international channel expansion",
                    "Deepen enterprise security audit posture",
                    "Expand developer advocacy footprint",
                ],
            },
            {"type": "blank", "speaker_notes": "Adjourn to executive discussion."},
        ],
    },
    "product_launch": {
        "name": "Product Launch Announcement",
        "description": "Feature announcements, market positioning, architecture, and go-to-market rollout.",
        "recommended_slides": 7,
        "default_template": "pitch_v1",
        "skeleton": [
            {
                "type": "title",
                "title": "{topic}",
                "subtitle": "Product Launch Announcement",
            },
            {
                "type": "section",
                "title": "Introducing the Next Generation",
                "subtitle": "Built for scale and reliability",
            },
            {
                "type": "bullets",
                "title": "Why Now?",
                "bullets": [
                    "Demands on autonomous systems are accelerating",
                    "Reliability requires deterministic tooling",
                    "Developers need seamless provider interoperability",
                ],
            },
            {
                "type": "two_column",
                "title": "Before vs After",
                "left": [
                    "Before",
                    "Manual brittle pipelines",
                    "High maintenance overhead",
                ],
                "right": [
                    "With New Product",
                    "Automated deterministic workflows",
                    "Zero maintenance overhead",
                ],
            },
            {
                "type": "quote",
                "quote": "This capability unlocked complete operational confidence for our team.",
                "attribution": "Lead Product Architect",
            },
            {
                "type": "timeline",
                "title": "Rollout Schedule",
                "items": [
                    {
                        "date": "Day 1",
                        "title": "Developer Preview",
                        "status": "completed",
                    },
                    {"date": "Day 14", "title": "Public Beta", "status": "in_progress"},
                    {
                        "date": "Day 30",
                        "title": "General Availability",
                        "status": "planned",
                    },
                ],
            },
            {
                "type": "bullets",
                "title": "Get Started Today",
                "bullets": [
                    "Install via standard pip extra",
                    "Review documentation and examples",
                    "Join the developer community",
                ],
            },
        ],
    },
    "training_workshop": {
        "name": "Training & Workshop Curriculum",
        "description": "Structured instructional slides for workshops, onboarding, or training courses.",
        "recommended_slides": 8,
        "default_template": "minimal_v1",
        "skeleton": [
            {
                "type": "title",
                "title": "{topic}",
                "subtitle": "Hands-on Technical Training",
            },
            {
                "type": "bullets",
                "title": "Workshop Agenda",
                "bullets": [
                    "Module 1: Foundations & Architecture",
                    "Module 2: Hands-on Implementation",
                    "Module 3: Best Practices & Verification",
                    "Module 4: Production Deployment",
                ],
            },
            {
                "type": "section",
                "title": "Module 1: Foundations",
                "subtitle": "Core concepts and invariants",
            },
            {
                "type": "bullets",
                "title": "Key Invariants",
                "bullets": [
                    "Always validate inputs before execution",
                    "Enforce strict schema conformance",
                    "Preserve audit logs and metadata",
                ],
            },
            {
                "type": "two_column",
                "title": "Lab Exercise: Comparison",
                "left": [
                    "Anti-Pattern",
                    "Calling external APIs directly",
                    "Ignoring error states",
                ],
                "right": [
                    "Recommended Pattern",
                    "Wrap in deterministic skill",
                    "Handle error envelopes gracefully",
                ],
            },
            {
                "type": "section",
                "title": "Module 2: Production Readiness",
                "subtitle": "Testing and CI gates",
            },
            {
                "type": "bullets",
                "title": "Summary & Key Takeaways",
                "bullets": [
                    "Deterministic testing catches regressions early",
                    "Contract separation simplifies provider swaps",
                    "Review documentation for advanced patterns",
                ],
            },
            {
                "type": "blank",
                "speaker_notes": "Conclude workshop and open for questions.",
            },
        ],
    },
}


def suggest_outline(
    archetype: str,
    topic: Optional[str] = None,
    constraints: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Generates a structured deck outline and skeleton deck_spec from an archetype.
    Executes entirely offline.
    """
    key = (archetype or "investor_pitch").lower().strip()
    if key not in ARCHETYPES:
        available = list(ARCHETYPES.keys())
        return {
            "success": False,
            "error_code": "UNKNOWN_ARCHETYPE",
            "message": f"Archetype '{archetype}' is not recognized. Available archetypes: {available}",
            "available_archetypes": available,
        }

    arch = ARCHETYPES[key]
    title_text = topic.strip() if topic and topic.strip() else "Executive Presentation"
    constraints = [c.lower().strip() for c in (constraints or [])]

    slides = []
    for slide_tpl in arch["skeleton"]:
        slide = dict(slide_tpl)
        if "title" in slide and "{topic}" in slide["title"]:
            slide["title"] = slide["title"].replace("{topic}", title_text)

        # Check negative constraints (e.g., 'no pricing', 'no business model', 'no team', 'no financial')
        slide_title = slide.get("title", "").lower()
        skip_slide = False
        for c in constraints:
            c_clean = c.lower().strip()
            for prefix in ("no ", "without ", "exclude ", "omit ", "skip "):
                if c_clean.startswith(prefix):
                    c_clean = c_clean[len(prefix) :].strip()
                    break
            if c_clean and c_clean in slide_title:
                skip_slide = True
                break
            if c_clean in (
                "pricing",
                "price",
                "financial",
                "financials",
                "cost",
                "costs",
            ) and any(
                term in slide_title
                for term in ("pricing", "cost", "financial", "ask", "fundraise")
            ):
                skip_slide = True
                break
            if c_clean in ("business model", "monetization", "revenue model") and (
                "business model" in slide_title or "revenue" in slide_title
            ):
                skip_slide = True
                break

        if skip_slide:
            continue

        slides.append(slide)

    deck_spec_skeleton = {
        "title": title_text,
        "template_id": arch["default_template"],
        "theme": {
            "accent_color": (
                "#6E57E0" if arch["default_template"] == "pitch_v1" else "#1E3A8A"
            ),
            "font_heading": "Calibri",
            "font_body": "Calibri",
        },
        "slides": slides,
    }

    return {
        "success": True,
        "action": "suggest_outline",
        "archetype": key,
        "name": arch["name"],
        "description": arch["description"],
        "recommended_slide_count": len(slides),
        "constraints_applied": constraints,
        "deck_spec": deck_spec_skeleton,
        "deck_spec_skeleton": deck_spec_skeleton,
    }
