"""Builds the data shown in the in-chat report card. The rating always comes from the rules."""
from __future__ import annotations

import math
import re
from importlib import resources
from typing import Any

from dispute_clause_analyzer.advice import improvement_path, tidy_up
from dispute_clause_analyzer.classifier import Classification, classify
from dispute_clause_analyzer.deciding_line import pick_lines
from dispute_clause_analyzer.rulebook import RatingType, Rulebook, load_rulebook

CARD_URI = "ui://dispute-clause-analyzer/report-card.html"
MAX_FACT_CHARS = 120
TONES = {5: "green", 4: "yellow", 3: "orange", 2: "red"}
GOOD_RATING = 4
NOT_STATED = "Not stated"
SEAT_LABEL = "Seat / place of execution"


def load_card_html() -> str:
    return resources.files("dispute_clause_analyzer").joinpath("ui", "report-card.html").read_text(encoding="utf-8")


def trim(text: str) -> str:
    """Collapse whitespace and cap length so card text stays short."""
    clean = " ".join(text.split())
    return clean if len(clean) <= MAX_FACT_CHARS else clean[: MAX_FACT_CHARS - 1].rstrip() + "…"


def _stated(value: str) -> str:
    clean = trim(value)
    return "" if clean.lower().strip(" .") in ("", NOT_STATED.lower()) else clean


def seat_value(seat: str, place_of_execution: str) -> str:
    """Seat and place of execution are the same thing (legal team, 2026-11-03): the stated seat, else the
    place of execution, else 'Not stated'. The venue of hearings is never used."""
    return _stated(seat) or _stated(place_of_execution) or NOT_STATED


def fact_rows(facts: dict[str, str]) -> list[dict[str, str]]:
    """The key facts in display order."""
    return [
        {"label": "Clause", "value": facts["clause_reference"] or NOT_STATED},
        {"label": "Arbitrator to be appointed by", "value": facts["who_picks"] or NOT_STATED},
        {"label": SEAT_LABEL, "value": facts["seat"]},
        {"label": "Online process", "value": facts["online_process"] or NOT_STATED},
    ]


def tone_for(rating: int | float | None) -> str:
    """Colour by the whole-number part, so 2.5 is red like 2 and 4.5 is yellow like 4."""
    return "gray" if rating is None else TONES.get(math.floor(rating), "gray")


def _risk_or_takeaways(rating: int | float, risk: str, rating_type: RatingType) -> dict[str, Any]:
    """A low rating shows its one-line risk; a high one (4/5 and up) shows its key takeaways instead."""
    if rating >= GOOD_RATING:
        return {"risk": "", "strengths": list(rating_type.strengths)}
    return {"risk": risk, "strengths": []}


def rating_view(rules: Rulebook, result: Classification) -> dict[str, Any]:
    """What the card and dashboard say about a rating: label, headline, risk or takeaways, and each part."""
    if result.type is None:
        return {"label": "Not rated", "headline": "No wording from the rating scale was found.", "risk": "",
                "strengths": [], "parts": [], "parts_line": ""}
    weakest = rules.type_by_name(result.type)
    parts = [{"type": t, "label": rules.type_by_name(t).label, "rating": rules.type_by_name(t).rating}
             for t in result.detected_types]
    if not result.mixed:
        return {"label": weakest.label, "headline": weakest.headline, "parts": parts, "parts_line": "",
                **_risk_or_takeaways(result.rating, weakest.risk, weakest)}
    mixed = rules.mixed
    listed = " and ".join(f"{p['label']} {p['rating']}/5" for p in parts)
    return {"label": f"{mixed['label']}: " + " + ".join(p["label"] for p in parts), "headline": mixed["headline"],
            "parts": parts, "parts_line": mixed["parts_line"].format(parts=listed),
            **_risk_or_takeaways(result.rating, mixed["risk"], weakest)}


def _ladder(rules: Rulebook, result: Classification) -> list[dict[str, Any]]:
    """The scale, with every level this clause uses marked current (two levels for a mixed clause)."""
    ratings = sorted({t.rating for t in rules.types})
    used = {rules.type_by_name(t).rating for t in result.detected_types}
    return [
        {
            "rating": r,
            "label": " / ".join(t.label for t in rules.types if t.rating == r),
            "current": r in used,
        }
        for r in ratings
    ]


def build_report_card(
    clause_text: str,
    deciding_quote: str,
    clause_reference: str,
    who_picks: str,
    seat_venue: str = "",
    online_process: str = "",
    rulebook: Rulebook | None = None,
    seat: str = "",
    venue: str = "",  # accepted from older callers, never shown
    place_of_execution: str = "",
) -> dict[str, Any]:
    rules = rulebook or load_rulebook()
    result = classify(clause_text, rules)
    reasons = list(result.review_reasons)
    lines, weakest_line = pick_lines(clause_text, deciding_quote, rules)

    facts = {
        "clause_reference": trim(clause_reference),
        "who_picks": trim(who_picks),
        "seat": seat_value(seat or seat_venue, place_of_execution),
        "online_process": trim(online_process),
    }
    return {
        "kind": "report_card",
        "rating": result.rating,
        "out_of": 5,
        "type": result.type,
        **rating_view(rules, result),
        "tone": tone_for(result.rating),
        "needs_review": bool(reasons),
        "review_reasons": reasons,
        "ladder": _ladder(rules, result),
        "facts": facts,
        "fact_rows": fact_rows(facts),
        "deciding_quote": weakest_line,
        "deciding_lines": lines,
        "matched_wording": list(result.matched_phrases),
        "top_rated": result.rating == max(t.rating for t in rules.types),
        "path": improvement_path(rules, result.type, result.rating),
        "also": tidy_up(rules, result),
        "disclaimer": rules.disclaimer,
        "personal_data_warning": rules.warning,
    }
