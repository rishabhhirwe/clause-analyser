"""Rulebook tests: the editable rule files must stay complete and valid."""
import re

import pytest

from dispute_clause_analyzer.rulebook import build_rulebook, load_rulebook

EXPECTED_RATINGS = {
    "presolv360": 5,
    "odr": 4,
    "institutional": 3,
    "mutual_consent": 3,
    "unilateral": 2,
}


def test_scale_matches_team_rating_doc():
    rulebook = load_rulebook()

    assert {t.id: t.rating for t in rulebook.types} == EXPECTED_RATINGS


def test_every_type_has_signals_that_compile():
    for rating_type in load_rulebook().types:
        assert rating_type.signals, rating_type.id
        for pattern in rating_type.signals:
            re.compile(pattern)


def test_every_type_has_an_improvement_suggestion():
    rulebook = load_rulebook()

    for rating_type in rulebook.types:
        improvement = rulebook.improvements[rating_type.id]
        assert improvement["next_step"]


def test_warning_mentions_personal_information():
    assert "personal information" in load_rulebook().warning.lower()


def test_examples_cover_every_type():
    rulebook = load_rulebook()

    assert {e["type"] for e in rulebook.examples} - {"mixed"} == set(EXPECTED_RATINGS)


def test_mixed_examples_are_rated_as_the_average_of_their_parts():
    mixed = [e for e in load_rulebook().examples if e["type"] == "mixed"]

    assert {e["rating"] for e in mixed} == {3, 4.5}
    for example in mixed:
        ratings = [EXPECTED_RATINGS[p] for p in example["parts"]]
        assert example["rating"] == sum(ratings) / len(ratings)


def test_mixed_rule_text_is_complete():
    assert "{labels}" in load_rulebook().mixed["recommendation"]
    assert "straightforward and unambiguous" in load_rulebook().mixed["recommendation"]


def test_rulebook_without_mixed_texts_fails_at_load():
    parts = _valid_parts()
    del parts["scale"]["mixed"]

    with pytest.raises(ValueError, match="mixed"):
        build_rulebook(**parts)


def _valid_parts() -> dict:
    scale = {
        "version": "test",
        "types": [{"id": "odr", "label": "ODR", "rating": 4, "meaning": "m", "signals": ["odr"]}],
        "mixed_clause_rules": ["r"],
        "mixed": {"label": "Mixed", "headline": "h", "risk": "r", "parts_line": "p {parts}", "recommendation": "k {labels}"},
    }
    improvements = {"odr": {"next_step": {"rating_after": 5}, "top_option": {"rating_after": 5}}}
    return {"scale": scale, "improvements": improvements, "examples": [], "warning": "w", "instructions": "i"}


def test_broken_signal_pattern_fails_at_load_naming_the_type():
    parts = _valid_parts()
    parts["scale"]["types"][0]["signals"] = ["odr ("]

    with pytest.raises(ValueError, match="odr"):
        build_rulebook(**parts)


def test_missing_improvement_fails_at_load():
    parts = _valid_parts()
    parts["improvements"] = {}

    with pytest.raises(ValueError, match="improvements"):
        build_rulebook(**parts)


@pytest.mark.parametrize("name", ["mutual_consent", "Mutual consent", "MUTUAL_CONSENT", " mutual consent "])
def test_type_lookup_accepts_id_or_label_in_any_case(name):
    assert load_rulebook().type_by_name(name).id == "mutual_consent"


def test_type_lookup_rejects_unknown_name():
    with pytest.raises(ValueError, match="Unknown type"):
        load_rulebook().type_by_name("nonsense")
