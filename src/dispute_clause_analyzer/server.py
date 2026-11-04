"""MCP server: the tools Claude calls to rate dispute resolution clauses."""
from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

from mcp.server.apps import Apps, ResourcePermissions, client_supports_apps
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from dispute_clause_analyzer.classifier import Classification, classify, quote_found
from dispute_clause_analyzer.pdf_report import build_portfolio_pdf, build_report_pdf, pdf_file_name, portfolio_file_name
from dispute_clause_analyzer.portfolio import AgreementInput, build_portfolio, portfolio_cards
from dispute_clause_analyzer.report_card import CARD_URI, build_report_card, load_card_html, rating_view
from dispute_clause_analyzer.rulebook import RatingType, load_rulebook

MAX_CLAUSE_CHARS = 20_000

RULES = load_rulebook()


def _known_type(name: str) -> RatingType:
    """Look up a type by id or label, turning an unknown name into an error message Claude can act on."""
    try:
        return RULES.type_by_name(name)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc


def _check_clause(clause_text: str) -> None:
    if not clause_text.strip():
        raise ToolError("clause_text is empty. Pass the full dispute resolution clause.")
    if len(clause_text) > MAX_CLAUSE_CHARS:
        raise ToolError(f"clause_text is longer than {MAX_CLAUSE_CHARS} characters. Pass only the dispute clause.")


def _card_can_show(ctx: Context) -> bool:
    """True only inside a live connection whose client renders MCP Apps (e.g. Claude Desktop)."""
    try:
        return client_supports_apps(ctx)
    except ValueError:
        return False


apps = Apps()
apps.add_html_resource(
    CARD_URI,
    load_card_html(),
    name="Clause report card",
    permissions=ResourcePermissions(clipboard_write={}),
    prefers_border=False,
)


CARD_FIELDS = (
    "deciding_quote", "clause_reference", "who_picks", "seat", "venue", "place_of_execution",
    "online_process", "seat_venue",
)


def _text(arguments: dict[str, Any], key: str) -> str:
    value = arguments.get(key)
    return value if isinstance(value, str) else ""


def _card_from(arguments: dict[str, Any]) -> dict[str, Any]:
    """Build a single-agreement card from tool arguments; the rating is always recalculated."""
    clause_text = arguments.get("clause_text")
    if not isinstance(clause_text, str):
        raise ToolError("original_arguments needs either 'agreements' or 'clause_text'.")
    _check_clause(clause_text)
    return build_report_card(clause_text=clause_text, rulebook=RULES, **{k: _text(arguments, k) for k in CARD_FIELDS})


@apps.tool(resource_uri=CARD_URI, structured_output=True)
def show_report_card(
    clause_text: str,
    ctx: Context,
    deciding_quote: str | None = None,
    clause_reference: str | None = None,
    who_picks: str | None = None,
    seat: str | None = None,
    venue: str | None = None,
    place_of_execution: str | None = None,
    online_process: str | None = None,
    seat_venue: str | None = None,
    file_name: str | None = None,
) -> dict[str, Any]:
    """Show the visual Clause Report Card in the chat. Call this last, after rate_clause.

    clause_text: the full dispute resolution clause, exactly as written (the rating is recalculated from it).
    deciding_quote: the sentence that decides who picks the arbitrator, word for word.
    clause_reference: clause number and heading, e.g. "Clause 8.1, Arbitration and Jurisdiction".
    who_picks, online_process: a few words each, e.g. "Lender alone", "Not mentioned".
    seat, place_of_execution: the seat of arbitration and where the agreement was executed (they are the same
    thing). Search the whole agreement (including schedules, exhibits and the opening "made at" line) and give
    each with where you found it, e.g. "Bangalore (Exhibit A)". Leave out anything the agreement does not say.
    The card shows the seat, or the place of execution if no seat is stated. venue is not shown.
    file_name: the agreement's file name, used to name the PDF if the user downloads one.
    Everything except clause_text is optional: leave out anything you cannot read.
    If card_shown is true, do not repeat the card in text; write at most two sentences.
    If card_shown is false, present the result as a text report card instead.
    """
    arguments = {k: v for k, v in locals().items() if k in CARD_FIELDS and v}
    card = _card_from({**arguments, "clause_text": clause_text})
    return {**card, "card_shown": _card_can_show(ctx)}


@apps.tool(resource_uri=CARD_URI, structured_output=True)
def show_portfolio(agreements: list[AgreementInput], ctx: Context) -> dict[str, Any]:
    """Show the visual portfolio dashboard for two or more agreements at once. Use this instead of
    show_report_card whenever the user shares several agreements. Every agreement is rated from the
    rules here, so you do not need to call rate_clause for each one first.

    For each agreement pass the file name, lender, clause reference, the full dispute clause exactly as
    written, the deciding sentence word for word, who picks the arbitrator, the seat and the place of
    execution (a few words each), and an optional one-line note the rating does not show.
    If card_shown is true, do not repeat the dashboard in text; write at most three sentences.
    If card_shown is false, present the result in text instead.
    """
    try:
        portfolio = build_portfolio(agreements, RULES)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc
    return {**portfolio, "card_shown": _card_can_show(ctx)}


