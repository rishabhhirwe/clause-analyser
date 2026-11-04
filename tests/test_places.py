"""Seat / place of execution: one item, venue never shown (legal team ruling, 2026-11-03)."""
import json
from pathlib import Path

from dispute_clause_analyzer.pdf_report import build_portfolio_pdf
from dispute_clause_analyzer.portfolio import AgreementInput, build_portfolio, portfolio_cards
from dispute_clause_analyzer.report_card import SEAT_LABEL, build_report_card, seat_value

CLAUSE = "the sole arbitrator to be appointed by mutual consent of the parties"


def test_stated_seat_is_used():
    assert seat_value(seat="Gurgaon (Schedule, point 13)", place_of_execution="Delhi") == "Gurgaon (Schedule, point 13)"


def test_place_of_execution_fills_in_when_the_seat_is_missing():
    assert seat_value(seat="", place_of_execution="Kolkata (stamp paper)") == "Kolkata (stamp paper)"
    assert seat_value(seat="Not stated", place_of_execution="Kolkata") == "Kolkata"


def test_neither_stated_reads_not_stated():
    assert seat_value(seat="", place_of_execution="not stated") == "Not stated"


def test_card_has_one_seat_row_and_no_venue():
    card = build_report_card(clause_text=CLAUSE, deciding_quote="", clause_reference="Cl. 11.6", who_picks="Both sides",
                             seat="", venue="Chennai", place_of_execution="Gurgaon, Haryana", online_process="Yes")

    assert [r["label"] for r in card["fact_rows"]] == ["Clause", "Arbitrator to be appointed by", SEAT_LABEL, "Online process"]
    assert card["fact_rows"][2]["value"] == "Gurgaon, Haryana"
    assert "Chennai" not in json.dumps(card)
    assert SEAT_LABEL == "Seat / place of execution"


def test_old_combined_seat_venue_still_counts_as_the_seat():
    card = build_report_card(clause_text=CLAUSE, deciding_quote="", clause_reference="", who_picks="", seat_venue="Mumbai")

    assert card["facts"]["seat"] == "Mumbai"


def test_portfolio_item_has_one_seat_place_and_no_venue():
    item = build_portfolio([AgreementInput(clause_text=CLAUSE, venue="Chennai", place_of_execution="Pune")])["items"][0]

    assert item["places"] == [{"label": SEAT_LABEL, "value": "Pune"}]
    assert "venue" not in item


def test_pdf_shows_seat_place_of_execution_and_never_venue():
    agreements = [AgreementInput(clause_text=CLAUSE, seat="Gurgaon", venue="Chennai")]
    pdf = build_portfolio_pdf(build_portfolio(agreements), portfolio_cards(agreements), compress=False)

    assert b"Seat / place of execution" in pdf
    assert b"Venue" not in pdf and b"Chennai" not in pdf


def test_card_html_draws_the_fact_rows_without_a_venue_fallback():
    from dispute_clause_analyzer.report_card import load_card_html

    html = load_card_html()
    assert "fact_rows" in html
    assert "Venue" not in html


def test_rules_tell_claude_to_find_only_the_seat_or_place_of_execution():
    instructions = (Path(__file__).parents[1] / "src" / "dispute_clause_analyzer" / "rules" / "instructions.md").read_text()

    assert "`venue`" not in instructions
