#!/usr/bin/env python3
"""
Organizes ~/second-brain/code-reviews into completed/<repo>/PR<num>/ and
pending/<repo>/PR<num>/ subfolders, based on live GitHub PR state.

Only ever touches loose *.md files sitting directly in code-reviews/,
code-reviews/pending/, or code-reviews/completed/ (files already inside a
<repo>/PR<num>/ folder are left alone).

Usage:
    python organize_code_reviews.py            # dry run, prints the plan
    python organize_code_reviews.py --apply    # actually moves/removes files
"""
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path.home() / "second-brain" / "code-reviews"
ORG = "Sonos-Inc"

# date-first convention: 2026-09-16-PR1578-round2-sonos-data-core-dbt.md
DATE_FIRST = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})-PR(?P<pr>\d+)(?P<desc>-[a-z0-9-]+?)?-(?P<repo>[a-z0-9-]+)\.md$"
)
# PR-first convention: PR1405-Sonos-Inc-sonos-data-core-dbt-2026-07-27.md
PR_FIRST = re.compile(
    r"^PR(?P<pr>\d+)-Sonos-Inc-(?P<repo>[a-z0-9-]+)-(?P<date>\d{4}-\d{2}-\d{2})\.md$"
)

KNOWN_REPOS = {
    "sonos-data-core-dbt",
    "sonos-data-cleansed-dbt",
    "sonos-data-finance-streamlit",
    "dpe-dispenser-pipeline-definitions",
    "dpe-snowflake-views-dbt",
}


def md5_of(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def parse_filename(name: str):
    m = DATE_FIRST.match(name)
    if m and m.group("repo") in KNOWN_REPOS:
        desc = (m.group("desc") or "").lstrip("-") or None
        return m.group("pr"), m.group("repo"), m.group("date"), desc
    m = PR_FIRST.match(name)
    if m and m.group("repo") in KNOWN_REPOS:
        return m.group("pr"), m.group("repo"), m.group("date"), None
    return None


def gh_state(pr: str, repo: str) -> str:
    try:
        out = subprocess.run(
            ["gh", "pr", "view", pr, "--repo", f"{ORG}/{repo}", "--json", "state"],
            capture_output=True, text=True, timeout=15, check=True,
        )
    except Exception as e:
        print(f"  ! could not check PR{pr} ({repo}) via gh: {e} — leaving in place")
        return "UNKNOWN"
    import json
    return json.loads(out.stdout)["state"]  # OPEN | MERGED | CLOSED


def find_loose_files():
    loose = []
    for sub in ("", "pending", "completed"):
        d = ROOT / sub if sub else ROOT
        if not d.is_dir():
            continue
        for f in d.glob("*.md"):
            loose.append(f)
    return loose


def main():
    apply = "--apply" in sys.argv

    loose = find_loose_files()
    if not loose:
        print("Nothing to do — no loose files found directly in code-reviews/, pending/, or completed/.")
        return

    unparsed = []
    parsed = []  # (path, pr, repo, date, desc)
    for f in loose:
        info = parse_filename(f.name)
        if info is None:
            unparsed.append(f)
        else:
            pr, repo, date, desc = info
            parsed.append((f, pr, repo, date, desc))

    # dedupe by content hash before deciding destinations
    by_hash = {}
    dupes = []
    for item in parsed:
        f = item[0]
        h = md5_of(f)
        by_hash.setdefault(h, []).append(item)
    keep = []
    for h, items in by_hash.items():
        keep.append(items[0])
        for extra in items[1:]:
            dupes.append(extra)

    # resolve state per (pr, repo)
    state_cache = {}
    moves = []
    for f, pr, repo, date, desc in keep:
        key = (pr, repo)
        if key not in state_cache:
            state_cache[key] = gh_state(pr, repo)
        state = state_cache[key]
        if state == "UNKNOWN":
            continue
        bucket = "pending" if state == "OPEN" else "completed"
        fname = f"{date}-{desc}.md" if desc else f"{date}.md"
        dest = ROOT / bucket / repo / f"PR{pr}" / fname
        moves.append((f, dest, state))

    print(f"Found {len(loose)} loose file(s).")
    if dupes:
        print(f"\n{len(dupes)} exact duplicate(s) to remove:")
        for f, pr, repo, date, desc in dupes:
            print(f"  RM  {f.relative_to(ROOT)}  (identical to a kept copy)")
    if unparsed:
        print(f"\n{len(unparsed)} file(s) didn't match a known naming pattern — left untouched, review manually:")
        for f in unparsed:
            print(f"  ?   {f.relative_to(ROOT)}")

    print(f"\n{len(moves)} file(s) to move:")
    for f, dest, state in moves:
        print(f"  MV  {f.relative_to(ROOT)}  ->  {dest.relative_to(ROOT)}   [{state}]")

    if not apply:
        print("\nDry run only. Re-run with --apply to perform these moves.")
        return

    for f, pr, repo, date, desc in dupes:
        f.unlink()
    for f, dest, _ in moves:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            print(f"  ! destination already exists, skipping: {dest.relative_to(ROOT)}")
            continue
        f.rename(dest)

    print("\nDone.")


if __name__ == "__main__":
    main()
