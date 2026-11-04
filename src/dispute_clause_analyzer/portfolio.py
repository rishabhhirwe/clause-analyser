"""Builds the bulk dashboard: every agreement rated from the rules, plus a summary."""
from __future__ import annotations

from typing import Any, Sequence

from pydantic import BaseModel, Field, field_validator

from dispute_clause_analyzer.advice import improvement_path, tidy_up
from dispute_clause_analyzer.classifier import classify
from dispute_clause_analyzer.report_card import SEAT_LABEL, build_report_card, rating_view, seat_value, tone_for, trim
from dispute_clause_analyzer.rulebook import Rulebook, load_rulebook

MAX_AGREEMENTS = 50
MAX_CLAUSE_CHARS = 20_000


class AgreementInput(BaseModel):
    """One agreement in a bulk upload. Only the clause text is essential; leave anything unreadable empty."""

    clause_text: str = Field(default="", max_length=MAX_CLAUSE_CHARS, description="The full dispute clause, exactly as written.")
    file_name: str = Field(default="", description="The PDF or file name, e.g. 'UNILATERAL.pdf'.")
    lender: str = Field(default="", description="Lender or bank name, a few words. Leave empty if it cannot be read.")
    clause_reference: str = Field(default="", description="Clause number and heading, e.g. 'Cl. 8.1, Arbitration'.")
    deciding_quote: str = Field(default="", description="The sentence that decides who picks the arbitrator, word for word.")
    who_picks: str = Field(default="", description="Who picks the arbitrator, a few words.")
    seat: str = Field(default="", description="Seat of arbitration as stated in the agreement, e.g. 'Bengaluru (clause 10)'.")
    venue: str = Field(default="", description="Not shown. Leave empty; the seat or place of execution is used instead.")
    place_of_execution: str = Field(default="", description="Where the agreement was executed, e.g. 'Bangalore (Exhibit A)'.")
    online_process: str = Field(default="", description="Whether the arbitration can run online, a few words.")
    seat_venue: str = Field(default="", description="Older combined field; prefer seat and place_of_execution.")
    note: str = Field(default="", description="Optional one-line note the rating does not show, e.g. a DRT carve-out.")
    problem: str = Field(default="", description="Only for a file that cannot be rated: 'No dispute clause found' or "
                         "'File could not be read'. Leave clause_text empty. The row shows as Not rated with this reason.")

    @field_validator("file_name", "lender", "clause_reference", "deciding_quote", "who_picks", "seat", "venue", "place_of_execution", "online_process",
                     "seat_venue", "note", "problem",
                     mode="before")
    @classmethod
    def _null_means_empty(cls, value: Any) -> Any:
        return "" if value is None else value


def _card(agreement: AgreementInput, rules: Rulebook) -> dict[str, Any]:
    """The full single-agreement card, opened when the user clicks a row on the dashboard."""
    card = build_report_card(
        clause_text=agreement.clause_text, deciding_quote=agreement.deciding_quote,
        clause_reference=agreement.clause_reference, who_picks=agreement.who_picks, seat_venue=agreement.seat_venue,
        online_process=agreement.online_process, rulebook=rules, seat=agreement.seat,
        place_of_execution=agreement.place_of_execution,
    )
    reasons = _reasons(agreement, card["review_reasons"])
    return {**card, "note": trim(agreement.note), "needs_review": bool(reasons), "review_reasons": reasons}


def _reasons(agreement: AgreementInput, found: list[str]) -> list[str]:
    """A file Claude could not rate gives its own reason instead of the general 'no wording found'."""
    return [trim(agreement.problem)] if agreement.problem.strip() else found


