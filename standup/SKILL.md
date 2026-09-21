---
name: standup
description: Draft a daily standup update from yesterday's branch and daily logs. Use when Alejandra asks for standup prep, "what did I do yesterday", or "/standup". Reads active branch logs and MEMORY.md to generate a concise standup.
argument-hint: [TICKET-KEY]
---

# Daily Standup Skill

Draft a standup update based on yesterday's work logs and today's plan.

## Parameters

- **`$0`** (optional) — Jira ticket key to focus on (e.g. `DATA-1234`). If omitted, scans all active branches.

## Workflow

1. **Read MEMORY.md** — Load active projects section to know which tickets are in flight.

2. **Read yesterday's logs** — For each active ticket (or the specified one):
   - `~/second-brain/projects/<repo>/<ticket>/daily/<yesterday>.md`
   - `~/second-brain/daily/<yesterday>.md`

3. **Read today's branch log** (if it exists) — To see if there's already a plan for today.

4. **Draft the standup** in this format:

```
## Standup — <today's date>

**Yesterday:**
- [What was worked on, key findings, decisions made]

**Today:**
- [Planned work based on open questions and next steps from yesterday's log]

**Blockers:**
- [Any blockers from yesterday's log, or "None"]
```

5. **Save the draft** to `~/second-brain/drafts/active/standup-<date>.md` for review.

6. **Print the draft** to the screen so Alejandra can copy it directly.

## Notes
- Keep it concise — standup format means 2-3 bullet points per section max
- Use the ticket key in the "Yesterday/Today" bullets (e.g. "DATA-1234: ...")
- Never post or send — this is always a draft for Alejandra to use manually
