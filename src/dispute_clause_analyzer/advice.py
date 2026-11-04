"""Turns a rating into advice: what to change to raise it, and what to tidy up."""
from __future__ import annotations

from typing import Any

from dispute_clause_analyzer.classifier import Classification
from dispute_clause_analyzer.rulebook import Rulebook


def improvement_path(rules: Rulebook, type_id: str | None, current: int | float | None = None) -> list[dict[str, Any]]:
    """Steps that raise the rating, lowest first, with each rating level listed once.

    For a mixed clause type_id is the weakest part and current is the averaged rating.
    """
    if type_id is None:
        return []
    current = rules.type_by_name(type_id).rating if current is None else current
    top = max(t.rating for t in rules.types)
    entry = rules.improvements[type_id]
    steps: list[dict[str, Any]] = []
    for key in ("next_step", "top_option"):
        step = entry[key]
        after = step["rating_after"]
        if after <= current or any(s["rating_after"] == after for s in steps):
            continue
        steps.append(
            {
                "label": "Top rating" if after == top else "Next step",
                "rating_after": after,
                "change": step["change"],
                "wording": step["wording"],
            }
        )
    return steps


def tidy_up(rules: Rulebook, result: Classification) -> list[str]:
    """For a clause with more than one way of picking the arbitrator: keep it straightforward and unambiguous."""
    if not result.mixed:
        return []
    labels = " and ".join(rules.type_by_name(t).label for t in result.detected_types)
    return [rules.mixed["recommendation"].format(labels=labels)]
