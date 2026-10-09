# claims.yml schema

All dates ISO (`2026-10-08`). Unknown keys are an error: the renderer is strict so typos do
not silently drop evidence.

```yaml
ticket: DATA-12345
title: Add a region column to the sales view
pr: "#1637"                    # optional
author: Your Name
as_of: 2026-10-08              # the date the numbers were measured
scope: "Audio HW, channel rows, FY25 Q1 - FY26 Q4"
ticket_file: ticket.md        # optional: the saved ticket text; acceptance criteria are checked against it, verbatim                    # renders the internal-draft banner

provenance:                    # what each set of numbers came from; must be literally true. One or two
                               # sentences per item (the linter warns past 350 characters)
  - label: "Finance Validation"
    text: "The PR's SQL compiled and run over production tables on 2026-10-08."
  - label: "Technical Validation"
    text: "Tests run in the author's dev build, which lagged production by about three days."

cards:                         # optional headline numbers on the first tab
  - {num: "63,877", label: "units with no usable F3", claim: c-gap}

requirements:                  # free-form business context for the first tab
  sections:
    - title: "The problem"
      html: "<p>...</p>"
      claims: [c-gap]            # required when the html shows a number (three digits or more)

claims:                        # every actionable statement, one place each
  - id: c-gap
    text: "FY25 Q1 gap is 63,877 sales units."
    status: VERIFIED           # VERIFIED | ASSUMED | UNKNOWN
    audience: finance          # finance | engineering | both
    evidence: "Gap query, new logic over production"      # required for VERIFIED
    source_query: queries/qa_quarter.sql                  # required for VERIFIED unless source is set
    source: null               # alternative to source_query: code | slack_message | jira_search | test_run
    source_ref: null           # what exactly (message date, test name) when source is set
    measured_at: 2026-10-08    # required when the source is a query or a test_run: the day it was run
    observed_at: null          # required when the source is code, slack_message or jira_search: the day
                               # it was stated or seen (a message's own date), not the day you read it
    footing: compiled_pr_over_prod   # prod | compiled_pr_over_prod | dev | n/a
    check: null                # required for ASSUMED and UNKNOWN: the specific check that settles it

acceptance_criteria:           # quoted from the ticket, verbatim
  - id: ac-1
    text: "Every column that exists today has an identical value for every row."
    result_html: "A hash over all 40 existing columns is identical (118,397,371 rows)."
    claims: [c-hash]           # status of the row = weakest linked claim

expected_results:              # the ticket's own "Expected Results" table, one row per check
  - check: "Total units, FY25 Q1"
    expected: "1,755,021, unchanged"
    measured_html: "1,755,027 today; the model does not change it."
    claims: [c-gap]            # required; row status = weakest linked claim

regression_checks:             # the ticket's own "Regression check" table, same shape
  - {check: "Row count", expected: "match production exactly", measured_html: "118,397,371 on both sides", claims: [c-hash]}

finance_validation:            # blocks of results a stakeholder can confirm
  intro_html: "<p>...</p>"
  blocks:
    - title: "Q1: The FY25 Q1 gap"
      measured_at: 2026-10-08
      query_file: queries/qd_total.sql   # shown collapsed under the block
      claims: [c-gap]            # their statuses decide the block's label; audience must fit the tab
      intro_html: "<p>optional</p>"   # shown above the table
      after_html: "<p>optional</p>"   # shown below the table
      table:
        columns: [Measure, Units]
        rows: [["Gap", "63,877"]]
        row_status: [VERIFIED]    # optional: colors each row green / amber / red

technical_validation:          # same shape as finance_validation
  intro_html: "<p>...</p>"
  blocks: []

context:                       # facts a stakeholder must confirm; the skill never signs these
  - id: x-1
    fact: "Units here are sales units, not Dollarized Demand units."
    why: "A figure quoted as DD units sends Finance to the wrong model."
    claim: c-units             # its evidence lives in a claim
    question: "Is the 63,877 a sales-unit gap?"
    who: ["Finance lead"]     # a string, or a list: the sign-off record is grouped per person
    signed_off_by: null        # must be present; null until the stakeholder confirms
    signed_off_date: null      # required whenever signed_off_by is set
```

## How an agent reads it

A fact is **authoritative** only when its claim is VERIFIED *and* `signed_off_by` is set.
VERIFIED but unsigned is "supported by data, not agreed by the business". ASSUMED and UNKNOWN
are open questions: say so rather than guess.

## What the renderer enforces

- VERIFIED needs `evidence`, and either an existing `source_query` file (plus `measured_at`) or a
  `source` plus `source_ref`. A `test_run` needs `measured_at`; `code`, `slack_message` and
  `jira_search` need `observed_at`.
- ASSUMED and UNKNOWN need `check`.
- Any card, requirements section, validation block, expected/regression row or context fact that
  shows a number (a thousands separator, or four or more digits) needs a `claims` link (or, for a
  block, a `query_file`). The renderer checks structure only; it cannot tell whether a claim is
  true.
- A claim placed in a block on the wrong side of its `audience` (finance claim in Technical, or
  engineering claim in Finance) gets a warning; `both` fits either.
- `signed_off_by` set without `signed_off_date` is an error; both keys must be present.
- Every claim must appear in the Evidence Status table (generated automatically), and a claim
  referenced nowhere gets a warning.

## Fields that exist mainly for migrating an existing page

- `body_html` on a validation block: raw HTML in place of `table:`. Use it only to migrate a page
  that already exists. New briefs should use `table:` (+ `row_status`), so the status shown comes
  from the claims and not from text typed into HTML. Inline status spans copied inside a
  `body_html` are not checked against the claims and can disagree with them.
- `acceptance_extra_html` (top level): raw HTML shown after the Acceptance Criteria tables, for the
  ticket's "out of scope" and "not covered" lists. It is not number-linted.
- `context_note_html` (top level): a note shown at the bottom of the Context for Agent tab.

## Headings show how claims split

A block or requirements section that links claims with different statuses shows a count per
status (for example VERIFIED×3 UNKNOWN×1), not only the weakest one. An acceptance row, which is a
single yes/no, still takes the weakest linked claim.
