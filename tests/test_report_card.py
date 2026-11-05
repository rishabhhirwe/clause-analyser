"""Report card tests: the data behind the in-chat card is built from the rules, not from Claude."""
from pathlib import Path

import pytest

from dispute_clause_analyzer.report_card import build_report_card, load_card_html

CLAUSES = Path(__file__).parent / "fixtures" / "clauses"

FACTS = {
    "clause_reference": "Clause 8.1, Arbitration and Jurisdiction",
    "who_picks": "Lender alone",
    "seat_venue": "Wherever the lender decides",
    "online_process": "Not mentioned",
}


def card_for(clause_id: str, quote: str = "nominated/ appointed by the Lender") -> dict:
    text = (CLAUSES / f"{clause_id}.txt").read_text(encoding="utf-8")
    return build_report_card(clause_text=text, deciding_quote=quote, **FACTS)


def test_card_rating_comes_from_the_rules():
    card = card_for("unilateral_lender_nominates")

    assert card["rating"] == 2
    assert card["type"] == "unilateral"
    assert card["label"] == "Unilateral"
    assert card["tone"] == "red"
    assert card["headline"]


@pytest.mark.parametrize(
    "clause_id, tone",
    [
        ("presolv360_named", "green"),
        ("odr_unnamed", "yellow"),
        ("institution_recognised", "orange"),
        ("unilateral_sole_arbitrator", "red"),
    ],
)
def test_tone_follows_rating(clause_id, tone):
    assert card_for(clause_id, quote="")["tone"] == tone


def test_card_ladder_marks_the_current_level():
    ladder = card_for("odr_unnamed", quote="")["ladder"]

    assert [step["rating"] for step in ladder] == [2, 3, 4, 5]
    assert [step["current"] for step in ladder] == [False, False, True, False]


def test_card_carries_facts_quote_and_matched_wording():
    card = card_for("unilateral_lender_nominates")

    assert card["facts"]["who_picks"] == "Lender alone"
    assert "nominated/ appointed by the Lender" in card["deciding_quote"]
    assert card["matched_wording"]


def test_card_includes_the_path_to_a_higher_rating():
    card = card_for("unilateral_lender_nominates")

    assert [s["rating_after"] for s in card["path"]] == [4, 5]
    assert card["top_rated"] is False


def test_odr_card_has_a_single_step_to_the_top():
    card = card_for("odr_unnamed", quote="")

    assert [s["rating_after"] for s in card["path"]] == [5]


def test_top_rated_clause_has_no_path():
    card = card_for("presolv360_named", quote="")

    assert card["top_rated"] is True
    assert card["path"] == []


def test_card_says_how_to_tidy_up_a_mixed_clause():
    text = (CLAUSES / "mixed_unilateral_and_odr.txt").read_text(encoding="utf-8")

    card = build_report_card(clause_text=text, deciding_quote="", **FACTS)

    assert card["rating"] == 3
    assert any("Unilateral" in note and "straightforward" in note for note in card["also"])


def test_clean_card_has_nothing_to_tidy_up():
    assert card_for("unilateral_lender_nominates")["also"] == []


def test_unrecognised_clause_gives_unrated_card_with_review():
    card = build_report_card(clause_text="Disputes go to the courts at Pune.", deciding_quote="", **FACTS)

    assert card["rating"] is None
    assert card["tone"] == "gray"
    assert card["needs_review"] is True
    assert card["path"] == []


def test_quote_missing_from_clause_is_replaced_by_the_real_line():
    card = card_for("unilateral_lender_nominates", quote="appointed by Presolv360")

    assert card["needs_review"] is False
    assert "Presolv360" not in card["deciding_quote"]


def test_quote_across_bullet_points_still_counts_as_found():
    quote = "following ODR platforms (Designated Institution) as stated below or any other ODR platform: Presolv360 ODR Institution; or Example ODR Institution"

    card = card_for("mixed_presolv360_and_any_odr", quote=quote)

    assert card["needs_review"] is False


def test_long_fact_text_is_trimmed():
    text = (CLAUSES / "unilateral_lender_nominates.txt").read_text(encoding="utf-8")
    facts = {**FACTS, "seat_venue": "x" * 500}

    card = build_report_card(clause_text=text, deciding_quote="", **facts)

    assert len(card["facts"]["seat"]) <= 120


def test_card_html_speaks_the_mcp_apps_protocol():
    html = load_card_html()

    for method in ("ui/initialize", "ui/notifications/initialized", "ui/notifications/tool-result",
                   "ui/notifications/size-changed"):
        assert method in html


def test_single_card_is_marked_for_the_card_view():
    assert card_for("unilateral_lender_nominates")["kind"] == "report_card"


def test_card_html_handles_both_views():
    html = load_card_html()

    assert "report_card" in html
    assert "portfolio" in html


def test_card_html_never_injects_raw_html():
    assert "innerHTML" not in load_card_html()


def test_card_html_tells_the_user_when_the_report_could_not_be_built():
    html = load_card_html()

    assert "isError" in html
    assert "tool-cancelled" in html
    assert "Ask Claude to try again" in html


def test_card_html_can_recover_after_the_app_restarts():
    html = load_card_html()

    assert "reload_report" in html
    assert "ui/notifications/tool-input" in html
    assert "localStorage" in html
    assert "Load report" in html


def test_card_html_can_read_a_result_that_only_has_text():
    assert "JSON.parse" in load_card_html()
