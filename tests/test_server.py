"""Server tests: the MCP tools Claude calls, exercised in-process."""
import asyncio
import base64
import json
from pathlib import Path

import pytest
from mcp.server.mcpserver.exceptions import ToolError, UnexpectedToolError

from dispute_clause_analyzer import server as server_module
from dispute_clause_analyzer.server import server

CLAUSES = Path(__file__).parent / "fixtures" / "clauses"


def call(tool: str, arguments: dict) -> dict:
    result = asyncio.run(server.call_tool(tool, arguments))
    assert result.is_error is False, result.content
    return json.loads(result.content[0].text)


def test_server_exposes_the_tools():
    names = {t.name for t in asyncio.run(server.list_tools())}

    assert names == {
        "get_rating_rules", "rate_clause", "get_examples", "suggest_better_clause",
        "show_report_card", "show_portfolio", "reload_report", "download_report_pdf", "save_report_pdf",
        "save_portfolio_pdf", "download_status",
    }


def test_reload_report_is_only_visible_to_the_card_not_to_claude():
    tool = next(t for t in asyncio.run(server.list_tools()) if t.name == "reload_report")

    assert tool.meta["ui"]["visibility"] == ["app"]


def test_reload_report_rebuilds_a_portfolio_from_the_original_arguments():
    clause = (CLAUSES / "unilateral_lender_nominates.txt").read_text()
    original = {"agreements": [{"file_name": "UNILATERAL.pdf", "clause_text": clause}]}

    result = asyncio.run(server.call_tool("reload_report", {"original_arguments": original}))

    assert result.structured_content["kind"] == "portfolio"
    assert result.structured_content["items"][0]["rating"] == 2


def test_reload_report_rebuilds_a_single_card_from_the_original_arguments():
    clause = (CLAUSES / "odr_unnamed.txt").read_text()

    result = asyncio.run(server.call_tool("reload_report", {"original_arguments": {"clause_text": clause}}))

    assert result.structured_content["kind"] == "report_card"
    assert result.structured_content["rating"] == 4


def test_reload_report_rejects_arguments_it_cannot_use():
    assert_clear_tool_error("reload_report", {"original_arguments": {"something": "else"}}, "clause_text")


def test_portfolio_tool_shares_the_card_ui():
    tools = {t.name: t for t in asyncio.run(server.list_tools())}

    assert tools["show_portfolio"].meta["ui"]["resourceUri"] == tools["show_report_card"].meta["ui"]["resourceUri"]


def test_show_portfolio_rates_every_agreement():
    agreements = [
        {"file_name": f"{name}.pdf", "lender": "L", "clause_reference": "Cl. 1",
         "clause_text": (CLAUSES / f"{name}.txt").read_text(), "deciding_quote": "", "who_picks": "x",
         "seat_venue": "y", "note": ""}
        for name in ("unilateral_lender_nominates", "odr_unnamed", "presolv360_named")
    ]

    result = asyncio.run(server.call_tool("show_portfolio", {"agreements": agreements}))

    assert [i["rating"] for i in result.structured_content["items"]] == [2, 4, 5]
    assert result.structured_content["card_shown"] is False


def test_show_portfolio_rejects_empty_list():
    assert_clear_tool_error("show_portfolio", {"agreements": []}, "at least one")


def test_report_card_tool_is_linked_to_the_card_ui():
    tool = next(t for t in asyncio.run(server.list_tools()) if t.name == "show_report_card")
    uri = tool.meta["ui"]["resourceUri"]

    contents = asyncio.run(server.read_resource(uri))

    assert contents[0].mime_type == "text/html;profile=mcp-app"
    assert "ui/initialize" in contents[0].content


def test_show_report_card_returns_card_data_and_says_whether_it_was_shown():
    clause = (CLAUSES / "unilateral_lender_nominates.txt").read_text()
    args = {
        "clause_text": clause,
        "deciding_quote": "nominated/ appointed by the Lender",
        "clause_reference": "Clause 8.1",
        "who_picks": "Lender alone",
        "seat_venue": "Lender decides",
        "online_process": "Not mentioned",
    }

    result = asyncio.run(server.call_tool("show_report_card", args))

    assert result.structured_content["rating"] == 2
    assert result.structured_content["card_shown"] is False


