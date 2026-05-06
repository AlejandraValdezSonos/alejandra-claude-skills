---
name: code-review
description: >
  Performs a thorough, standards-aware code review of a git branch against its base branch.
  Use this skill whenever a user asks to review a branch, audit changes, check a PR, or
  wants feedback on what's been added or modified in a feature branch. Trigger on phrases
  like "review my branch", "review these changes", "check the diff on X branch", "what's
  wrong with my feature branch", "code review for <branch>", or "can you look at the changes
  in <branch>?". Also trigger when the user provides a project path + branch name and asks
  what changed or whether it looks good — even if they don't use the words "code review."
---

# Code Review Skill

You are performing a structured, two-phase code review of a git branch. The goal is to give
the developer actionable, specific feedback — not a list of nit-picks, but a genuine review
that catches real problems and helps them write better code.

## Inputs

- **Project path**: A path to a git repository on disk (or a name if it's a known dir). Default to `.` if not specified.
- **Branch name**: The feature branch to review.
- **Base branch**: Default to `test`. If the user specifies a different base (e.g., `main`, `develop`), use that.

## Phase 1: Understand the Changes

### 1a. Verify the branch exists

```bash
cd <project_path> && git fetch --all --quiet 2>/dev/null; git branch -a | grep -i "<branch>"
```

If the branch doesn't exist or has no commits, stop and tell the user clearly (include the branch name you searched for, and suggest checking `git branch -a` themselves).

### 1b. Get the diff

```bash
git diff <base_branch>...<branch> --stat
git diff <base_branch>...<branch>
```

If the diff is empty, tell the user there are no changes between the branches and stop.

**Large diff handling**: If the raw diff is more than ~600 lines, do NOT try to process it all at once. Instead:
1. Get the file list from `--stat` first
2. For monorepos or projects with many packages, identify which service/package is most affected (look at path prefixes — e.g., `services/auth/`, `packages/api/`) and focus the review there
3. Process the diff in logical chunks: review files one at a time, starting with the most substantive changes (not test files or lock files)
4. Skip generated files (e.g., `package-lock.json`, `*.generated.ts`, `dist/`, `build/`) entirely

### 1c. Get recent commit messages

```bash
git log <base_branch>..<branch> --oneline
```

This gives you context about the developer's intent, which matters for calibrating the review.

## Repo-Specific Standards

### sonos-data-cleansed-dbt

If the project path contains `sonos-data-cleansed-dbt`, apply AutomateDV guidelines as the **primary standard** for all Data Vault modeling code. Specifically check for:

- **Hub models**: Must use `automate_dv.hub()` macro. Verify `src_pk`, `src_nk`, `src_ldts`, `src_source` are correctly mapped. Business keys should not be transformed inside the macro call — transformations belong in the staging layer.
- **Link models**: Must use `automate_dv.link()`. Check that all FK references point to the correct hub PKs, and that no business logic leaks into the link.
- **Satellite models**: Must use `automate_dv.sat()` or `automate_dv.eff_sat()` / `automate_dv.ma_sat()` as appropriate. Verify `src_hashdiff` is derived from the correct set of descriptive attributes and that no PK columns are included in the hashdiff.
- **Staging models**: Must use `automate_dv.stage()` macro. Check that hashing uses `automate_dv.hash_columns()` with the correct algorithm (typically `MD5` or `SHA` depending on project config), and that all columns fed into hashes are `UPPER(TRIM(...))` normalized.
- **Ref integrity**: Links and satellites must reference hub/link PKs via `ref()`, not hardcoded table names.
- **`dbt_project.yml` config**: AutomateDV models should be materialized as `incremental` (not `table` or `view`) unless there is an explicit reason noted in a comment.
- **Ghost records**: Check whether ghost/default records are handled consistently with the rest of the project.

Flag any deviation from these patterns as **HIGH** severity — AutomateDV macros are opinionated and incorrect usage silently produces wrong Data Vault output.

### sonos-data-core-dbt

If the project path contains `sonos-data-core-dbt`, apply the following null handling standards. This is Kimball Dimensional Modeling 101 adapted for the DataVault 2.0 binary hash key pattern used at Sonos.

#### Null handling sentinel values (the Sonos standard)

Every dimension — whether sourced from the legacy warehouse or the new DV2.0 layer — must have at minimum one unknown/null record. Sentinel values by column type:

| Column type | Sentinel value |
|---|---|
| DV2.0 binary hash key | `'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF'` (64 F's) |
| Legacy integer key | `-1` |
| Varchar / string | `'*N/A'` (sorts to top of list for easy business identification) |
| Date | `'1900-01-01'` |
| Numeric / measure in dimensions | `-1` |

**Note:** Mixing `-1` and binary hash key handling in the same model is correct and expected — legacy keys are integers and use `-1`, new DV2.0 keys are binary and use 64 F's. Do **not** flag this as an inconsistency.

#### Checks to apply:

**HIGH severity:**

- **Dimension missing unknown record entirely**: Any dimension model (dim_*, bridge_*) or viz dimension that does not include a row representing the unknown member. Without it, fact rows with unresolved FK lookups have nowhere to point and will break BI filters.
- **Fact table NULL foreign keys not handled**: Fact tables with nullable FK columns must coalesce null keys to the unknown member sentinel (`'FFFF...'` for binary keys, `-1` for legacy integer keys). A fact row with a null FK that doesn't resolve to the unknown dimension member is a violation.
- **Wrong sentinel for key type**: Using `-1` for a DV2.0 binary hash key column, or using `'FFFF...'` for a legacy integer key. The sentinel must match the key type.

**MEDIUM severity:**

- **Nullable varchar/string dimension columns not coalesced to `'*N/A'`**: Any string attribute column in a viz or dim model that can return null instead of `'*N/A'`.
- **Date column defaulting to something other than `'1900-01-01'`**: Using `null`, `current_date`, or another arbitrary date as the unknown member default for date columns in dimensions.
- **Sentinel value misspelled**: `'*N/A'` spelled as `'N/A'`, `'* N/A'`, `'*n/a'`, `'Unknown'`, or `'(blank)'` — causes incorrect sorting and inconsistency in BI filter lists.
- **Audit columns exposed in viz output**: Columns like `dw_created_by`, `dw_modified_by`, `dw_created_date`, `dw_modified_date` should not surface in viz models.

## Phase 2: Infer the Coding Standards

Before reviewing the diff, you need to understand what "good" looks like for *this* project. This is what separates a useful review from a generic one.

### 2a. Check for explicit standards files (highest priority)

Look for these in the project root and changed directories:

```bash
find <project_path> -maxdepth 3 -name "CONTRIBUTING.md" -o -name ".eslintrc*" -o -name ".eslintrc.js" -o -name "pyproject.toml" -o -name ".pylintrc" -o -name "tslint.json" -o -name ".rubocop.yml" -o -name "checkstyle.xml" -o -name "setup.cfg" -o -name ".prettierrc*" | head -20
```

If any are found, read the relevant ones. These are **ground truth** — they override anything you might infer from the codebase. Flag violations against these explicitly.

### 2b. Sample existing code to infer standards

Pick 3–5 files from the project that are *not* part of the diff — ideally files in the same module or layer as the changed code. Look for:

- Naming conventions (camelCase vs snake_case, file naming patterns)
- Error handling patterns (try/catch style, custom error classes, return codes)
- How functions are structured (length, abstraction level)
- Comment and docstring conventions
- How tests are written (test naming, use of mocks/fixtures, assertion style)
- Import organization
- Logging patterns

You don't need to be exhaustive — you're building a mental model, not writing a style guide. Capture the key patterns you notice.

### 2c. Note the tech stack

Look at the file extensions, imports, and any config files (`package.json`, `Cargo.toml`, `go.mod`, `requirements.txt`) to understand the language, framework, and runtime. This affects what constitutes good vs. bad code.

## Phase 3: Review the Diff

Now review the changed code with two lenses:

### Lens 1: Standards consistency

For each changed file, compare the new code against the standards you observed. Flag things like:
- Different naming conventions from the rest of the codebase
- Error handling that doesn't follow the established pattern
- Missing or inconsistent logging
- Structural differences from similar files
- Test patterns that diverge from existing tests

Only flag inconsistencies that actually matter — style nit-picks with no functional implication should be marked LOW severity or omitted.

### Lens 2: General code quality

Regardless of project standards, look for:
- **Logic bugs**: Off-by-one errors, incorrect conditionals, missing null/undefined checks, unreachable code
- **Security issues**: SQL injection, XSS, hardcoded secrets, insecure deserialization, missing auth checks, path traversal
- **Missing tests**: If there are new functions or logic paths with no corresponding test coverage, note it
- **Performance**: N+1 queries, unnecessary re-computation in loops, blocking I/O in async contexts
- **Unclear naming**: Variables like `tmp`, `data`, `result` that don't communicate intent
- **Dead code**: Commented-out code left in, unused imports, variables declared but never used
- **Breaking column changes**: If a column is **deleted or renamed** in any model, check for downstream impact:
  - Search for other models that `ref()` this model and select the affected column by name — any hardcoded column reference in a downstream SELECT will silently return null or error at runtime
  - For dbt projects: grep for the old column name across `models/` to find downstream consumers
  - Flag as **HIGH** if downstream models exist that reference the removed/renamed column and there is no corresponding update to those models in the same PR
  - Flag as **MEDIUM** if the column is exposed in a `.yml` schema file (description, tests) that wasn't updated to match

### dbt projects (applies to any repo using dbt)

When the diff contains `.sql` or `.yml` files in a `models/` directory, apply these additional checks:

#### HIGH severity:

- **No tests on new model**: Any new model without at least `not_null` and `unique` tests on its primary key in a `.yml` schema file. Untested models silently produce bad data.
- **Incremental model missing `is_incremental()` filter**: A new `{{ config(materialized='incremental') }}` model that doesn't filter with `{% if is_incremental() %}` will full-refresh on every run, defeating the purpose and causing performance issues.
- **Incremental model missing `unique_key`**: Without `unique_key` in the config, dbt can't deduplicate on incremental runs — leads to duplicate rows accumulating over time.
- **Direct table reference instead of `ref()` or `source()`**: Hardcoded `FROM schema.table_name` bypasses dbt's lineage graph and breaks cross-environment portability. Flag any raw SQL table reference that should be a `ref()` or `source()`.

#### MEDIUM severity:

- **New model missing `.yml` entry entirely**: Every new model should have a corresponding entry in a schema `.yml` file with at minimum a model-level description and primary key test.
- **Columns in model not documented in `.yml`**: Any column added to a model that has no `description` in the schema `.yml`. All columns — especially ones exposed to BI or downstream consumers — should have a description. Flag missing descriptions as MEDIUM.
- **`.yml` descriptions that are empty or placeholder**: A description of `""`, `"TODO"`, `"TBD"`, or that just restates the column name word-for-word is not documentation. Flag these.
- **Fan-out join without dedup**: A join where the right-side table can have multiple matching rows and there is no `GROUP BY`, `DISTINCT`, `QUALIFY ROW_NUMBER()`, or similar guard. Silently multiplies rows and inflates metrics.
- **SCD treatment inconsistency** (Kimball models): A dimension column that should be historized (Type 2) being overwritten (Type 1), or vice versa — especially if neighboring columns in the same model handle it differently.

#### LOW severity:

- **Grain not documented**: For new fact or mart models, the grain (what one row represents) should be stated in the model description or a comment at the top of the file. Without it, reviewers can't verify the logic is correct.
- **Duplicate `ref()` calls to the same model**: A CTE that `ref()`s the same upstream model more than once. Consolidate into one CTE at the top.
- **Window functions without `PARTITION BY`** on tables that are clearly large (fact tables, event logs) — may cause full-table sort and poor query performance.
- **Hardcoded environment values**: `{{ target.schema }}` hardcoded as a string, hardcoded database names, or `LIMIT` clauses left in production model SQL.

## Phase 4: Write the Review

Structure the output like this:

---

## Code Review: `<branch>` → `<base_branch>`

**Project**: `<path>`
**Files changed**: N | **Lines added**: +X | **Lines removed**: -Y
**Commits**: (brief list from git log)

### Summary

2–4 sentences. What did this branch do? Overall quality assessment. Is it ready to merge, or does it need significant work?

### Findings

List findings grouped by file. For each finding:

```
**[SEVERITY] filename.ext (line N or lines N–M)**
<Clear explanation of the issue and why it matters>

*Suggested fix:*
<Code snippet or description of what to do instead — omit if the fix is obvious>
```

Severity levels:
- **CRITICAL** — Will likely cause a bug in production, security vulnerability, or data loss
- **HIGH** — Logic error, missing test coverage for important paths, meaningful security gap
- **MEDIUM** — Standards violation that matters (e.g., inconsistent error handling that could confuse future maintainers), or a code quality issue that adds real risk
- **LOW** — Minor style inconsistency, unclear name, optional improvement

If there are no findings in a file, skip it.

### Standards Observations

A brief paragraph (2–4 sentences) noting how the new code relates to the existing codebase style — what's consistent, what diverges, whether the diff fits in or feels foreign.

### Overall Verdict

One of:
- ✅ **Approved** — Looks good, ready to merge
- ⚠️ **Approved with minor comments** — Mergeable but the findings are worth addressing
- 🔄 **Changes requested** — At least one HIGH or CRITICAL finding that should be resolved before merging

---

## Important calibration notes

**Be specific.** "This function is too long" is unhelpful. "This function handles both input validation and database write logic — splitting it would make each part easier to test" is useful.

**Don't over-flag.** If something is stylistically different but harmless, LOW severity at most. The goal is to help the developer, not to produce an impressive-looking list.

**Security issues always surface.** Even if the project has no security policy or linter, flag potential security vulnerabilities regardless.

**When uncertain, say so.** "This looks like it might cause a race condition if called concurrently, but I'd need to know more about how this is scheduled" is fine — better than either silence or false confidence.

**Generated/vendored files**: Do not review `package-lock.json`, `yarn.lock`, `*.generated.*`, `dist/`, `vendor/`, or similar. Note in the summary if they appear in the diff but skip them in the findings.
