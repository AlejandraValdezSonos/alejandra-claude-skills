---
name: validate-pr
model: claude-opus-4-6
description: >
  Validates a GitHub PR branch locally by running dbt compile, dbt test, and a
  Snowflake data audit comparing dev vs prod for changed models. Also supports
  post-merge validation comparing DATA_WAREHOUSE_TEST vs DATA_WAREHOUSE (prod).
  Appends results to the existing code review draft. Trigger on phrases like
  "validate PR #123", "run validation on this PR", "check if PR #123 compiles",
  or "validate in test" / "validate test vs prod" after a merge.
---

# Validate PR Skill

Two modes:

- **Pre-merge** (default): checks out the branch, runs dbt compile/run/test against
  dev, and audits `DATA_WAREHOUSE_DEV` vs `DATA_WAREHOUSE` (prod).
- **Post-merge**: skips dbt steps, audits `DATA_WAREHOUSE_TEST` vs `DATA_WAREHOUSE`
  (prod) for the models changed in the merged PR. Use this after the test DAG
  succeeds. Triggered when the user says "validate in test", "test vs prod", or
  "post-merge validation".

## Inputs

- **PR number**: The GitHub PR number to validate.
- **Mode**: `pre-merge` (default) or `post-merge`.
- **Repo**: Default to `sonos-data-core-dbt`. If the user specifies a different repo, use that.
- **Repo path**: Default to `/Users/avaldez/development/sonos-data-core-dbt`.

---

## Step 0: Determine mode

If mode is **post-merge**, skip Steps 3–6 (no dbt compile/run/test needed — the test
DAG already built the models). Go directly from Step 2 to Step 7, then run the
post-merge audit in Step 8 using `DATA_WAREHOUSE_TEST` as the reference environment
instead of `DATA_WAREHOUSE_DEV`. The audit compares:
- **Test**: `DATA_WAREHOUSE_TEST.{schema}.{model}`
- **Prod**: `DATA_WAREHOUSE.{schema}.{model}`

All other steps (schema mapping, audit logic, output format) are identical.

---

## Step 1: Fetch PR details from GitHub

```bash
gh pr view <pr_number> --repo Sonos-Inc/<repo> \
  --json headRefName,files,body,title \
  --jq '{branch: .headRefName, files: [.files[].path], title: .title, body: .body}'
```

From the file list, extract changed dbt model names:
- Keep only files matching `models/**/*.sql`
- Strip the `models/` prefix, subdirectories, and `.sql` extension to get the model name
- Also record the full file path — you'll need it to derive the Snowflake schema (see Step 7)
- Exclude generated files, seeds, analyses, and snapshots

If no `.sql` model files changed, stop and tell the user there are no dbt models to validate.

Also extract the Jira ticket key from the branch name (e.g. `DATA-17232` from `DATA-17232-some-description`).

---

## Step 2: Fetch Jira ticket context

Using the Jira integration, fetch the ticket identified in Step 1:

```python
from jira_integration import get_client
client = get_client()
issue = client.issue('<ticket_key>')
description = issue.fields.description
summary = issue.fields.summary
```

Use the ticket summary and description to determine the **change type** for each model:
- **Column addition** — PR adds new columns to an existing model, existing logic unchanged
- **Logic change** — existing columns or joins are modified
- **Legacy recreation** — PR is rebuilding a legacy model; ticket will mention the old model name
- **Brand new model** — model does not exist in prod yet

This context drives what audit SQL gets run in Step 8.

---

## Step 3: Check for uncommitted changes

```bash
cd <repo_path> && git status --porcelain
```

If there is any output, **stop immediately** and tell the user:

> "Uncommitted changes detected in `<repo_path>`. Please commit or stash your work before running validation, then try again."

---

## Step 4: Record current branch

```bash
cd <repo_path> && git rev-parse --abbrev-ref HEAD
```

Save this — you will restore it at the end.

---

## Step 5: Fetch and checkout the PR branch

```bash
cd <repo_path> && git fetch origin <branch_name> && git checkout <branch_name>
```

If checkout fails, report the error and stop.

