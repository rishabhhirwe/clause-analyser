"""Builds downloadable PDFs: one agreement's report card, or a portfolio of several agreements."""
from __future__ import annotations

import datetime as dt
import io
import re
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import ListFlowable, ListItem, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from dispute_clause_analyzer.pdf_gauge import gauge

TONE_COLOURS = {
    "green": ("#1d7a46", "#e6f4ea"),
    "yellow": ("#8a6100", "#fdf5d9"),
    "orange": ("#b54708", "#fff1e3"),
    "red": ("#b42318", "#fdecea"),
    "gray": ("#5f5e5a", "#efeeea"),
}
FACT_LABELS = (
    ("clause_reference", "Clause"),
    ("who_picks", "Arbitrator to be appointed by"),
    ("seat", "Seat / place of execution"),
    ("online_process", "Online process"),
)
# Standard PDF fonts cannot draw these characters, so they are swapped for plain equivalents.
REPLACEMENTS = {"→": "->", "←": "<-", "⚠️": "", "⚠": "", "‑": "-", "−": "-"}
OUT_OF = 5
REPORT_TITLE = "Clause Rating Report"
# File names have no spaces: Claude Desktop saves a downloaded file under its name with spaces turned
# into "%20", so "Clause rating report.pdf" would arrive as "Clause%20rating%20report.pdf".
FILE_PREFIX = "Clause-rating-report"


def _stamp() -> str:
    """Date and time for file names, e.g. '2026-11-03_17-19'."""
    return dt.datetime.now().strftime("%Y-%m-%d_%H-%M")


def pdf_file_name(title: str, date: str | None = None) -> str:
    """A safe file name with the date and time, such as 'Clause-rating-report_UNILATERAL_2026-11-02_17-19.pdf'."""
    day = date or _stamp()
    stem = re.sub(r"\.pdf$", "", title.strip(), flags=re.IGNORECASE)
    stem = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-")[:60].strip("-")
    return f"{FILE_PREFIX}_{stem}_{day}.pdf" if stem else f"{FILE_PREFIX}_{day}.pdf"


def portfolio_file_name(count: int, date: str | None = None) -> str:
    """For example 'Clause-rating-report_10-agreements_2026-11-02_17-19.pdf'."""
    day = date or _stamp()
    return f"{FILE_PREFIX}_{count}-agreement{'' if count == 1 else 's'}_{day}.pdf"


def _safe(text: Any) -> str:
    value = str(text or "")
    for old, new in REPLACEMENTS.items():
        value = value.replace(old, new)
    return escape(value)


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=base["BodyText"], fontName="Times-Roman", fontSize=10, leading=14, alignment=TA_LEFT)
    return {
        "title": ParagraphStyle("title", parent=body, fontName="Times-Bold", fontSize=16, leading=20),
        "sub": ParagraphStyle("sub", parent=body, textColor=colors.HexColor("#6b6a65"), fontSize=9),
        "label": ParagraphStyle("label", parent=body, fontName="Times-Bold", fontSize=14, leading=18),
        "section": ParagraphStyle("section", parent=body, fontName="Times-Bold", fontSize=11, spaceBefore=10, spaceAfter=4),
        "body": body,
        "quote": ParagraphStyle("quote", parent=body, fontName="Times-Roman", fontSize=11, leading=15, leftIndent=8),
        "muted": ParagraphStyle("muted", parent=body, textColor=colors.HexColor("#6b6a65"), fontSize=9, leading=12),
        "small": ParagraphStyle("small", parent=body, fontSize=8, leading=11, textColor=colors.HexColor("#4a4945")),
    }


def _tone_colour(tone: str | None) -> str:
    return TONE_COLOURS.get(tone or "gray", TONE_COLOURS["gray"])[0]


def _rating_block(card: dict[str, Any], st: dict[str, ParagraphStyle]) -> Table:
    """The gauge (as on the card, no box) next to the clause type."""
    fg = _tone_colour(card.get("tone"))
    dial = gauge(card.get("rating"), OUT_OF, fg, width=32 * mm)
    text = [Paragraph(f'<font color="{fg}">{_safe(card.get("label"))}</font>', st["label"])]
    text.append(Paragraph(_safe(card.get("parts_line") or "Dispute resolution clause type"), st["muted"]))
    table = Table([[dial, text]], colWidths=[36 * mm, None])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, 0), 0),
        ("LEFTPADDING", (1, 0), (1, 0), 8),
    ]))
    return table


