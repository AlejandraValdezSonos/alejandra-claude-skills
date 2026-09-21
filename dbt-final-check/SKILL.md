---
name: dbt-final-check
model: claude-opus-4-6
description: >
  Pre-PR self-check on the current branch. Verifies methodology compliance
  (Kimball for core, Data Vault for cleansed), DRY/optimization analysis, and
  style consistency against existing repo models. Run this before /create-pr.
  Triggers on "final check", "dbt check", "check my branch", "ready for PR?",
  "/dbt-final-check", or "is my branch ready".
---

# dbt Final Check

You are running a pre-PR self-check on Alejandra's current branch. The goal is to catch
methodology violations, duplicated logic, optimization issues, and style inconsistencies
BEFORE opening a PR — so she doesn't get flagged in review for things she could fix now.

**Bucky parity, but full-coverage:** the repo's PR reviewer (Bucky, `Sonos-Inc/bucky@v2`)
reviews with seven lenses (compat-api, correctness, docs-drift, intent, performance,
security, testing) driven by the repo's AGENTS.md — but it batches, covering more of the
PR on each new commit, so findings dribble out over multiple push cycles. This skill's
contract is the opposite: **one exhaustive pass over the ENTIRE branch diff, every lens
against every changed hunk, before the first push.** Success = Bucky's real runs find
nothing. Never sample, never defer a file to "next iteration" — there is no next iteration.

This is NOT a code review for a peer. The tone is direct and fix-oriented: "this needs to
change" rather than "consider changing this."

## Inputs

- **Repo path**: Default to the current working directory. Detect which repo from the path:
  - `sonos-data-core-dbt` → Kimball methodology checks
  - `sonos-data-cleansed-dbt` → Data Vault methodology checks

## Phase 0: Full-diff inventory (the anti-batching contract)

Before any checking, enumerate the complete review surface and hold yourself to it:

```bash
git fetch origin test
git diff origin/test...HEAD --stat            # every file, committed
git diff --stat                               # plus uncommitted work
```

Build a **coverage checklist**: one row per changed file. The run is not complete until
every row has been examined under every applicable lens (Phase 4.5) plus the existing
phases. If the diff is large, work through ALL of it in this run — spawn subagents per
file group if needed — never truncate to "the most important files." The final output
must include the coverage matrix so it's provable nothing was skipped.

## Phase 1: Identify changed models

```bash
git diff test...HEAD --name-only -- '*.sql' '*.yml' '*.yaml'
```

Separate into:
- **New files** (not on `test` branch)
- **Modified files** (exist on both, have changes)

Also check for uncommitted changes:
```bash
git diff --name-only -- '*.sql' '*.yml' '*.yaml'
git diff --cached --name-only -- '*.sql' '*.yml' '*.yaml'
```

If there are uncommitted changes, warn Alejandra but continue checking committed work.

Read every changed `.sql` and `.yml` file. You'll need the full contents for all checks below.

## Phase 2: Style consistency check

For each changed model, find 2–3 **existing models in the same directory** that are NOT
part of the current branch changes. These are the style reference models.

```bash
# Example: changed model is models/warehouse/finance/fact_foo.sql
ls models/warehouse/finance/fact_*.sql | head -5
```

Read each reference model and its `.yml`. Compare the following structural elements and
flag any deviation in the changed models:

### CTE organization
- What CTE naming pattern do existing models use? (`source`, `renamed`, `final`? or
  domain-specific like `gl_lines`, `cost_centers`, `joined`?)
- Do existing models use a single `final` CTE or multiple layered CTEs?
- Is there a consistent CTE ordering pattern (sources first, then joins, then transforms)?

### Column conventions
- Column naming: UPPER vs lower, snake_case consistency
- Column ordering: Keys first? Dimensions then measures? Audit columns at the end?
- Alias style: `AS` keyword always present? Trailing commas vs leading commas?

### Description style (yml)
- Do sibling columns in the same `.yml` (or sibling models in the same directory) use
  `{{ doc("...") }}` doc-block references for descriptions? If so, a hardcoded description
  string on a new/changed column is a deviation — flag it.
