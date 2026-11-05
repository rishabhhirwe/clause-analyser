"""Advice tests: what to change to raise a clause's rating, built from the rules."""
from pathlib import Path

import pytest

from dispute_clause_analyzer.advice import improvement_path, tidy_up
from dispute_clause_analyzer.classifier import classify
from dispute_clause_analyzer.rulebook import load_rulebook

CLAUSES = Path(__file__).parent / "fixtures" / "clauses"
RULES = load_rulebook()


def clause(clause_id: str) -> str:
    return (CLAUSES / f"{clause_id}.txt").read_text(encoding="utf-8")


def test_unilateral_path_climbs_through_each_rating_once():
    path = improvement_path(RULES, "unilateral")

    assert [s["rating_after"] for s in path] == [4, 5]
    assert [s["label"] for s in path] == ["Next step", "Top rating"]


def test_odr_path_has_one_step_not_two_identical_ones():
    path = improvement_path(RULES, "odr")

    assert [s["rating_after"] for s in path] == [5]
    assert path[0]["label"] == "Top rating"


@pytest.mark.parametrize("type_id", ["mutual_consent", "institutional"])
def test_three_out_of_five_paths_go_to_four_then_five(type_id):
    assert [s["rating_after"] for s in improvement_path(RULES, type_id)] == [4, 5]


def test_top_rated_and_unrated_have_no_path():
    assert improvement_path(RULES, "presolv360") == []
    assert improvement_path(RULES, None) == []


def test_every_step_says_what_to_change():
    for type_id in ("unilateral", "mutual_consent", "institutional", "odr"):
        for step in improvement_path(RULES, type_id):
            assert step["change"]
            assert step["wording"]


def test_paths_never_lower_the_rating():
    for rating_type in RULES.types:
        for step in improvement_path(RULES, rating_type.id):
            assert step["rating_after"] > rating_type.rating


def test_tidy_up_tells_the_user_to_keep_one_way_when_clause_conflicts():
    text = (
        "The sole arbitrator shall be appointed by the Lender. "
        "Alternatively a sole arbitrator appointed by mutual consent of the parties."
    )

    notes = tidy_up(RULES, classify(text))

    assert len(notes) == 1
    assert "straightforward and unambiguous" in notes[0]
    assert "Unilateral" in notes[0] and "Mutual consent" in notes[0]


def test_tidy_up_is_empty_for_a_clean_clause():
    assert tidy_up(RULES, classify(clause("unilateral_lender_nominates"))) == []
    assert tidy_up(RULES, classify("Disputes go to the courts at Pune.")) == []
