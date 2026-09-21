---
name: create-design-doc
description: Generate a design doc for a Jira ticket and save it to ~/second-brain/development/<TICKET>/design-doc.md. Use when Alejandra provides a ticket key or Jira URL and wants a design doc drafted. Triggers on "create design doc", "draft design doc", "design doc for DATA-XXXXX", "/create-design-doc", or when a Jira URL is provided and a design doc is requested.
argument-hint: <TICKET-KEY or Jira URL>
---

# Create Design Doc Skill

Fetch a Jira ticket, generate a structured design doc, and save it to the second-brain vault.

## Parameters

- **`$0`** (required) — Jira ticket key (e.g. `DATA-1234`) or full Jira URL (e.g. `https://jira.sonos.com/browse/DATA-1234`). Extract the key from a URL if needed.

## Repo Alias Map

When reading Jira ticket text or generated design doc content, resolve these shorthand names to local paths. Ticket descriptions often use informal names — always translate before searching.

| Shorthand in ticket | Local repo path |
|---|---|
| `cleansed`, `cleansed-dbt`, `sonos-data-cleansed-dbt`, `cleansed layer` | `/Users/avaldez/development/sonos-data-cleansed-dbt` |
| `core`, `core-dbt`, `data-core-dbt`, `sonos-data-core-dbt`, `data mart` | `/Users/avaldez/development/sonos-data-core-dbt` |
| `snowflake-views`, `views-dbt`, `dpe-snowflake-views-dbt` | `/Users/avaldez/development/dpe-snowflake-views-dbt` |
| `streamlit`, `finance-streamlit`, `sonos-data-finance-streamlit` | `/Users/avaldez/development/sonos-data-finance-streamlit` |
| `dispenser`, `dpe-dispenser-pipeline-definitions` | `/Users/avaldez/development/dpe-dispenser-pipeline-definitions` |
| `cortex`, `sonos-cortex-semantic-dbt` | `/Users/avaldez/development/sonos-cortex-semantic-dbt` |

> If a ticket references a repo not in this table (e.g. `dlh-dv-poc-dbt`, `dpe-snowflake-admin`), note it as "not cloned locally" in the Model Research section.

## Workflow

### 1. Parse the ticket key

If `$0` is a URL, extract the ticket key from the path:
- `https://jira.sonos.com/browse/DATA-16911` → `DATA-16911`

Validate it matches `DATA-\d+`. If not, ask the user to confirm.

### 2. Run the briefing command

```bash
~/.claude/venv/bin/python3 ~/.claude/scripts/integrations/query.py jira briefing <TICKET-KEY>
```

This will:
- Fetch the Jira ticket (summary, description, status, priority, labels)
- Parse problem statement, investigation plan, out-of-scope, and definition of done from the Jira description
- Use Claude Haiku to generate an Action Plan, Technical Completion checklist, and Business Success Criteria
- Save the design doc to `~/second-brain/development/<TICKET-KEY>/design-doc.md`

### 3. Codebase Research

After the briefing command generates the design doc, **read the file** and extract every dbt model name mentioned (look for patterns like `fact_*`, `dim_*`, `viz_*`, `sat_*`, `hub_*`, `link_*`, `stg_*`, `bridge_*`).

**First, apply the Repo Alias Map** — scan the Jira ticket text and generated design doc for any repo mentions (e.g. "cleansed", "core", "views-dbt") and resolve them using the table above. Note which repos are referenced so you know where to focus the search.

Search all local repos that exist on disk:

```bash
# Find the model SQL file across all repos
find /Users/avaldez/development/sonos-data-core-dbt/models \
     /Users/avaldez/development/sonos-data-cleansed-dbt/models \
     /Users/avaldez/development/dpe-snowflake-views-dbt \
     /Users/avaldez/development/sonos-cortex-semantic-dbt \
     -name "<model_name>.sql" 2>/dev/null

# Find schema YAML entries
grep -rl "<model_name>" \
     /Users/avaldez/development/sonos-data-core-dbt/models \
     /Users/avaldez/development/sonos-data-cleansed-dbt/models \
     /Users/avaldez/development/dpe-snowflake-views-dbt \
     /Users/avaldez/development/sonos-cortex-semantic-dbt \
     --include="*.yml" 2>/dev/null
```

