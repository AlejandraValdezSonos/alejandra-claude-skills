# Reviewer Pattern Library — Bucky + Lili

Mined from actual review comments on Alejandra's merged/open PRs (as of 2026-09-01:
PRs 1230, 1262, 1287, 1410, 1455, 1481, 1498, 1500, 1535). Check every changed file
against every pattern below. Refresh this library after each reviewed PR:
`gh api "repos/Sonos-Inc/sonos-data-core-dbt/pulls/<n>/comments" --jq '.[] | select(.user.login == "sonos-bucky[bot]" or .user.login == "lilitangsonos") | ...'`
and fold any NEW finding-type in.

## Bucky (sonos-bucky[bot]) — mechanical/static find-classes

**correctness**
- Partial-key or label-only joins in derivation CTEs that over-produce combinations
  (PR 1535: cycle-label-only cross join stamped months a cycle never forecast).
- Many-to-many joins from joining two same-grain sets on a coarser key
  (PR 1500: country RPU joined F3-grain revenue to F3-grain units on country keys —
  duplicated sums when a country has multiple F3s).
- Driving-table starvation: a chain that starts from source A emits no row for
  combos that exist only in source B, while a downstream FULL OUTER JOIN still
  produces those rows expecting enrichment (PR 1500: rpu chain started from revenue,
  unit-only rows got no RPU; PR 1481: placeholder spine from revenue only).
- Wrong aggregate for "latest": MAX(value) across rows instead of value-at-latest-row
  (PR 1481: country fallback took max RPU across each F3's latest row, mixing months).
- Unbounded expansion of open-ended validity (`valid_to 9999-12-31`) across a date
  spine (PR 1535: prices stamped to fiscal 463802).

**testing** (Bucky's most consistent Medium)
- New core behavior with no test that would fail if it silently regressed. His framing
  every time: "the existing tests can still pass if X goes wrong" — run that thought
  experiment per invariant. Examples: cascade fallback branches never forced (1455),
  recognition landing in the wrong month while totals still balance (1481), precedence
  flip (1535), mutable-sheet keys losing not_null/unique/relationship tests their seed
  version had (1498), omitted-row blindness — tests validate present rows but not that
  required rows are still present (1498: SLT group silently dropped → coalesced to *N/A).
- try_to_date / silent-null conversions with no not_null test downstream (1498).

**docs-drift** (his most reliable Low/Medium — check file by file, never from memory)
- Model .yml description contradicting new SQL behavior (1481: "prelim excluded" vs
  SQL including them; 1500: "falls back to actuals RPU" vs direct MSRP fallback).
- Shared `_finance_docs.md` blocks stale after behavior change: grain listed with
  columns that don't exist, provenance claims ("always from SAP") invalidated by new
  fill paths, filter/flag semantics reversed (1455: GA Delay doc said "within quarter",
  SQL says "before quarter").
- Macro .yml descriptions naming consumers that don't exist / missing real ones (1455).
- **AGENTS.md domain summaries**: adding a warehouse model without updating the
  warehouse_finance overview paragraph (1481) — he checks AGENTS.md itself.
- PR description vs code (intent lens): undeclared deviations from the ticket's stated
  design get flagged (1481: JIRA said debundled-only, SQL used amount_usd, PR body
  didn't mention the deviation) — declare every deviation explicitly.

- Filter consistency across sibling derivation branches: when two CTEs feed the same
  derived set (e.g. a cycle list from Finance ∪ DP sources), a filter present on one
  branch but not the other is a finding even if currently latent — the unfiltered
  branch can leak rows the consumer excludes (PR 1535 round 2: FY25 exclusion on the
  DP branch but not `forecast_unit_weights`).
- Tests must match the grain of the invariant: a label-level reconciliation passes
  while month-level coverage inside a label is broken — assert at the full key of the
  behavior being pinned (PR 1535 round 2: compare (cycle, month) pairs, not labels).
- Test symmetry across sibling models: an invariant pinned on the actuals fact needs
  its forecast counterpart if the forecast fact implements the same rule with its own
  code path (PR 1535 round 2: forecast SAP-precedence test).
- Per-source coverage at the fill's own grain: when two sources fill one table, a
  coverage test can be satisfied by source A's rows while source B silently drops out —
  pin each source's contribution at the finest grain its fill operates on (PR 1535
  round 3: pair-level coverage passed on SAP gap-fill rows while Anaplan-only NPI
  products could vanish from prelim labels; fix = product-grain prelim parity test).

**docs-drift (round-2 lesson): follow exposure chains, not just changed files** — when
a fact's behavior changes, the downstream viz .yml descriptions describing that behavior
are stale even though the viz files aren't in the diff (PR 1535 round 2: both viz MSRP
ymls). Sweep every viz/exposure model that selects from a changed model. Also re-check
AGENTS.md domain overview paragraphs (he checks those — PR 1481).

**repo-convention**
- New standalone tests/ files outside established domains get flagged against the
  repo guidance (1481 — before tests/finance/ was established); know the current
  conventions in AGENTS.md and cite them when deviating.

## Lili (lilitangsonos) — architecture & judgment find-classes

- **Placement & genericity**: reference data useful to all teams belongs in
  `warehouse_mdm`, generic; domain-specific filtering stays in the domain fact
  (1410: dim_product_msrp → mdm, DD-specific filters → fact_product_msrp).
- **PK discipline**: every dim needs an explicit PK; if one key is already unique,
  don't carry a second hash key "just in case" (1410: drop condition_access_hk).
- **Naming simplicity**: prefer plain names (valid_from/valid_to/is_active) over
  source-flavored ones (1410).
- **SCD semantics end-to-end**: is_deleted doesn't belong on an SCD (history is
  retained, not deleted); an "SCD" built on top of an upstream latest-record-only
  view isn't an SCD — history tracking must be coherent across layers (1410, 1230).
- **DRY across sibling models**: "repeated logic in both facts — do we need two
  models, or one model computing both?" (1410: fact_product_msrp vs _forecast).
  Have an answer ready when two models share large logic blocks.
- **Every filter needs a reason**: "is this filter needed?" (1410) — be able to
  justify each WHERE clause or remove it.
- **Column retention rationale**: dropping columns (valid_to) upstream needs a why
  if downstream could use them (1410).
- **Requirements fidelity**: the calculation must match the requesting artifact
  (spreadsheet/ticket) line-for-line, at the requested granularity; removing
  requested metrics to dodge NULLs is never acceptable (1287). Unexplained NULLs in
  delivered metrics get queried directly — she runs her own validation SQL.
- **Follow-up ticket discipline**: known-incomplete pieces (e.g., F2/F3 parents
  pending Anaplan) need a named follow-up ticket, not a TODO (1230).
- **What earns fast approval**: validation queries + attached HTML guide she can run
  herself (1500: "thanks for the validation queries and the attached html. i ran some
  queries and it makes sense").
