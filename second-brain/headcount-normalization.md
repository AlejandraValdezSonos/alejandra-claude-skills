# Headcount Normalization — DATA-17211

**Ticket:** DATA-17211
**Date:** 2026-04-20 (updated 2026-05-05)
**Status:** Blocked on PR #1287 (DATA-17284v2) merging — changes requested, see dependency section below

---

## What It Is

Normalized Headcount removes org-transfer noise so each month's headcount is comparable on a like-for-like basis — as if all transfers across the full period had already happened from day one.

**Formula:**
```
Transfer Normalization     = Total net transfers (full period) − Cumulative net transfers to date
Normalized Avg HC          = Average HC + Transfer Normalization
Normalized Ending HC       = Ending HC + Transfer Normalization  (not yet in any model — see gaps)
```

The adjustment shrinks toward zero as you move forward in time. By the final month it equals zero (normalized = raw).

---

## Walkthrough: Finance Management Group

| Month | Ending HC | Cumulative Net Transfers | Total Net (full period) | Normalization | Normalized HC |
|---|---|---|---|---|---|
| M01 Oct | 78 | −2 | −8 | −6 | 72 |
| M02 Nov | 74 | −2 | −8 | −6 | 68 |
| M03 Dec | 71.5 | −4 | −8 | −4 | 67.5 |

Finance had net −8 transfers over the full period. In October, only −2 had happened — so normalization = −8 − (−2) = −6, meaning "6 more net departures are still coming."

**Validated against:** local validation CSV

---

## Key Design Decisions (updated 2026-04-24)

### Two models are required — normalization cannot roll up from cost center grain

Tested whether `sum(normalized_head_count)` from `viz_worker_headcount_agg` (partitioned at `cost_center + ic_band + country`) aggregates correctly to management group level. It does not — differences up to 12,000+ heads for Product Creation vs `viz_worker_headcount_normalized`.

**Root cause:** partitioning window functions at cost center grain and summing to MG level produces incorrect results because the normalization adjustment gets applied independently per cost center partition, not per management group.

