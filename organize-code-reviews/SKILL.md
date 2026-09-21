---
name: organize-code-reviews
description: Reorganize ~/second-brain/code-reviews so PR review drafts live under completed/<repo>/PR<num>/ or pending/<repo>/PR<num>/ instead of piling up as loose files. Use when the code-reviews or code-reviews/pending folder has loose .md files again, or when Alejandra asks to clean up / tidy / organize code reviews. Triggers on "clean up code reviews", "organize code reviews", "tidy up pending", "/organize-code-reviews".
---

# Organize Code Reviews

Keeps `~/second-brain/code-reviews/` tidy: every PR review draft, comment draft, or validation
note ends up under `completed/<repo>/PR<num>/` or `pending/<repo>/PR<num>/`, grouped by PR so a
PR's full review history (round 1, round 2, comment drafts, validation runs) lives in one folder.

## Why this exists

Review drafts get written straight into `code-reviews/`, `code-reviews/pending/`, or
`code-reviews/completed/` as flat files (e.g. `2026-09-16-PR1578-sonos-data-core-dbt.md` or the
older `PR1578-Sonos-Inc-sonos-data-core-dbt-2026-09-16.md` convention). Nothing ever sorts them
into folders, so all three locations accumulate loose files over time.

## What "done" means

A PR's reviews live in `pending/` while the PR is still `OPEN` on GitHub, and move to `completed/`
once it's `MERGED` or `CLOSED`. This skill checks live state with `gh pr view` — it does not guess
from file age.

## Workflow

1. **Dry run first:**
   ```bash
   ~/.claude/venv/bin/python3 ~/.claude/skills/organize-code-reviews/scripts/organize_code_reviews.py
   ```
   This scans for loose `.md` files directly inside `code-reviews/`, `code-reviews/pending/`, and
   `code-reviews/completed/` (files already sorted into a `<repo>/PR<num>/` folder are left alone),
   and prints:
   - Exact-duplicate files it would remove (byte-identical content only — never guesses).
   - Files it can't confidently parse (unrecognized naming pattern) — these are always left in
     place for manual triage, never moved or deleted.
   - The move plan: source → destination, tagged with the PR's live GitHub state.

2. **Show Alejandra the plan** and ask before applying — these are file moves/deletes across her
   second brain, not reversible via git (the vault isn't a git repo).

3. **Apply, only after confirmation:**
   ```bash
   ~/.claude/venv/bin/python3 ~/.claude/skills/organize-code-reviews/scripts/organize_code_reviews.py --apply
   ```

4. **Report** what moved, what was deduped, and what was left unparsed for her to sort by hand.

## Notes

- Recognizes two filename conventions: `<date>-PR<num>[-<descriptor>]-<repo>.md` and
  `PR<num>-Sonos-Inc-<repo>-<date>.md`. Repo must be one of the known repo slugs in the script —
  add new ones to `KNOWN_REPOS` in `organize_code_reviews.py` as new repos come up rather than
  loosening the pattern match.
- Never overwrites an existing destination file; flags collisions instead of silently clobbering.
- Only deletes files that are byte-identical duplicates of a file it's about to keep.
