---
name: validate-pr
description: >
  Validates a GitHub PR branch locally by running dbt compile, dbt test, and a
  Snowflake data audit comparing dev vs prod for changed models. Appends results
  to the existing code review draft. Trigger on phrases like "validate PR #123",
  "run validation on this PR", or "check if PR #123 compiles".
---

# Validate PR Skill

Validates a PR branch locally by checking out the branch, running dbt compile,
dbt test, and a Snowflake data quality audit comparing dev output vs production.
Appends all results to the existing code review draft.

## Inputs

- **PR number**: The GitHub PR number to validate.
- **Repo**: Default to `sonos-data-core-dbt`. If the user specifies a different repo, use that.
- **Repo path**: Default to `/Users/avaldez/development/sonos-data-core-dbt`.

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

## Step 6: Run dbt compile and dbt test

```bash
cd <repo_path> && dbt compile -s <model1> <model2> ...
cd <repo_path> && dbt run -s <model1> <model2> ...
cd <repo_path> && dbt test -s <model1> <model2> ...
```

Capture output for each. Note:
- **Compile failure**: CRITICAL — stop, report the error, restore branch, do not run audit
- **dbt run failure**: CRITICAL — model couldn't build in dev, stop and report
- **Test failures**: HIGH — record which tests failed on which models
- **Test pass**: note count of passed tests

---

## Step 7: Derive Snowflake table references

For each changed model, derive the dev and prod fully-qualified table names using the
schema mapping from `dbt_project.yml`:

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

Then construct:
- **Dev**: `DATA_WAREHOUSE_DEV.{DBT_DW_SCHEMA}_{SCHEMA_UPPERCASE}.{MODEL_UPPERCASE}`
- **Prod**: `DATA_WAREHOUSE.{SCHEMA_UPPERCASE}.{MODEL_UPPERCASE}`

`DBT_DW_SCHEMA` comes from the environment variable of the same name.

---

## Step 8: Run Snowflake data audit

Connect using `snowflake-connector-python` with keypair auth from env vars:

```python
import os
import snowflake.connector
from cryptography.hazmat.primitives.serialization import load_pem_private_key

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
```

For each model, run the appropriate audit queries based on the change type from Step 2:

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

Same as Audit A but also check distinct value counts for key dimension columns to
catch unexpected changes in cardinality.

```sql
-- Distinct value count for key columns
select 'dev' as env, count(distinct <key_col>) as distinct_count from <dev_table>
union all
select 'prod' as env, count(distinct <key_col>) as distinct_count from <prod_table>;
```

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

No prod table to compare against. Instead validate completeness vs source:

```sql
-- Row count in new model
select count(*) as row_count from <dev_table>;

-- Null check on primary key
select count_if(<pk_col> is null) as null_pk_count from <dev_table>;

-- Duplicate check on primary key
select count(*) - count(distinct <pk_col>) as duplicate_count from <dev_table>;

-- Sentinel value check (unknown member row present)
select count(*) as unknown_row_count
from <dev_table>
where <pk_col> = 'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF'
   or <integer_pk_col> = -1;
```

---

## Step 9: Return to original branch

```bash
cd <repo_path> && git checkout <original_branch>
```

Always run this, even if earlier steps failed.

---

## Step 10: Append results to the existing draft

Find the draft in `~/second-brain/code-reviews/PR<pr_number>-*.md` and append:

```markdown
---

## Validation Results

**Run:** <YYYY-MM-DD HH:MM>
**Branch:** `<branch_name>`
**Jira:** <ticket_key> — <ticket_summary>
**Models validated:** <model1>, <model2>, ...

### dbt compile
✅ All models compiled successfully.
OR
❌ Compile failed — see error below. Review blocked until fixed.
<error>

### dbt run
✅ All models built successfully in dev.
OR
❌ Build failed — see error below.
<error>

### dbt test
**X passed / Y failed / Z errored**
✅ All schema tests passed.
OR
| Model | Test | Status |
|---|---|---|
| model_name | not_null_pk | ❌ FAILED |

### Data Audit — <change_type>

| Check | Dev | Prod / Legacy | Delta | Status |
|---|---|---|---|---|
| Row count | 1,234,567 | 1,234,567 | 0 | ✅ |
| sum(revenue_amount) | 9,823,441.22 | 9,823,441.22 | 0.00 | ✅ |
| null_pct(cost_center_key) | 0.00% | 0.00% | 0.00% | ✅ |
| distinct(fiscal_period_key) | 48 | 48 | 0 | ✅ |

<Any flagged differences with explanation>
```

If no draft exists, print results to terminal and note the 8 AM review hasn't run yet.

---

## Important notes

- **Always restore the original branch** (Step 9) even if earlier steps fail.
- **Never run `dbt run` in prod** — only against the dev target.
- If `dbt` is not found, remind the user to activate their virtual environment.
- If the prod table doesn't exist (brand new model), switch to Audit D automatically.
- If the Jira ticket key can't be parsed from the branch name, ask the user for it.
- Limit audit queries to a sample if tables are very large (> 100M rows) — add `LIMIT 1000000` to row-level scans.
