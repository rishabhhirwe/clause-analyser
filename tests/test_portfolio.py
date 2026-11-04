"""Portfolio tests: the bulk dashboard rates every agreement from the rules and summarises them."""
import json
from pathlib import Path

import pytest

from dispute_clause_analyzer.portfolio import MAX_AGREEMENTS, AgreementInput, build_portfolio

FIXTURES = Path(__file__).parent / "fixtures"
ANSWER_KEY = json.loads((FIXTURES / "answer_key.json").read_text())["clauses"]
AGREEMENT_IDS = [c["id"] for c in ANSWER_KEY]


def agreement(clause_id: str, **overrides) -> AgreementInput:
    base = {
        "file_name": f"{clause_id}.pdf",
        "lender": "Lender",
        "clause_reference": "Clause 1",
        "clause_text": (FIXTURES / "clauses" / f"{clause_id}.txt").read_text(),
        "deciding_quote": "",
        "who_picks": "Someone",
        "seat_venue": "Somewhere",
        "note": "",
    }
    return AgreementInput(**{**base, **overrides})


def test_all_test_agreements_get_their_expected_ratings():
    portfolio = build_portfolio([agreement(i) for i in AGREEMENT_IDS])
    expected = {f"{c['id']}.pdf": c["rating"] for c in ANSWER_KEY if c["id"] in AGREEMENT_IDS}

    assert {item["file_name"]: item["rating"] for item in portfolio["items"]} == expected


def test_summary_counts_and_average():
    portfolio = build_portfolio([agreement(i) for i in AGREEMENT_IDS])
    summary = portfolio["summary"]

    assert summary["total"] == 13
    assert summary["distribution"] == {"5": 3, "4.5": 1, "4": 1, "3": 6, "2": 2}
    assert summary["average"] == 3.5
    assert summary["top_rated"] == 3
    assert summary["lowest_rated"] == 2
    assert summary["needs_review"] == 0


def test_items_are_sorted_worst_first():
    portfolio = build_portfolio([agreement(i) for i in AGREEMENT_IDS])
    ratings = [item["rating"] for item in portfolio["items"]]

    assert ratings == sorted(ratings)


def test_each_item_carries_its_path_except_top_rated():
    items = {i["file_name"]: i for i in build_portfolio([agreement(i) for i in AGREEMENT_IDS])["items"]}

    assert [s["rating_after"] for s in items["unilateral_lender_nominates.pdf"]["path"]] == [4, 5]
    assert [s["rating_after"] for s in items["odr_unnamed.pdf"]["path"]] == [5]
    assert items["presolv360_named.pdf"]["path"] == []


def test_mixed_item_says_to_keep_one_way_of_picking():
    items = {i["file_name"]: i for i in build_portfolio([agreement(i) for i in AGREEMENT_IDS])["items"]}

    assert any("Unilateral" in note for note in items["mixed_unilateral_and_odr.pdf"]["also"])


def test_summary_shows_the_average_each_round_of_fixes_would_reach():
    summary = build_portfolio([agreement(i) for i in AGREEMENT_IDS])["summary"]

    assert summary["average"] == 3.5
    assert summary["average_after_next_step"] == 4.4
    assert summary["average_after_top"] == 5.0


def test_summary_groups_the_to_do_list_by_action_worst_first():
    actions = build_portfolio([agreement(i) for i in AGREEMENT_IDS])["summary"]["actions"]

    assert [(a["label"], a["count"], a["rating_after"]) for a in actions] == [
        ("Unilateral", 2, 4),
        ("Institutional", 2, 4),
        ("Mixed: ODR + Unilateral", 1, 4),
        ("Mutual consent", 3, 4),
        ("ODR", 1, 5),
        ("Mixed: Presolv360 + ODR", 1, 5),
    ]
    unilateral = actions[0]
    assert sorted(unilateral["files"]) == ["unilateral_lender_nominates.pdf", "unilateral_sole_arbitrator.pdf"]
    assert unilateral["change"]


def test_top_rated_only_portfolio_has_no_actions():
    summary = build_portfolio([agreement("presolv360_named")])["summary"]

    assert summary["actions"] == []
    assert summary["average_after_next_step"] == 5.0


def test_unrated_agreements_are_left_out_of_the_potential_averages():
    unknown = agreement("unilateral_lender_nominates", clause_text="Disputes go to the courts at Pune.")

    summary = build_portfolio([unknown, agreement("unilateral_lender_nominates")])["summary"]

    assert summary["average_after_next_step"] == 4.0