def _facts_table(card: dict[str, Any], st: dict[str, ParagraphStyle]) -> Table:
    facts = card.get("facts") or {}
    pairs = [(r["label"], r["value"]) for r in card.get("fact_rows") or []] or [
        (label, facts.get(key) or "Not stated") for key, label in FACT_LABELS]
    rows = [[Paragraph(f"<b>{_safe(label)}</b>", st["body"]), Paragraph(_safe(value), st["body"])] for label, value in pairs]
    table = Table(rows, colWidths=[64 * mm, None])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d8d6cf")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f6f5f1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return table


def _bullets(items: list[str], st: dict[str, ParagraphStyle]) -> ListFlowable:
    return ListFlowable([ListItem(Paragraph(_safe(i), st["body"]), leftIndent=10) for i in items],
                        bulletType="bullet", start="-", leftIndent=10, bulletFontName="Times-Roman")


def _recommendation(card: dict[str, Any], st: dict[str, ParagraphStyle]) -> list[Any]:
    parts: list[Any] = [Paragraph("Recommendation", st["section"])]
    for step in card.get("path") or []:
        parts.append(Paragraph(f"<b>{_safe(step['label'])} (to {step['rating_after']}/5):</b> {_safe(step['change'])}", st["body"]))
        if step.get("wording"):
            parts.append(Paragraph(f"Suggested wording: {_safe(step['wording'])}", st["quote"]))
        parts.append(Spacer(1, 4))
    return parts


def _card_body(card: dict[str, Any], st: dict[str, ParagraphStyle]) -> list[Any]:
    """Everything on a card from the rating down, without the page title or the disclaimer."""
    story: list[Any] = [_rating_block(card, st)]
    if card.get("risk"):
        story += [Paragraph("Risk", st["section"]), Paragraph(_safe(card["risk"]), st["body"])]
    if card.get("strengths"):
        story += [Paragraph("Key takeaways", st["section"]), _bullets(card["strengths"], st)]
    if card.get("needs_review"):
        story += [Paragraph("Needs human review", st["section"]), _bullets(card.get("review_reasons") or [], st)]
    story += [Paragraph("Key facts", st["section"]), _facts_table(card, st)]
    lines = card.get("deciding_lines") or ([card["deciding_quote"]] if card.get("deciding_quote") else [])
    if lines:
        heading = "The line that decides it" if len(lines) == 1 else "The lines that decide it"
        story += [Paragraph(heading, st["section"])] + [Paragraph(f"&ldquo;{_safe(line)}&rdquo;", st["quote"]) for line in lines]
    if card.get("path"):
        story += _recommendation(card, st)
    if card.get("also"):
        story += [Paragraph("Also tidy up", st["section"]), _bullets(card["also"], st)]
    return story


def _disclaimer(text: str, st: dict[str, ParagraphStyle]) -> list[Any]:
    return [Spacer(1, 14), Paragraph(_safe(text), st["small"])] if text else []


def _header(heading: str, subtitle: str, st: dict[str, ParagraphStyle]) -> list[Any]:
    today = dt.date.today().strftime("%d %b %Y")
    sub = f"{_safe(subtitle)} &nbsp;&middot;&nbsp; {today}" if subtitle else today
    return [Paragraph(_safe(heading), st["title"]), Paragraph(sub, st["sub"]), Spacer(1, 8)]


def _content(card: dict[str, Any], title: str, st: dict[str, ParagraphStyle]) -> list[Any]:
    return _header(REPORT_TITLE, title, st) + _card_body(card, st) + _disclaimer(card.get("disclaimer", ""), st)


def _cell(text: Any, st: dict[str, ParagraphStyle], style: str = "body") -> Paragraph:
    return Paragraph(_safe(text), st[style])


