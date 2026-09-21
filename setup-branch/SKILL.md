---
name: setup-branch
description: Set up the second-brain directory structure for a new Jira branch. Use when Alejandra starts working on a new DATA-XXXXX ticket/branch. Triggers on "setup branch", "new branch", "start ticket", "/setup-branch", or when a DATA-XXXXX pattern is mentioned as a new branch being started.
argument-hint: <TICKET-KEY> [repo-name]
---

# Branch Setup Skill

Set up the full second-brain directory structure for a new Jira branch and draft an initial design document from the ticket.

## Parameters

- **`$0`** (required) — Jira ticket key (e.g. `DATA-1234`)
- **`$1`** (optional) — Repository name (e.g. `sonos-dbt`). Defaults to the name of the current working directory.

## Workflow

1. **Validate the ticket key** — Ensure it matches the `DATA-XXXXX` pattern. If not, ask the user to confirm.

2. **Determine the repo name** — Use `$1` if provided. Otherwise use the current working directory name (`basename $PWD`).

3. **Run the branch setup script:**
   ```bash
   ~/.claude/venv/bin/python3 ~/.claude/skills/setup-branch/scripts/create_branch_structure.py <TICKET-KEY> <repo-name>
   ```

4. **Fetch the Jira ticket and draft a design doc:**
   ```bash
   ~/.claude/venv/bin/python3 ~/.claude/scripts/integrations/query.py jira briefing <TICKET-KEY> <repo-name>
   ```

5. **Tell Alejandra what was created** — List the paths of all files and directories created.

6. **Suggest next steps:**
   - Open the design doc and fill in the "Proposed Approach" section
   - Start today's branch log with what you plan to do
   - Run the memory indexer after adding notes: `~/.claude/venv/bin/python3 ~/.claude/scripts/memory_index.py`
