# Dispute Clause Analyzer: instructions for AI agents and developers

## What this project is

An MCP server for Claude (Desktop Chat and Code). It rates the dispute resolution clause of agreements on Presolv360's 5-point scale and shows the result as a visual card, a portfolio dashboard, recommendations and downloadable PDFs.

Claude reads the agreement and finds the clause. This server decides the rating with fixed rules, so the same clause always gets the same rating, on any model.

## The rating scale

| Rating | Type | Who picks the arbitrator |
| --- | --- | --- |
| 5/5 | Presolv360 | Presolv360 is named (alone or among named options) |
| 4/5 | ODR | An online dispute resolution institution, not named |
| 3/5 | Institutional | An unnamed institution |
| 3/5 | Mutual consent | The parties together, including from names the lender proposes |
| 2/5 | Unilateral | The lender alone |

**Mixed clauses.** If a clause has more than one way of picking the arbitrator, the rating is the average of the parts, to one decimal place. For example, Unilateral 2/5 + ODR 4/5 = 3/5, and Unilateral 2/5 + Institutional 3/5 = 2.5/5. A "notwithstanding" part does not override the rest. The recommendation is to keep the clause straightforward and unambiguous. The legal team decided this on 2026-11-03.

## Source of truth

The ratings come from the 10 reference agreements and Presolv360's "Clause Rating_Strength wise" document, not from opinion.

- Never change a rating rule because it seems better. If a change makes any clause in `tests/fixtures/` rate differently from `tests/fixtures/answer_key.json`, the change is wrong, unless the legal team has changed the source.
- The test clauses in `tests/fixtures/clauses/` are made up: they follow the wording of real dispute clauses but name no real lender. Never add real client clauses to the project; keep them in `_session-files/`, which stays out of git.
- Seat and place of execution are the same thing; the venue of hearings is not shown (legal team, 2026-11-03).
- Named institutions other than Presolv360 (MCIA, DIAC, SIAC, CORD, Sama) are not yet covered and come back unrated.

## Where things live

All code is in `src/dispute_clause_analyzer/`.

| File | What it does |
| --- | --- |
| `rules/scale.json` | The five types, their ratings, risk lines, strengths and the wording that signals each type |
| `rules/improvements.json`, `examples.json` | Suggested better wording; the reference clauses |
| `rules/warning.md`, `disclaimer.md` | The personal data warning and the disclaimer shown to users |
| `rules/instructions.md` | How Claude should use the tools (read by Claude at connection) |
| `classifier.py` | Finds every type in the clause text and averages them for a mixed clause |
| `report_card.py` | Builds the single-agreement card, including the mixed-clause parts and the seat / place of execution item |
| `portfolio.py` | Builds the several-agreement dashboard data |
| `pdf_report.py` | Builds the single and bulk PDFs |
| `ui/report-card.html` | The card and dashboard (one self-contained page, no `innerHTML`) |
| `server.py` | The MCP tools |

## How to work on the code

- Write the test first, watch it fail, then make it pass.
- Run `.venv/bin/pytest` before saying a change is done. All tests must pass.
- After any change to the rules, every reference clause must still get its confirmed rating.
- Check card and dashboard changes in the local test page (`.claude/launch.json`, config `card-test`, which serves `_session-files/card-test/`), in light and dark.
- Keep files small and functions short. Do not mutate data in place; return new copies.
- The rating is always recalculated on the server from the clause text. Never take a rating from Claude's own reading.

## Model

The rating is the same on any model. The model only affects how well Claude finds the clause in a long agreement and fills in the facts (who picks the arbitrator, seat / place of execution).

For the best results use Claude Opus 5.5. In Claude Code, start with `/rate-clause` (`.claude/skills/rate-clause/SKILL.md`): it runs the whole job on Opus 5.5 whichever model the session is on. This only works when the command is typed. When Claude starts the skill by itself, the session keeps its own model (tested). In Claude Desktop Chat the user picks the model.

## Privacy

- Never commit client agreements, PDFs, lender names or anything containing personal data. `_session-files/` stays out of git.
- Users are warned to remove personal data before uploading (`rules/warning.md`).
- Do not make the repository public, or share or host the server, without approval from the project owner.

## Working rules

- Use plain, simple wording in anything users see, and no em dashes.
- Only edit documentation when asked.
- Ask before posting to Linear or any other outside service.
- Report outcomes honestly: if a test fails or a check was not run, say so.
