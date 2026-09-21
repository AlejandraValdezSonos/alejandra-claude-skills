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
- **PR number**: Optional. If provided (e.g. `#386`), fetch PR comments from GitHub and evaluate Jira AC coverage. If not provided, skip Phases 1d and 1e.

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

### 1d. Fetch PR comments (if PR number provided)

```bash
gh pr view <pr_number> --repo Sonos-Inc/<repo> \
  --json comments,reviews \
  --jq '{
    comments: [.comments[] | {author: .author.login, body: .body}],
    reviews: [.reviews[] | {author: .author.login, state: .state, body: .body}]
  }'
```

Read all comments and review threads. Note:
- **What other reviewers (including Bucky) have already flagged** — do not re-raise findings that are already called out and actively being addressed in the thread. If a finding is raised but the author has not yet responded or fixed it, you should still include it.
- **Commitments the author made in comments** — e.g. "will fix in follow-up ticket", "this is intentional because X", "Leslie confirmed Y". These count as context for evaluating AC items.
- **Resolved vs. unresolved threads** — a finding with an approved resolution is closed; one with no response is still open.
- **What the PR description says vs. what commenters push back on** — discrepancies matter.

Summarize the comment thread state briefly. You will use this in the AC coverage section of the review.

### 1e. Fetch Jira ticket and extract AC (if PR number provided)

Parse the Jira ticket key from the branch name (e.g. `DATA-17344` from branch `DATA-17344` or `DATA-17344-some-description`). If no key is parseable, skip this step.

```python
import os, dotenv, requests
dotenv.load_dotenv(os.path.expanduser('~/.claude/scripts/integrations/.env'))
url = os.environ['JIRA_SERVER']
token = os.environ['JIRA_PAT']
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
r = requests.get(f'{url}/rest/api/2/issue/{ticket_key}', headers=headers)
data = r.json()
description = data['fields']['description']
summary = data['fields']['summary']
```

From the ticket description, extract:
1. **Problem Statement** — what problem or business need this ticket addresses. Usually under `h2. Problem Statement` or the opening paragraph.
2. **Acceptance Criteria** — the explicit list of conditions the PR must satisfy to close the ticket. Usually under a heading like `h2. Acceptance Criteria` or `AC:`.
3. **What Needs to Be Built** — requirements that should be reflected in the diff.
4. **Dependencies** — any external sign-offs or coordination steps required (e.g. "validate with Finance", "coordinate with Leslie").

Display a **Ticket Context** block immediately — before any diff analysis — so the intent is clear before reviewing code:

```
### Ticket Context: <TICKET-KEY> — <summary>

**Problem:** <1–2 sentence problem statement from the ticket>
**AC items found:** <count>
```

If the ticket has no structured description, write the raw summary as the problem statement and note that no structured AC was found.

You will evaluate each AC item in Phase 4.

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

#### Staging model conventions (sonos-data-core-dbt only)

**Do NOT flag the following as findings for `models/staging/**` files:**
- Missing `not_null`, `unique`, or `dbt_utils.unique_combination_of_columns` tests in staging `.yml` files — tests are not added to staging models by team convention
- Missing column `description` entries in staging `.yml` files — column descriptions are not added to staging models by team convention

These rules override the general dbt HIGH/MEDIUM severity checks above. Apply the full testing and documentation standard only to `models/warehouse/**` and `models/viz/**`.

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

- **Inline comments or ticket references in SQL files**: Descriptive prose or ticket refs (e.g. `-- DATA-12345 - this model does X`) embedded in `.sql` files should not exist. Documentation belongs in the corresponding `.yml` file, not inline in SQL.
- **String normalization in intermediate instead of staging**: `TRIM()`, null coercion, and string cleanup on key/dimension columns belong in the staging model. If an intermediate applies `trim(col) != ''` on columns that staging passed through uncleaned, flag it.
- **New intermediate or mart model missing a paired `.yml` file**: Every new model that is not a staging passthrough must have a corresponding `.yml` with at minimum a model description and primary key test.
- **Mart/warehouse yml descriptions using inline prose instead of doc blocks**: If the project uses `'{{ doc("model_name") }}'` references in mart/warehouse ymls, flag any new model using a long inline description (`description: >`) instead. Documentation prose belongs in the doc block `.md` file.

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

