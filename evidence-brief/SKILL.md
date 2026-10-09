---
name: evidence-brief
description: >
  Builds a ticket's evidence brief: a structured claims.yml (every claim labeled
  VERIFIED / ASSUMED / UNKNOWN with its evidence or the check that would settle it), the saved
  queries behind each number, and a rendered five-tab HTML page (Finance Requirements,
  Acceptance Criteria, Finance Validation, Technical Validation, Context for Agent). Use this
  whenever the user needs to demo or show a change to Finance or another stakeholder, write up
  validation for a PR or ticket, check a ticket's acceptance criteria against data, capture
  business context an AI agent should know, or get stakeholder sign-off on facts, even if they
  do not say "evidence brief". Triggers include "demo page", "validation page", "show Finance",
  "stakeholder review", "AC check", "context for agent", "verify this before I present it",
  "/evidence-brief".
---

# Evidence brief

A brief answers four questions for a ticket: what does the business need, did we meet the
ticket's acceptance criteria, can a stakeholder confirm the numbers, and what must the next
person (or agent) know before touching this area. The output is built so the same material
serves a Finance demo today and an agent's context later.

**The structured file is the product; the HTML is a view of it.** HTML is hard for an agent to
parse and easy to let drift from the data. `claims.yml` is what an agent reads; `render.py`
turns it into the page. Never hand-edit the HTML: change `claims.yml` and re-render.

## Scope

In scope: `claims.yml`, `queries/`, the rendered page. Out of scope for v1, so do not expand
into them: generating `tests/<domain>/validate_*` from acceptance criteria, writing to Jira or
a PR, and contacting stakeholders. Say what you would have done, and stop.

## Output location

Choose the folder in this order: a location the user names; otherwise the folder where they
keep per-ticket notes if one exists (look for a `development/<TICKET>/` or similar convention in
their notes directory); otherwise `./evidence-briefs/<TICKET>/` in the current directory. Say
where you wrote it. Do not ask about this unless two choices are equally plausible.

A folder named for the ticket, containing `claims.yml`, `queries/*.sql` plus
`queries/README.md`, `<ticket>-brief-<YYYY-MM-DD>.html` for people, and a Markdown copy
`<ticket>-brief-<YYYY-MM-DD>.md` for notes systems and agents that read only `.md` files (the
renderer writes both; the Markdown includes the saved SQL in code blocks, since those `.sql`
files are invisible to a notes system). Mention both paths when you report.

## Workflow

1. **Gather sources first, write nothing yet.** The Jira ticket (description, acceptance
   criteria, Validation tables), the PR body and diff stat, the Slack thread if one is linked, and
   any notes or saved queries the user keeps for the ticket. Quote the ticket's acceptance
   criteria verbatim.
2. **Decide the measuring footing before running anything.** Read
   `references/evidence-rules.md` (section "Where numbers come from"). One page must use one
   footing; mixing a lagging dev schema with production produces tables that do not tie.
3. **Get the numbers, reusing what already exists.** Look in the ticket folder for saved queries
   and results first. Reuse a saved result when it exists and is still current, and carry its own
   `measured_at`; do not stamp it with today's date. Run a query yourself (read-only Snowflake is
   fine) when the folder has none or they are stale, and save the SQL to `queries/`. A number you
   did not measure or read from a saved result is ASSUMED or UNKNOWN, not VERIFIED, however sure
   you feel. Facts you looked up (a Slack message, a Jira search, a code read) carry `observed_at`,
   the date the thing was stated or seen, not the day you read it.
4. **Write `claims.yml`** (schema in `references/claims-schema.md`; a small working example is in
   `assets/example/`). Give each claim a status,
   its evidence or the check that would settle it, and an `audience`.
5. **Route claims to tabs with the audience rule** in `references/tab-rules.md`.
6. **Lint and render:** `python <skill>/scripts/render.py <ticket-folder>`. It checks structure and fails when a
   VERIFIED claim has no saved query or dated source, when a number appears in a card, section,
   block or row with no claim behind it, or when a sign-off is filled in without a date. It
   cannot judge whether a claim is true; that is still your job. Fix the claims; do not weaken the check.
7. **Read `references/pitfalls.md` and re-read the page against it** before you present it.
   Those are mistakes already made on this work, each with the reason.
8. **Report briefly:** file path, what is VERIFIED, and the open ASSUMED/UNKNOWN items, led by
   the one most likely to be challenged.

## Migrating an existing page

To bring an old hand-built page into this format, put its prose in `requirements.sections` and
`body_html`, then add the structured claims around it. Treat `body_html` as a migration path: the
page is then only as honest as the text inside it. For a new brief use `table:` and let the claims
supply the status.

## Keep the first screen short

The provenance box and the headline cards are the first thing a reader sees. Give each provenance
item a sentence or two and show at most four or five cards. Put the detail in the claims, where
it is labeled and dated, not in a paragraph at the top. Quote acceptance criteria exactly as the
ticket words them and set `ticket_file` so the linter can check.

## Sign-off is never yours

The Context for Agent tab lists business facts a named stakeholder must confirm. Leave
`signed_off_by` and `signed_off_date` null. An agent treats a fact as authoritative only when
it is VERIFIED *and* signed off. Filling a sign-off in yourself defeats the purpose of the tab.

## Tone

Lead with the conclusion and its label. Name the artifact behind a VERIFIED claim (query file,
test, message). If something is unknown, say so; do not fill it with a plausible guess.
