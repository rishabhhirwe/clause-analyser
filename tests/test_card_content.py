"""Card content tests: seat / venue / place of execution, risk reason, key takeaways, wording, PDF."""
import base64
from pathlib import Path

import pytest

from dispute_clause_analyzer.pdf_report import build_report_pdf, pdf_file_name
from dispute_clause_analyzer.portfolio import AgreementInput, build_portfolio
from dispute_clause_analyzer.report_card import build_report_card
from dispute_clause_analyzer.rulebook import load_rulebook

CLAUSES = Path(__file__).parent / "fixtures" / "clauses"
RULES = load_rulebook()

DISCLAIMER_START = "This tool provides preliminary informational analysis only and does not constitute legal advice"
WARNING_TEXT = (
    "Please remove or redact all personal information of the parties and other individuals mentioned in the "
    "document before uploading it, to protect personal data and support compliance with the DPDP Act."
)


def card(clause_id: str, **facts) -> dict:
    return build_report_card(
        clause_text=(CLAUSES / f"{clause_id}.txt").read_text(),
        deciding_quote="",
        clause_reference=facts.pop("clause_reference", "Clause 1"),
        who_picks=facts.pop("who_picks", "Someone"),
        seat_venue=facts.pop("seat_venue", ""),
        online_process=facts.pop("online_process", ""),
        **facts,
    )


def test_warning_uses_the_approved_wording():
    assert RULES.warning.startswith("Warning")
    assert WARNING_TEXT in RULES.warning


def test_disclaimer_uses_the_approved_wording():
    assert RULES.disclaimer.startswith("Disclaimer")
    assert DISCLAIMER_START in RULES.disclaimer
    assert "consult your legal advisor" in RULES.disclaimer


def test_every_type_explains_its_risk_in_one_full_sentence():
    for rating_type in RULES.types:
        assert rating_type.risk.endswith("."), rating_type.id
        assert 80 <= len(rating_type.risk) <= 240, rating_type.id
        assert rating_type.risk.count(". ") == 0, f"{rating_type.id} risk should be one sentence"


def test_good_ratings_have_key_takeaways():
    for rating_type in RULES.types:
        if rating_type.rating >= 4:
            assert len(rating_type.strengths) >= 2, rating_type.id


def test_card_shows_the_seat_and_leaves_out_the_venue():
    result = card("institution_recognised", seat="Bangalore (via Exhibit A)", venue="Not stated",
                  place_of_execution="Bangalore (Exhibit A)")

    assert result["facts"]["seat"] == "Bangalore (via Exhibit A)"
    assert "venue" not in result["facts"]


def test_old_combined_seat_venue_still_shows_as_the_seat():
    result = card("unilateral_lender_nominates", seat_venue="Wherever the lender decides")

    assert result["facts"]["seat"] == "Wherever the lender decides"


def test_card_carries_the_risk_reason():
    result = card("unilateral_lender_nominates")

    assert result["risk"] == RULES.type_by_name("unilateral").risk


def test_good_rating_card_lists_key_takeaways():
    assert card("presolv360_named")["strengths"] == list(RULES.type_by_name("presolv360").strengths)
    assert card("odr_unnamed")["strengths"] == list(RULES.type_by_name("odr").strengths)


def test_low_rating_card_has_no_key_takeaways():
    assert card("unilateral_lender_nominates")["strengths"] == []
    assert card("mutual_consent_scanned")["strengths"] == []


def test_card_and_portfolio_use_the_approved_disclaimer():
    agreements = [AgreementInput(file_name="a.pdf", clause_text=(CLAUSES / "odr_unnamed.txt").read_text())]

    assert card("odr_unnamed")["disclaimer"] == RULES.disclaimer
    assert build_portfolio(agreements)["disclaimer"] == RULES.disclaimer


def test_portfolio_items_carry_seat_risk_and_takeaways():
    agreement = AgreementInput(
        file_name="p360.pdf", clause_text=(CLAUSES / "presolv360_named.txt").read_text(),
        seat="Bengaluru", venue="Online", place_of_execution="Bengaluru",
    )

    item = build_portfolio([agreement])["items"][0]

    assert item["seat"] == "Bengaluru"
    assert item["risk"] == ""
    assert item["strengths"]


