# Which tab a claim belongs in

Ask: **who can confirm this claim, and in what terms?**

| | Finance Validation | Technical Validation |
|---|---|---|
| Test | A business stakeholder can read the result in business terms and check it against something they own (a workbook, the cube, a report), or it answers a question they asked. | Only an engineer can judge it: correctness of the build, not of the business numbers. |
| Looks like | Units by quarter and by channel, a gap-to-recovered walk, a tie-out to their workbook, "does this match?" | Test results, mutation checks, grain and fan-out checks, hash identity of existing columns, contract and CI status, column-by-column comparisons. |
| Asked of the reader | "Please confirm this looks right." | "Is the build sound?" |

Second test for the boundary: **would the stakeholder change their answer if this were wrong?**
If a wrong value would change what they confirm, it is Finance. If it would only change whether
an engineer trusts the build, it is Technical.

## Rules

- Set `audience` on every claim: `finance`, `engineering`, or `both`.
- A claim lives in one place and is referenced by id elsewhere. The Acceptance Criteria tab
  cuts across by design: it follows the ticket's wording and links to claims in either tab.
- If it is unclear, put the claim in Technical and flag it for the engineer. A cluttered
  Finance tab costs the demo more than a metric Finance did not see.
- Each tab's intro states what it contains, so a reader knows why they are looking at it.
- Context for Agent holds business and data facts a stakeholder must confirm, whatever their
  audience elsewhere. Its rows are a different kind of object (see the schema).

## Examples

- Row counts and a measure total equal to production, in the stakeholder's units: Finance.
- A hash over all existing columns equal to production: Technical (the Acceptance Criteria tab
  may cite it).
- A tie-out to the cube Finance reads: Finance.
- A mutation check that fails a guard: Technical.
