# Memory

## Active Projects
<!-- Updated by heartbeat and daily reflection — list active Jira tickets here -->

## Projects
- [Headcount Normalization — DATA-17211](projects/headcount-normalization.md) — Transfer-based HC normalization: formula, dbt model changes, Streamlit wiring per chart

## Key Decisions
<!-- Data model decisions, naming conventions, architectural choices -->

## Code Review Patterns
<!-- Common findings from reviewing peers' dbt models -->

## Important Facts
<!-- Things to remember across sessions — team context, recurring issues, etc. -->


---
_Reflected from 2026-05-05 on 2026-05-06:_

## Active Projects
- **DATA-17211** — Headcount normalization branch validated: `dbt compile`, `dbt run`, and `dbt test` all passing against `viz_worker_headcount_agg` and `viz_worker_headcount_normalized` in Snowflake. PR #1287 (DATA-17284v2) under review.

## Code Review Patterns
- **Hardcoded date filters** are a recurring risk in finance models — spotted `20230430` hardcoded in `viz_revenue_measures` / GL journal line models (PR #1262, DATA-17232). Flag these in reviews as maintenance/correctness debt.
- **Null-handling at period boundaries** is a specific concern for `transfer_normalization` column in worker headcount models — worth checking in any model that spans fiscal/calendar period edges.
- **`base_unit_of_measure` column propagation** through the fact layer (staging → fact → viz) can silently break if not explicitly carried at each layer — flagged in finance schema PR #1262.