@apps.tool(resource_uri=CARD_URI, visibility=["app"], structured_output=True)
def reload_report(original_arguments: dict[str, Any]) -> dict[str, Any]:
    """Rebuild a report card or portfolio from the arguments of the original show_report_card or
    show_portfolio call. Called by the card itself when a chat is reopened after the app restarts."""
    agreements = original_arguments.get("agreements")
    if isinstance(agreements, list):
        try:
            parsed = [AgreementInput(**a) for a in agreements]
            return {**build_portfolio(parsed, RULES), "card_shown": True}
        except (ValueError, TypeError) as exc:
            raise ToolError(f"Could not rebuild the portfolio: {exc}") from exc
    return {**_card_from(original_arguments), "card_shown": True}


def _download_dir() -> Path:
    custom = os.environ.get("CLAUSE_ANALYSER_DOWNLOAD_DIR")
    if custom:
        return Path(custom).expanduser()
    downloads = Path.home() / "Downloads"
    return downloads if downloads.is_dir() else Path.home()


def _save_pdf(pdf: bytes, file_name: str) -> str | None:
    """Save into the download folder without overwriting; returns the path, or None if it cannot be written."""
    folder = _download_dir()
    target = folder / file_name
    copy = 2
    while target.exists():
        target = folder / f"{file_name[:-4]} ({copy}).pdf"
        copy += 1
    try:
        folder.mkdir(parents=True, exist_ok=True)
        target.write_bytes(pdf)
    except OSError:
        return None
    return str(target)


def _portfolio_pdf(agreements: list[AgreementInput], title: str | None) -> tuple[float | None, bytes, str]:
    """A summary page plus one page per agreement, in upload order. Returns the average, the PDF and its file name."""
    try:
        portfolio = build_portfolio(agreements, RULES)
        pdf = build_portfolio_pdf(portfolio, portfolio_cards(agreements, RULES), title=(title or "").strip())
    except ValueError as exc:
        raise ToolError(str(exc)) from exc
    return portfolio["summary"]["average"], pdf, portfolio_file_name(len(agreements))


def _pdf_for(arguments: dict[str, Any], title: str | None) -> tuple[int | float | None, bytes, str]:
    agreements = arguments.get("agreements")
    if isinstance(agreements, list):
        try:
            parsed = [AgreementInput(**a) for a in agreements]
        except (ValueError, TypeError) as exc:
            raise ToolError(f"Could not read the agreements: {exc}") from exc
        return _portfolio_pdf(parsed, title)
    card = _card_from(arguments)
    name = (title or "").strip() or _text(arguments, "clause_reference") or "Clause"
    return card["rating"], build_report_pdf(card, title=name), pdf_file_name(name)


@apps.tool(resource_uri=CARD_URI, visibility=["app"], structured_output=True)
def download_status(file_name: str) -> dict[str, Any]:
    """Whether a downloaded PDF has arrived in the Downloads folder. Called by the card after the app's
    download dialog closes, because the app reports success even when the user clicks Cancel."""
    name = Path(file_name).name
    if not name.lower().endswith(".pdf"):
        raise ToolError("file_name must be the name of a PDF.")
    return {"file_name": name, "found": (_download_dir() / name).is_file()}


@apps.tool(resource_uri=CARD_URI, visibility=["app"], structured_output=True)
def download_report_pdf(original_arguments: dict[str, Any], title: str | None = None, save: bool = False) -> dict[str, Any]:
    """Make a PDF for the Download PDF button: one agreement's card, or (for show_portfolio arguments) a
    summary page plus one page per agreement. With save=True it is also saved to the Downloads folder
    (used when the app cannot hand the file to the user directly)."""
    rating, pdf, name = _pdf_for(original_arguments, title)
    return {
        "file_name": name,
        "mime_type": "application/pdf",
        "pdf_base64": base64.b64encode(pdf).decode("ascii"),
        "saved_to": _save_pdf(pdf, name) if save else None,
        "rating": rating,
    }


server = MCPServer(
    name="Dispute Clause Analyzer",
    instructions=f"{RULES.instructions}\n\nPersonal information warning to show the user:\n{RULES.warning}",
    version="0.3.0",
    extensions=[apps],
)


def _review_reasons(result: Classification, text: str, claimed: RatingType | None, quote: str | None) -> list[str]:
    reasons = list(result.review_reasons)
    if claimed and result.type and claimed.id not in result.detected_types:
        reasons.append(f"Claude claimed '{claimed.id}' but the wording matches '{result.type}'. Check the deciding sentence.")
    if quote and not quote_found(quote, text):
        reasons.append("The deciding quote was not found word for word in the clause text.")
    return reasons


