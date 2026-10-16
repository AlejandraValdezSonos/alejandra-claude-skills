---
name: ic-sync
description: Weekly sync of Alejandra's work to the 14 IC2 competencies, and quarterly rollup into check-in drafts. Gathers Jira/GitHub/vault activity, proposes competency tags with evidence, she confirms, confirmed items are saved to ~/second-brain/ic-progress/. Triggers on "ic sync", "tag my week", "ic progress", "quarterly check-in draft", "/ic-sync".
argument-hint: [YYYY-Www | Q4 FY26]   (default: current week)
---

# IC Sync

Tracks progress against the IC2 Guide (Google Sheet "AV: Growth Framework...", tab IC2 Guide). Two modes:
**weekly** (default) and **quarter** (argument looks like `Q4`, `Q4 FY26`, or `rollup`).

## Hard rules
- Read-only toward the outside world. Never write to Jira, GitHub, Slack, Google Sheets/Docs. The only files written are under `~/second-brain/ic-progress/`. Drafts are for Alejandra to paste herself.
- **Every tag cites evidence** (ticket key, PR URL, or vault path). No evidence, no tag. Proposals are ASSUMED until she confirms; only `confirmed` entries feed rollups.
- Never invent outcomes, numbers, or stakeholder reactions. If a claim needs a fact that is not in an item's evidence, leave it out or ask.
- Self-reported items (mentoring, courses, support rotation) are saved as `source: manual` and labeled self-reported in rollups.
- Never carry personal/leave details or anything outside work evidence into drafts.

## Files
- Competencies + IC2 guidance + signals: `~/.claude/scripts/ic_progress/competencies.yml`
- Gather script: `python3 ~/.claude/scripts/ic_progress/gather.py [--week YYYY-Www | --start D --end D] --save --json`
  (raw output lands in `~/second-brain/ic-progress/raw/<label>.json`)
- Weekly file: `~/second-brain/ic-progress/YYYY-Www.md` · Rollups: `~/second-brain/ic-progress/rollups/<FYxx-Qn>.md`
- Style examples: her Q2/Q3 FY26 check-ins in Google Doc `1qDnEVOI6SfJu-i380YQRTTvWb1W9uQ3eNV7kQBcNR4Y` (read via the Drive connector if connected).

Fiscal calendar: FY starts in October. Q1 = Oct-Dec, Q2 = Jan-Mar, Q3 = Apr-Jun, Q4 = Jul-Sep; FY26 = Oct 2025 - Sep 2026.

## Weekly mode
1. Resolve the week (default: current ISO week, Mon -> today). Run gather with `--save --json`; report any `warnings` from it verbatim.
2. Read `competencies.yml` and the existing `ic-progress/YYYY-Www.md` if present. Skip items already `confirmed` or `skipped` (match on entry `id`).
3. Build one **unit per ticket** (ticket + its PRs, reviews, vault files) plus loose units for unlinked PRs (release PRs, others) and daily-note-only items.
4. Propose tags. Start from these rules, then use judgment, reading a PR's changed files (`gh pr view N -R repo --json files`) or ticket/vault text when it settles the question:
   - Review submitted on a PR (`prs_reviewed`) -> `code_review` (high). Reviewing a teammate's design/spike ticket also -> `design_review`.
   - Release PR (`kind: release`) -> `operational_excellence` (high).
   - Authored PR adding/changing models in warehouse/viz/semantic_views, or grain/key/bridge decisions -> `architecture_design` (medium-high).
   - Authored PR adding schema tests or `tests/<domain>/` files, or validation notes/evidence brief -> `testing` (high if files confirm).
   - `design-doc.md` in the ticket's vault folder -> `design_review` (high).
   - Jira `my_role: reporter_only` (she filed it, someone else owns it) -> `kpi_driven` / `prioritization` / `scope` (medium; this is scoping evidence, NOT work done - say so).
   - Spike issue type, or option comparisons / root-cause notes -> `problem_solving` (medium).
   - Work spanning several repos or several teams' models -> `impact` (medium).
   - Addressed review rounds on her own PR (e.g. Bucky/Lili comments) -> `incorporating_feedback` (medium; confirm rounds exist).
   - `language_knowledge`, `coaching_learning_mentoring`, `communication_collaboration`: only when evidence is explicit; otherwise ask in step 6.
   - Tag count: 1-3 per unit. Prefer the best-evidenced ones over covering all 14.
