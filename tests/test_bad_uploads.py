"""Fail-safes for documents that cannot be rated: no dispute clause, or a file Claude cannot read."""
from pathlib import Path

from dispute_clause_analyzer.portfolio import AgreementInput, build_portfolio
from dispute_clause_analyzer.rulebook import load_rulebook

CLAUSES = Path(__file__).parent / "fixtures" / "clauses"
GOOD = (CLAUSES / "unilateral_lender_nominates.txt").read_text(encoding="utf-8")


def test_a_bad_file_in_a_bulk_upload_becomes_a_not_rated_row_with_its_reason():
    portfolio = build_portfolio([
        AgreementInput(file_name="good.pdf", clause_text=GOOD),
        AgreementInput(file_name="resume.pdf", problem="No dispute clause found"),
        AgreementInput(file_name="locked.pdf", problem="File could not be read"),
    ])
    items = {i["file_name"]: i for i in portfolio["items"]}

    assert items["good.pdf"]["rating"] == 2
    for name, reason in (("resume.pdf", "No dispute clause found"), ("locked.pdf", "File could not be read")):
        assert items[name]["rating"] is None
        assert items[name]["label"] == "Not rated"
        assert items[name]["review_reasons"] == [reason]
        assert items[name]["card"]["review_reasons"] == [reason]
    assert portfolio["summary"]["needs_review"] == 2
    assert portfolio["summary"]["average"] == 2


def test_clause_text_may_be_left_out_for_a_bad_file():
    assert AgreementInput(file_name="x.pdf", problem="File could not be read").clause_text == ""


def test_instructions_say_what_to_do_with_bad_documents():
    text = load_rulebook().instructions

    assert "couldn't find a dispute resolution" in text
    assert "couldn't read this file" in text
    assert "`problem`" in text
    assert "scanned" not in text.lower() or "scanned pages are fine" in text.lower()


def test_nothing_says_the_tool_is_only_for_loan_agreements():
    root = Path(__file__).parents[1]
    for path in ("AGENTS.md", "README.md", ".claude/skills/rate-clause/SKILL.md"):
        assert "loan agreements" not in (root / path).read_text(encoding="utf-8"), path