def test_show_report_card_rejects_empty_clause():
    args = {"clause_text": " ", "deciding_quote": "", "clause_reference": "", "who_picks": "",
            "seat_venue": "", "online_process": ""}

    assert_clear_tool_error("show_report_card", args, "empty")


def test_server_instructions_require_the_personal_data_warning():
    assert "personal information" in server.instructions.lower()


def test_rate_clause_returns_rating_reason_and_warning():
    clause = (CLAUSES / "unilateral_lender_nominates.txt").read_text()

    out = call("rate_clause", {"clause_text": clause})

    assert out["rating"] == 2
    assert out["out_of"] == 5
    assert out["type_label"] == "Unilateral"
    assert out["reason"]
    assert "personal information" in out["personal_data_warning"].lower()


def test_rate_clause_flags_when_claude_picked_a_different_type():
    clause = (CLAUSES / "mutual_consent_lender_three_names.txt").read_text()

    out = call("rate_clause", {"clause_text": clause, "claimed_type": "unilateral"})

    assert out["rating"] == 3
    assert out["needs_review"] is True
    assert any("claimed" in r.lower() for r in out["review_reasons"])


def test_rate_clause_flags_quote_not_found_in_clause():
    clause = (CLAUSES / "presolv360_named.txt").read_text()

    out = call("rate_clause", {"clause_text": clause, "deciding_quote": "appointed by the Lender"})

    assert out["needs_review"] is True
    assert any("quote" in r.lower() for r in out["review_reasons"])


@pytest.mark.parametrize("claimed", ["ODR", "odr", "Odr"])
def test_claimed_type_is_matched_regardless_of_case(claimed):
    clause = (CLAUSES / "odr_unnamed.txt").read_text()

    out = call("rate_clause", {"clause_text": clause, "claimed_type": claimed})

    assert out["needs_review"] is False


def test_claimed_type_accepts_the_label_form():
    clause = (CLAUSES / "mutual_consent_scanned.txt").read_text()

    out = call("rate_clause", {"clause_text": clause, "claimed_type": "Mutual consent"})

    assert out["needs_review"] is False


def test_rate_clause_rejects_unknown_claimed_type():
    assert_clear_tool_error("rate_clause", {"clause_text": "text", "claimed_type": "nonsense"}, "Unknown type")


def test_rate_clause_accepts_quote_with_different_spacing():
    clause = (CLAUSES / "presolv360_named.txt").read_text()
    quote = "administered electronically by   Presolv360"

    out = call("rate_clause", {"clause_text": clause, "deciding_quote": quote})

    assert out["needs_review"] is False


def assert_clear_tool_error(tool: str, arguments: dict, expected_text: str) -> None:
    """Bad input must be a deliberate ToolError with a helpful message, never a crash."""
    with pytest.raises(ToolError) as excinfo:
        asyncio.run(server.call_tool(tool, arguments))

    assert not isinstance(excinfo.value, UnexpectedToolError)
    assert expected_text in str(excinfo.value)


def test_rate_clause_rejects_empty_text():
    assert_clear_tool_error("rate_clause", {"clause_text": "   "}, "empty")


def test_rate_clause_rejects_overly_long_text():
    assert_clear_tool_error("rate_clause", {"clause_text": "x" * 20_001}, "longer than")


def test_get_examples_rejects_unknown_type():
    assert_clear_tool_error("get_examples", {"type": "nonsense"}, "Unknown type")


def test_get_rating_rules_lists_scale_and_mixed_rules():
    out = call("get_rating_rules", {})

    assert [t["rating"] for t in out["scale"]] == [5, 4, 3, 3, 2]
    assert len(out["mixed_clause_rules"]) >= 2


def test_get_examples_can_filter_by_type():
    out = call("get_examples", {"type": "odr"})

    assert out["examples"]
    assert all(e["type"] == "odr" or "odr" in e.get("parts", []) for e in out["examples"])


def test_get_examples_by_type_includes_mixed_clauses_with_that_part():
    sources = [e["source"] for e in call("get_examples", {"type": "unilateral"})["examples"]]

    assert any("notwithstanding" in s for s in sources)


def test_suggest_better_clause_gives_next_step_and_top_option():
    out = call("suggest_better_clause", {"current_type": "unilateral"})

    assert out["current_rating"] == 2
    assert out["next_step"]["rating_after"] == 4
    assert out["top_option"]["rating_after"] == 5


