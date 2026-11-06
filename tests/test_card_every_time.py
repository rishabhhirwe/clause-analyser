"""Rating a clause always shows the card: the card belongs to rate_clause itself, so Claude cannot skip it."""
import asyncio
import json
from pathlib import Path

from dispute_clause_analyzer.report_card import CARD_URI
from dispute_clause_analyzer.server import RULES, server

CLAUSE = (Path(__file__).parent / "fixtures" / "clauses" / "unilateral_lender_nominates.txt").read_text(encoding="utf-8")


def tools() -> dict:
    return {t.name: t for t in asyncio.run(server.list_tools())}


def call(name: str, arguments: dict) -> dict:
    result = asyncio.run(server.call_tool(name, arguments))
    assert result.is_error is False, result.content
    return json.loads(result.content[0].text)


def test_rate_clause_carries_the_card():
    assert tools()["rate_clause"].meta["ui"]["resourceUri"] == CARD_URI


def test_rate_clause_returns_the_card_and_the_rating():
    out = call("rate_clause", {
        "clause_text": CLAUSE, "claimed_type": "unilateral", "clause_reference": "Clause 12.1",
        "who_picks": "Lender alone", "seat": "Kolkata (opening line)", "online_process": "Not mentioned",
        "file_name": "UNILATERAL.pdf"})

    assert out["kind"] == "report_card"
    assert (out["rating"], out["type"], out["type_label"]) == (2, "unilateral", "Unilateral")
    assert out["reason"] and out["path"] and out["personal_data_warning"] == RULES.warning
    assert out["facts"]["seat"] == "Kolkata (opening line)" and out["facts"]["clause_reference"] == "Clause 12.1"
    assert "card_shown" in out and out["hosted"] is False


def test_rate_clause_keeps_flagging_a_wrong_guess_from_claude():
    out = call("rate_clause", {"clause_text": CLAUSE, "claimed_type": "odr"})

    assert out["needs_review"] is True
    assert any("claimed" in reason for reason in out["review_reasons"])


def test_card_rebuilds_from_rate_clause_arguments():
    out = call("reload_report", {"original_arguments": {"clause_text": CLAUSE, "claimed_type": "unilateral",
                                                         "seat": "Kolkata"}})

    assert out["rating"] == 2 and out["facts"]["seat"] == "Kolkata"


def test_instructions_say_the_rating_shows_the_card_once():
    text = RULES.instructions

    assert "`rate_clause` shows the report card" in text
    assert "Do not call `show_report_card` after `rate_clause`" in text