def _summary_table(items: list[dict[str, Any]], st: dict[str, ParagraphStyle]) -> Table:
    rows: list[list[Any]] = [[Paragraph(f"<b>{h}</b>", st["body"]) for h in ("#", "Agreement", "Rating", "Type", "Appointed by")]]
    for item in items:
        name = item["file_name"] + (f" ({item['lender']})" if item.get("lender") else "")
        rows.append([
            _cell(item["position"], st), _cell(name, st),
            gauge(item.get("rating"), OUT_OF, _tone_colour(item.get("tone")), width=14 * mm, caption=False),
            _cell(item.get("label"), st), _cell(item.get("who_picks") or "Not stated", st),
        ])
    table = Table(rows, colWidths=[9 * mm, 56 * mm, 18 * mm, 32 * mm, None], repeatRows=1)
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d8d6cf")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f6f5f1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return table


def _metrics(summary: dict[str, Any], st: dict[str, ParagraphStyle]) -> list[Any]:
    average = "-" if summary.get("average") is None else f"{summary['average']} out of {OUT_OF}"
    spread = " &nbsp;&middot;&nbsp; ".join(f"{n} at {r}/5" for r, n in summary.get("distribution", {}).items() if n)
    lines = [f"<b>Agreements:</b> {summary['total']}", f"<b>Average rating:</b> {average}"]
    if spread:
        lines.append(f"<b>Ratings:</b> {spread}")
    if summary.get("unrated"):
        lines.append(f"<b>Not rated:</b> {summary['unrated']}")
    if summary.get("needs_review"):
        lines.append(f"<b>Need human review:</b> {summary['needs_review']}")
    return [Paragraph(line, st["body"]) for line in lines]


def _summary_page(portfolio: dict[str, Any], items: list[dict[str, Any]], title: str, st: dict[str, ParagraphStyle]) -> list[Any]:
    summary = portfolio["summary"]
    return (
        _header(REPORT_TITLE, title, st)
        + _metrics(summary, st)
        + [Paragraph("Agreements", st["section"]), _summary_table(items, st)]
    )


def _agreement_page(item: dict[str, Any], card: dict[str, Any], total: int, st: dict[str, ParagraphStyle]) -> list[Any]:
    heading = f"Agreement {item['position']} of {total}: {item['file_name']}"
    detail = " &nbsp;&middot;&nbsp; ".join(_safe(v) for v in (item.get("lender"), item.get("clause_reference")) if v)
    story: list[Any] = [Paragraph(_safe(heading), st["label"])]
    if detail:
        story.append(Paragraph(detail, st["sub"]))
    if item.get("note"):
        story.append(Paragraph(f"Note: {_safe(item['note'])}", st["muted"]))
    return story + [Spacer(1, 8)] + _card_body(card, st)


def _document(buffer: io.BytesIO, title: str, compress: bool) -> SimpleDocTemplate:
    return SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
        title=title, author="Clause Analyser", pageCompression=1 if compress else 0, initialFontName="Times-Roman",
    )


def build_report_pdf(card: dict[str, Any] | None, title: str, compress: bool = True) -> bytes:
    """Render a single-agreement card as PDF bytes. Raises ValueError for anything that is not a single card."""
    if not isinstance(card, dict) or card.get("kind") != "report_card":
        raise ValueError("A PDF can only be made from a single-agreement report card.")
    buffer = io.BytesIO()
    _document(buffer, f"{REPORT_TITLE} - {title}", compress).build(_content(card, title, _styles()))
    return buffer.getvalue()


def build_portfolio_pdf(portfolio: dict[str, Any], cards: list[dict[str, Any]], title: str = "", compress: bool = True) -> bytes:
    """Render a summary page, then one page per agreement, all in upload order, then the disclaimer once.

    portfolio is the dashboard data from build_portfolio; cards are the matching report cards from
    portfolio_cards, in upload order.
    """
    if not isinstance(portfolio, dict) or portfolio.get("kind") != "portfolio":
        raise ValueError("A portfolio PDF needs the data from build_portfolio.")
    items = sorted(portfolio["items"], key=lambda i: i["position"])
    if len(items) != len(cards):
        raise ValueError("Each agreement in the portfolio needs its report card.")
    st = _styles()
    story = _summary_page(portfolio, items, title, st)
    for item, card in zip(items, cards):
        story += [PageBreak()] + _agreement_page(item, card, len(items), st)
    story += _disclaimer(portfolio.get("disclaimer", ""), st)
    buffer = io.BytesIO()
    _document(buffer, REPORT_TITLE, compress).build(story)
    return buffer.getvalue()
