"""Loads and validates the editable rule files that ship with the package."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from types import MappingProxyType
from typing import Any, Mapping, Sequence

RULES_DIR = "rules"
MIXED_KEYS = ("label", "headline", "risk", "parts_line", "recommendation")


@dataclass(frozen=True)
class RatingType:
    id: str
    label: str
    rating: int
    headline: str
    meaning: str
    risk: str
    strengths: tuple[str, ...]
    signals: tuple[str, ...]
    patterns: tuple[re.Pattern[str], ...]


@dataclass(frozen=True)
class Rulebook:
    version: str
    types: tuple[RatingType, ...]
    mixed_clause_rules: tuple[str, ...]
    mixed: Mapping[str, str]
    improvements: Mapping[str, Mapping[str, Any]]
    examples: tuple[Mapping[str, Any], ...]
    warning: str
    instructions: str
    disclaimer: str = ""

    def type_by_name(self, name: str) -> RatingType:
        """Find a type by its id or label, ignoring case, spaces and underscores."""
        key = re.sub(r"[\s_]+", "_", name.strip().lower())
        for rating_type in self.types:
            if key in (rating_type.id, re.sub(r"\s+", "_", rating_type.label.lower())):
                return rating_type
        known = ", ".join(t.id for t in self.types)
        raise ValueError(f"Unknown type '{name}'. Known types: {known}")


def _compile(patterns: Sequence[str], owner: str) -> tuple[re.Pattern[str], ...]:
    try:
        return tuple(re.compile(p) for p in patterns)
    except re.error as exc:
        raise ValueError(f"Invalid pattern in scale.json for '{owner}': {exc}") from exc


def _parse_type(raw: Mapping[str, Any]) -> RatingType:
    signals = tuple(raw["signals"])
    return RatingType(
        id=raw["id"],
        label=raw["label"],
        rating=int(raw["rating"]),
        headline=raw.get("headline", ""),
        risk=raw.get("risk", ""),
        strengths=tuple(raw.get("strengths", ())),
        meaning=raw["meaning"],
        signals=signals,
        patterns=_compile(signals, raw["id"]),
    )


def build_rulebook(
    scale: Mapping[str, Any],
    improvements: Mapping[str, Any],
    examples: Sequence[Mapping[str, Any]],
    warning: str,
    instructions: str,
    disclaimer: str = "",
) -> Rulebook:
    """Validate the raw rule data and return an immutable rulebook."""
    types = tuple(_parse_type(t) for t in scale["types"])
    cleaned = {k: v for k, v in improvements.items() if not k.startswith("_")}
    missing = [t.id for t in types if t.id not in cleaned]
    if missing:
        raise ValueError(f"improvements.json has no entry for: {', '.join(missing)}")
    mixed = scale.get("mixed", {})
    missing_text = [k for k in MIXED_KEYS if k not in mixed]
    if missing_text:
        raise ValueError(f"scale.json 'mixed' is missing: {', '.join(missing_text)}")
    return Rulebook(
        version=scale["version"],
        types=types,
        mixed_clause_rules=tuple(scale["mixed_clause_rules"]),
        mixed=MappingProxyType(dict(mixed)),
        improvements=MappingProxyType(cleaned),
        examples=tuple(examples),
        warning=warning.strip(),
        instructions=instructions.strip(),
        disclaimer=disclaimer.strip(),
    )


def read_rule_file(name: str) -> str:
    """Read one of the rule files shipped in the package's rules folder."""
    return resources.files("dispute_clause_analyzer").joinpath(RULES_DIR, name).read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def load_rulebook() -> Rulebook:
    """Load the rule files shipped in the package. Raises ValueError if they are invalid."""
    return build_rulebook(
        scale=json.loads(read_rule_file("scale.json")),
        improvements=json.loads(read_rule_file("improvements.json")),
        examples=json.loads(read_rule_file("examples.json"))["examples"],
        warning=read_rule_file("warning.md"),
        instructions=read_rule_file("instructions.md"),
        disclaimer=read_rule_file("disclaimer.md"),
    )
