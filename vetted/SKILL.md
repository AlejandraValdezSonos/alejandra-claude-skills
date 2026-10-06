---
name: vetted
description: >
  Investigate → adversarially verify → present only what survived. Runs an investigator
  agent to gather primary evidence for a question (bug, design decision, source behavior,
  ticket scope), then a fresh-context skeptic agent that tries to refute each finding, and
  returns a decision-ready brief where every claim is labeled and every recommendation is
  approved or blocked. Use when a wrong answer would cost real time — designing a ticket,
  debugging a model, or answering a stakeholder. Triggers on "vet this", "verify this
  before you tell me", "/vetted", "is this actually true", "design this ticket properly",
  or any question where Alejandra has already pushed back on unverified claims.
---

# Vetted

Purpose: stop the loop where a recommendation arrives, Alejandra asks "did you actually
check that," and the session restarts. Nothing reaches her here until an independent agent
has tried to kill it.

**Run the phases without asking permission between them.** Local reads, greps, `dbt
compile`, and read-only Snowflake queries are pre-authorized. The only stop is the final
decision, which is hers.

## Phase 0 — Decompose

Turn the request into a numbered list of **discrete, checkable claims**. Not topics —
claims that can be true or false.

Bad: "understand how pricing conditions join."
Good: "(1) `condition_access_hk` is unique per row in `v_pricing_conditions`.
(2) `sat_pricing_condition` has exactly one row per `pricing_condition_hk` per load date.
(3) rows with NULL `material_nk` exist in the raw source, not just post-join."

Show this list before investigating. If the request is genuinely one claim, say so and
move on — do not inflate it.

## Phase 1 — Investigate

Spawn the **investigator** agent (`subagent_type: "investigator"`). For a multi-part
question, spawn one per independent claim cluster, in a single message so they run
concurrently. Give each agent:

- the specific claims it owns
- the repo path and branch
- which methodology applies (`sonos-data-core-dbt` → Kimball, `sonos-data-cleansed-dbt`
  → Data Vault)
- the Snowflake access pattern (Python connector, private key **object**, warehouse
  `DATA_ORG_WH`, source tables in `ODS.REF`)

## Phase 2 — Adversarial verification

Spawn the **skeptic** agent (`subagent_type: "skeptic"`) — **a fresh spawn, never a
fork.** It must not inherit the investigator's context or it will inherit its assumptions.

Hand it: the claim list, each claim's STATUS, its EVIDENCE, its HOW TO REPRODUCE, and the
RECOMMENDATION. Nothing else — no narrative framing, no "I think this is right."

For a recommendation that is expensive to get wrong (schema change, PR-bound design, or
anything going to a stakeholder), spawn **two or three skeptics with different lenses** —
e.g. one on grain/uniqueness, one on data correctness at the source, one on methodology
compliance — concurrently. Majority REFUTED/UNSUPPORTED on a load-bearing claim blocks the
recommendation.

## Phase 3 — Reconcile

Do not just relay the skeptic. Reconcile:

- **CONFIRMED** → keep, with evidence.
- **REFUTED** → drop the claim *and* anything that rested on it. Say what died and why.
- **UNSUPPORTED** → if you can settle it with a query or read **right now, do it** and
  re-verify. Only escalate to her what genuinely cannot be settled locally.
- If the skeptic BLOCKED the recommendation: do not present the blocked recommendation as
  an option. Either fix it and re-run Phase 2, or report that the question isn't settled
  and what's needed.

Loop Phase 1→3 again if the skeptic's MISSED list opens real ground. Two rounds max, then
report honestly where it stands.

## Output — what Alejandra actually sees

Keep it short. She is reviewing decisions, not reading a transcript.

```markdown
## Recommendation
<the action, one or two sentences>  — skeptic verdict: APPROVED / APPROVED WITH CONDITIONS

### Rests on (verified)
- [VERIFIED] <claim> — <evidence: query result / file:line> — reproduced by skeptic

### Needs your decision
- <the specific open question, with my recommended answer>

### Dropped in verification
- <claim> — refuted because <reason>   ← include this; it's how she knows vetting ran

### Still unknown
- <claim> — cannot be settled locally because <reason>
```

Nothing appears under "Rests on" that a skeptic did not independently reproduce. If that
section is empty, the honest output is "not settled yet" — say that instead of
manufacturing confidence.

## After the run

If this was ticket work under a `DATA-XXXXX` branch, append the vetted findings to
`~/second-brain/development/<TICKET>/execution-log.md` and update the design doc if a
verified finding changed the design. Do not create new doc files — update the existing
four.