def test_pdf_is_a_valid_document_with_the_key_content():
    data = card("unilateral_lender_nominates", clause_reference="Clause 8.1", seat="Kolkata")

    pdf = build_report_pdf(data, title="UNILATERAL.pdf", compress=False)

    assert pdf.startswith(b"%PDF")
    for text in (b"Unilateral", b"Clause 8.1", b"Kolkata", b"Recommendation", b"Disclaimer"):
        assert text in pdf, text


def test_single_pdf_shows_the_score_as_a_gauge_and_the_disclaimer_last():
    pdf = build_report_pdf(card("unilateral_lender_nominates"), title="UNILATERAL.pdf", compress=False)

    assert b"(2/5) Tj" not in pdf
    assert b"out of 5" in pdf
    assert pdf.index(b"Disclaimer") > pdf.index(b"Recommendation")


def test_pdf_for_a_good_rating_lists_key_takeaways():
    pdf = build_report_pdf(card("presolv360_named"), title="p360.pdf", compress=False)

    assert b"Key takeaways" in pdf


def test_pdf_file_name_is_safe_and_dated():
    name = pdf_file_name("UNILATERAL / ABC: 2024?.pdf", date="2026-11-02_17-19")

    assert name == "Clause-rating-report_UNILATERAL-ABC-2024_2026-11-02_17-19.pdf"


def test_pdf_file_names_have_no_spaces_so_claude_cannot_turn_them_into_percent_codes():
    from dispute_clause_analyzer.pdf_report import portfolio_file_name

    assert " " not in pdf_file_name("Mutual Consent.pdf") and "%" not in pdf_file_name("Mutual Consent.pdf")
    assert " " not in portfolio_file_name(10)


def test_pdf_file_names_carry_the_time_by_default():
    import re

    from dispute_clause_analyzer.pdf_report import portfolio_file_name

    stamp = r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}\.pdf$"
    assert re.search(stamp, pdf_file_name("UNILATERAL.pdf"))
    assert re.search(r"^Clause-rating-report_10-agreements_" + stamp, portfolio_file_name(10))


def test_pdf_file_name_has_a_fallback():
    assert pdf_file_name("", date="2026-11-02") == "Clause-rating-report_2026-11-02.pdf"


def test_pdf_bytes_survive_base64_round_trip():
    pdf = build_report_pdf(card("odr_unnamed"), title="odr.pdf")

    assert base64.b64decode(base64.b64encode(pdf)) == pdf


@pytest.mark.parametrize("bad", [None, {}, {"kind": "portfolio"}])
def test_pdf_rejects_data_that_is_not_a_single_card(bad):
    with pytest.raises(ValueError):
        build_report_pdf(bad, title="x")


def test_low_rating_card_shows_the_risk_and_no_takeaways():
    result = card("mutual_consent_scanned")

    assert result["risk"] == RULES.type_by_name("mutual_consent").risk
    assert result["strengths"] == []


def test_high_rating_card_shows_takeaways_and_no_risk():
    result = card("presolv360_named")

    assert result["risk"] == ""
    assert result["strengths"]


def test_high_mixed_card_shows_the_takeaways_of_its_weakest_part():
    result = card("mixed_presolv360_and_any_odr")

    assert result["rating"] == 4.5
    assert result["risk"] == ""
    assert result["strengths"] == list(RULES.type_by_name("odr").strengths)


def test_low_mixed_card_shows_the_mixed_risk():
    result = card("mixed_unilateral_and_odr")

    assert result["risk"] == RULES.mixed["risk"]
    assert result["strengths"] == []


def test_card_html_has_a_labelled_risk_box():
    from dispute_clause_analyzer.report_card import load_card_html

    html = load_card_html()
    assert "risk-box" in html
    assert "⚠️ Risk" in html


def test_pdf_has_a_risk_section_only_for_low_ratings():
    low = build_report_pdf(card("unilateral_lender_nominates"), title="Low", compress=False)
    high = build_report_pdf(card("presolv360_named"), title="High", compress=False)

    assert b"(Risk)" in low
    assert b"(Risk)" not in high
    assert b"Key takeaways" in high


def test_card_html_draws_the_score_as_a_gauge_not_a_box():
    from dispute_clause_analyzer.report_card import load_card_html

    html = load_card_html()
    assert "function gauge(" in html
    assert "out of 5" in html
    assert "function grade(" not in html


def test_single_pdf_is_titled_clause_rating_report():
    pdf = build_report_pdf(card("unilateral_lender_nominates"), title="UNILATERAL.pdf", compress=False)

    assert b"Clause Rating Report" in pdf
    assert b"Dispute Clause Report" not in pdf
