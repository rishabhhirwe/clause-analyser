"""Mixed clauses: more than one way of picking the arbitrator gets the average of the parts.

Legal team ruling, 2026-11-03: for example unilateral + ODR is (2 + 4) / 2 = 3, and the
recommendation is to keep the clause straightforward and unambiguous.
"""
from pathlib import Path

from dispute_clause_analyzer.classifier import classify
from dispute_clause_analyzer.pdf_report import build_report_pdf
from dispute_clause_analyzer.portfolio import AgreementInput, build_portfolio
from dispute_clause_analyzer.report_card import build_report_card

CLAUSES = Path(__file__).parent / "fixtures" / "clauses"
UNILATERAL_AND_ODR = (
    "Disputes shall be referred to a sole arbitrator to be nominated by the Lender. "
    "Alternatively the sole arbitrator shall be appointed by any online dispute resolution forum."
)
UNILATERAL_AND_INSTITUTIONAL = (
    "Disputes shall be referred to a sole arbitrator to be nominated by the Lender, or to a sole "
    "arbitrator appointed by a recognised independent institution."
)


def card(text: str) -> dict:
    return build_report_card(clause_text=text, deciding_quote="", clause_reference="Cl. 9", who_picks="Mixed")


def test_unilateral_and_odr_average_to_three():
    result = classify(UNILATERAL_AND_ODR)

    assert result.rating == 3
    assert result.mixed is True
    assert set(result.detected_types) == {"unilateral", "odr"}
    assert result.needs_review is False


def test_unilateral_and_institutional_average_to_two_and_a_half():
    assert classify(UNILATERAL_AND_INSTITUTIONAL).rating == 2.5


def test_mixed_type_is_the_weakest_part_so_advice_fixes_it():
    assert classify(UNILATERAL_AND_ODR).type == "unilateral"


def test_notwithstanding_no_longer_lets_one_part_win():
    assert classify((CLAUSES / "mixed_unilateral_and_odr.txt").read_text()).rating == 3


def test_presolv360_or_cord_is_one_way_and_stays_five():
    result = classify((CLAUSES / "presolv360_or_named_odr.txt").read_text())

    assert (result.rating, result.mixed) == (5, False)


def test_whole_ratings_stay_whole_numbers():
    assert isinstance(classify(UNILATERAL_AND_ODR).rating, int)
    assert isinstance(classify((CLAUSES / "odr_unnamed.txt").read_text()).rating, int)


def test_card_shows_the_average_and_each_part():
    result = card(UNILATERAL_AND_INSTITUTIONAL)

    assert result["rating"] == 2.5
    assert result["label"] == "Mixed: Institutional + Unilateral"
    assert result["parts"] == [{"type": "institutional", "label": "Institutional", "rating": 3},
                               {"type": "unilateral", "label": "Unilateral", "rating": 2}]
    assert result["tone"] == "red"
    assert [step["rating"] for step in result["ladder"] if step["current"]] == [2, 3]


def test_card_recommends_a_straightforward_unambiguous_clause():
    result = card(UNILATERAL_AND_ODR)

    assert any("straightforward and unambiguous" in note for note in result["also"])
    assert all(step["rating_after"] > 3 for step in result["path"])
    assert result["path"]


def test_single_type_card_has_one_part_and_no_mixed_advice():
    result = card((CLAUSES / "unilateral_lender_nominates.txt").read_text())

    assert result["parts"] == [{"type": "unilateral", "label": "Unilateral", "rating": 2}]
    assert result["label"] == "Unilateral"
    assert result["also"] == []


def test_portfolio_counts_half_scores_and_averages_them():
    portfolio = build_portfolio([AgreementInput(clause_text=UNILATERAL_AND_INSTITUTIONAL),
                                 AgreementInput(clause_text=UNILATERAL_AND_ODR)])
    summary = portfolio["summary"]

    assert summary["distribution"]["2.5"] == 1
    assert summary["distribution"]["3"] == 1
    assert summary["average"] == 2.8
    assert portfolio["items"][0]["parts"][0]["label"] == "Institutional"


def test_pdf_prints_the_half_score_and_the_parts():
    pdf = build_report_pdf(card(UNILATERAL_AND_INSTITUTIONAL), title="Mixed", compress=False)

    assert b"(2.5) Tj" in pdf
    assert b"Average of Institutional 3/5 and Unilateral 2/5" in pdf
