---
name: create-pr
model: claude-opus-4-6
description: Push the current branch and open a pull request against the test branch
argument-hint: "[PR title description]"
---

## Create a Pull Request

You are helping Alejandra push her current branch and create a GitHub pull request. Follow these steps exactly.

### Step 1 — Gather context

Run these in parallel:
- `git branch --show-current` — get the branch name (expected format: `DATA-XXXXX`)
- `git status` — confirm nothing is unstaged
- `git log test..HEAD --oneline` — list commits that will be included in the PR
- `git diff test...HEAD -- '*.sql' '*.yml' '*.yaml'` — summarize what changed

### Step 2 — Confirm clean state

If there are uncommitted changes, stop and tell Alejandra to commit them first. Do not proceed.

### Step 3 — Push the branch

```bash
git push -u origin HEAD
```

### Step 4 — Fetch Jira acceptance criteria

Use the branch name to extract the Jira ticket key (e.g. `DATA-17380` from `DATA-17380-some-description`).

Fetch the ticket from Jira:

```python
from jira_integration import get_client
client = get_client()
issue = client.issue('<ticket_key>')
summary = issue.fields.summary
description = issue.fields.description
acceptance_criteria = issue.fields.customfield_10034  # AC field — may vary
```

Parse the acceptance criteria from the ticket. They are typically in a bulleted or numbered
list format in the description or a dedicated AC field. Extract each criterion as a checklist
item. If no AC field exists, look for a section labeled "Acceptance Criteria", "AC", or
"Definition of Done" in the ticket description.

If no acceptance criteria can be found, note it in the PR body as:
> ⚠️ No acceptance criteria found on `DATA-XXXXX` — add AC to the ticket and update this PR.

### Step 5 — Read the repo's PR template

```bash
cat "$(git rev-parse --show-toplevel)/.github/pull_request_template.md" 2>/dev/null
```

Read the template contents. This is the **authoritative** checklist — always use whatever
is in the file, not a hardcoded copy. The template may change over time and the PR should
always reflect the latest version.

If the file doesn't exist, skip the checklist section entirely and note it in the PR body.

### Step 6 — Draft the PR

**PR title format:** `DATA-XXXXX: <short description>`
- If `$ARGUMENTS` were provided, use them as the description
- Otherwise infer a short description from the Jira summary, commits, and changed files

**PR body** must use the following structure. Fill in each section based on the commits,
diff, and Jira ticket context:

```markdown
## What problem does this solve: (business context)
<why this change was needed — from the Jira ticket summary/description>

## Expected Output:
<what the end result looks like — model changes, dashboard updates, seed refreshes, etc.>

## What changed:
<concise bullet list of files/models changed and what was done>

## What testing was completed?
<dbt tests run, seed tests, compile checks, etc.>

## What validation was completed?
<Snowflake queries, dashboard spot checks, stakeholder sign-off, etc.>

---

## Acceptance Criteria — DATA-XXXXX

<For each AC from the Jira ticket, create a checkbox item. Check it off if the diff
clearly satisfies it. Leave unchecked if it cannot be confirmed from the code alone.>

- [x] <criterion that is met based on the diff>
- [ ] <criterion that needs manual verification or is not yet addressed>

---

<INSERT THE REPO PR TEMPLATE HERE — from Step 5>

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

**Checklist auto-fill rules:**

After inserting the repo's PR template, walk through each checkbox item and auto-check
the ones that can be verified from the diff and repo state. The template uses `- [ ]`
for unchecked items — change to `- [x]` where appropriate.

Items that CAN be auto-checked (verify from the diff):

| Checklist item (substring match) | How to verify | Check if... |
|---|---|---|
| "brief description of the change" | PR body has filled-in "What changed" section | Always ✅ (you wrote it) |
| "matching YML documentation" | Every new `.sql` has a `.yml` entry in the diff | All match |
| "appropriate folders" | New models follow layer prefix (`stg_` in staging, `dim_`/`fact_` in warehouse, `viz_` in viz) | All follow convention |
| "defined in the dbt_project.yml" | New directories have a config block in `dbt_project.yml` | Config exists |
| "dbt contracts enforced" | Warehouse/viz `.yml` files have `data_type` on every column | All complete |
| "model documentation been updated" | Modified `.sql` files have corresponding `.yml` changes in diff | All have `.yml` changes |
| "model testing been updated" | Modified models have test entries in `.yml` changes | Tests present |
| "naming conventions" | Model names follow `stg_`, `dim_`, `fact_`, `viz_`, `int__`, `tra_`, `agg_`, `bridge_` prefixes | All follow convention |

Items that CANNOT be auto-checked (leave unchecked — require manual verification):
- "CI checks passed" — CI hasn't run yet when creating the PR
- "rebased against the latest commit" — requires checking remote state
- "update the appropriate requirements file" — only if new deps were added
- "data loaded successfully" — requires Snowflake verification
- "downstream impact" — requires stakeholder context
- "cleanup steps" — requires deployment knowledge
- "materialization appropriate" — requires judgment call
- "downstream reports and dashboards" — requires exposure knowledge

**Section relevance from the template:** The template has sections "For all new models"
and "For any updated models". Only include a section if it's relevant:
- Include "For all new models" only if the PR contains new model files
- Include "For any updated models" only if the PR modifies existing model files
- Include both if the PR has both new and modified models
- Always include "For all changes"

### Step 7 — Create the PR

Target branch is always `test`.

Show Alejandra the drafted title and full body **before** creating. Ask for confirmation.

```bash
gh pr create --base test --title "<title>" --body "$(cat <<'EOF'
<body content>
EOF
)"
```

### Step 8 — Return the PR URL

Print the PR URL so Alejandra can open it.

### Attaching HTML validation/demo files

When Alejandra asks to attach an HTML file to the PR:

1. **Upload to Confluence** using `confluence_upload_attachment` with the relevant page's `content_id`
2. **Link in the PR body** using the **direct download URL** (not the Confluence page URL):
   ```
   📎 **[filename.html](https://sonosinc.atlassian.net/wiki/download/attachments/<PAGE_ID>/filename.html)** — click to download.
   ```
3. The URL pattern is: `https://sonosinc.atlassian.net/wiki/download/attachments/{page_id}/{filename}`
4. **Do NOT** use the page URL (`https://sonosinc.atlassian.net/wiki/spaces/DATA/pages/{page_id}`) — that goes to the Confluence page, not the file download.

Known Confluence page IDs:
- DD pipeline: `3000959049`
- MSRP design: `2827714593`

### Rules
- Never push to `main` or `master`
- Always target `test` as the base branch
- PR title must include the Jira ticket key (`DATA-XXXXX:`)
- Show Alejandra the drafted title and body **before** creating — ask for confirmation if anything is ambiguous
- Do not squash or amend commits
- Always draft for review — never create the PR without showing the body first
