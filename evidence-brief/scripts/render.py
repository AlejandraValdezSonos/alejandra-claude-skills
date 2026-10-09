#!/usr/bin/env python3
"""Lint claims.yml and render the five-tab evidence brief.

Usage: python render.py <ticket-folder> [--out FILE] [--lint-only]

<ticket-folder> holds claims.yml and queries/. Exit code 1 on any lint error; warnings print but do
not fail. The checks exist so a number cannot reach the page without a saved source, and so a
stakeholder sign-off cannot be invented by the renderer.
"""
import argparse
import datetime
import html
import os
import re
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "..", "assets")

STATUSES = {"VERIFIED": "st-v", "ASSUMED": "st-a", "UNKNOWN": "st-u"}
AUDIENCES = {"finance", "engineering", "both"}
NON_QUERY_SOURCES = {"code", "slack_message", "jira_search", "test_run"}
FOOTINGS = {"prod", "compiled_pr_over_prod", "dev", "n/a"}
NUMBER = re.compile(r"\d{1,3}(?:,\d{3})+|\d{4,}")

TOP_KEYS = {
    "ticket", "title", "pr", "author", "as_of", "scope", "draft", "provenance", "cards",
    "requirements", "claims", "acceptance_criteria", "expected_results", "regression_checks",
    "finance_validation", "technical_validation", "context", "acceptance_extra_html",
    "context_note_html", "ticket_file",
}
CLAIM_KEYS = {
    "id", "text", "status", "audience", "evidence", "source_query", "source", "source_ref",
    "measured_at", "observed_at", "footing", "check",
}
# Sources that are looked up or read, not run: they carry observed_at (when it was stated or seen),
# not measured_at. Running a query or a test is a measurement and carries measured_at.
OBSERVED_SOURCES = {"code", "slack_message", "jira_search"}
CONTEXT_KEYS = {"id", "fact", "why", "claim", "who", "question", "signed_off_by", "signed_off_date"}


def esc(text):
    return html.escape(str(text if text is not None else ""))


def tag(status):
    return f'<span class="st {STATUSES[status]}">{status}</span>'


def row_class(status):
    return {"VERIFIED": "match", "ASSUMED": "neutral", "UNKNOWN": "gap"}[status]


def load(folder):
    path = os.path.join(folder, "claims.yml")
    with open(path) as fh:
        return yaml.safe_load(fh), path


