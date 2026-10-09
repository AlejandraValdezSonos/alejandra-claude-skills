# Evidence rules

## The three labels

- **VERIFIED**: checked against data, code, or a primary source (a test result, a query, a
  message). Requires the artifact, the date measured, and the footing. "I read it and it looks
  right" is not evidence.
- **ASSUMED**: believed true, not checked. Requires the specific check that would verify it, not
  "needs verification". Example: "compare the workbook's cut date with the snapshot date".
- **UNKNOWN**: could not be determined. Say so plainly. Requires the check that could settle it.

Why: a claim someone would act on (change a model, tell a stakeholder) must show how it is
known. Confident prose over unchecked ground is how a wrong statement reaches a stakeholder.

## Absence is the riskiest claim

Never write "X does not exist in the source" from a query or join result alone. Check the raw
source, then distinguish "X is not surfacing in our query because of Y" from "X does not exist".
A scoped search that finds nothing is VERIFIED only for that scope: say "a text search of
project DATA for tickets created since Sep 25 found none", not "no ticket exists".

## Where numbers come from (pick one footing per page)

| Footing | Use when | Watch for |
|---|---|---|
| **Production** | The measure only uses columns that already exist there. | Nothing; it is the reference. |
| **Compiled PR over production** | The change is not deployed. Compile the changed model and swap every dev ref for its production schema, keeping only the changed objects in dev. | State it on the page; the queries shown to readers cannot run until deploy. |
| **Dev build** | Tests and mutation checks. | A dev schema can lag production by days (measured ~3 days, ~1% on one occasion). Never use dev totals to reproduce stakeholder figures. |

State on the page which footing produced which numbers. The callout must be literally true:
"every number" is almost never true when tests ran in dev and some queries ran on production.

## Provenance for each VERIFIED claim

`source_query` (a file in `queries/`) or a named non-query source (`code`, `slack_message`,
`jira_search`, `test_run`) plus a reference, and `measured_at`. If a figure came from an earlier
session or document, re-run it before labeling it VERIFIED today, or keep the earlier date.

## Mutation checks

A passing test proves little unless it can fail. For each guard, break it on purpose and
record that it failed. Re-run it on the day you tag it; do not carry a prior result forward
under today's date.

## Stakeholder statements

A message a stakeholder wrote in a channel is first-hand evidence: quote it with the date.
What they said is not necessarily a decision: record their wording ("would not want to add")
and any follow-up questions they asked, and keep "decided" for decisions.