**Conclusion:** normalization must be computed at management group grain. `viz_worker_headcount_normalized` (from PR #1287) is the correct model for normalized HC.

### Normalization is employees only

Applies to `headcount_source = 'Employee-Workday'` only. Contingent workers have no transfer keys in Workday so normalization would always be zero. CW data is excluded from `viz_worker_headcount_normalized` intentionally.

### IC band normalization does not exist

Neither model supports normalized headcount broken down by IC band:
- `viz_worker_headcount_normalized` — management group grain only, no IC band
- `viz_worker_headcount_agg` — has normalization columns but at wrong grain for MG roll-up

Transfer keys track cost center changes, not IC band changes. A promotion from IC3 to M4 within the same cost center does not generate a transfer key — so true IC band normalization cannot be derived from the current data.

**If Finance needs IC band normalized numbers (Option B):** requires a new model that distributes MG-level normalization proportionally across IC bands based on average headcount share. This is an approximation, not exact. Scope as a separate ticket and confirm with stakeholder before building.

**Stakeholder question to ask:**
> "The current data model supports normalized headcount at the management group level. Do you also need to see normalized headcount broken down by IC band? If yes, that's additional model work — if no, we can move forward with what's already built."

---

## Dependency: PR #1287 (DATA-17284v2)

PR #1275 was closed; replaced by PR #1287 (`DATA-17284v2`). Adds:
- `viz_worker_headcount_normalized` — new model, management group grain, Employee-Workday only, `slt_member` included
- `transfer_in`, `transfer_out`, `average_head_count`, `transfer_normalization`, `normalized_head_count`, `slt_member` added to `viz_worker_headcount_agg`
- Column names aligned: `fiscal_month`, `fiscal_quarter`, `fiscal_year` (no `_desc` suffix)

**Must merge before DATA-17211 Streamlit work can be completed.**

**Status:** Changes requested (2026-05-05). Outstanding items:
1. Reinstate `normalized_ending_headcount` = `ending_head_count + transfer_normalization` — dropped after a reviewer question; needed for "Ending HC | Normalized" dashboard toggle
2. Rename `normalized_head_count` → `normalized_avg_headcount` in both models for clarity
3. _(handled in DATA-17211)_ Rename all `*_head_count` → `*_headcount` across both models + Streamlit — coordinated cutover, Alejandra will do this in her branch
4. Add `not_null` tests on grain keys for `viz_worker_headcount_normalized`
5. Update `_worker_docs.md`: `transfer_normalization` doc says "null for ADP/NonEmployee" but SQL returns 0

---

## Gaps in `viz_worker_headcount_normalized` vs `viz_worker_headcount_agg`

| Gap | Why needed | Status |
|---|---|---|
| `normalized_ending_headcount` = `ending_head_count + transfer_normalization` | Covers "Ending HC + Normalized" toggle combination | ❌ Dropped in PR #1287 — requested to reinstate |
| `slt_member` | Dashboard groups HC charts by SLT member | ✅ Present in PR #1287 |
| `fiscal_month_desc` → `fiscal_month` | Column name alignment | ✅ Fixed in PR #1287 |
| `fiscal_quarter_desc` → `fiscal_quarter` | Column name alignment | ✅ Fixed in PR #1287 |
| `fiscal_year_desc` → `fiscal_year` | Column name alignment | ✅ Fixed in PR #1287 |
| Rename `*_head_count` → `*_headcount` across both models | Match Finance terminology | 🔜 DATA-17211 — Alejandra will handle with Streamlit cutover |

---

## Dashboard Toggle Design

Two toggles in the HC tab:

**Toggle 1 — HC Metric:**  `Ending HC` / `Avg Ending HC`

**Toggle 2 — View:**  `Reported (Actuals)` / `Normalized`

### Supported combinations

| Toggle 1 | Toggle 2 | Column | Source model |
|---|---|---|---|
| Ending HC | Reported | `ENDING_HEAD_COUNT` | `viz_worker_headcount_agg` |
| Avg Ending HC | Reported | `AVERAGE_HEAD_COUNT` | `viz_worker_headcount_agg` |
| Avg Ending HC | Normalized | `NORMALIZED_AVG_HEADCOUNT` | `viz_worker_headcount_normalized` (rename pending in PR) |
| Ending HC | Normalized | `NORMALIZED_ENDING_HEADCOUNT` | `viz_worker_headcount_normalized` (needs to be added in PR) |

### Model usage per chart type

| Chart type | Model | Notes |
|---|---|---|
| MG-level HC charts (Reported) | `viz_worker_headcount_agg` | `sum(ENDING_HEAD_COUNT or AVERAGE_HEAD_COUNT)` |
| MG-level HC charts (Normalized) | `viz_worker_headcount_normalized` | Direct — already at MG grain |
| IC band breakdown | `viz_worker_headcount_agg` | Always as-reported `ENDING_HEAD_COUNT` — normalization not available at IC band level |
| Headcount Bridge | `viz_worker_headcount_agg` | **Exclude from toggle** — bridge shows movement components, normalizing endpoints without adjusting legs breaks the math |
| Forecast charts | `viz_worker_headcount_forecast_agg` | **Exclude from toggle** — forecast has no transfer keys |

### Streamlit implementation notes

- Load `viz_worker_headcount_normalized` as a separate `load_headcount_normalized_data()` function in `utils.py`
- Toggle 2 (Normalized) is only meaningful for actuals — disable or hide when viewing forecast periods
- When Normalized is selected, IC band charts stay on as-reported `ENDING_HEAD_COUNT` — label clearly
- Headcount Bridge always stays as-reported regardless of toggle state

---

## Notes
- Normalization applies to **actuals only** — forecast data has no transfer keys
- Applies to **employees only** (Workday source) — CWs excluded from `viz_worker_headcount_normalized`
- Original design doc proposed adding normalization directly to `viz_worker_headcount_agg` — this approach was tested and does not produce correct MG-level numbers
