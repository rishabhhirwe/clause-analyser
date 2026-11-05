"""Portfolio PDF tests: a summary page, then one page per agreement, in upload order."""
from pathlib import Path

from dispute_clause_analyzer.pdf_report import build_portfolio_pdf
from dispute_clause_analyzer.portfolio import AgreementInput, build_portfolio, portfolio_cards

CLAUSES = Path(__file__).parent / "fixtures" / "clauses"
UPLOAD_ORDER = [("p360.pdf", "presolv360_named"), ("UNILATERAL.pdf", "unilateral_lender_nominates"), ("odr clause.pdf", "odr_unnamed")]


def agreements() -> list[AgreementInput]:
    return [
        AgreementInput(file_name=name, lender="Lender", clause_reference="Cl. 1",
                       clause_text=(CLAUSES / f"{clause_id}.txt").read_text(encoding="utf-8"), seat="Seat " + name)
        for name, clause_id in UPLOAD_ORDER
    ]


def pdf_bytes() -> bytes:
    items = agreements()
    return build_portfolio_pdf(build_portfolio(items), portfolio_cards(items), compress=False)


def test_portfolio_items_remember_their_upload_position():
    items = build_portfolio(agreements())["items"]

    assert sorted((i["position"], i["file_name"]) for i in items) == [(1, "p360.pdf"), (2, "UNILATERAL.pdf"), (3, "odr clause.pdf")]


def test_portfolio_cards_are_full_cards_in_upload_order():
    cards = portfolio_cards(agreements())

    assert [c["kind"] for c in cards] == ["report_card"] * 3
    assert [c["rating"] for c in cards] == [5, 2, 4]
    assert cards[1]["facts"]["seat"] == "Seat UNILATERAL.pdf"


def test_portfolio_pdf_is_a_valid_document():
    assert pdf_bytes().startswith(b"%PDF")


def test_portfolio_pdf_has_a_summary_page_without_shared_recommendations():
    pdf = pdf_bytes()

    for text in (b"Clause Rating Report", b"Average rating"):
        assert text in pdf, text
    assert b"Portfolio Report" not in pdf
    for text in (b"Agreements",):
        assert text in pdf, text
    assert b"Recommendations" not in pdf


def test_portfolio_pdf_shows_the_disclaimer_once_at_the_very_end():
    pdf = pdf_bytes()

    assert pdf.count(b"Disclaimer") == 1
    assert pdf.index(b"Disclaimer") > pdf.index(b"Agreement 3 of 3")


def test_portfolio_pdf_scores_are_gauges_not_fractions():
    pdf = pdf_bytes()

    assert b"(5/5) Tj" not in pdf and b"(2/5) Tj" not in pdf
    assert b"out of 5" in pdf


def test_portfolio_pdf_has_one_page_per_agreement_in_upload_order():
    pdf = pdf_bytes()
    headings = [pdf.find(f"Agreement {n} of 3".encode()) for n in (1, 2, 3)]

    assert all(h > 0 for h in headings)
    assert headings == sorted(headings)
    assert pdf.find(b"Agreement 1 of 3: p360.pdf") >= 0
    assert pdf.find(b"Agreement 2 of 3: UNILATERAL.pdf") >= 0


def test_summary_table_lists_agreements_in_upload_order():
    pdf = pdf_bytes()
    first_seen = [pdf.find(name.encode()) for name, _ in UPLOAD_ORDER]

    assert first_seen == sorted(first_seen)


def test_online_process_is_optional_for_each_agreement():
    item = AgreementInput(clause_text="sole arbitrator nominated by the Lender", online_process="Not mentioned")

    assert item.online_process == "Not mentioned"
    assert AgreementInput(clause_text="x", online_process=None).online_process == ""


def test_portfolio_pdf_rejects_anything_that_is_not_a_portfolio():
    import pytest

    with pytest.raises(ValueError):
        build_portfolio_pdf({"kind": "report_card"}, [])


def test_portfolio_pdf_needs_a_card_for_every_agreement():
    import pytest

    items = agreements()
    with pytest.raises(ValueError):
        build_portfolio_pdf(build_portfolio(items), portfolio_cards(items)[:1])


def test_portfolio_pdf_shows_unrated_agreements_and_review_counts():
    items = [AgreementInput(file_name="courts.pdf", clause_text="Disputes go to the courts at Pune.", note="Court only"),
             *agreements()]

    pdf = build_portfolio_pdf(build_portfolio(items), portfolio_cards(items), compress=False)

    for text in (b"Not rated:", b"Need human review:", b"Note: Court only"):
        assert text in pdf, text


def test_download_button_keeps_showing_the_saved_file_name():
    from dispute_clause_analyzer.report_card import load_card_html

    html = load_card_html()
    download = html[html.index("function downloadPdf("):html.index("function pdfButton(")]
    assert "Saved to Downloads: " in download
    assert "setTimeout" not in download