### Ticket & AC Coverage

*(Include this section only when a PR number was provided and a Jira ticket was found.)*

**Ticket:** `<TICKET-KEY>` — <one-line summary>

For each AC item extracted from the ticket, evaluate whether the PR satisfies it. Use the diff, PR description, and comment thread as evidence.

| # | Acceptance Criterion | Status | Evidence / Notes |
|---|---|---|---|
| 1 | <ac item text, shortened> | ✅ Met / ⚠️ Partial / ❌ Not met | <what in the PR satisfies or fails this — cite specific file, comment, or PR description section> |
| 2 | ... | ... | ... |

Status rules:
- **✅ Met** — satisfied by the diff or explicitly validated in the PR description / Jira comments
- **⚠️ Partial** — partially addressed but something is missing or unverified (e.g. validation stopped at the wrong layer, stakeholder sign-off not documented)
- **❌ Not met** — no evidence in the PR that this was done

**PR comment thread summary:** 1–3 sentences on what reviewers have flagged, what's been resolved, and what's still open. If no comments exist, write "No review comments yet."

If all AC items are ✅, note that the ticket requirements are fully satisfied. If any are ⚠️ or ❌, these should be reflected in the Overall Verdict (a ⚠️ partial AC item is at minimum a MEDIUM finding; an ❌ unmet AC item should block merge).

### Overall Verdict

One of:
- ✅ **Approved** — Looks good, ready to merge
- ⚠️ **Approved with minor comments** — Mergeable but the findings are worth addressing
- 🔄 **Changes requested** — At least one HIGH or CRITICAL finding, or one ❌ unmet AC item, that should be resolved before merging

---

## Important calibration notes

**Be specific.** "This function is too long" is unhelpful. "This function handles both input validation and database write logic — splitting it would make each part easier to test" is useful.

**Don't over-flag.** If something is stylistically different but harmless, LOW severity at most. The goal is to help the developer, not to produce an impressive-looking list.

**Security issues always surface.** Even if the project has no security policy or linter, flag potential security vulnerabilities regardless.

**When uncertain, say so.** "This looks like it might cause a race condition if called concurrently, but I'd need to know more about how this is scheduled" is fine — better than either silence or false confidence.

**Generated/vendored files**: Do not review `package-lock.json`, `yarn.lock`, `*.generated.*`, `dist/`, `vendor/`, or similar. Note in the summary if they appear in the diff but skip them in the findings.

## Important output rules

- **Do NOT include a "Files Changed" section** with raw diff blocks and "Your notes:" placeholders. The diff is already in the PR — reproducing it in the review draft adds length without value. Findings in Phase 4 are sufficient; link to the file/line by name if needed.

## Phase 5: Save to Second Brain

After writing the review, save it to `~/second-brain/code-reviews/pending/` using this filename format:

```
YYYY-MM-DD-PR<number>-<repo-name>.md
```

Where `YYYY-MM-DD` is today's date, `<number>` is the PR number, and `<repo-name>` is the short repo name (e.g. `sonos-data-core-dbt`).

The file header must follow this structure exactly (before the review content):

```markdown
# Code Review Draft: PR #<N> — <TICKET-KEY> | <PR title>
_Review and edit before posting to GitHub. Do NOT post automatically._

**PR:** [<PR title>](<PR URL>)
**Repo:** <org>/<repo> | **Author:** <author>
**Branch:** `<branch>` → `<base>`
**Drafted:** <today's date>
**Ticket:** [[<TICKET-KEY>]]
```

- If the branch name is a Jira ticket key (e.g. `DATA-17232`), use that as `<TICKET-KEY>`.
- If the author is Alejandra (`AlejandraValdezSonos`), use `[[development/<TICKET-KEY>/design-doc|<TICKET-KEY>]]` as the ticket link instead — it points to her own design doc.
- For peer reviews, `[[<TICKET-KEY>]]` links to the ticket stub in `data-model-decisions/`.