---

## Step 6: Run dbt compile, run, and test (with downstream impact)

### 6a. Compile and run the changed models

```bash
cd <repo_path> && dbt compile -s <model1> <model2> ...
cd <repo_path> && dbt run -s <model1> <model2> ...
cd <repo_path> && dbt test -s <model1> <model2> ...
```

Capture output for each. Note:
- **Compile failure**: CRITICAL — stop, report the error, restore branch, do not run audit
- **dbt run failure**: CRITICAL — model couldn't build in dev, stop and report. If the error
  contains `contract` or `schema_change`, parse and surface the specific column mismatch
  (e.g., "Column `FOO` is in the SQL but missing from the `.yml`") rather than dumping the
  raw dbt error.
- **Test failures**: HIGH — record which tests failed on which models
- **Test pass**: note count of passed tests

### 6b. Compile downstream dependents

After the changed models build successfully, compile their downstream dependents to catch
contract violations or broken references in child models:

```bash
cd <repo_path> && dbt compile -s <model1>+ <model2>+ --exclude <model1> <model2>
```

This runs the `+` (downstream) selector but excludes the models themselves (already built).
If any downstream model fails to compile, report it as **HIGH** — the PR will break a child
model on the next DAG run.

### 6c. Incremental model verification

For any model with `materialized='incremental'` in its config:

1. The `dbt run` in Step 6a was a full refresh (first build in dev). Run it **again** to
   exercise the `is_incremental()` path:

```bash
cd <repo_path> && dbt run -s <incremental_model>
```

2. Compare row counts before and after the second run. If the second run produces the
   exact same row count as the first, the incremental filter is working (no new source
   data = no new rows). If the row count doubles, the `is_incremental()` filter is broken
   or missing — flag as **CRITICAL**.

---

## Step 7: Derive Snowflake table references

For each changed model, derive the dev and prod fully-qualified table names.

### 7a. Parse schema mapping from dbt_project.yml (preferred)

Instead of relying on a hardcoded mapping, parse the schema from `dbt_project.yml`:

```bash
cd <repo_path> && cat dbt_project.yml
```

Look for the `models:` config block. Each subdirectory path maps to a `+schema:` value.
For example:
```yaml
models:
  sonos_data_core:
    warehouse:
      finance:
        +schema: warehouse_finance
```

Build the mapping dynamically from what you find. If parsing fails, fall back to this
hardcoded mapping:

| Model path prefix | Snowflake schema |
|---|---|
| `models/warehouse/finance/` | `warehouse_finance` |
| `models/warehouse/dealer/` | `warehouse_dealer` |
| `models/warehouse/inventory/` | `warehouse_inventory` |
| `models/warehouse/event/` | `warehouse_event` |
| `models/warehouse/mdm/` | `warehouse_mdm` |
| `models/warehouse/survey/` | `warehouse_survey` |
| `models/warehouse/contact/` | `warehouse_contact` |
| `models/warehouse/customer/` | `warehouse_customer` |
| `models/warehouse/bizops/` | `warehouse_bizops` |
| `models/warehouse/worker/` | `warehouse_worker` |
| `models/viz/finance/` | `warehouse_finance` |
| `models/viz/forecast/` | `warehouse_forecast` |
| `models/viz/survey/` | `warehouse_survey` |
| `models/viz/inventory/` | `warehouse_inventory` |
| `models/viz/customer/` | `warehouse_customer` |
| `models/viz/gbs/` | `mart_finance_gbs` |
| `models/viz/worker/` | `warehouse_worker` |
| `models/staging/finance/` | `finance` |
| `models/transformation/finance/` | `finance` |

### 7b. Construct fully-qualified table names

**Pre-merge:**
- **Dev**: `DATA_WAREHOUSE_DEV.{DBT_DW_SCHEMA}_{SCHEMA_UPPERCASE}.{MODEL_UPPERCASE}`
- **Prod**: `DATA_WAREHOUSE.{SCHEMA_UPPERCASE}.{MODEL_UPPERCASE}`

`DBT_DW_SCHEMA` comes from the environment variable of the same name.