def lint(data, folder):
    errors, warnings = [], []
    for key in data:
        if key not in TOP_KEYS:
            errors.append(f"unknown top-level key '{key}'")
    for req in ("ticket", "title", "as_of", "claims"):
        if req not in data:
            errors.append(f"missing required key '{req}'")
    claims = {}
    for c in data.get("claims", []) or []:
        cid = c.get("id", "<no id>")
        for key in c:
            if key not in CLAIM_KEYS:
                errors.append(f"claim {cid}: unknown key '{key}'")
        if cid in claims:
            errors.append(f"claim {cid}: duplicate id")
        claims[cid] = c
        status = c.get("status")
        if status not in STATUSES:
            errors.append(f"claim {cid}: status must be one of {sorted(STATUSES)}")
            continue
        if c.get("audience") not in AUDIENCES:
            errors.append(f"claim {cid}: audience must be one of {sorted(AUDIENCES)}")
        if not c.get("text"):
            errors.append(f"claim {cid}: missing text")
        if c.get("footing") is not None and c["footing"] not in FOOTINGS:
            errors.append(f"claim {cid}: footing must be one of {sorted(FOOTINGS)}")
        if status == "VERIFIED":
            if not c.get("evidence"):
                errors.append(f"claim {cid}: VERIFIED needs 'evidence'")
            sq, src = c.get("source_query"), c.get("source")
            if sq:
                if not os.path.exists(os.path.join(folder, sq)):
                    errors.append(f"claim {cid}: source_query '{sq}' does not exist (save the query first)")
                if not c.get("measured_at"):
                    errors.append(f"claim {cid}: a query needs 'measured_at' (the day it was run)")
            elif src:
                if src not in NON_QUERY_SOURCES:
                    errors.append(f"claim {cid}: source must be one of {sorted(NON_QUERY_SOURCES)}")
                if not c.get("source_ref"):
                    errors.append(f"claim {cid}: source '{src}' needs 'source_ref' (what exactly)")
                if src in OBSERVED_SOURCES and not c.get("observed_at"):
                    errors.append(f"claim {cid}: source '{src}' needs 'observed_at' (when it was stated or seen, "
                                  "not the day you read it)")
                if src == "test_run" and not c.get("measured_at"):
                    errors.append(f"claim {cid}: a test_run needs 'measured_at'")
            else:
                errors.append(f"claim {cid}: VERIFIED needs a source_query file or a source")
        elif not c.get("check"):
            errors.append(f"claim {cid}: {status} needs 'check' (the specific check that would settle it)")

    def known(ids, where):
        for i in ids or []:
            if i not in claims:
                errors.append(f"{where}: references unknown claim '{i}'")

    referenced = set()
    for item in data.get("provenance", []) or []:
        if len(str(item.get("text", ""))) > 350:
            warnings.append(f"provenance '{item.get('label')}': {len(item['text'])} characters. Keep each item to a "
                            "sentence or two and put the detail in the claims; this box is the first thing a reader sees")
    if len(data.get("cards", []) or []) > 5:
        warnings.append("more than 5 cards: the headline row loses its point")
    ticket_text = ""
    if data.get("ticket_file"):
        tpath = os.path.join(folder, data["ticket_file"])
        if os.path.exists(tpath):
            ticket_text = re.sub(r"[`*_]", "", open(tpath, errors="ignore").read())
            ticket_text = re.sub(r"\s+", " ", ticket_text).lower()
        else:
            errors.append(f"ticket_file '{data['ticket_file']}' does not exist")

    def needs_source(text, claim_ids, where, has_query=False):
        if NUMBER.search(str(text or "")) and not (claim_ids or has_query):
            errors.append(f"{where}: shows numbers but names no claim (or query) as their source")

    for card in data.get("cards", []) or []:
        if card.get("claim"):
            known([card["claim"]], "card")
            referenced.add(card["claim"])
        needs_source(card.get("num"), [card.get("claim")] if card.get("claim") else [], f"card '{card.get('label')}'")
    for sec in (data.get("requirements") or {}).get("sections", []) or []:
        where = f"requirements section '{sec.get('title')}'"
        known(sec.get("claims"), where)
        referenced.update(sec.get("claims") or [])
        needs_source(sec.get("html"), sec.get("claims"), where)
    for key in ("expected_results", "regression_checks"):
        for r in data.get(key, []) or []:
            where = f"{key} row '{r.get('check')}'"
            if not r.get("claims"):
                errors.append(f"{where}: needs at least one claim (its evidence)")
            known(r.get("claims"), where)
            referenced.update(r.get("claims") or [])
    for ac in data.get("acceptance_criteria", []) or []:
        if ticket_text:
            quoted = re.sub(r"\s+", " ", re.sub(r"[`*_]", "", str(ac.get("text", "")))).lower()
            if quoted[:60] not in ticket_text:
                warnings.append(f"acceptance criterion {ac.get('id')}: not found verbatim in {data['ticket_file']} "
                                "(quote the ticket's wording; do not paraphrase)")
        known(ac.get("claims"), f"acceptance criterion {ac.get('id')}")
        referenced.update(ac.get("claims") or [])
        if not ac.get("claims"):
            errors.append(f"acceptance criterion {ac.get('id')}: needs at least one claim (its evidence)")
    for tab in ("finance_validation", "technical_validation"):
        for b in (data.get(tab) or {}).get("blocks", []) or []:
            where = f"{tab} block '{b.get('title')}'"
            known(b.get("claims"), where)
            referenced.update(b.get("claims") or [])
            qf = b.get("query_file")
            if qf and not os.path.exists(os.path.join(folder, qf)):
                errors.append(f"{where}: query_file '{qf}' does not exist")
            shown = " ".join(str(x) for r in (b.get("table") or {}).get("rows", []) for x in r)
            shown += " " + " ".join(str(b.get(k, "")) for k in ("intro_html", "body_html", "after_html"))
            needs_source(shown, b.get("claims"), where, has_query=bool(qf))
            if not b.get("measured_at"):
                warnings.append(f"{where}: no measured_at")
            wrong = "engineering" if tab == "finance_validation" else "finance"
            for i in b.get("claims") or []:
                if i in claims and claims[i].get("audience") == wrong:
                    warnings.append(f"{where}: claim '{i}' has audience '{wrong}' but sits in "
                                    f"{tab.replace('_', ' ')} (see references/tab-rules.md)")
    for ctx in data.get("context", []) or []:
        cid = ctx.get("id", "<no id>")
        for key in ctx:
            if key not in CONTEXT_KEYS:
                errors.append(f"context {cid}: unknown key '{key}'")
        for need in ("signed_off_by", "signed_off_date"):
            if need not in ctx:
                errors.append(f"context {cid}: key '{need}' must be present (null until signed)")
        if ctx.get("signed_off_by") and not ctx.get("signed_off_date"):
            errors.append(f"context {cid}: signed_off_by is set without signed_off_date")
        if ctx.get("signed_off_date") and not ctx.get("signed_off_by"):
            errors.append(f"context {cid}: signed_off_date is set without signed_off_by")
        if ctx.get("claim"):
            known([ctx["claim"]], f"context {cid}")
            referenced.add(ctx["claim"])
        else:
            warnings.append(f"context {cid}: no linked claim, so no evidence status")
        needs_source(ctx.get("fact"), [ctx["claim"]] if ctx.get("claim") else [], f"context {cid}")
    for cid in claims:
        if cid not in referenced:
            warnings.append(f"claim {cid}: not referenced by any tab (it only appears in Evidence Status)")
    return errors, warnings, claims


