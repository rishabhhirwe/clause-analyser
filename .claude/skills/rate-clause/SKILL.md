---
name: rate-clause
description: Rate the dispute resolution (arbitration) clause of one or more agreements on Presolv360's 5-point scale using the dispute-clause-analyzer tools. Use whenever the user shares an agreement or clause and asks to rate, score, check or review its dispute resolution, arbitration or jurisdiction clause.
model: claude-opus-5-5
---

# Rate a dispute resolution clause

Use the `dispute-clause-analyzer` MCP tools and follow the server's own instructions exactly. In short:

1. Find the dispute resolution clause by meaning, not by heading, and copy it exactly as written.
2. Search the whole agreement for the seat and the place of execution (they count as one item), writing the actual place and where it was found.
3. One agreement: call `rate_clause` with the clause and its short facts. It shows the report card itself, so do not call `show_report_card` afterwards, and never rate the clause yourself.
4. Several agreements: call `show_portfolio` once with all of them, in the order they were shared.
5. Never change the rating the tools return, and never invent numbers if a tool fails.