def test_suggest_better_clause_accepts_the_label_form():
    out = call("suggest_better_clause", {"current_type": "Mutual consent"})

    assert out["current_type"] == "mutual_consent"
    assert out["current_rating"] == 3


def test_rate_clause_with_unknown_wording_asks_for_review():
    out = call("rate_clause", {"clause_text": "Disputes go to the courts at Pune."})

    assert out["rating"] is None
    assert out["needs_review"] is True
    assert "no wording" in out["reason"].lower()


def test_rate_clause_reports_the_parts_of_a_mixed_clause():
    clause = (CLAUSES / "mixed_unilateral_and_odr.txt").read_text()

    out = call("rate_clause", {"clause_text": clause})

    assert (out["rating"], out["mixed"], out["type"]) == (3, True, "unilateral")
    assert [p["rating"] for p in out["parts"]] == [4, 2]
    assert out["type_label"] == "Mixed: ODR + Unilateral"
    assert "average" in out["reason"]


def test_suggest_better_clause_rejects_unknown_type():
    assert_clear_tool_error("suggest_better_clause", {"current_type": "nonsense"}, "Unknown type")


def test_show_portfolio_accepts_agreements_with_unreadable_details():
    clause = (CLAUSES / "mutual_consent_scanned.txt").read_text()
    agreements = [{"file_name": "Mutual Consent.pdf", "clause_text": clause, "lender": None}]

    result = asyncio.run(server.call_tool("show_portfolio", {"agreements": agreements}))

    assert result.structured_content["items"][0]["rating"] == 3


def test_show_report_card_accepts_just_the_clause():
    clause = (CLAUSES / "unilateral_lender_nominates.txt").read_text()

    result = asyncio.run(server.call_tool("show_report_card", {"clause_text": clause}))

    assert result.structured_content["rating"] == 2
    assert result.structured_content["facts"]["who_picks"] == ""


def test_show_report_card_uses_seat_or_place_of_execution_and_ignores_venue():
    clause = (CLAUSES / "institution_recognised.txt").read_text()
    args = {"clause_text": clause, "seat": "Bangalore", "venue": "Not stated", "place_of_execution": "Bangalore (Exhibit A)"}

    facts = asyncio.run(server.call_tool("show_report_card", args)).structured_content["facts"]

    assert facts["seat"] == "Bangalore"
    assert "venue" not in facts


def test_pdf_tools_exist_and_the_card_one_is_hidden_from_claude():
    tools = {t.name: t for t in asyncio.run(server.list_tools())}

    assert "save_report_pdf" in tools
    assert tools["download_report_pdf"].meta["ui"]["visibility"] == ["app"]


def test_save_report_pdf_writes_the_file_to_the_download_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUSE_ANALYSER_DOWNLOAD_DIR", str(tmp_path))
    clause = (CLAUSES / "unilateral_lender_nominates.txt").read_text()

    out = call("save_report_pdf", {"clause_text": clause, "title": "UNILATERAL.pdf", "seat": "Kolkata"})

    saved = Path(out["saved_to"])
    assert saved.parent == tmp_path
    assert saved.read_bytes().startswith(b"%PDF")
    assert out["rating"] == 2