5. Present numbered proposals grouped by ticket, compact:
   `3. DATA-17846 Capture user feedback... [assignee] PR #1649 (authored), 1 vault file`
   `   -> architecture_design (high: new models in models/semantic_views_evaluations), testing (med: yml tests in PR)`
   Mark each tag high/med/low. Reply grammar to tell her: `ok all` | `ok 1-5,8` | `3: +problem_solving -testing` | `skip 6`.
6. After the replies, ask once for things the tools cannot see this week: mentoring/coaching, learning/courses, support rotation, feedback requested or received, stakeholder communication worth recording. Save any as manual entries (no link; ask for the date).
7. Write/merge `ic-progress/YYYY-Www.md`. Format - YAML front matter only, one list:
   ```yaml
   ---
   week: 2026-W42
   window: [2026-10-12, 2026-10-18]
   entries:
     - id: ticket:DATA-17846          # or pr:<org/repo>#<n>, manual:<date>-<slug>
       title: "..."
       source: gather                 # gather | manual
       refs: ["https://...", "second-brain/development/DATA-17846/..."]
       competencies: [architecture_design, testing]
       why: "one line citing the evidence"
       status: confirmed              # confirmed | skipped
   ---
   ```
   Re-running must not duplicate ids; update an existing id in place.
8. Reply with: counts confirmed/skipped, competencies with no evidence this week, and the file path. 3-6 lines.

## Quarter mode
1. Resolve the quarter window. If weekly files exist for it, use their `confirmed` entries. If not (first backfill), run gather for the whole window and run the weekly proposal/confirm flow **per ticket in batches of ~15**, saving as `ic-progress/<FYxx-Qn>-backfill.md` in the same schema.
2. Write `ic-progress/rollups/<FYxx-Qn>.md` containing, using only confirmed entries:
   a. **Recap** - 2-3 first-person, past-tense paragraphs in her voice (see style below). Cover accomplishments, challenges, and development goals, since the Confluence form asks for exactly those. Challenges must come from evidence (blockers, reversals, review findings); if there is none, say "no challenge evidence captured" in the gaps list instead of inventing one.
   b. **Per-competency entries** - for each of the 14, a short cell like her Q3 column: ticket keys/links + 1-2 sentences, ready to paste into the sheet's Q column. Competencies with no confirmed evidence are listed under **Gaps**, not padded.
   c. **Check-In doc sections** - Description/Action per competency in her existing format (status, link list).
   d. **Evidence appendix** - each claim -> its refs, labeled VERIFIED (link/path) or SELF-REPORTED.
3. Show the draft in the reply (recap in full, the rest summarized) and the file path. She edits and pastes herself.

### Voice (from her Q2/Q3 check-ins)
First person, plain, past tense. Names the stakeholders and teams she worked with when the evidence shows them. States what changed and why it mattered in one clause. Honest about what was dropped or cancelled. No superlatives, no "leveraged/spearheaded". Links over adjectives.

## Gotchas learned building gather.py
- PRs opened by the AI Data Engineer workflow are authored by another token with her as assignee; gather already counts them.
- 71 vault code-review drafts are not proof of review; "reviewed" means a review was submitted (GitHub timestamp).
- Reporter-only Jira tickets inflate "tickets worked"; keep them separate.

## Helper scripts (use these; they encode the checks below)
All live in `~/.claude/scripts/ic_progress/`:
- `gather.py` - raw activity for a window (`--week`, `--start/--end`, `--save`). Excludes PRs whose only in-window activity is "updated"; counts PRs assigned to her (AI Data Engineer PRs); tags release PRs `kind: release`; labels Jira tickets `my_role: assignee | reporter_only | referenced`.
- `propose.py <label> [--batch N --size 15]` - applies the tagging rules, enriches PRs with changed files and human-reviewer counts, checks reporter-only tickets' descriptions, writes `raw/<label>-proposals.json`. Unit numbers are indexes into that file; regenerating keeps the order stable.
- `confirm.py <label> --out <file> --ok 1,3-5 --skip 2 [--edit "N:-tag,+tag"] [--note "N:text"] [--group "idxs|id|title|tags|extra refs"] [--fold "N|entry_id"]` - writes confirmed/skipped entries; idempotent by id.

