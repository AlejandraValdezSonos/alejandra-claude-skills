# evidence-brief

Builds an evidence brief for a ticket: a structured `claims.yml` (every claim labeled
VERIFIED / ASSUMED / UNKNOWN, with its evidence or the check that would settle it), the saved
queries behind each number, and a five-tab HTML page you can show a stakeholder:

1. Finance Requirements (business context plus an auto-built Evidence Status table)
2. Acceptance Criteria (the ticket's own wording, each mapped to evidence)
3. Finance Validation (results a stakeholder can read in business terms and confirm)
4. Technical Validation (tests, breaks on purpose, grain checks: judged by an engineer)
5. Context for Agent (facts a stakeholder must confirm, each with who to ask and a sign-off line)

`claims.yml` is the product; the HTML and the Markdown are views of it. An agent should read
`claims.yml`, or the `.md` copy if it can only see Markdown (the notes systems that index only `.md`
files can't read `.yml` or `.html`). A fact is authoritative only when it is VERIFIED **and** signed off.

## Use it

In Claude Code, ask for it in plain words ("build the evidence page for DATA-1234", "I need to
show Finance what changed") or run `/evidence-brief`. The skill gathers the ticket, PR and any
saved notes, runs read-only queries or reuses saved results, writes `claims.yml`, and renders.

Render or lint by hand:

```bash
python3 scripts/render.py path/to/ticket-folder            # lint, then write the HTML and a Markdown copy
python3 scripts/render.py path/to/ticket-folder --lint-only
python3 scripts/render.py path/to/ticket-folder --no-md    # skip the Markdown copy
```

Requires Python 3 and PyYAML (`pip install pyyaml`). Try it on the fictional example:
`python3 scripts/render.py assets/example --out /tmp/example.html`.

## When to run it

Best moment: **after dev validation and before the stakeholder demo or merge**, once the numbers
have settled. Run it again **after deploy** to re-measure on production. You can start the Context
for Agent tab as soon as the ticket is scoped, so stakeholders confirm facts before you build.
Avoid running it while the code is still changing: claims go stale and have to be re-checked.

## What it will not do

- Fill in a stakeholder sign-off. Those stay empty until the person confirms.
- Write to Jira, Slack or GitHub, or contact anyone.
- Generate dbt tests from acceptance criteria (a possible later addition).

## Files

- `SKILL.md`: the workflow the agent follows
- `scripts/render.py`: lint and render. It checks structure (a VERIFIED claim needs a saved
  query or a dated source; a number needs a claim behind it; a sign-off needs a date). It cannot
  tell whether a claim is true.
- `references/`: evidence rules, which tab a claim belongs in, the schema, and the mistakes
  already made (each with the reason)
- `assets/`: page styling, and a small fictional example