def summary(statuses):
    """Heading label for a block or section: one tag when its claims agree, otherwise a count per
    status. A block with nine verified claims and one unknown must not read as UNKNOWN."""
    present = [st for st in ("VERIFIED", "ASSUMED", "UNKNOWN") if st in statuses]
    if len(present) == 1:
        return tag(present[0])
    return " ".join(f"{tag(st)}&times;{statuses.count(st)}" for st in present)


def weakest(statuses):
    order = ["UNKNOWN", "ASSUMED", "VERIFIED"]
    return min(statuses, key=order.index) if statuses else "UNKNOWN"


def table(columns, rows, row_status=None):
    out = ["<table>", "  <tr>" + "".join(f"<th>{esc(c)}</th>" for c in columns) + "</tr>"]
    for i, r in enumerate(rows):
        cls = ""
        if row_status and i < len(row_status) and row_status[i] in STATUSES:
            cls = f' class="{row_class(row_status[i])}"'
        cells = "".join(f"<td>{c if isinstance(c, str) and c.startswith('<') else esc(c)}</td>" for c in r)
        out.append(f"  <tr{cls}>{cells}</tr>")
    out.append("</table>")
    return "\n".join(out)


COMPILED_START = "with v as (\n"


def collapse_compiled(body):
    """A query that starts with `with v as (<compiled model>)` repeats a very large compiled model;
    keep the part a reader needs and name what was collapsed. The end of the model is found by
    matching parentheses (skipping strings and comments), not by guessing at a closing line."""
    if not body.startswith(COMPILED_START):
        return body
    depth, i, n = 1, len(COMPILED_START), len(body)
    while i < n and depth:
        ch = body[i]
        if ch == "'":
            i += 1
            while i < n and body[i] != "'":
                i += 1
        elif body.startswith("--", i):
            while i < n and body[i] != "\n":
                i += 1
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        i += 1
    if depth or body[len(COMPILED_START):i].count("\n") <= 40:
        return body
    lines = body[len(COMPILED_START):i].count("\n") + 1
    note = (f"-- v = the changed model as compiled from the PR over production upstream "
            f"({lines} lines, collapsed; see queries/README.md to regenerate)\n")
    return note + "with v as (<compiled model>)" + body[i:]


def query_box(folder, rel, label="Query"):
    with open(os.path.join(folder, rel)) as fh:
        body = collapse_compiled(fh.read())
    return f'<details><summary>{esc(label)}: <code>{esc(rel)}</code></summary>\n<div class="query-box">{esc(body)}</div>\n</details>'


def legend():
    return (
        '<div class="callout callout-blue"><strong>How to read the labels on this page.</strong>'
        f'<table class="legend"><tr><td>{tag("VERIFIED")}</td><td>Checked against data, code or a primary '
        "source; the evidence and date are named.</td></tr>"
        f'<tr><td>{tag("ASSUMED")}</td><td>Believed true, not checked. Each states the check that would settle it.</td></tr>'
        f'<tr><td>{tag("UNKNOWN")}</td><td>Could not be determined. Stated plainly, not guessed.</td></tr></table></div>'
    )


