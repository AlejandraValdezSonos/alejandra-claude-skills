#!/usr/bin/env python3
"""
Creates the second-brain directory structure for a new Jira branch.
Usage: python create_branch_structure.py <TICKET-KEY> [repo-name]
"""
import sys
import re
from pathlib import Path
from datetime import date

VAULT = Path.home() / "second-brain"


def create_branch_structure(ticket_key: str, repo_name: str):
    ticket_key = ticket_key.upper()

    if not re.match(r'^DATA-\d+$', ticket_key):
        print(f"Error: '{ticket_key}' doesn't match DATA-XXXXX pattern.")
        sys.exit(1)

    today = date.today().isoformat()
    ticket_dir = VAULT / "development" / ticket_key
    daily_dir = ticket_dir / "daily"

    # Create directories
    daily_dir.mkdir(parents=True, exist_ok=True)

    created = []

    # Design doc at ticket root (placeholder — filled by jira briefing command)
    design_doc = ticket_dir / "design-doc.md"
    if not design_doc.exists():
        design_doc.write_text(
            f"# Design Doc: {ticket_key}\n\n"
            f"_Run `/setup-branch {ticket_key} {repo_name}` to populate from Jira._\n\n"
            f"## Problem Statement\n\n\n"
            f"## Proposed Approach\n\n\n"
            f"## Key Design Decisions\n\n\n"
            f"## Acceptance Criteria\n\n\n"
            f"## Open Questions\n\n"
        )
        created.append(str(design_doc))

    # Today's daily log — repo as H2 section within the file
    daily_log = daily_dir / f"{today}.md"
    if daily_log.exists():
        # Append new repo section to existing log for today
        existing = daily_log.read_text()
        if f"## {repo_name}" not in existing:
            daily_log.write_text(
                existing.rstrip() + f"\n\n## {repo_name}\n\n"
                f"### Plan for Today\n\n\n"
                f"### Key Findings\n\n\n"
                f"### Decisions Made\n\n\n"
                f"### Blockers\n\n\n"
                f"### Next Steps\n\n"
            )
            created.append(f"{str(daily_log)} (appended ## {repo_name} section)")
        else:
            print(f"  (## {repo_name} section already exists in {today}.md — skipped)")
    else:
        daily_log.write_text(
            f"# {ticket_key} — {today}\n\n"
            f"**Ticket:** [[development/{ticket_key}/design-doc|{ticket_key}]]\n\n"
            f"## {repo_name}\n\n"
            f"### Plan for Today\n\n\n"
            f"### Key Findings\n\n\n"
            f"### Decisions Made\n\n\n"
            f"### Blockers\n\n\n"
            f"### Next Steps\n\n"
        )
        created.append(str(daily_log))

    print(f"Branch structure ready for {ticket_key} in repo '{repo_name}':")
    for path in created:
        print(f"  Created: {path}")
    if not created:
        print("  (directories already exist — no files overwritten)")

    print(f"\nTicket dir: {ticket_dir}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: create_branch_structure.py <TICKET-KEY> [repo-name]")
        sys.exit(1)

    ticket_key = sys.argv[1]
    repo_name = sys.argv[2] if len(sys.argv) > 2 else Path.cwd().name
    create_branch_structure(ticket_key, repo_name)
