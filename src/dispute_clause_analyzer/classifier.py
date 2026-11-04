"""Decides a clause's rating from its wording, using the rulebook."""
from __future__ import annotations

import re
from dataclasses import dataclass

from dispute_clause_analyzer.rulebook import Rulebook, load_rulebook

DASHES = re.compile(r"[‐-―−]")

Signals = dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class Classification:
    """type is the weakest part, so advice fixes it; rating is the average of all parts."""

    type: str | None
    rating: int | float | None
    detected_types: tuple[str, ...]
    matched_phrases: tuple[str, ...]
    needs_review: bool
    review_reasons: tuple[str, ...]

    @property
    def mixed(self) -> bool:
        return len(self.detected_types) > 1


def average_rating(ratings: list[int]) -> int | float:
    """The average to one decimal place, as a whole number when it is one (3, not 3.0)."""
    mean = round(sum(ratings) / len(ratings), 1)
    return int(mean) if mean.is_integer() else mean


def normalize(text: str) -> str:
    """Lowercase, unify quotes and dashes, and collapse whitespace so wording matches across layouts."""
    unified = text.replace("“", '"').replace("”", '"').replace("’", "'")
    unified = DASHES.sub("-", unified)
    return re.sub(r"\s+", " ", unified).strip().lower()


def quote_found(quote: str, clause_text: str) -> bool:
    """True if the quote appears in the clause, ignoring case, spacing, punctuation and bullet marks."""
    def words(text: str) -> str:
        return " ".join(re.findall(r"[a-z0-9]+", normalize(text)))

    return words(quote) in words(clause_text)


def _find_signals(text: str, rulebook: Rulebook) -> Signals:
    found: Signals = {}
    for rating_type in rulebook.types:
        hits = tuple(dict.fromkeys(m.group(0) for p in rating_type.patterns for m in p.finditer(text)))
        if hits:
            found[rating_type.id] = hits
    return found


def classify(clause_text: str, rulebook: Rulebook | None = None) -> Classification:
    """Rate a clause. More than one way of picking the arbitrator gets the average of the parts
    (legal team ruling, 2026-11-03)."""
    rules = rulebook or load_rulebook()
    detected = _find_signals(normalize(clause_text), rules)

    if not detected:
        reason = "No wording from the rating scale was found. The clause may be new wording or not a dispute clause."
        return Classification(None, None, (), (), True, (reason,))

    ratings = [rules.type_by_name(t).rating for t in detected]
    return Classification(
        type=min(detected, key=lambda t: rules.type_by_name(t).rating),
        rating=average_rating(ratings),
        detected_types=tuple(detected),
        matched_phrases=tuple(dict.fromkeys(p for hits in detected.values() for p in hits)),
        needs_review=False,
        review_reasons=(),
    )
