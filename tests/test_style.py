"""House style: Times New Roman everywhere, and the 'Arbitrator to be appointed by' label."""
from pathlib import Path

from dispute_clause_analyzer.pdf_report import build_report_pdf
from dispute_clause_analyzer.report_card import build_report_card, load_card_html
from dispute_clause_analyzer.rulebook import load_rulebook

CLAUSE = (Path(__file__).parent / "fixtures" / "clauses" / "unilateral_lender_nominates.txt").read_text(encoding="utf-8")


def card() -> dict:
    return build_report_card(clause_text=CLAUSE, deciding_quote="", clause_reference="Cl. 8.1", who_picks="Lender alone")


def test_card_page_uses_times_new_roman_only():
    html = load_card_html()

    assert '"Times New Roman"' in html
    for other in ("-apple-system", "Segoe UI", "Roboto", "sans-serif", "Georgia"):
        assert other not in html, other


def test_pdf_text_is_all_in_times():
    import re

    pdf = build_report_pdf(card(), title="UNILATERAL.pdf", compress=False)
    fonts = dict(re.findall(rb"/BaseFont /([\w-]+) .*?/Name /(F\d+)", pdf, re.S))
    # Fonts that draw text: a font choice followed by "(text)" before its block ends with ET.
    used = set(re.findall(rb"/(F\d+) [\d.]+ Tf(?:(?!ET)[^()])*\(", pdf))

    assert {name for name, ref in fonts.items() if ref in used} == {b"Times-Roman", b"Times-Bold"}


def test_label_reads_arbitrator_to_be_appointed_by_everywhere():
    pdf = build_report_pdf(card(), title="UNILATERAL.pdf", compress=False)

    assert card()["fact_rows"][1]["label"] == "Arbitrator to be appointed by"
    assert b"Arbitrator to be appointed by" in pdf
    for text in (load_card_html(), load_rulebook().instructions, pdf.decode("latin-1")):
        assert "Who picks" not in text
