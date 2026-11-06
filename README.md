# Dispute Clause Analyzer

An MCP server that lets Claude rate the dispute resolution clause of a contract on Presolv360's 5-point scale.

| Rating | Type | Who picks the arbitrator |
| --- | --- | --- |
| 5/5 | Presolv360 | Presolv360 is named as the institution (alone or among named options) |
| 4/5 | ODR | An online dispute resolution institution, not named in the contract |
| 3/5 | Institutional | An unnamed institution ("a recognised independent institution") |
| 3/5 | Mutual consent | The parties together, including from names proposed by the lender |
| 2/5 | Unilateral | The lender alone |

**Mixed clauses.** If a clause has more than one way of picking the arbitrator, the rating is the average of the parts, to one decimal place. For example, Unilateral 2/5 + ODR 4/5 = 3/5, and Unilateral 2/5 + Institutional 3/5 = 2.5/5. A "notwithstanding" part does not override the rest. The recommendation is to keep the clause straightforward and unambiguous. The legal team decided this on 2026-11-03.

Claude reads the contract and finds the clause; this server decides the rating with fixed rules, so the same clause always gets the same rating.

## What users see

- **Report card** for one agreement: a rating badge, a one-line risk reason, key facts (clause, who picks the arbitrator, seat / place of execution, online process), the line that decides the rating, key takeaways for good ratings, a recommendation with suggested wording, and the disclaimer. Seat and place of execution count as the same thing and are shown as one item: the seat if stated, otherwise the place of execution. The venue of hearings is not shown. A mixed clause shows each part's rating under the average.
- **Dashboard** for several agreements: average rating, how many got each rating, filters, expandable rows and a Recommendations panel.
- **PDFs:** a Download PDF button on the card and on the dashboard. One agreement gives a one-page report. Several agreements give one PDF with a summary page, then one page per agreement in upload order. In chat, Claude can also save the PDF to your Downloads folder.
- If the app cannot show the card, Claude writes the same report as text.

## Tools

| Tool | What it does |
| --- | --- |
| `get_rating_rules` | The scale, the rules for mixed clauses, and the personal information warning |
| `rate_clause` | Rates a clause and double-checks Claude's reading of it |
| `get_examples` | Reference clauses with confirmed ratings |
| `suggest_better_clause` | The smallest change that moves the clause up the scale, plus the 5/5 option |
| `show_report_card` | Shows the visual report card for one agreement |
| `show_portfolio` | Shows the dashboard for several agreements (up to 50) |
| `save_report_pdf` | Saves a PDF for one agreement to Downloads |
| `save_portfolio_pdf` | Saves one PDF for several agreements to Downloads |

The card and dashboard also use a few app-only tools (`reload_report`, `download_report_pdf`) that Claude does not call.

## Which Claude model to use

The rating itself comes from the rules in this server, so it is the same on any model. The model only affects how well Claude finds the clause in a long agreement and fills in the facts (who picks the arbitrator, seat / place of execution).

For the best results use Claude Opus 5.5. In Claude Code, start with `/rate-clause` (for example `/rate-clause` followed by the agreement): it runs the whole job on Opus 5.5 whichever model the session is on. Without the command, the session keeps whatever model is selected. In Claude Desktop Chat, pick Opus 5.5 from the model menu yourself.

## Editing the rules

The rules are plain files in `src/dispute_clause_analyzer/rules/`:

- `scale.json`: the five types, their ratings, and the wording that signals each one
- `improvements.json`: suggested better wording for each type
- `examples.json`: reference clauses with confirmed ratings
- `warning.md`: the personal information warning shown to users
- `disclaimer.md`: the disclaimer shown on every card and PDF
- `instructions.md`: how Claude should use the tools

After any change, run the tests (about 195, all must pass). Every reference clause in `tests/fixtures/` must still get its confirmed rating (`tests/fixtures/answer_key.json`).

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

The server command is `.venv/bin/dispute-clause-analyzer` (it talks to Claude over stdio). To add it to Claude Desktop, point `mcpServers` in `claude_desktop_config.json` at that command and restart the app. PDFs need `reportlab`, which is installed with the package.

For people working on the code, see `AGENTS.md`.

## Use it online

The connector can also run online, so it works on claude.ai and in the Claude apps without installing anything. Add it once in Claude: **Settings > Connectors > Add custom connector**, and paste the connector's address followed by `/mcp`.

To host it, deploy this repository on Render with `render.yaml` (it builds the `Dockerfile`), then set `PUBLIC_HOST` to the address Render gives. Online, PDFs come from the Download PDF button on the card or dashboard; the tools that save to a Downloads folder are only available when the connector runs on the user's own computer.

## Privacy Policy

- **What is collected:** only what Claude sends to the connector to answer a request: the text of the dispute resolution clause and short details such as the clause reference and seat.
- **How it is used:** solely to calculate the rating and build the report card or PDF for that request.
- **Storage and retention:** clause text and reports are not stored, logged or kept after the request is answered. The online server keeps only basic technical logs (time, address and status of each request) for security, and no clause content.
- **Sharing:** nothing is sold or shared with third parties. The online version runs on Render, which hosts the server.
- **When it runs on your computer** (desktop extension), nothing is sent to us at all.
- **Personal data:** please remove names, phone numbers and other personal details from agreements before uploading.
- **Contact:** privacy questions can be sent to Presolv360 at [CONTACT EMAIL TO BE CONFIRMED].

## Source of truth

The ratings come from Presolv360's "Clause Rating_Strength wise" document and the 10 reference agreements. This tool gives a first review, not legal advice.

## Licence

Released under the MIT licence (see `LICENSE`). Copyright (c) 2026 Presolv360.

The licence covers the code only. The Presolv360 name and logo are not licensed: a copy or changed version must not be presented as an official Presolv360 product.