def _reason(result: Classification) -> str:
    if result.type is None:
        return "No wording from the rating scale was found in this clause."
    if result.mixed:
        parts = " and ".join(f"{p['label']} ({p['rating']}/5)" for p in rating_view(RULES, result)["parts"])
        return f"The clause has more than one way of picking the arbitrator: {parts}. The rating is the average, {result.rating}/5."
    rating_type = RULES.type_by_name(result.type)
    return f"{rating_type.label} ({rating_type.rating}/5): {rating_type.meaning}"


@server.tool()
def get_rating_rules() -> dict[str, Any]:
    """Get Presolv360's rating scale for dispute resolution clauses, the rules for mixed clauses,
    and the personal information warning. Call this before rating a clause."""
    return {
        "version": RULES.version,
        "scale": [{"type": t.id, "label": t.label, "rating": t.rating, "meaning": t.meaning} for t in RULES.types],
        "mixed_clause_rules": list(RULES.mixed_clause_rules),
        "personal_data_warning": RULES.warning,
    }


@server.tool()
def rate_clause(clause_text: str, claimed_type: str | None = None, deciding_quote: str | None = None) -> dict[str, Any]:
    """Rate a dispute resolution clause out of 5.

    clause_text: the full dispute resolution clause, copied exactly as written, including all sub-parts.
    claimed_type: the type you believe it is (presolv360, odr, institutional, mutual_consent, unilateral).
    For a clause with more than one way of picking the arbitrator, give the weakest one.
    deciding_quote: the sentence that decides who picks the arbitrator, copied word for word.
    If mixed is true, the rating is the average of parts and type is the weakest part (pass it to
    suggest_better_clause).
    """
    _check_clause(clause_text)
    claimed = _known_type(claimed_type) if claimed_type else None
    result = classify(clause_text, RULES)
    reasons = _review_reasons(result, clause_text, claimed, deciding_quote)
    view = rating_view(RULES, result)
    return {
        "rating": result.rating,
        "out_of": 5,
        "type": result.type,
        "type_label": view["label"] if result.type else None,
        "mixed": result.mixed,
        "parts": view["parts"],
        "reason": _reason(result),
        "matched_wording": list(result.matched_phrases),
        "needs_review": bool(reasons),
        "review_reasons": reasons,
        "personal_data_warning": RULES.warning,
    }


@server.tool()
def get_examples(type: str | None = None) -> dict[str, Any]:
    """Get reference clauses with confirmed ratings, optionally filtered by type
    (presolv360, odr, institutional, mutual_consent, unilateral). Mixed clauses are listed under each of their parts."""
    wanted = _known_type(type).id if type is not None else None
    examples = [dict(e) for e in RULES.examples if wanted is None or wanted in (e["type"], *e.get("parts", ()))]
    return {"examples": examples}


@server.tool()
def suggest_better_clause(current_type: str) -> dict[str, Any]:
    """Get the smallest change that moves a clause up the scale, plus the wording that reaches 5/5.
    current_type is the type returned by rate_clause."""
    rating_type = _known_type(current_type)
    improvement = RULES.improvements[rating_type.id]
    return {
        "current_type": rating_type.id,
        "current_rating": rating_type.rating,
        "next_step": dict(improvement["next_step"]),
        "top_option": dict(improvement["top_option"]),
        "note": "Suggestions are neutral. Bracketed institution names are placeholders for the parties to choose.",
    }


@server.tool()
def save_report_pdf(
    clause_text: str,
    title: str | None = None,
    deciding_quote: str | None = None,
    clause_reference: str | None = None,
    who_picks: str | None = None,
    seat: str | None = None,
    venue: str | None = None,
    place_of_execution: str | None = None,
    online_process: str | None = None,
) -> dict[str, Any]:
    """Save a PDF of the report card for one agreement to the user's Downloads folder. Use this when the
    user asks for a PDF. Pass the same details you passed to show_report_card; title is usually the file name."""
    arguments = {k: v for k, v in locals().items() if k in CARD_FIELDS and v}
    rating, pdf, name = _pdf_for({**arguments, "clause_text": clause_text}, title)
    saved = _saved_or_error(pdf, name)
    return {"saved_to": saved, "file_name": Path(saved).name, "rating": rating}


@server.tool()
def save_portfolio_pdf(agreements: list[AgreementInput], title: str | None = None) -> dict[str, Any]:
    """Save one PDF covering several agreements to the user's Downloads folder: a summary page, then one
    page per agreement, in the order they were uploaded. Use this when the user asks for a PDF of a bulk
    upload. Pass the same agreements you passed to show_portfolio, in the same order."""
    average, pdf, name = _portfolio_pdf(agreements, title)
    saved = _saved_or_error(pdf, name)
    return {"saved_to": saved, "file_name": Path(saved).name, "agreements": len(agreements), "average": average}


def _saved_or_error(pdf: bytes, name: str) -> str:
    saved = _save_pdf(pdf, name)
    if saved is None:
        raise ToolError(f"Could not save the PDF to {_download_dir()}.")
    return saved


def main() -> None:
    server.run()


if __name__ == "__main__":
    main()