**Post-merge:**
- **Test**: `DATA_WAREHOUSE_TEST.{SCHEMA_UPPERCASE}.{MODEL_UPPERCASE}`
- **Prod**: `DATA_WAREHOUSE.{SCHEMA_UPPERCASE}.{MODEL_UPPERCASE}`

---

## Step 8: Run Snowflake data audit

### 8a. Connect to Snowflake

Connect using `snowflake-connector-python` with keypair auth from env vars:

```python
import os
import snowflake.connector
from cryptography.hazmat.primitives.serialization import load_pem_private_key

try:
    with open(os.environ['DBT_SNOWFLAKE_PRIVATE_KEY_PATH'], 'rb') as f:
        private_key = load_pem_private_key(
            f.read(),
            password=os.environ['DBT_PRIVATE_KEY_PASSPHRASE'].encode()
        )

    conn = snowflake.connector.connect(
        account=os.environ['DBT_SNOWFLAKE_ACCOUNT'],
        user=os.environ['DBT_USER'],
        role=os.environ['DBT_ROLE'],
        warehouse=os.environ.get('DBT_WH', 'DATA_ORG_WH_L'),
        private_key=private_key,
    )
except FileNotFoundError:
    # Report: "Private key file not found at $DBT_SNOWFLAKE_PRIVATE_KEY_PATH. Check your .env or dbt profiles.yml."
    # Restore branch and stop.
except KeyError as e:
    # Report: "Missing environment variable: {e}. Required: DBT_SNOWFLAKE_PRIVATE_KEY_PATH, DBT_PRIVATE_KEY_PASSPHRASE, DBT_SNOWFLAKE_ACCOUNT, DBT_USER, DBT_ROLE."
    # Restore branch and stop.
except snowflake.connector.errors.DatabaseError as e:
    # Parse the error and report actionable message:
    #   - "Authentication failed" → "Snowflake auth failed. Check that your private key and passphrase are correct and the key hasn't expired."
    #   - "Role ... does not exist" → "Role {role} not found. Verify DBT_ROLE is set correctly."
    #   - "Warehouse ... does not exist or not authorized" → "Warehouse suspended or inaccessible. Try: ALTER WAREHOUSE DATA_ORG_WH_L RESUME;"
    #   - Other → Surface the raw error message.
    # Restore branch and stop.
```

### 8b. Run audit queries

For each model, run the appropriate audit queries based on the change type from Step 2.
**Every audit type** starts with the grain validation query (8c) before running its
type-specific checks.

### 8c. Grain validation (runs for ALL audit types)

Verify that the declared primary key is actually unique. Extract the PK column(s) from
the model's `.yml` file (look for columns with `unique` and `not_null` tests, or a
`dbt_utils.unique_combination_of_columns` test).

```sql
-- PK uniqueness check
SELECT <pk_col1>, <pk_col2>, COUNT(*) AS cnt
FROM <dev_table>
GROUP BY <pk_col1>, <pk_col2>
HAVING COUNT(*) > 1
ORDER BY cnt DESC
LIMIT 10;
```

If any rows are returned, flag as **CRITICAL** — the grain is broken. Include the top
offending key values in the report so the developer can debug.

For compound PKs, also verify each component individually to narrow down the fan-out source:

```sql
-- Cardinality of each PK component
SELECT 'total_rows' AS metric, COUNT(*) AS val FROM <dev_table>
UNION ALL
SELECT 'distinct_<pk_col1>', COUNT(DISTINCT <pk_col1>) FROM <dev_table>
UNION ALL
SELECT 'distinct_<pk_col2>', COUNT(DISTINCT <pk_col2>) FROM <dev_table>;
```

### Audit A — Column addition (existing model, new columns added)

Verify existing columns are unaffected. Shared columns should have identical row counts,
null rates, and aggregate totals between dev and prod.