def test_download_report_pdf_returns_the_file_for_the_card(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUSE_ANALYSER_DOWNLOAD_DIR", str(tmp_path))
    clause = (CLAUSES / "presolv360_named.txt").read_text()

    out = call("download_report_pdf", {"original_arguments": {"clause_text": clause}, "title": "p360.pdf"})

    assert base64.b64decode(out["pdf_base64"]).startswith(b"%PDF")
    assert out["file_name"].endswith(".pdf")
    assert out["mime_type"] == "application/pdf"


def test_download_report_pdf_makes_a_portfolio_pdf_for_the_dashboard(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUSE_ANALYSER_DOWNLOAD_DIR", str(tmp_path))
    original = {"agreements": [
        {"file_name": "UNILATERAL.pdf", "clause_text": (CLAUSES / "unilateral_lender_nominates.txt").read_text()},
        {"file_name": "odr clause.pdf", "clause_text": (CLAUSES / "odr_unnamed.txt").read_text()},
    ]}

    out = call("download_report_pdf", {"original_arguments": original})

    assert base64.b64decode(out["pdf_base64"]).startswith(b"%PDF")
    assert out["file_name"].startswith("Clause-rating-report_2-agreements_")


def test_save_portfolio_pdf_saves_one_file_for_all_agreements(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUSE_ANALYSER_DOWNLOAD_DIR", str(tmp_path))
    agreements = [{"file_name": "p360.pdf", "clause_text": (CLAUSES / "presolv360_named.txt").read_text()},
                  {"file_name": "UNILATERAL.pdf", "clause_text": (CLAUSES / "unilateral_lender_nominates.txt").read_text()}]

    out = call("save_portfolio_pdf", {"agreements": agreements})

    assert Path(out["saved_to"]).read_bytes().startswith(b"%PDF")
    assert out["agreements"] == 2


def test_saving_twice_keeps_both_files(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUSE_ANALYSER_DOWNLOAD_DIR", str(tmp_path))
    args = {"clause_text": (CLAUSES / "odr_unnamed.txt").read_text(), "title": "odr.pdf"}

    first = call("save_report_pdf", args)["saved_to"]
    second = call("save_report_pdf", args)["saved_to"]

    assert first != second
    assert second.endswith("(2).pdf")


def test_card_download_can_also_save_when_asked(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUSE_ANALYSER_DOWNLOAD_DIR", str(tmp_path))
    original = {"clause_text": (CLAUSES / "odr_unnamed.txt").read_text()}

    out = call("download_report_pdf", {"original_arguments": original, "title": "odr.pdf", "save": True})

    assert Path(out["saved_to"]).read_bytes().startswith(b"%PDF")


def test_save_report_pdf_fails_clearly_when_the_folder_cannot_be_written(tmp_path, monkeypatch):
    blocker = tmp_path / "not-a-folder"
    blocker.write_text("x")
    monkeypatch.setenv("CLAUSE_ANALYSER_DOWNLOAD_DIR", str(blocker / "inside"))
    args = {"clause_text": (CLAUSES / "odr_unnamed.txt").read_text()}

    assert_clear_tool_error("save_report_pdf", args, "Could not save the PDF")


def test_download_report_pdf_explains_unreadable_agreements():
    assert_clear_tool_error("download_report_pdf", {"original_arguments": {"agreements": [{"clause_text": ["not", "text"]}]}},
                            "Could not read the agreements")


def test_save_portfolio_pdf_reports_when_it_cannot_save(monkeypatch):
    monkeypatch.setattr(server_module, "_save_pdf", lambda pdf, name: None)
    agreements = [{"clause_text": (CLAUSES / "unilateral_lender_nominates.txt").read_text()}]

    assert_clear_tool_error("save_portfolio_pdf", {"agreements": agreements}, "Could not save the PDF")


def test_download_status_says_whether_the_file_reached_the_download_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUSE_ANALYSER_DOWNLOAD_DIR", str(tmp_path))
    (tmp_path / "Clause-rating-report_X_2026-11-04_12-00.pdf").write_bytes(b"%PDF")

    assert call("download_status", {"file_name": "Clause-rating-report_X_2026-11-04_12-00.pdf"})["found"] is True
    assert call("download_status", {"file_name": "Clause-rating-report_Y_2026-11-04_12-00.pdf"})["found"] is False


def test_download_status_only_looks_inside_the_download_folder(tmp_path, monkeypatch):
    folder = tmp_path / "downloads"
    folder.mkdir()
    (tmp_path / "secret.pdf").write_bytes(b"%PDF")
    monkeypatch.setenv("CLAUSE_ANALYSER_DOWNLOAD_DIR", str(folder))

    assert call("download_status", {"file_name": "../secret.pdf"})["found"] is False
    assert_clear_tool_error("download_status", {"file_name": "notes.txt"}, "PDF")


def test_download_status_is_only_visible_to_the_card():
    tool = next(t for t in asyncio.run(server.list_tools()) if t.name == "download_status")

    assert tool.meta["ui"]["visibility"] == ["app"]


def test_card_checks_the_download_really_happened_and_sends_a_plain_file_name():
    from dispute_clause_analyzer.report_card import load_card_html

    html = load_card_html()
    download = html[html.index("function downloadPdf("):html.index("function pdfButton(")]
    assert "download_status" in html
    assert "cancelled" not in download.lower()
    assert "Checking Downloads" not in download
    assert "encodeURIComponent" not in download