def render_blocks(section, folder, claims, title, audience_text):
    sec = section or {}
    out = [f"<h1>{esc(title)}</h1>", f"<p><em>{esc(audience_text)}</em></p>", legend()]
    if sec.get("intro_html"):
        out.append(sec["intro_html"])
    for b in sec.get("blocks", []) or []:
        sts = [claims[i]["status"] for i in b.get("claims", []) or []]
        head = esc(b["title"])
        if sts:
            head += " " + summary(sts)
        if b.get("measured_at"):
            head += f' <span class="source-tag">measured {esc(b["measured_at"])}</span>'
        out.append(f"<h2>{head}</h2>")
        if b.get("intro_html"):
            out.append(b["intro_html"])
        t = b.get("table")
        if t:
            out.append(table(t["columns"], t["rows"], t.get("row_status")))
        if b.get("body_html"):
            out.append(b["body_html"])
        if b.get("after_html"):
            out.append(b["after_html"])
        if b.get("query_file"):
            out.append(query_box(folder, b["query_file"]))
    return "\n".join(out)


def evidence_table(claims, number=None):
    out = [f"<h2>{str(number) + '. ' if number else ''}Evidence Status</h2>",
           "<p>Every claim on these pages that someone could act on, with its status. Anything not "
           f'{tag("VERIFIED")} states how it can be settled.</p>',
           '<table>\n  <tr><th style="width:110px">Status</th><th>Claim</th><th>Evidence, or the check that would settle it</th></tr>']
    ordered = sorted(claims.values(), key=lambda c: ["VERIFIED", "ASSUMED", "UNKNOWN"].index(c["status"]))
    for c in ordered:
        if c["status"] == "VERIFIED":
            when = (f"measured {c['measured_at']}" if c.get("measured_at") else f"stated {c['observed_at']}")
            ev = esc(c["evidence"]) + (f' <span class="source-tag">{esc(when)}'
                                       + (f' · {esc(c["footing"])}' if c.get("footing") else "") + "</span>")
        else:
            ev = esc(c["check"])
        out.append(f'  <tr class="{row_class(c["status"])}"><td>{tag(c["status"])}</td><td>{esc(c["text"])}</td><td>{ev}</td></tr>')
    out.append("</table>")
    return "\n".join(out)