## Extra evidence checks (learned from the Q4 FY26 backfill)
- **Design Review** needs a design that was shared: a Confluence page she created (with HTML guides attached) or a PR description/comment linking the guide. A `design-doc.md` in the vault alone is not enough. Local copies in ~/Downloads and ~/Desktop/avaldez-second-brain are duplicates; count each guide once.
- **Testing**: scan each authored PR's diff (`gh pr diff`) for added test entries in model `.yml` files as well as files under `tests/`.
- **Incorporating feedback**: require commits pushed after the first human (non-bot) review; reviewers `sonos-bucky` and `copilot-pull-request-reviewer` are bots. Commit dates can shift on rebase.
- **Communication / Coaching**: search her own Slack messages with the stakeholders (Leslie Patterson, Heather Jones, Caroline Herlihy, Sarah Arrastia) for the window; store paraphrase and conversation/date only, never message text or customer names.
- **Language Knowledge**: her skills (e.g. /dbt-final-check) count; dated by file creation time, not git history (the skills repo history starts 2026-09-21).
- Check-in format: Quarterly Check-Ins Overview (Confluence PSH 1452967592): informal, Workday text box + attachments, five prompts (progress vs goals, biggest-impact contributions, challenges/support needed, feedback for the manager, development next steps). Submitting locks the Workday task, so save first.
- Rollup writes two cell styles: short (one key + sentence, matching her Q3 cells) and detailed.

## Review app
A Streamlit app in Docker (`~/development/ic-progress-app`, `docker compose up -d`, http://localhost:8501) shows the backfill, rollup and weekly files and saves answers to open items in `ic-progress/review-state.yml`. It reads these files; it does not change them. After running `/ic-sync` or regenerating a rollup, reload the page.

The review app groups files by fiscal quarter (October start): weekly files by `window`, rollups by file name (`rollups/FY27-Q1.md`). Name quarter rollups `<FYxx-Qn>.md` so the app finds them.

## Target level (tracking toward the next level)
`competencies.yml` has `level` (current, e.g. IC2) and `target_level` (e.g. IC3). When `target_level` is set:
- **Weekly mode, after the tag proposals:** for each entry you propose or confirm, check it against the target level's wording for that competency
  (`~/.claude/scripts/ic_progress/levels_de.yml` -> `competencies.<id>.<TARGET>`). Propose a **stretch flag** only when the entry itself
  evidences a specific phrase of the target wording. Be conservative; no flag is better than a stretched one. Append to
  `~/second-brain/ic-progress/stretch-<TARGET>.yml` under `flags:` with `entry` (the entry id), `competency`, `strength` (`strong` = the entry
  directly shows it, `partial` = it points that way), `wording` (the phrase), `why` (one sentence linking the entry's evidence to the phrase),
  `quarter` (fiscal quarter of the entry, e.g. FY27-Q1), `status: proposed`, `proposed_by: Claude (draft)`. Never mark a flag confirmed:
  Alejandra confirms or rejects each one in the app (Path tab), and only confirmed flags count towards suggestions.
- **Quarter mode:** also write `~/second-brain/ic-progress/gap-<TARGET>-<FYxx-Qn>.yml`: per competency `summary`, `matches` (wording, entries,
  strength, note), `gaps`, `unknown` (what the data cannot show), `next` (one idea). Every match must link to confirmed entries. Label the file
  as a draft. Do not claim creativity, independence or mentoring the entries do not show; say "unknown" instead.
- The Sonos Job Leveling Guidelines say they are not a checklist, promotion scorecard or a way to compare people. Keep this a development aid:
  no "meets IC3" verdicts, no scores.