For each model found on disk, read:
1. **The SQL file** — materialization, grain (what one row represents), key columns, joins, any window functions or filters
2. **The schema YAML entry** — existing tests, column descriptions, known constraints

Then run a downstream ref search to find consumers:

```bash
grep -rl "ref('<model_name>')" \
     /Users/avaldez/development/sonos-data-core-dbt/models \
     /Users/avaldez/development/sonos-data-cleansed-dbt/models \
     --include="*.sql" 2>/dev/null
```

Use everything gathered to produce a **Model Research** block and append it to the design doc (before the PR Prep section). Structure it as:

```markdown
---

## Model Research

> Auto-populated from repo on disk. Verify before acting on.

### Model Inventory

| Model | Repo | Layer | Materialization | Change Type | Notes |
|---|---|---|---|---|---|
| `model_name` | sonos-data-core-dbt | viz/finance | table | modify | e.g. adding columns |

### Current State: `<model_name>`

**File:** `models/path/to/model_name.sql`
**Grain:** <what one row represents, inferred from SQL>
**Key columns:** <list of important columns>
**Upstream deps:** `ref('...')`, `ref('...')`

### Downstream Consumers of `<model_name>`

- `downstream_model_a` — `models/viz/finance/downstream_model_a.sql`
- `downstream_model_b` — ...

> ⚠️ Any column rename or removal in `<model_name>` will break these — check them in the PR.

### Models Not Found on Disk

- `model_name` — not found in either repo. May be a new model (brand new build) or in a different repo.
```

**If no model names are mentioned in the ticket**, skip this step and note it in the doc.

**If a model isn't found in either repo**, mark it as likely new and note it in the Model Inventory under "brand new".

### 4. Append a PR Prep section to the design doc

After the briefing command saves the design doc, **read the file** and append the following section to the end. Pre-populate each field from what is already in the doc — do not leave it fully blank. Pull from Problem Statement → business context, Business Success Criteria → expected output, Technical Completion → testing.

```markdown
---

## PR Prep

> Fill in as you work. These fields map directly to the `/create-pr` PR body template.

**What problem does this solve (business context):**
<!-- From Problem Statement above — summarize in 1-2 sentences for a reviewer who hasn't read the ticket -->
<pre-fill from Problem Statement>

**Expected Output:**
<!-- From Business Success Criteria above — what does "done" look like from a stakeholder perspective? -->
<pre-fill from Business Success Criteria>

**What changed:**
<!-- Pre-filled from Model Inventory in Model Research section above — update as you work -->
<pre-fill one bullet per model from Model Inventory, format: `model_name` — <change type and what was done>

**What testing was completed:**
<!-- From Technical Completion above — dbt compile, dbt test, specific test names that must pass -->
<pre-fill from Technical Completion>

**What validation was completed:**
<!-- Snowflake spot-checks, dashboard comparisons, stakeholder sign-off — fill in as you validate -->
- [ ]
```

Write the appended content to `~/second-brain/development/<TICKET-KEY>/design-doc.md` using Edit (not Write, to avoid overwriting the generated content).

### 4. Read and display the full doc

Read `~/second-brain/development/<TICKET-KEY>/design-doc.md` and print its full contents so Alejandra can review it inline.

### 5. Report what was created

Tell Alejandra:
- The file path of the design doc
- That the **Proposed Approach** and **PR Prep** sections may need to be updated as work progresses
- Suggested next steps:
  - Review and fill in any `<!-- ... -->` placeholder sections
  - Run `/setup-branch <TICKET-KEY>` if this is a new branch (creates the full directory structure)
  - Start today's branch log: `~/second-brain/development/<TICKET-KEY>/daily/<today>.md`
  - Update the **What changed** and **What validation was completed** bullets in PR Prep as work is done

## Notes

- Never post to Jira — this is always a draft
- The design doc is saved at `~/second-brain/development/<TICKET-KEY>/design-doc.md` (not in `projects/`)
- If the ticket has no structured description (no `h2.` headers), the problem statement will be the raw description and the Proposed Approach will have placeholders — flag this to Alejandra
- If the Claude generation step fails (no `ANTHROPIC_API_KEY` or network error), the Action Plan / Technical Completion / Business Success Criteria sections will contain placeholder comments — flag this
- The PR Prep section is the source of truth for `/create-pr` — keep it updated as work progresses
