"""The line that decides it: always from the clause, and always containing the words that decided the rating."""
from pathlib import Path

from dispute_clause_analyzer.classifier import quote_found
from dispute_clause_analyzer.deciding_line import MAX_LINE_CHARS, deciding_lines
from dispute_clause_analyzer.pdf_report import build_report_pdf
from dispute_clause_analyzer.portfolio import AgreementInput, build_portfolio
from dispute_clause_analyzer.report_card import build_report_card, load_card_html

CLAUSES = Path(__file__).parent / "fixtures" / "clauses"


def text(clause_id: str) -> str:
    return (CLAUSES / f"{clause_id}.txt").read_text()


def card(clause_id: str, quote: str = "") -> dict:
    return build_report_card(clause_text=text(clause_id), deciding_quote=quote, clause_reference="Cl. 1", who_picks="x")


def test_a_presolv360_clause_shows_the_line_naming_presolv360_even_if_claude_quoted_another():
    result = card("presolv360_or_named_odr", quote="The juridical seat of arbitration shall be Kolkata, West Bengal.")

    assert len(result["deciding_lines"]) == 1
    assert "Presolv360" in result["deciding_lines"][0]
    assert result["deciding_quote"] == result["deciding_lines"][0]


def test_a_good_quote_from_claude_is_kept_as_it_is():
    quote = "the same shall be referred to arbitration by a sole arbitrator to be nominated/ appointed by the Lender."

    assert card("unilateral_lender_nominates", quote=quote)["deciding_lines"] == [quote]


def test_a_mixed_clause_shows_one_line_per_part():
    lines = card("mixed_unilateral_and_odr")["deciding_lines"]

    assert len(lines) == 2
    assert "online dispute resolution" in lines[0].lower()
    assert "lender" in lines[1].lower()


def test_lines_are_taken_from_the_clause_and_kept_short():
    for clause_id in ("mixed_presolv360_and_any_odr", "mutual_consent_online_hearings", "institution_recognised", "odr_unnamed"):
        for line in card(clause_id)["deciding_lines"]:
            assert len(line) <= MAX_LINE_CHARS + 2, line
            assert quote_found(line.strip("…"), text(clause_id)), line


def test_long_sentences_are_trimmed_with_dots_around_the_deciding_words():
    sentence = ("This Agreement and every annexure, schedule and side letter, together with all notices, demands, statements "
                "and other papers exchanged between the parties at any time, shall in every case be subject to the following, "
                "namely that the sole arbitrator shall be appointed by the Lender, and the Borrower agrees to the same without "
                "any objection of any kind whatsoever, now or at any time in the future, for any reason at all")

    line = deciding_lines(sentence, "")[0]

    assert line.startswith("…") and line.endswith("…")
    assert "appointed by the Lender" in line
    assert len(line) <= MAX_LINE_CHARS + 2


def test_unrated_clause_has_no_line():
    assert deciding_lines("Disputes go to the courts at Pune.", "Disputes go to the courts at Pune.") == []


def test_a_wrong_quote_is_replaced_rather_than_flagged_for_review():
    result = card("unilateral_lender_nominates", quote="appointed by Presolv360")

    assert result["needs_review"] is False
    assert "Lender" in result["deciding_lines"][0]


def test_dashboard_items_use_the_same_lines():
    item = build_portfolio([AgreementInput(clause_text=text("mixed_unilateral_and_odr"), deciding_quote="nonsense")])["items"][0]

    assert len(item["card"]["deciding_lines"]) == 2
    assert item["needs_review"] is False


def test_card_and_pdf_show_every_line():
    result = card("mixed_unilateral_and_odr")
    pdf = build_report_pdf(result, title="Mixed", compress=False).decode("latin-1")

    assert "card.deciding_lines" in load_card_html()
    for line in result["deciding_lines"]:
        assert line.split()[2] in pdf
    assert "The lines that decide it" in pdf