```sql
-- 1. Row count comparison
select 'dev' as env, count(*) as row_count from <dev_table>
union all
select 'prod' as env, count(*) as row_count from <prod_table>;

-- 2. For each shared numeric column: sum comparison
select 'dev' as env, sum(<col>) as total from <dev_table>
union all
select 'prod' as env, sum(<col>) as total from <prod_table>;

-- 3. Null rate check on shared columns
select
    'dev' as env,
    count_if(<col> is null) as null_count,
    count(*) as total,
    round(null_count / total * 100, 2) as null_pct
from <dev_table>
union all
select
    'prod' as env,
    count_if(<col> is null) as null_count,
    count(*) as total,
    round(null_count / total * 100, 2) as null_pct
from <prod_table>;
```

Flag as HIGH if row counts differ or existing column sums diverge by more than 0.01%.

### Audit B — Logic change

Same as Audit A, plus:

**Distinct value counts** for key dimension columns to catch unexpected cardinality changes:

```sql
select 'dev' as env, count(distinct <key_col>) as distinct_count from <dev_table>
union all
select 'prod' as env, count(distinct <key_col>) as distinct_count from <prod_table>;
```

**Period-level metric comparison** for time-series models (any model with a date/period
column like `fiscal_period`, `calendar_month`, `period_key`, `posting_date`, etc.):

```sql
-- Period-level sum comparison — catches offsetting errors that net to zero in aggregate
SELECT * FROM (
    SELECT fiscal_period, SUM(<metric>) AS total FROM <dev_table> GROUP BY 1
    MINUS
    SELECT fiscal_period, SUM(<metric>) AS total FROM <prod_table> GROUP BY 1
)
ORDER BY fiscal_period;
```

If any rows are returned, flag as **HIGH** — the aggregate totals may match but individual
periods have drifted. Include the specific periods and delta values in the report.

To identify the date/period column, check the model's SQL or `.yml` for columns named
`fiscal_period`, `fiscal_year_period`, `calendar_month`, `period_key`, `posting_date`,
`effective_date`, or similar. If none exist, skip the period-level check and note it was
skipped because no period column was identified.

### Audit C — Legacy model recreation

Compare the new model output against the legacy model named in the Jira ticket.
Derive the legacy table name from the ticket description.

```sql
-- Row count
select 'new (dev)' as env, count(*) from <dev_table>
union all
select 'legacy (prod)' as env, count(*) from <legacy_prod_table>;

-- Shared column comparison: null rates and distinct counts
-- Run for each column that exists in both models
select 'new' as env, count_if(<col> is null) as nulls, count(distinct <col>) as distinct_vals from <dev_table>
union all
select 'legacy' as env, count_if(<col> is null) as nulls, count(distinct <col>) as distinct_vals from <legacy_prod_table>;

-- Key metric totals (numeric columns)
select 'new' as env, sum(<numeric_col>) from <dev_table>
union all
select 'legacy' as env, sum(<numeric_col>) from <legacy_prod_table>;
```

### Audit D — Brand new model

No prod table to compare against. Validate completeness and integrity:

```sql
-- 1. Row count in new model
select count(*) as row_count from <dev_table>;

-- 2. Null check on primary key
select count_if(<pk_col> is null) as null_pk_count from <dev_table>;

-- 3. Duplicate check on primary key
select count(*) - count(distinct <pk_col>) as duplicate_count from <dev_table>;

-- 4. Sentinel value check (unknown member row present)
select count(*) as unknown_row_count
from <dev_table>
where <pk_col> = 'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF'
   or <integer_pk_col> = -1;
```

**Source completeness check**: Identify the upstream source(s) by reading the model's SQL
for `ref()` or `source()` calls. For each direct upstream source, compare row counts to
verify the new model isn't silently dropping data:

```sql
-- Compare new model row count against upstream source
-- (adjust the source table reference based on what ref()/source() resolves to)
select 'new_model' as label, count(*) as row_count from <dev_table>
union all
select 'upstream_source', count(*) from <upstream_source_table>;
```

If the new model has significantly fewer rows than its source (and there's no obvious
`WHERE` filter or aggregation to explain it), flag as **MEDIUM** and note the delta.
If the model is an aggregate (has `GROUP BY`), this check is informational only — just
report the ratio.

---