def test_unrecognised_clause_is_listed_first_and_flagged():
    unknown = agreement("unilateral_lender_nominates", file_name="mystery.pdf", clause_text="Disputes go to the courts at Pune.")

    portfolio = build_portfolio([agreement("presolv360_named"), unknown])

    assert portfolio["items"][0]["file_name"] == "mystery.pdf"
    assert portfolio["items"][0]["rating"] is None
    assert portfolio["summary"]["needs_review"] == 1
    assert portfolio["summary"]["unrated"] == 1
    assert portfolio["summary"]["average"] == 5.0


def test_quote_not_in_clause_is_replaced_not_flagged():
    wrong = agreement("unilateral_lender_nominates", deciding_quote="appointed by Presolv360")

    item = build_portfolio([wrong])["items"][0]

    assert item["needs_review"] is False
    assert "Lender" in item["card"]["deciding_quote"]


def test_portfolio_is_marked_for_the_dashboard_view():
    assert build_portfolio([agreement("odr_unnamed")])["kind"] == "portfolio"


def test_empty_list_is_rejected():
    with pytest.raises(ValueError, match="at least one"):
        build_portfolio([])


def test_too_many_agreements_are_rejected():
    with pytest.raises(ValueError, match=str(MAX_AGREEMENTS)):
        build_portfolio([agreement("odr_unnamed")] * (MAX_AGREEMENTS + 1))


def test_only_the_file_name_and_clause_are_required():
    minimal = AgreementInput(file_name="scan.pdf", clause_text=(FIXTURES / "clauses" / "odr_unnamed.txt").read_text())

    item = build_portfolio([minimal])["items"][0]

    assert item["rating"] == 4
    assert item["lender"] == ""
    assert item["who_picks"] == ""


@pytest.mark.parametrize("field", ["lender", "clause_reference", "deciding_quote", "who_picks", "seat_venue", "note"])
def test_null_optional_fields_are_treated_as_empty(field):
    data = {"file_name": "a.pdf", "clause_text": "sole arbitrator nominated by the Lender", field: None}

    assert getattr(AgreementInput(**data), field) == ""


def test_missing_file_name_gets_a_numbered_placeholder():
    nameless = AgreementInput(clause_text="sole arbitrator nominated by the Lender")

    items = build_portfolio([agreement("odr_unnamed"), nameless])["items"]

    assert "Agreement 2" in {i["file_name"] for i in items}


def test_each_item_carries_its_full_report_card_for_the_click_through():
    portfolio = build_portfolio([agreement(i, note="DRT carve-out") for i in AGREEMENT_IDS])

    for item in portfolio["items"]:
        card = item["card"]
        assert card["kind"] == "report_card"
        assert card["rating"] == item["rating"]
        assert card["disclaimer"] == portfolio["disclaimer"]
        assert card["note"] == "DRT carve-out"


def test_dashboard_html_opens_the_full_card_and_has_no_shared_recommendations_panel():
    from dispute_clause_analyzer.report_card import load_card_html

    html = load_card_html()
    assert "function cardBody(" in html
    assert "item.card" in html
    assert "actionsPanel" not in html


def test_opened_dashboard_card_has_no_disclaimer_of_its_own():
    from dispute_clause_analyzer.report_card import load_card_html

    html = load_card_html()
    detail = html[html.index("function portfolioDetail("):html.index("function renderPortfolio(")]
    assert "disclaimer" not in detail
    assert "disclaimerBlock(data.disclaimer)" in html


def test_dashboard_and_text_layout_are_titled_clause_rating_report():
    from dispute_clause_analyzer.report_card import load_card_html
    from dispute_clause_analyzer.rulebook import load_rulebook

    for text in (load_card_html(), load_rulebook().instructions):
        assert "Clause Rating Report" in text
        assert "Portfolio report" not in text


def test_needs_review_tile_only_shows_when_something_needs_checking():
    from dispute_clause_analyzer.report_card import load_card_html

    html = load_card_html()
    summary = html[html.index("function portfolioSummary("):html.index("var bar = el(")]
    assert "all clear" not in summary
    assert 's.needs_review ? metric("Needs review"' in summary


def test_card_shows_progress_while_claude_is_still_writing_the_agreements():
    from dispute_clause_analyzer.report_card import load_card_html

    html = load_card_html()
    handler = html[html.index('window.addEventListener("message"'):html.index("if (window.ResizeObserver)")]
    assert "ui/notifications/tool-input-partial" in handler
    assert "Claude is reading the agreements" in html
    assert "clearTimeout(waitTimer)" in html
