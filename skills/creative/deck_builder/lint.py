"""Presentation quality heuristics and linting for creative/deck_builder."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def lint_deck(
    deck_spec: Dict[str, Any],
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Evaluates presentation quality heuristics beyond basic schema validation.
    Returns a score (0-100), boolean passed status, and actionable findings.
    Executes entirely offline.
    """
    options = options or {}
    min_score = options.get("min_score", 70)
    strict_a11y = options.get("strict_a11y", False)

    findings: List[Dict[str, Any]] = []
    slides = deck_spec.get("slides", [])
    total_slides = len(slides)

    # Deck-level checks
    if total_slides < 3:
        findings.append(
            {
                "code": "LOW_SLIDE_COUNT",
                "rule": "Minimum Deck Length",
                "severity": "warning",
                "slide_index": -1,
                "message": f"Deck has only {total_slides} slide(s). Complete decks typically have at least 3 slides.",
                "suggestion": "Add cover title, body content, and conclusion or Q&A slide.",
            }
        )
    elif total_slides > 25:
        findings.append(
            {
                "code": "DECK_TOO_LONG",
                "rule": "Maximum Deck Length",
                "severity": "warning",
                "slide_index": -1,
                "message": f"Deck contains {total_slides} slides, which may exceed standard audience attention spans.",
                "suggestion": "Condense secondary points into an appendix or combine related slides.",
            }
        )

    # Visual monotony: check consecutive layout repetition
    consecutive_layout = None
    consecutive_count = 0
    for idx, slide in enumerate(slides):
        stype = slide.get("type", "unknown")
        if stype == consecutive_layout and stype not in ("blank", "section"):
            consecutive_count += 1
            if consecutive_count == 3:
                findings.append(
                    {
                        "code": "MONOTONOUS_LAYOUT",
                        "rule": "Layout Variety",
                        "severity": "warning",
                        "slide_index": idx,
                        "message": f"Three consecutive slides use layout '{stype}'.",
                        "suggestion": (
                            "Vary slide presentation by introducing a chart, comparison, quote, or metrics slide."
                        ),
                    }
                )
        else:
            consecutive_layout = stype
            consecutive_count = 1

    # Slide-by-slide checks
    for idx, slide in enumerate(slides):
        stype = slide.get("type", "blank")
        title = slide.get("title", "")

        # Check empty title on slides requiring headers
        if stype not in ("blank", "quote") and (not title or not str(title).strip()):
            findings.append(
                {
                    "code": "EMPTY_TITLE",
                    "rule": "Slide Title Requirement",
                    "severity": "warning",
                    "slide_index": idx,
                    "message": f"Slide {idx + 1} ({stype}) lacks a descriptive title.",
                    "suggestion": "Add a clear, action-oriented headline to orient the audience.",
                }
            )

        # Bullets checks
        if stype == "bullets":
            bullets = slide.get("bullets", [])
            if len(bullets) == 1:
                findings.append(
                    {
                        "code": "ORPHAN_BULLET",
                        "rule": "Bullet List Density",
                        "severity": "warning",
                        "slide_index": idx,
                        "message": f"Slide {idx + 1} contains only a single bullet point.",
                        "suggestion": (
                            "Convert single bullet to subtitle or callout quote, or add supporting bullet points."
                        ),
                    }
                )
            elif len(bullets) > 6:
                findings.append(
                    {
                        "code": "WALL_OF_TEXT",
                        "rule": "Bullet Overload",
                        "severity": "warning",
                        "slide_index": idx,
                        "message": f"Slide {idx + 1} has {len(bullets)} bullets, exceeding recommended limit of 6.",
                        "suggestion": "Trim to top 4-5 takeaways or split into a two-column or multi-slide layout.",
                    }
                )

            for b_idx, bullet in enumerate(bullets):
                if len(str(bullet)) > 140:
                    findings.append(
                        {
                            "code": "WALL_OF_TEXT",
                            "rule": "Bullet Character Cap",
                            "severity": "warning",
                            "slide_index": idx,
                            "message": (
                                f"Slide {idx + 1} bullet {b_idx + 1} has {len(str(bullet))} chars (exceeds 140)."
                            ),
                            "suggestion": (
                                "Shorten bullet text to concise phrases; move narrative detail to speaker_notes."
                            ),
                        }
                    )

        # Chart checks
        elif stype == "chart":
            chart = slide.get("chart", {})
            if not chart.get("categories"):
                findings.append(
                    {
                        "code": "CHART_NO_TITLE",
                        "rule": "Chart Completeness",
                        "severity": "warning",
                        "slide_index": idx,
                        "message": f"Slide {idx + 1} chart has no category labels.",
                        "suggestion": "Specify categories for all data points.",
                    }
                )
            for s_idx, s in enumerate(chart.get("series", [])):
                if not s.get("name"):
                    findings.append(
                        {
                            "code": "CHART_NO_TITLE",
                            "rule": "Series Naming",
                            "severity": "warning",
                            "slide_index": idx,
                            "message": f"Slide {idx + 1} chart series {s_idx + 1} is missing a series name.",
                            "suggestion": "Assign a legend label to every data series.",
                        }
                    )

        # Metrics checks
        elif stype == "metrics":
            metrics = slide.get("metrics", [])
            for m_idx, m in enumerate(metrics):
                if not m.get("label"):
                    findings.append(
                        {
                            "code": "METRIC_WITHOUT_LABEL",
                            "rule": "Metric Labeling",
                            "severity": "warning",
                            "slide_index": idx,
                            "message": f"Slide {idx + 1} metric {m_idx + 1} lacks a contextual label.",
                            "suggestion": "Provide a descriptive label clarifying what the metric represents.",
                        }
                    )

        # Image accessibility checks
        if "image" in slide and isinstance(slide["image"], dict):
            img_obj = slide["image"]
            if strict_a11y and not img_obj.get("alt") and not img_obj.get("caption"):
                findings.append(
                    {
                        "code": "MISSING_ALT",
                        "rule": "Accessibility Alt-Text",
                        "severity": "warning",
                        "slide_index": idx,
                        "message": f"Slide {idx + 1} image is missing alt text or caption.",
                        "suggestion": "Add an 'alt' description for screen readers and accessibility audits.",
                    }
                )

    # Calculate quality score: start from 100, deduct points per finding
    deductions = sum(10 if f["severity"] == "error" else 5 for f in findings)
    score = max(0, min(100, 100 - deductions))

    errors = [f for f in findings if f.get("severity") == "error"]
    warnings = [f for f in findings if f.get("severity") == "warning"]

    return {
        "success": True,
        "action": "lint_deck",
        "score": score,
        "passed": score >= min_score,
        "min_score": min_score,
        "slide_count": total_slides,
        "findings_count": len(findings),
        "findings": findings,
        "issues": findings,
        "errors": errors,
        "warnings": warnings,
    }