## Step 9: Return to original branch

```bash
cd <repo_path> && git checkout <original_branch>
```

Always run this, even if earlier steps failed.

---

## Step 10: Append results to the existing draft

Find the draft in `~/second-brain/code-reviews/PR<pr_number>-*.md` and append.
If no draft exists, print results to terminal and note the 8 AM review hasn't run yet.

For **pre-merge**, append:

```markdown
---

## Validation Results — Pre-merge (Dev vs Prod)

**Run:** <YYYY-MM-DD HH:MM> | **Branch:** `<branch_name>` | **Models validated:** <model1>, <model2>, ...

### dbt compile
✅ All models compiled successfully.
OR ❌ Compile failed — <error>

### dbt run
✅ All models built successfully in dev.
OR ❌ Build failed — <error>
OR ❌ Contract violation — <specific column mismatch details>

### dbt test
**X passed / Y failed / Z errored**

### Downstream compile check
✅ All N downstream models compile successfully.
OR ⚠️ N downstream model(s) failed to compile:
- `<child_model>`: <error summary>

### Incremental verification
_(only shown for incremental models)_
✅ Second run produced expected row count (no duplication).
OR ❌ CRITICAL — Row count doubled on second run: <first_count> → <second_count>. The `is_incremental()` filter is broken.

### Grain Validation

| Model | PK Columns | Unique? | Duplicate rows |
|---|---|---|---|
| <model_name> | <pk_col1, pk_col2> | ✅/❌ | 0 or N |

### Data Audit — <change_type> (Dev vs Prod)

| Check | Dev | Prod | Delta | Status |
|---|---|---|---|---|
| row_count | ... | ... | ... | ✅/⚠️ |
| sum(<metric>) | ... | ... | ... | ✅/⚠️ |
| null_pct(<col>) | ... | ... | ... | ✅/⚠️ |

### Period-Level Comparison
_(only shown for logic changes on time-series models)_

| Period | Dev | Prod | Delta | Status |
|---|---|---|---|---|
| 2026001 | ... | ... | ... | ✅/⚠️ |

<SQL used and any flagged differences with explanation>
```

For **post-merge**, append:

```markdown
---

## Validation Results — Post-merge (Test vs Prod)

**Run:** <YYYY-MM-DD HH:MM> | **DAG:** test DAG succeeded | **Models validated:** <model1>, <model2>, ...

### Grain Validation

| Model | PK Columns | Unique? | Duplicate rows |
|---|---|---|---|
| <model_name> | <pk_col1, pk_col2> | ✅/❌ | 0 or N |

### Data Audit — <change_type> (DATA_WAREHOUSE_TEST vs DATA_WAREHOUSE)

| Model | Check | Test | Prod | Delta | Status |
|---|---|---|---|---|---|
| model_name | row_count | ... | ... | ... | ✅/⚠️ |
| model_name | sum(<metric>) | ... | ... | ... | ✅/⚠️ |
| model_name | null_pct(<col>) | ... | ... | ... | ✅/⚠️ |

### Period-Level Comparison
_(only shown for logic changes on time-series models)_

| Model | Period | Test | Prod | Delta | Status |
|---|---|---|---|---|---|
| model_name | 2026001 | ... | ... | ... | ✅/⚠️ |

<SQL used and any flagged differences with explanation>
```

---

## Important notes

- **Always restore the original branch** (Step 9) even if earlier steps fail.
- **Never run `dbt run` in prod** — only against the dev target.
- If `dbt` is not found, remind the user to activate their virtual environment.
- If the prod table doesn't exist (brand new model), switch to Audit D automatically.
- If the Jira ticket key can't be parsed from the branch name, ask the user for it.
- Limit audit queries to a sample if tables are very large (> 100M rows) — add `LIMIT 1000000` to row-level scans.
- **Snowflake connection errors**: Always catch and surface actionable messages rather than raw tracebacks. Common failures: expired key, wrong role, suspended warehouse, missing env vars.
- **Schema mapping**: Always try to parse `dbt_project.yml` first. The hardcoded fallback table will go stale as new domains are added.