def _item(agreement: AgreementInput, rules: Rulebook, position: int) -> dict[str, Any]:
    result = classify(agreement.clause_text, rules)
    reasons = _reasons(agreement, list(result.review_reasons))
    seat = seat_value(agreement.seat or agreement.seat_venue, agreement.place_of_execution)
    view = rating_view(rules, result)
    return {
        "position": position,
        "file_name": trim(agreement.file_name) or f"Agreement {position}",
        "lender": trim(agreement.lender),
        "clause_reference": trim(agreement.clause_reference),
        "rating": result.rating,
        **{k: view[k] for k in ("label", "headline", "risk", "strengths", "parts", "parts_line")},
        "tone": tone_for(result.rating),
        "who_picks": trim(agreement.who_picks),
        "seat": seat,
        "places": [{"label": SEAT_LABEL, "value": seat}],
        "note": trim(agreement.note),
        "needs_review": bool(reasons),
        "review_reasons": reasons,
        "path": improvement_path(rules, result.type, result.rating),
        "also": tidy_up(rules, result),
        "card": _card(agreement, rules),
    }


def _rating_after(item: dict[str, Any], step_index: int) -> int | float | None:
    """The rating an agreement would have after its first step (0) or its last step (-1)."""
    if item["rating"] is None:
        return None
    return item["path"][step_index]["rating_after"] if item["path"] else item["rating"]


def _average(values: list[int | float | None]) -> float | None:
    known = [v for v in values if v is not None]
    return round(sum(known) / len(known), 1) if known else None


def _actions(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The to-do list: agreements that need the same change, grouped, worst first."""
    groups: dict[str, dict[str, Any]] = {}
    for item in items:
        if not item["path"]:
            continue
        first = item["path"][0]
        group = groups.setdefault(
            item["label"],
            {"label": item["label"], "rating": item["rating"], "rating_after": first["rating_after"],
             "change": first["change"], "tone": item["tone"], "files": []},
        )
        group["files"].append(item["file_name"])
    ordered = sorted(groups.values(), key=lambda g: (g["rating"], g["label"]))
    return [{**g, "count": len(g["files"])} for g in ordered]


def _summary(items: list[dict[str, Any]], rules: Rulebook) -> dict[str, Any]:
    rated = [i["rating"] for i in items if i["rating"] is not None]
    scale = sorted({t.rating for t in rules.types} | set(rated), reverse=True)
    return {
        "total": len(items),
        "rated": len(rated),
        "unrated": len(items) - len(rated),
        "average": _average(rated),
        "average_after_next_step": _average([_rating_after(i, 0) for i in items]),
        "average_after_top": _average([_rating_after(i, -1) for i in items]),
        "distribution": {str(r): rated.count(r) for r in scale},
        "top_rated": rated.count(max(t.rating for t in rules.types)),
        "lowest_rated": rated.count(min(t.rating for t in rules.types)),
        "needs_review": sum(1 for i in items if i["needs_review"]),
        "actions": _actions(items),
    }


def _check_count(agreements: Sequence[AgreementInput]) -> None:
    if not agreements:
        raise ValueError("Pass at least one agreement.")
    if len(agreements) > MAX_AGREEMENTS:
        raise ValueError(f"Too many agreements: the dashboard takes up to {MAX_AGREEMENTS} at a time.")


def portfolio_cards(agreements: Sequence[AgreementInput], rulebook: Rulebook | None = None) -> list[dict[str, Any]]:
    """A full report card for each agreement, in the order they were uploaded (used for the bulk PDF)."""
    _check_count(agreements)
    rules = rulebook or load_rulebook()
    return [_card(a, rules) for a in agreements]


def build_portfolio(agreements: Sequence[AgreementInput], rulebook: Rulebook | None = None) -> dict[str, Any]:
    _check_count(agreements)
    rules = rulebook or load_rulebook()
    items = sorted((_item(a, rules, n) for n, a in enumerate(agreements, start=1)), key=lambda i: -1 if i["rating"] is None else i["rating"])
    return {
        "kind": "portfolio",
        "summary": _summary(items, rules),
        "items": items,
        "disclaimer": rules.disclaimer,
    }