def render(data, folder, claims):
    meta = (f'<strong>Ticket:</strong> {esc(data["ticket"])} &nbsp;|&nbsp; '
            + (f'<strong>PR:</strong> {esc(data["pr"])} &nbsp;|&nbsp; ' if data.get("pr") else "")
            + (f'<strong>Author:</strong> {esc(data["author"])} &nbsp;|&nbsp; ' if data.get("author") else "")
            + f'<strong>Data as of:</strong> {esc(data["as_of"])}'
            + (f' &nbsp;|&nbsp; <strong>Scope:</strong> {esc(data["scope"])}' if data.get("scope") else ""))
    prov = ""
    if data.get("draft") or data.get("provenance"):
        items = "".join(f"<li><strong>{esc(p['label'])}:</strong> {esc(p['text'])}</li>" for p in data.get("provenance", []) or [])
        prov = ('<div class="callout callout-yellow"><strong>Internal draft.</strong> Where each set of numbers came from:'
                f"<ul>{items}</ul></div>")
    cards = ""
    if data.get("cards"):
        cards = '<div class="cards">' + "".join(
            f'<div class="card"><div class="num">{esc(c["num"])}</div><div class="lbl">{esc(c["label"])}</div></div>'
            for c in data["cards"]) + "</div>"
    req = ""
    n_sections = 0
    for n_sections, s_ in enumerate((data.get("requirements") or {}).get("sections", []) or [], start=1):
        sts = [claims[i]["status"] for i in s_.get("claims", []) or []]
        req += f"<h2>{n_sections}. {esc(s_['title'])}" + (f" {summary(sts)}" if sts else "") + f"</h2>\n{s_['html']}\n"
    tab1 = (f'<div id="requirements" class="tab-content active">\n<h1>{esc(data["title"])}</h1>\n<p>{meta}</p>\n{prov}\n{legend()}\n{cards}\n{req}\n'
            f"{evidence_table(claims, n_sections + 1)}\n</div>")

    ac_rows = []
    for ac in data.get("acceptance_criteria", []) or []:
        st = weakest([claims[i]["status"] for i in ac["claims"]])
        ac_rows.append([str(ac["id"]), esc(ac["text"]), ac.get("result_html", ""), tag(st)])
    ac_status = [weakest([claims[i]["status"] for i in ac["claims"]]) for ac in data.get("acceptance_criteria", []) or []]
    met = sum(1 for s in ac_status if s == "VERIFIED")
    extra = ""
    for key, title in (("expected_results", "Expected results table (from the ticket)"), ("regression_checks", "Regression check (from the ticket)")):
        rows = data.get(key) or []
        if rows:
            body = []
            for r in rows:
                st = weakest([claims[i]["status"] for i in r["claims"]])
                body.append([r["check"], r["expected"], r.get("measured_html", ""), tag(st)])
            extra += f"<h2>{title}</h2>\n" + table(["What to check", "Ticket expects", "Measured", "Status"], body,
                                                    [weakest([claims[i]["status"] for i in r["claims"]]) for r in rows])
    linked = []
    for item in (data.get("acceptance_criteria") or []) + (data.get("expected_results") or []) + (data.get("regression_checks") or []):
        for cid in item.get("claims") or []:
            sq = claims[cid].get("source_query")
            if sq and sq not in linked:
                linked.append(sq)
    ac_queries = "\n".join(query_box(folder, q_, "Query") for q_ in linked)
    tab2 = ('<div id="acceptance" class="tab-content">\n<h1>Acceptance Criteria</h1>\n'
            f"<p>Quoted from the ticket and mapped to evidence. {met} of {len(ac_status)} are VERIFIED.</p>\n{legend()}\n"
            "<h2>Acceptance criteria</h2>\n"
            + table(["#", "Criterion (from the ticket)", "Result", "Status"], ac_rows, ac_status) + f"\n{extra}\n{ac_queries}\n{data.get('acceptance_extra_html', '')}\n</div>")

    tab3 = ('<div id="finance" class="tab-content">\n'
            + render_blocks(data.get("finance_validation"), folder, claims, "Finance Validation",
                            "Results a stakeholder can read in business terms and check against something they own. Please confirm each looks right, or flag it.")
            + "\n</div>")
    tab4 = ('<div id="technical" class="tab-content">\n'
            + render_blocks(data.get("technical_validation"), folder, claims, "Technical Validation",
                            "Evidence that the build is sound: tests, breaks on purpose, grain and fan-out, contracts. Judged by an engineer.")
            + "\n</div>")

    cards_html, by_who = [], {}
    for c in data.get("context", []) or []:
        st = claims[c["claim"]]["status"] if c.get("claim") else "UNKNOWN"
        if c.get("claim") and st == "VERIFIED":
            ev = f'{claims[c["claim"]]["text"]} Evidence: {claims[c["claim"]]["evidence"]}'
        elif c.get("claim"):
            ev = f'{claims[c["claim"]]["text"]} To settle it: {claims[c["claim"]]["check"]}'
        else:
            ev = "no linked claim"
        if c.get("signed_off_by"):
            sign_tag = '<span class="st st-v">SIGNED OFF</span>'
            sign = f'{esc(c["signed_off_by"])}, {esc(c["signed_off_date"])}'
        else:
            sign_tag = '<span class="st st-a">PENDING</span>'
            sign = "Confirmed by: ____ &nbsp; Date: ____"
        for person in (c["who"] if isinstance(c["who"], list) else [c["who"]]):
            by_who.setdefault(person, []).append((str(c["id"]), bool(c.get("signed_off_by"))))
        cards_html.append(
            f'<div class="fact"><div class="fact-head"><div class="fact-num">{esc(str(c["id"]))}</div>'
            f'<div class="fact-text">{c["fact"]}</div><div class="fact-status">{tag(st)}<br>{sign_tag}</div></div>'
            '<div class="fact-grid">'
            f'<div><h4>Why an agent needs it</h4><p>{esc(c["why"])}</p></div>'
            f'<div><h4>Evidence</h4><p>{esc(ev)}</p></div>'
            f'<div><h4>Who confirms</h4><p>{esc(", ".join(c["who"]) if isinstance(c["who"], list) else c["who"])}</p><p><em>Ask:</em> {esc(c["question"])}</p></div>'
            f'<div><h4>Sign-off</h4><p>{sign}</p></div></div></div>')
    rec = ["<h2>Sign-off record</h2>", table(["Who confirms", "Facts", "Signed off"],
           [[esc(w), esc(", ".join(str(i) for i, _ in rows)), f"{sum(1 for _, ok in rows if ok)} of {len(rows)}"] for w, rows in by_who.items()])]
    tab5 = ('<div id="context" class="tab-content">\n<h1>Context for Agent</h1>\n'
            '<div class="callout callout-yellow"><strong>Read signed-off status first.</strong> A fact is authoritative only when its evidence is '
            f'{tag("VERIFIED")} <em>and</em> a stakeholder has signed it off. Everything else is an open question: say so rather than guess. '
            "The skill that built this page never fills in a sign-off.</div>\n"
            "<h2>How an agent should use this page</h2>\n<ul>"
            f"<li>Treat a fact as <strong>authoritative</strong> only when it is signed off <em>and</em> its evidence is {tag('VERIFIED')}.</li>"
            f"<li>Treat {tag('ASSUMED')} and {tag('UNKNOWN')} facts as open questions. Say so in any answer; do not fill the gap with a plausible guess.</li>"
            "<li>If a request crosses something these facts mark as out of scope or Finance-gated, stop and ask; do not work around it.</li>"
            "<li>Before reusing a number, check the date it was measured. Closed quarters can move.</li></ul>\n"
            "<h2>Facts to confirm with stakeholders</h2>\n"
            + "\n".join(cards_html) + "\n" + "\n".join(rec) + f"\n{data.get('context_note_html', '')}\n</div>")

    css = open(os.path.join(ASSETS, "template.css")).read()
    js = open(os.path.join(ASSETS, "template.js")).read()
    nav = ("<div class=\"tab-nav\">\n"
           "  <button class=\"tab-btn active\" onclick=\"showTab('requirements')\">Finance Requirements</button>\n"
           "  <button class=\"tab-btn\" onclick=\"showTab('acceptance')\">Acceptance Criteria</button>\n"
           "  <button class=\"tab-btn\" onclick=\"showTab('finance')\">Finance Validation</button>\n"
           "  <button class=\"tab-btn\" onclick=\"showTab('technical')\">Technical Validation</button>\n"
           "  <button class=\"tab-btn\" onclick=\"showTab('context')\">Context for Agent</button>\n</div>")
    return (f'<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8">\n<title>{esc(data["ticket"])} — {esc(data["title"])}</title>\n'
            f"<style>\n{css}</style>\n</head>\n<body>\n{nav}\n{tab1}\n{tab2}\n{tab3}\n{tab4}\n{tab5}\n<script>\n{js}</script>\n</body>\n</html>\n")


