"""Picks "the line that decides it" from the clause itself, so it always holds the words that decided the rating.

Claude's own quote is kept when it is in the clause and contains the deciding words for every part. Otherwise the
sentence around those words is taken from the clause: one line per part for a mixed clause, trimmed when long.
"""
from __future__ import annotations

import re

from dispute_clause_analyzer.classifier import DASHES, classify, normalize, quote_found
from dispute_clause_analyzer.rulebook import Rulebook, load_rulebook

MAX_LINE_CHARS = 220  # about two lines on the card
ELLIPSIS = "…"
SHORT_WORD = 2  # "Rs.", "No." and "1." do not end a sentence


def _display(text: str) -> str:
    """The clause as normalize() sees it, but keeping capital letters, so positions line up."""
    unified = DASHES.sub("-", text.replace("“", '"').replace("”", '"').replace("’", "'"))
    return re.sub(r"\s+", " ", unified).strip()


def _sentence_end(text: str, i: int) -> bool:
    if text[i] not in ".;" or (i + 1 < len(text) and text[i + 1] != " "):
        return False
    word = re.search(r"(\S+)$", text[:i])
    return len(re.sub(r"[^A-Za-z]", "", word.group(1) if word else "")) > SHORT_WORD


def _sentence(text: str, start: int, end: int) -> tuple[int, int]:
    left = max((i + 1 for i in range(start) if _sentence_end(text, i)), default=0)
    right = next((i + 1 for i in range(end, len(text)) if _sentence_end(text, i)), len(text))
    return left, right


def _trim(text: str, start: int, end: int) -> str:
    """The sentence around text[start:end], cut to about two lines around those words with "…" where cut."""
    left, right = _sentence(text, start, end)
    if right - left <= MAX_LINE_CHARS:
        return text[left:right].strip()
    spare = max(0, MAX_LINE_CHARS - (end - start))
    a = max(left, start - spare // 2)
    b = min(right, a + MAX_LINE_CHARS)
    a = max(left, b - MAX_LINE_CHARS)
    if a > left and 0 <= text.find(" ", a) < start:
        a = text.find(" ", a) + 1
    if b < right and text.rfind(" ", 0, b) > end:
        b = text.rfind(" ", 0, b)
    return (ELLIPSIS if a > left else "") + text[a:b].strip() + (ELLIPSIS if b < right else "")


def _covers(quote: str, types: tuple[str, ...], rules: Rulebook) -> bool:
    lowered = normalize(quote)
    return all(any(p.search(lowered) for p in rules.type_by_name(t).patterns) for t in types)


def pick_lines(clause_text: str, quote: str, rulebook: Rulebook | None = None) -> tuple[list[str], str]:
    """The lines to show, and the one for the weakest part (the one the next-step suggestion replaces)."""
    rules = rulebook or load_rulebook()
    result = classify(clause_text, rules)
    if not result.detected_types:
        return [], ""
    claude = " ".join(quote.split())
    if claude and quote_found(claude, clause_text) and _covers(claude, result.detected_types, rules):
        return [claude], claude
    text = _display(clause_text)
    lowered = text.lower()
    by_type: dict[str, str] = {}
    for type_id in result.detected_types:
        first = min((m for p in rules.type_by_name(type_id).patterns for m in [p.search(lowered)] if m), key=lambda m: m.start())
        by_type[type_id] = _trim(text, first.start(), first.end())
    return list(dict.fromkeys(by_type.values())), by_type[result.type]


def deciding_lines(clause_text: str, quote: str, rulebook: Rulebook | None = None) -> list[str]:
    return pick_lines(clause_text, quote, rulebook)[0]
