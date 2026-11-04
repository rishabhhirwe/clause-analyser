"""Regression tests for real-world wording beyond the 13 reference clauses (from code review)."""
import pytest

from dispute_clause_analyzer.classifier import classify


@pytest.mark.parametrize(
    "text",
    [
        "The sole arbitrator shall be appointed by the Lender.",
        "a sole arbitrator, to be appointed by the Lender",
        "The Lender shall appoint a sole arbitrator.",
        "the arbitrator shall be appointed solely by the Bank",
        "The Bank may nominate the sole arbitrator.",
    ],
)
def test_common_unilateral_wordings_are_caught(text):
    result = classify(text)

    assert result.type == "unilateral"
    assert result.rating == 2


def test_company_is_not_assumed_to_be_the_lender():
    result = classify("The sole arbitrator shall be appointed by the Company, being the Borrower.")

    assert result.type is None
    assert result.needs_review is True


def test_two_types_with_the_same_rating_are_still_a_mix():
    result = classify(
        "a sole arbitrator appointed by mutual consent of the parties or by a recognised independent institution"
    )

    assert result.rating == 3
    assert result.mixed is True


def test_presolv360_mentioned_alongside_lender_appointment_is_not_five():
    result = classify(
        "The Borrower may not choose Presolv360. The sole arbitrator shall be appointed by the Lender."
    )

    assert result.rating == 3.5
    assert result.mixed is True


@pytest.mark.parametrize(
    "override",
    [
        "Notwithstanding anything contained herein to the contrary,",
        "Notwithstanding anything contained in this Agreement to the contrary,",
        "Notwithstanding the foregoing,",
    ],
)
def test_notwithstanding_parts_are_averaged_like_any_other_mix(override):
    text = (
        "(i) Disputes shall be referred to a sole arbitrator to be nominated by the Lender. "
        f"(ii) {override} the sole arbitrator shall be appointed by any online dispute resolution forum."
    )
    result = classify(text)

    assert result.rating == 3
    assert result.mixed is True


@pytest.mark.parametrize(
    "text, expected",
    [
        ("the Lender shall propose three (3) names for the sole arbitrator", "mutual_consent"),
        ("the Lender shall propose 3 names, of which the Borrower selects one", "mutual_consent"),
        ("the sole arbitrator shall be appointed by any ODR platform", "odr"),
        ("administered electronically by Presolv‑360 under its rules", "presolv360"),
    ],
)
def test_additional_wording_variants(text, expected):
    assert classify(text).type == expected


def test_matched_phrases_have_no_duplicates():
    text = "sole arbitrator nominated by the Lender. Again, sole arbitrator nominated by the Lender."

    phrases = classify(text).matched_phrases

    assert len(phrases) == len(set(phrases))
