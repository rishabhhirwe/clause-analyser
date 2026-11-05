"""Rating tests: every reference clause must get the rating the team confirmed."""
import json
from pathlib import Path

import pytest

from dispute_clause_analyzer.classifier import classify

FIXTURES = Path(__file__).parent / "fixtures"
ANSWER_KEY = json.loads((FIXTURES / "answer_key.json").read_text(encoding="utf-8"))["clauses"]


def load_clause(clause_id: str) -> str:
    return (FIXTURES / "clauses" / f"{clause_id}.txt").read_text(encoding="utf-8")


@pytest.mark.parametrize("case", ANSWER_KEY, ids=[c["id"] for c in ANSWER_KEY])
def test_reference_clause_gets_confirmed_rating(case):
    result = classify(load_clause(case["id"]))

    assert result.detected_types == tuple(case.get("parts", [case["type"]]))
    assert result.mixed is (case["type"] == "mixed")
    assert result.rating == case["rating"]
    assert result.needs_review is False


def test_odr_used_only_for_conducting_the_case_does_not_change_rating():
    result = classify(load_clause("mutual_consent_online_hearings"))

    assert result.type == "mutual_consent"
    assert "odr" not in result.detected_types


def test_clause_without_any_known_wording_needs_review():
    result = classify("Any dispute shall be referred to the courts at Pune.")

    assert result.rating is None
    assert result.needs_review is True
    assert result.review_reasons


def test_wording_is_matched_regardless_of_case_and_line_breaks():
    text = "the Sole\nArbitrator   NOMINATED by the\nLender"

    assert classify(text).type == "unilateral"


def test_matched_phrases_are_reported_for_explanation():
    result = classify(load_clause("unilateral_lender_nominates"))

    assert any("lender" in phrase for phrase in result.matched_phrases)