- *Fix:* add a `{% docs <column_name> %}` block to the layer's docs markdown file
  (e.g. `models/warehouse/bizops/_bizops_docs.md`) and reference it with
  `description: '{{ doc("<column_name>") }}'`. Check whether a doc block with that name
  already exists in the repo before creating one (`grep -rn 'docs <name>' --include="*.md" models/`).
- Caught in the wild (2026-09-01, DATA-17684): new fact/viz columns were added with
  hardcoded description strings while every sibling column used `doc()` refs.

### Config block
- Does the existing model use `{{ config(...) }}` or rely on `dbt_project.yml`?
- Tags, pre/post hooks, materialization — do they match siblings?

### Documentation and testing patterns (layer-specific)

This is critical — each layer has different conventions for where docs and tests live:

**Staging (`models/staging/`):**
- `.yml` files typically have minimal documentation — source column descriptions only
- Tests are minimal or absent at this layer (tested upstream or downstream)
- Check: does the new staging model follow this minimal pattern, or is it over-documented?

**Intermediate (`models/intermediate/`):**
- Ephemeral materialization — no `.yml` tests expected (can't test ephemeral models)
- May have a `.yml` entry for documentation but no tests
- Check: is the model actually ephemeral? Does it have tests it shouldn't?

**Warehouse (`models/warehouse/`) and Viz (`models/viz/`):**
- **This is where docs and tests belong.** Every model MUST have:
  - A `.yml` entry with model-level description
  - Column-level descriptions (especially for contract-enforced models)
  - `data_type` on every column (contract enforcement)
  - Primary key tests (`unique` + `not_null`)
  - Relationship tests where FK references exist
- Check existing sibling models to see what tests they have and flag if the new model
  is missing tests that siblings consistently include (e.g., all other `fact_*` models
  in the same dir have `accepted_values` on a status column)

**Report deviations as a comparison table:**

```
| Element | Repo pattern (from <reference_model>) | Your model | Fix needed? |
|---|---|---|---|
| CTE naming | source → renamed → final | raw → joined → output | ⚠️ Rename CTEs |
| Column order | keys → dims → measures → audit | mixed | ⚠️ Reorder |
| Tests | unique + not_null on PK, accepted_values on type | only unique on PK | ⚠️ Add not_null, accepted_values |
| Doc descriptions | all columns documented | 3 columns missing | ⚠️ Add descriptions |
```

## Phase 3: Methodology compliance

### Kimball checks (sonos-data-core-dbt only)

For each changed model, verify:

**Dimensions (`dim_*`, `bridge_*`):**
- [ ] Unknown/null member row present (sentinel values per column type)
- [ ] Wide and flat — no snowflaking (joining to other dims instead of denormalizing)
- [ ] SCD type appropriate per attribute (Type 1 vs Type 2)
- [ ] Conformed dims reused via `ref()` — not reinventing `dim_date`, `dim_product`, etc.
- [ ] String attributes coalesced to `'*N/A'`, dates to `'1900-01-01'`

**Facts (`fact_*`, `agg_*`):**
- [ ] Grain documented (model description or top-of-file comment)
- [ ] Grain verified — PK columns uniquely identify rows
- [ ] FK columns coalesced to unknown member sentinel (no bare NULLs)
- [ ] Correct fact type (transaction, periodic snapshot, accumulating snapshot)
- [ ] Measures are appropriate (additive vs semi-additive vs non-additive)
- [ ] Degenerate dimensions kept in fact (not spun into unnecessary dims)
- [ ] No fact-to-fact joins without going through conformed dimensions

**Viz (`viz_*`):**
- [ ] No audit columns (`dw_created_by`, `dw_modified_by`, etc.)
- [ ] Unknown member row present (via `create_viz_with_unknown` macro or manual UNION)
- [ ] Contract enforced with `data_type` on all columns

**Staging (`stg_*`):**
- [ ] Sources from `source('cleansed', ...)` — not legacy `source('dwm', ...)` / `source('ods', ...)`
- [ ] If legacy source is used, is there a cleansed equivalent available?

### Data Vault checks (sonos-data-cleansed-dbt only)

For each changed model, verify:

**Hubs (`hub_*`):**
- [ ] Single business key (plus hash key, load date, record source)
- [ ] No descriptive attributes in the hub
- [ ] Sourced from ALL staging models that produce this business key
- [ ] Uses `automate_dv.hub()` macro correctly

**Satellites (`sat_*`):**
- [ ] Hashdiff includes ALL payload columns (including FK/NK references)
- [ ] No PK columns in hashdiff
- [ ] Correctly attached to parent hub/link via hash key FK
- [ ] Split by rate-of-change if entity is wide
- [ ] Uses `automate_dv.sat()` (or `eff_sat()` / `ma_sat()`) correctly

**Links (`link_*`):**
- [ ] Connects exactly the right hubs
- [ ] Non-temporal (no business dates — those go in effectivity satellites)
- [ ] Uses `automate_dv.link()` correctly

**Staging (`stg_*`):**
- [ ] All columns normalized with `UPPER(TRIM(...))` before hashing
- [ ] Hash algorithm consistent with project
- [ ] Derived columns separated from source columns
- [ ] Null business keys handled (ghost records)
- [ ] Uses `automate_dv.stage()` macro

**Business vault (`bv_*`, `v_*`):**
- [ ] Complex business logic lives here, not in raw vault
- [ ] Materialized as `incremental` unless explicitly justified

## Phase 4: DRY and optimization analysis

### 4a. DRY check — within changed models

Look across all changed `.sql` files for repeated patterns:
- Same `CASE WHEN` block appearing in 2+ models
- Same `COALESCE` / null-handling pattern repeated
- Same join pattern (same tables, same keys) duplicated
- Same CTE logic copy-pasted between models

If a pattern repeats 3+ times, suggest extracting to:
- A **macro** (if it's reusable SQL logic)
- A **shared CTE** in an intermediate model (if it's a data transformation)
- An **ephemeral model** (if it's a reusable dataset)

Include a draft of what the extraction would look like.

### 4b. DRY check — against existing repo models

For each changed model, grep the repo for patterns that already exist as macros or
shared models:

```bash
# Check if similar logic already exists in macros/
grep -rn '<distinctive_pattern>' macros/ --include="*.sql" | head -5
```

Common things to check:
- Is there an existing macro for the null-handling pattern being used?
- Is there an existing intermediate model that produces the same dataset?
- Does the repo have a `create_viz_with_unknown` or similar macro that should be used
  instead of manual UNION ALL for unknown rows?
- Are there existing `get_columns` or column-generation macros being bypassed?

### 4c. Optimization check

For each changed model:

**Query performance:**
- `SELECT *` from wide upstream models when only a few columns are needed
- `DISTINCT` used as a dedup band-aid (should be `GROUP BY` with explicit aggregation)
- `ORDER BY` in non-viz models (unnecessary sort cost)
- Window functions without `PARTITION BY` on large tables
- Full table scans on large sources without `WHERE` filters
- Cartesian / fan-out joins without dedup guards
- Missing `cluster_by` on large table materializations

**Incremental models:**
- Has `is_incremental()` filter?
- Has `unique_key` in config?
- Uses HWM pattern instead of full source scan?

**CTE efficiency:**
- Redundant CTEs that could be collapsed
- Same expensive expression computed multiple times (extract to CTE or lateral alias)
- CTEs that are only referenced once and add no readability value

### 4d. Behavioral change detection

When a refactor changes HOW data flows (not just performance), flag the row-level impact.
These are NOT style or optimization issues — they change what rows appear in the output.

**Common patterns that silently change row sets:**

- **LEFT JOIN → conditional aggregation (CASE WHEN):** Merging two CTEs that read the same
  source into one CTE with `SUM(CASE WHEN ...)` changes which combos appear. A LEFT JOIN
  produces rows only from the driving table; conditional aggregation in a single GROUP BY
  produces rows for ANY matching measure_type. The result set can grow (new combos appear)
  or shrink (combos that existed only in the left table may now get NULLs differently).
  **Always flag this and recommend a before/after row count + DD total comparison.**

- **Subquery → CTE extraction:** Usually safe (same semantics), but check that the CTE
  isn't referenced elsewhere with different filters — extracting it shares the filter set.

- **COALESCE chain reordering:** Changing `COALESCE(a.col, b.col)` to `COALESCE(b.col, a.col)`
  changes which source wins. Flag any COALESCE reordering as a behavioral change.

- **Adding/removing a join key:** Adding `forecast_cycle` to a join changes the match
  cardinality. What was a 1:many becomes 1:1 (or vice versa). Flag and verify row counts.

- **Changing driving table in a LEFT JOIN:** Switching from `FROM a LEFT JOIN b` to
  `FROM b LEFT JOIN a` changes which rows survive. Always flag.

**When you detect any of these patterns, add a "Behavioral Impact" section to the output
with a specific recommendation to run before/after validation queries:**

```
### Behavioral Impact

⚠️ N refactors detected that may change output rows:

1. **`<model_name>.sql`** — <pattern detected>
   *Risk:* <what could change — more rows, fewer rows, different values>
   *Verify:* Run row count + DD total comparison before and after the change.
   Do NOT rely on dbt tests alone — they may pass while output shifts.
```

## Phase 4.5: Bucky lens sweep — full PR, single pass

Run each of Bucky's seven lenses over the **complete** diff from Phase 0. These overlap
partially with Phases 2–4; where they do, cross-reference rather than duplicate findings.

**intent** — Does the diff do what the ticket/PR description says, and nothing undeclared?
Bucky diffs the PR description against the code — so will this check. Flag: delivered
behavior missing from the description, described behavior missing from the code, and
undeclared scope (Bucky treats surprise changes as findings). If a PR body exists, read it
with `gh pr view --json body`; otherwise use the Jira AC.

**correctness** — Grain, joins, filters, boundary logic, per changed model. Hunt the
classes Bucky has actually caught in this repo: label-only or partial-key joins that
over-produce rows (carry the full key through derivation CTEs); unbounded expansions of
open-ended validity ranges (`valid_to 9999-12-31` × date spines); cross joins without a
bounding join; fan-out on group-grain joins (a product group ↔ many product_ids);
anti-join keys narrower than the precedence rule they implement. For every derived
row-set, ask: "can this produce a combination the consumer can never read?" — if yes,
bound it.

**testing** — For each behavioral invariant the branch introduces, run the silent-failure
thought experiment: *"if this logic regressed tomorrow, which existing test fails?"* If
the answer is "none" and the blast radius is material, a standing test is required (schema
test in the .yml, or `tests/finance/`-style singular where that pattern is established).
State the invariant, not the implementation, when proposing it.

**docs-drift** — For every changed model: does the .yml description still describe the
model's actual behavior? Do shared doc blocks (`_docs.md` / `_finance_docs.md`) referenced
by its columns still hold (sources, nullability, provenance)? New behavior (fallback
sources, NULL markers, coverage bounds) must be reflected. This is the lens Bucky most
reliably flags — check it file by file, not from memory.

**compat-api** — The AGENTS.md cross-repo contract check: any removed/renamed/retyped
column in `models/warehouse/**` or `models/viz/**`? If yes, grep the three sibling repos
for the old identifier. Locally there is no `_cross_repos/`, so use, in order of
preference: existing local clones (`~/development/<repo>`), or GitHub code search
(`gh api search/code?q=<identifier>+repo:Sonos-Inc/<repo>`). Pure additions pass; note
them as non-breaking.

**performance** — Phase 4c covers this; re-scan the full diff once more for anything 4c's
model-by-model pass missed at the cross-model level (repeated scans of the same big
source across CTEs/models, missing bounds on spines).

**security** — Hardcoded credentials/schemas/tokens; masking-policy columns touched
without their `masking_policy` yml entries; new grants implied but not configured; PII
columns surfaced into wider-access layers.

**modeling-judgment (the Lili lens)** — The human-reviewer axis Bucky doesn't cover:
schema placement and genericity (shared reference data → mdm, domain filters → domain
fact), PK discipline (every dim has one; no redundant second key), SCD semantics coherent
end-to-end (no is_deleted on SCDs; no "SCD" built on a latest-only upstream), DRY across
sibling models (two models sharing large logic blocks need a stated reason to be two),
every WHERE clause justifiable, dropped columns justified, and requirements fidelity —
the output matches the requesting artifact line-for-line at the requested grain, with no
metric dropped to dodge NULLs, and unexplained NULLs in delivered metrics resolved.

**Pattern library:** before finishing the sweep, check every changed file against
`references/reviewer-patterns.md` in this skill's directory — concrete find-classes mined
from Bucky's and Lili's actual comments on past PRs. After each new reviewed PR, fold any
novel finding-type back into that file (the refresh command is at the top of it).

Record per-lens results into the Phase 0 coverage matrix (✅ clean / finding ref / N/A).

## Phase 5: Output

Print results to terminal in this format:

```markdown
## dbt Final Check — `<branch_name>`

**Repo:** `<repo_name>` | **Models checked:** N | **Date:** YYYY-MM-DD

---

### Coverage matrix (Phase 0 × Phase 4.5 — proves full-PR coverage)

| File | intent | correctness | testing | docs-drift | compat-api | performance | security | modeling-judgment |
|---|---|---|---|---|---|---|---|
| model_a.sql | ✅ | F1 | ✅ | F3 | ✅ | ✅ | ✅ |
<every changed file gets a row; findings referenced by number; no blanks allowed>

### Bucky Lens Findings

<numbered findings from Phase 4.5, most severe first, each tagged with its lens —
these are the findings Bucky would otherwise deliver over multiple batched runs>

### Style Consistency

<comparison tables from Phase 2, one per changed model>

### Methodology Compliance

<checklist results from Phase 3 — only show failures/warnings, skip passing items>

✅ N checks passed
⚠️ N issues found:

1. **`<model_name>.sql`** — <issue description>
   *Fix:* <what to do>

2. ...

### DRY Analysis

<findings from Phase 4a and 4b>

✅ No repeated patterns found.
OR
⚠️ N patterns could be refactored:

1. **Repeated pattern:** <description>
   **Found in:** `model_a.sql` (line N), `model_b.sql` (line N), `model_c.sql` (line N)
   *Suggested extraction:*
   ```sql
   -- macro: <macro_name>
   <draft macro SQL>
   ```

### Optimization

<findings from Phase 4c>

✅ No optimization concerns.
OR
⚠️ N optimization issues:

1. **`<model_name>.sql`** — <issue and why it matters>
   *Fix:* <what to change>

---

### Verdict

✅ **Ready for PR** — no blocking issues found
OR
⚠️ **Almost ready** — N non-blocking issues to consider fixing
OR
❌ **Not ready** — N blocking issues must be fixed before opening a PR

Blocking issues are: methodology violations, missing PK tests on warehouse/viz models,
contract violations (missing data_type), and CRITICAL optimization problems (cartesian joins,
broken incremental filters).
```

## Important notes

- This is a self-check, not a peer review. Be direct: "fix this" not "consider this."
- Only flag real issues — don't pad the output with passing checks.
- If a model is in staging, don't flag it for missing warehouse-level docs/tests.
- If a pattern is used everywhere in the repo (even if suboptimal), don't flag it in the
  developer's model — that's a repo-wide refactor, not a branch fix.
- The DRY check should have a threshold: don't flag 2 similar lines, flag 3+ repeated
  blocks of 5+ lines.
- For macro suggestions, check that a similar macro doesn't already exist before suggesting
  a new one.