# ---------------------------------------------------------------------------------------------
# Markdown output: the same brief as plain text, for notes systems and agents that read only .md.
# ---------------------------------------------------------------------------------------------
from html.parser import HTMLParser


class _HtmlToMd(HTMLParser):
    """Small converter for the HTML fragments used in claims.yml (paragraphs, lists, tables, code)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.lists, self.table, self.row, self.cell = [], [], None, None, None
        self.in_query, self.query, self.pending_summary = False, [], None
        self.quote = 0
        self._source_tag_open = False

    def _w(self, t):
        if self.cell is not None:
            self.cell.append(t)
        elif self.in_query:
            self.query.append(t)
        else:
            self.out.append(t)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class", "")
        if tag in ("h1", "h2", "h3", "h4"):
            self._w("\n\n#### ")
        elif tag == "p":
            self._w("\n\n")
        elif tag in ("ul", "ol"):
            self.lists.append(tag)
            self._w("\n")
        elif tag == "li":
            self._w("\n" + "  " * (len(self.lists) - 1) + ("- " if not self.lists or self.lists[-1] == "ul" else "1. "))
        elif tag == "table":
            self.table = []
        elif tag == "tr":
            self.row = []
        elif tag in ("td", "th"):
            self.cell = []
        elif tag == "br":
            self._w(" " if self.cell is not None else "  \n")
        elif tag in ("strong", "b"):
            self._w("**")
        elif tag in ("em", "i"):
            self._w("*")
        elif tag == "code" and not self.in_query:
            self._w("`")
        elif tag == "summary":
            self._w("\n\n**")
        elif tag == "div" and "query-box" in cls:
            self.in_query, self.query = True, []
        elif tag == "div" and "callout" in cls:
            self._w("\n\n> ")
        elif tag == "div":
            self._w("\n\n")
        elif tag == "span" and "st" in cls.split():
            self._w("[")
        elif tag == "span" and "source-tag" in cls.split():
            self._w(" (")
            self._source_tag_open = True

    def handle_endtag(self, tag):
        if tag in ("ul", "ol") and self.lists:
            self.lists.pop()
            self._w("\n")
        elif tag in ("td", "th") and self.cell is not None:
            self.row.append(re.sub(r"\s+", " ", "".join(self.cell)).strip().replace("|", "\\|"))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if self.table is not None:
                self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            rows = [r for r in self.table if r]
            if rows:
                width = max(len(r) for r in rows)
                rows = [r + [""] * (width - len(r)) for r in rows]
                self._w("\n\n| " + " | ".join(rows[0]) + " |\n|" + "---|" * width + "\n")
                for r in rows[1:]:
                    self._w("| " + " | ".join(r) + " |\n")
            self.table = None
        elif tag in ("strong", "b"):
            self._w("**")
        elif tag in ("em", "i"):
            self._w("*")
        elif tag == "code" and not self.in_query:
            self._w("`")
        elif tag == "summary":
            self._w("**\n")
        elif tag == "div" and self.in_query:
            self.in_query = False
            self._w("\n\n```sql\n" + "".join(self.query).strip("\n") + "\n```\n")
        elif tag == "span" and self._source_tag_open:
            self._w(")")
            self._source_tag_open = False

    def handle_data(self, data):
        if self.in_query:
            self.query.append(data)
            return
        data = re.sub(r"\s+", " ", data)
        if data.strip() or (self.cell is not None and data):
            self._w(data)

    def handle_entityref(self, name):
        pass


def html_to_md(fragment):
    # a closing bracket for status chips: <span class="st ...">VERIFIED</span> becomes [VERIFIED]
    fragment = re.sub(r'(<span class="st [^"]*">[^<]*)(</span>)', r"\1]\2", fragment or "")
    conv = _HtmlToMd()
    conv.feed(fragment)
    text = "".join(conv.out)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _md_status(st):
    return f"**{st}**"


def render_markdown(data, folder, claims):
    L = []
    add = L.append
    add(f"# {data['ticket']}: {data['title']}\n")
    meta = [f"Ticket: {data['ticket']}"]
    for key, label in (("pr", "PR"), ("author", "Author"), ("as_of", "Data as of"), ("scope", "Scope")):
        if data.get(key):
            meta.append(f"{label}: {data[key]}")
    add(" | ".join(meta) + "\n")
    add("Status labels: **VERIFIED** = checked against data, code or a primary source (evidence and date named); "
        "**ASSUMED** = believed, not checked (the check is stated); **UNKNOWN** = could not be determined. "
        "A fact is authoritative only when it is VERIFIED **and** signed off by the named stakeholder.\n")
    if data.get("draft"):
        add("> Internal draft.\n")
    if data.get("provenance"):
        add("## Where the numbers came from\n")
        for item in data["provenance"]:
            add(f"- **{item['label']}:** {item['text']}")
        add("")
    if data.get("cards"):
        add("## Headline\n")
        for c in data["cards"]:
            add(f"- **{c['num']}**: {c['label']}")
        add("")
    reqs = (data.get("requirements") or {}).get("sections", []) or []
    if reqs:
        add("## Business context\n")
        for n, sec in enumerate(reqs, 1):
            sts = [claims[i]["status"] for i in sec.get("claims", []) or []]
            add(f"### {n}. {sec['title']}" + (f"  ({', '.join(sorted(set(sts)))})" if sts else "") + "\n")
            add(html_to_md(sec["html"]) + "\n")
    add("## Acceptance criteria (quoted from the ticket)\n")
    add("| # | Criterion | Result | Status |\n|---|---|---|---|")
    for ac in data.get("acceptance_criteria", []) or []:
        st = weakest([claims[i]["status"] for i in ac["claims"]])
        add(f"| {ac['id']} | {ac['text']} | {html_to_md(ac.get('result_html', '')).replace(chr(10), ' ')} | {st} |")
    add("")
    for key, title in (("expected_results", "Expected results (from the ticket)"), ("regression_checks", "Regression check (from the ticket)")):
        rows = data.get(key) or []
        if rows:
            add(f"### {title}\n")
            add("| What to check | Ticket expects | Measured | Status |\n|---|---|---|---|")
            for r in rows:
                st = weakest([claims[i]["status"] for i in r["claims"]])
                add(f"| {r['check']} | {r['expected']} | {html_to_md(r.get('measured_html', '')).replace(chr(10), ' ')} | {st} |")
            add("")
    if data.get("acceptance_extra_html"):
        add(html_to_md(data["acceptance_extra_html"]) + "\n")
    used_queries = []
    for key, title, intro in (("finance_validation", "Finance validation", "Results a stakeholder can read in business terms and confirm."),
                              ("technical_validation", "Technical validation", "Evidence that the build is sound: tests, deliberate breaks, grain checks.")):
        sec = data.get(key) or {}
        add(f"## {title}\n\n{intro}\n")
        if sec.get("intro_html"):
            add(html_to_md(sec["intro_html"]) + "\n")
        for b in sec.get("blocks", []) or []:
            sts = [claims[i]["status"] for i in b.get("claims", []) or []]
            counts = ", ".join(f"{st} x{sts.count(st)}" for st in ("VERIFIED", "ASSUMED", "UNKNOWN") if st in sts)
            add(f"### {b['title']}" + (f"  ({counts})" if counts else "") + (f"  measured {b['measured_at']}" if b.get("measured_at") else "") + "\n")
            if b.get("intro_html"):
                add(html_to_md(b["intro_html"]) + "\n")
            t = b.get("table")
            if t:
                add("| " + " | ".join(t["columns"]) + " |\n|" + "---|" * len(t["columns"]))
                for r in t["rows"]:
                    add("| " + " | ".join(html_to_md(str(x)).replace(chr(10), " ") for x in r) + " |")
                add("")
            if b.get("body_html"):
                add(html_to_md(b["body_html"]) + "\n")
            if b.get("after_html"):
                add(html_to_md(b["after_html"]) + "\n")
            if b.get("query_file"):
                used_queries.append(b["query_file"])
                add(f"Query: `{b['query_file']}` (shown in full under Queries below)\n")
    add("## Context for an agent (facts a stakeholder must confirm)\n")
    add("Authoritative only when VERIFIED **and** signed off. Everything else is an open question: say so, do not guess.\n")
    for c in data.get("context", []) or []:
        st = claims[c["claim"]]["status"] if c.get("claim") else "UNKNOWN"
        if c.get("claim") and st == "VERIFIED":
            ev = f"{claims[c['claim']]['text']} Evidence: {claims[c['claim']]['evidence']}"
        elif c.get("claim"):
            ev = f"{claims[c['claim']]['text']} To settle it: {claims[c['claim']]['check']}"
        else:
            ev = "no linked claim"
        who = ", ".join(c["who"]) if isinstance(c["who"], list) else c["who"]
        sign = f"SIGNED OFF by {c['signed_off_by']} on {c['signed_off_date']}" if c.get("signed_off_by") else "PENDING (not yet confirmed)"
        add(f"### {c['id']}. {html_to_md(c['fact'])}\n")
        add(f"- **Evidence status:** {st}. {ev}")
        add(f"- **Why an agent needs it:** {c['why']}")
        add(f"- **Who confirms:** {who}. Ask: {c['question']}")
        add(f"- **Sign-off:** {sign}\n")
    if data.get("context_note_html"):
        add(html_to_md(data["context_note_html"]) + "\n")
    add("## Evidence status (every claim)\n")
    add("| Status | Claim | Evidence, or the check that would settle it | Date | Footing |\n|---|---|---|---|---|")
    for c in sorted(claims.values(), key=lambda c: ["VERIFIED", "ASSUMED", "UNKNOWN"].index(c["status"])):
        ev = c["evidence"] if c["status"] == "VERIFIED" else c["check"]
        when = c.get("measured_at") or c.get("observed_at") or ""
        add(f"| {c['status']} | {c['text']} | {ev} | {when} | {c.get('footing', '')} |".replace("\n", " "))
    add("")
    # saved queries, in full, because a notes system cannot see the .sql files
    qfiles = list(dict.fromkeys(used_queries + [c["source_query"] for c in claims.values() if c.get("source_query")]))
    if qfiles:
        add("## Queries\n")
        add("Saved SQL behind the verified numbers. A leading `with v as (<compiled model>)` stands for the changed model compiled over production upstream; see `queries/README.md` to regenerate it.\n")
        for q in qfiles:
            path = os.path.join(folder, q)
            if os.path.exists(path):
                add(f"### `{q}`\n\n```sql\n{collapse_compiled(open(path).read()).strip()}\n```\n")
    return "\n".join(L).strip() + "\n"



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--out")
    ap.add_argument("--lint-only", action="store_true")
    ap.add_argument("--no-md", action="store_true", help="do not also write the Markdown version")
    args = ap.parse_args()
    data, path = load(args.folder)
    errors, warnings, claims = lint(data, args.folder)
    for w in warnings:
        print(f"warning: {w}")
    for e in errors:
        print(f"ERROR: {e}")
    if errors:
        print(f"\n{len(errors)} error(s); not rendered.")
        sys.exit(1)
    if args.lint_only:
        print("lint ok")
        return
    out = args.out or os.path.join(args.folder, f"{str(data['ticket']).lower()}-brief-{data['as_of']}.html")
    with open(out, "w") as fh:
        fh.write(render(data, args.folder, claims))
    print(f"rendered {out}")
    if not args.no_md:
        md_out = os.path.splitext(out)[0] + ".md"
        with open(md_out, "w") as fh:
            fh.write(render_markdown(data, args.folder, claims))
        print(f"rendered {md_out}")


if __name__ == "__main__":
    main()
