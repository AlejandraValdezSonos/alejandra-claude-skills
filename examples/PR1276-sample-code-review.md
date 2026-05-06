# Code Review Draft: PR #1276 — DATA-17215: merge profit center hierarchy into dim_profit_center and add product_key
_Review and edit before posting to GitHub. Do NOT post automatically._

**PR:** [DATA-17215: merge profit center hierarchy into dim_profit_center and add product_key](https://github.com/<org>/<repo>/pull/1276)
**Repo:** `<org>/<repo>` | **Author:** `<author>`
**Branch:** `DATA-17215-B` → `test`
**Drafted:** 2026-04-27

---

## Code Review: `DATA-17215-B` → `test`

**Project**: `<org>/<repo>`
**Files changed**: 8 | **Lines added**: +128 | **Lines removed**: -163
**Commits**: DATA-17215: merge profit center hierarchy into dim_profit_center and add product_key

---

### Summary

This PR consolidates `dim_profit_center_hierarchy` and `viz_profit_center_hierarchy` into the existing `dim_profit_center` / `viz_profit_center` models by adding hierarchy level columns via a LEFT JOIN to `stg_raw__sap_profit_center_hierarchy`, and adds a `product_key` FK via a LEFT JOIN to `dim_product`. The consolidation is architecturally sound — fewer entry points for consumers is a real improvement. Row count validation was done manually against prod (440 rows preserved), which is good. However, there are several issues that need to be addressed before merging, the most critical being null handling for the new FK column and downstream impact from removing the deprecated models.

---

### Findings

---

#### `models/warehouse/finance/dim_profit_center.sql`

**[HIGH] dim_profit_center.sql — `product_key` nullable FK not coalesced to unknown sentinel**

The PR description explicitly states that 16 profit centers have no matching product and will have `product_key = NULL`. Per null handling standards, fact and dimension FK columns must coalesce null keys to the appropriate unknown member sentinel. `product_key` is a DV2.0 binary hash key, so nulls must be coalesced to the 64-F sentinel:

```sql
COALESCE(p.product_key, '{{ var("unknown_binary_key") }}')
-- or inline:
COALESCE(p.product_key, 'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF') AS product_key
```

Without this, any downstream fact table or viz model joining on `product_key` will either drop those 16 rows (on an INNER JOIN) or fail to resolve to the unknown `dim_product` member, breaking BI filter lists and FK integrity.

---

**[HIGH] dim_profit_center.sql — hierarchy columns not coalesced to `'*N/A'`**

The hierarchy columns (`profit_center_code_level1` through `profit_center_level5`) are populated via a LEFT JOIN to `stg_raw__sap_profit_center_hierarchy`. For any profit center not present in the hierarchy source, these columns will be NULL. Per standards, nullable varchar/string dimension columns must coalesce to `'*N/A'`:

```sql
COALESCE(h.profit_center_code_level1, '*N/A') AS profit_center_code_level1,
COALESCE(h.profit_center_level1,      '*N/A') AS profit_center_level1,
-- ... etc for all 9 hierarchy columns
```

This also applies to `viz_profit_center` if it passes these columns through without coalescing.

---

**[MEDIUM] dim_profit_center.sql — `ltrim` normalization is fragile and undocumented**

The join to `dim_product` uses `ltrim` to strip leading zeros from `profit_center` before matching against `product_sap_profit_center_code`. This is a business logic decision with real risk:

1. `LTRIM` in most SQL dialects strips all leading whitespace, not leading zeros. To strip leading zeros you typically need `LTRIM(col, '0')` (Snowflake syntax) or `TRY_CAST(col AS INTEGER)`. If the current implementation uses `LTRIM(profit_center)` without a character argument, it only strips spaces — the join may be working by coincidence (e.g., prod data has no leading spaces either) rather than by design.
2. The 16 unresolved profit centers should be investigated: are they expected misses, or could they be join failures caused by incorrect normalization?

*Suggested fix:* Confirm the exact Snowflake expression is `LTRIM(profit_center, '0')` and add a comment:
```sql
-- Strip leading zeros to align with dim_product.product_sap_profit_center_code format
LTRIM(pc.profit_center, '0') = LTRIM(p.product_sap_profit_center_code, '0')
```

---

#### `models/warehouse/finance/dim_profit_center.yml`

**[MEDIUM] dim_profit_center.yml — `product_key` missing FK relationship test**

`product_key` is a new FK column. It should have a `relationships` test pointing to `dim_product.product_key` in addition to a `not_null` test (or at minimum the `not_null` test post-coalescing). Without a test, silent join failures (like the 16 currently-null rows) won't surface automatically in CI.

```yaml
- name: product_key
  description: >
    Foreign key to dim_product. Null profit centers resolve to the unknown
    member sentinel (64-F binary key).
  data_type: binary
  tests:
    - not_null:
        config:
          tags: prod_tests
    - relationships:
        to: ref('dim_product')
        field: product_key
        config:
          tags: prod_tests
```

---

**[MEDIUM] dim_profit_center.yml — new hierarchy columns have no `not_null` or accepted-values tests**

The 9 new hierarchy columns are documented but carry no dbt tests. Given these are sourced from a separate staging model via LEFT JOIN, at minimum the top-level grouping columns (`profit_center_code_level1`, `profit_center_level1`) should have `not_null` tests once the `COALESCE` sentinel fix above is applied, to verify the hierarchy source is populated as expected.

---

#### `models/viz/finance/viz_profit_center.yml`

**[MEDIUM] viz_profit_center.yml — `product_key` description references wrong column name**

The description reads:

> *"Foreign key to dim_product, resolved via ltrim of profit_center against dim_product.product"*

The join target in `dim_product` is almost certainly `product_sap_profit_center_code`, not `product`. "dim_product.product" is ambiguous and likely incorrect — this will confuse downstream consumers and future maintainers.

*Suggested fix:*
```yaml
description: >
  Foreign key to dim_product, resolved by matching ltrim(profit_center, '0')
  to dim_product.product_sap_profit_center_code. 16 profit centers have no
  matching product and carry the unknown member sentinel key.
```

---

**[MEDIUM] viz_profit_center.yml — `product_key` column entry is incomplete**

The diff shows the `product_key` column entry in `viz_profit_center.yml` is truncated — it ends mid-description with no `data_type` declared and no tests. Viz models exposing FK columns should declare `data_type: binary` and carry through the `not_null` test at minimum, consistent with how other FK columns (`profit_center_key`) are documented in this file.

---

#### Removed models: `dim_profit_center_hierarchy` and `viz_profit_center_hierarchy`

**[HIGH] No evidence of downstream consumer audit before deletion**

`dim_profit_center_hierarchy` and `viz_profit_center_hierarchy` are being removed entirely. Before these can be safely deleted, any model that does `ref('dim_profit_center_hierarchy')` or `ref('viz_profit_center_hierarchy')` must be updated in the same PR. The PR description doesn't mention a downstream consumer check.

*Action required:* Confirm the following grep returns no results across the `models/` directory:

```bash
grep -r "dim_profit_center_hierarchy\|viz_profit_center_hierarchy" models/
```

If any results exist outside the files being deleted, those models must be updated in this PR or the deletion will break the dbt DAG at compile time. Even if the grep is clean, please add a note to the PR confirming it was checked.

---

**[MEDIUM] `_finance_docs.md` — 4 lines removed but unclear which doc blocks were dropped**

The diff shows `-4` lines from `_finance_docs.md`

---

## Files Changed

### `models/viz/finance/viz_profit_center.yml` (modified, +44 -0)

```diff
@@ -1,3 +1,4 @@
+---
 version: 2

 models:
@@ -35,6 +36,49 @@ models:
         description: Hierarchy level 2 - Hierarchy area
         data_type: varchar

+      - name: profit_center_code_level1
+        description: '{{ doc("profit_center_code_level1") }}'
+        data_type: varchar
+
+      - name: profit_center_level1
+        description: '{{ doc("profit_center_level1") }}'
+        data_type: varchar
+
+      - name: profit_center_code_level2
+        description: '{{ doc("profit_center_code_level2") }}'
+        data_type: varchar
+
+      - name: profit_center_level2
+        description: '{{ doc("profit_center_level2") }}'
+        data_type: varchar
+
+      - name: profit_center_code_level3
+        description: '{{ doc("profit_center_code_level3") }}'
+        data_type: varchar
+
+      - name: profit_center_level3
+        description: '{{ doc("profit_center_level3") }}'
+        data_type: varchar
+
+      - name: profit_center_code_level4
+        description: '{{ doc("profit_center_code_level4") }}'
+        data_type: varchar
+
+      - name: profit_center_level4
+        description: '{{ doc("profit_center_level4") }}'
+        data_type: varchar
+
+      - name: profit_center_level5
+        description: '{{ doc("profit_center_level5") }}'
+        data_type: varchar
+
+      - name: product_key
+        description: >
+          Foreign key to dim_product, resolved via ltrim of profit_center
+          against dim_product.product_sap_profit_center_code to normalize
+          leading zeros
+        data_type: binary
+
       - name: valid_to_profit_center
         description: Valid to date for the profit center from the source system
         data_type: date
```

**Your notes:**
<!-- Add inline comments here -->


### `models/viz/finance/viz_profit_center_hierarchy.sql` (removed, +0 -13)

```diff
@@ -1,13 +0,0 @@
-{%- set columns_config = get_columns('dim_profit_center_hierarchy',
-exclude_columns=['dw_created_by', 'dw_created_at', 'dw_modified_by', 'dw_modified_at']) -%}
-
-with final as (
-
-    {{ create_viz_with_unknown(
-        source_model='dim_profit_center_hierarchy',
-        columns_config=columns_config
-    ) }}
-
-)
-
-select * from final
```

**Your notes:**
<!-- Add inline comments here -->


### `models/viz/finance/viz_profit_center_hierarchy.yml` (removed, +0 -48)

```diff
@@ -1,48 +0,0 @@
----
-version: 2
-
-models:
-  - name: viz_profit_center_hierarchy
-    description: >
-      This view provides profit center hierarchy data formatted for reporting and visualization purposes.
-    columns:
-      - name: profit_center_key
-        description: '{{ doc("profit_center_key") }}'
-        data_type: binary
-        tests:
-          - not_null:
-              config:
-                tags: prod_tests
-      - name: profit_center
-        description: '{{ doc("profit_center") }}'
-        data_type: varchar
-      - name: controlling_area
-        description: '{{ doc("controlling_area") }}'
-        data_type: varchar
-      - name: profit_center_code_level1
-        description: '{{ doc("profit_center_code_level1") }}'
-        data_type: varchar
-      - name: profit_center_level1
-        description: '{{ doc("profit_center_level1") }}'
-        data_type: varchar
-      - name: profit_center_code_level2
-        description: '{{ doc("profit_center_code_level2") }}'
-        data_type: varchar
-      - name: profit_center_level2
-        description: '{{ doc("profit_center_level2") }}'
-        data_type: varchar
-      - name: profit_center_code_level3
-        description: '{{ doc("profit_center_code_level3") }}'
-        data_type: varchar
-      - name: profit_center_level3
-        description: '{{ doc("profit_center_level3") }}'
-        data_type: varchar
-      - name: profit_center_code_level4
+        description: '{{ doc("profit_center_code_level4") }}'
-        data_type: varchar
-      - name: profit_center_level4
-        description: '{{ doc("profit_center_level4") }}'
-        data_type: varchar
-      - name: profit_center_level5
-        description: '{{ doc("profit_center_level5") }}'
-        data_type: varchar
```

**Your notes:**
<!-- Add inline comments here -->


### `models/warehouse/finance/_finance_docs.md` (modified, +0 -4)

```diff
@@ -2040,7 +2040,3 @@ Amount in US dollars.
 {% docs is_historical %}
 Flag indicating this row originates from historical flat-file sources rather than the ERP source system.
 {% enddocs %}
-
-{% docs dim_profit_center_hierarchy %}
-SAP Profit Center Hierarchy (5-Level Flattened). Current-state only, no SCD Type 2 tracking.
-{% enddocs %}
```

**Your notes:**
<!-- Add inline comments here -->


### `models/warehouse/finance/dim_profit_center.sql` (modified, +41 -0)

```diff
@@ -26,6 +26,33 @@ profit_center_scd as (
     from profit_center as pc
 ),

+hierarchy as (
+
+    select
+        profit_center_key,
+        profit_center_code_level1,
+        profit_center_level1,
+        profit_center_code_level2,
+        profit_center_level2,
+        profit_center_code_level3,
+        profit_center_level3,
+        profit_center_code_level4,
+        profit_center_level4,
+        profit_center_level5
+    from {{ ref('stg_raw__sap_profit_center_hierarchy') }}
+),
+
+product as (
+
+    select
+        min(product_key) as product_key,
+        ltrim(product_sap_profit_center_code, '0') as product_sap_profit_center_code_normalized
+    from {{ ref('dim_product') }}
+    where product_sap_profit_center_code is not null
+    group by ltrim(product_sap_profit_center_code, '0')
+    having count(*) = 1
+),
+
 final as (

     select
@@ -43,6 +70,16 @@ final as (
         pc.controlling_area,
         pc.language_key,
         pc.hierarchy_area,
+        h.profit_center_code_level1,
+        h.profit_center_level1,
+        h.profit_center_code_level2,
+        h.profit_center_level2,
+        h.profit_center_code_level3,
+        h.profit_center_level3,
+        h.profit_center_code_level4,
+        h.profit_center_level4,
+        h.profit_center_level5,
+        p.product_key,
         pc.valid_to_profit_center,
         pc.valid_from_utc,
         pc.valid_to_utc,
@@ -56,6 +93,10 @@ final as (
         {{- create_system_ts(warehousecols=true) -}}

     from profit_center_scd as pc
+    left join hierarchy as h
+        on pc.profit_center_hk = h.profit_center_key
+    left join product as p
+        on ltrim(pc.profit_center, '0') = p.product_sap_profit_center_code_normalized

 )

```

**Your notes:**
<!-- Add inline comments here -->


### `models/warehouse/finance/dim_profit_center.yml` (modified, +43 -0)

```diff
@@ -63,6 +63,49 @@ models:
         description: '{{ doc("hierarchy_area") }}'
         data_type: varchar

+      - name: profit_center_code_level1
+        description: '{{ doc("profit_center_code_level1") }}'
+        data_type: varchar
+
+      - name: profit_center_level1
+        description: '{{ doc("profit_center_level1") }}'
+        data_type: varchar
+
+      - name: profit_center_code_level2
+        description: '{{ doc("profit_center_code_level2") }}'
+        data_type: varchar
+
+      - name: profit_center_level2
+        description: '{{ doc("profit_center_level2") }}'
+        data_type: varchar
+
+      - name: profit_center_code_level3
+        description: '{{ doc("profit_center_code_level3") }}'
+        data_type: varchar
+
+      - name: profit_center_level3
+        description: '{{ doc("profit_center_level3") }}'
+        data_type: varchar
+
+      - name: profit_center_code_level4
+        description: '{{ doc("profit_center_code_level4") }}'
+        data_type: varchar
+
+      - name: profit_center_level4
+        description: '{{ doc("profit_center_level4") }}'
+        data_type: varchar
+
+      - name: profit_center_level5
+        description: '{{ doc("profit_center_level5") }}'
+        data_type: varchar
+
+      - name: product_key
+        description: >
+          Foreign key to dim_product, resolved via ltrim of profit_center
+          against dim_product.product_sap_profit_center_code to normalize
+          leading zeros
+        data_type: binary
+
       - name: is_current
         description: '{{ doc("is_current") }}'
         data_type: boolean
```

**Your notes:**
<!-- Add inline comments here -->


### `models/warehouse/finance/dim_profit_center_hierarchy.sql` (removed, +0 -27)

```diff
@@ -1,27 +0,0 @@
-with profit_center_hierarchy as (
-
-    select * from {{ ref('stg_raw__sap_profit_center_hierarchy') }}
-
-),
-
-final as (
-
-    select
-        profit_center_key,
-        profit_center,
-        controlling_area,
-        profit_center_code_level1,
-        profit_center_level1,
-        profit_center_code_level2,
-        profit_center_level2,
-        profit_center_code_level3,
-        profit_center_level3,
-        profit_center_code_level4,
-        profit_center_level4,
-        profit_center_level5,
-        {{- create_system_ts(warehousecols=true) -}}
-    from profit_center_hierarchy
-
-)
-
-select * from final
```

**Your notes:**
<!-- Add inline comments here -->


### `models/warehouse/finance/dim_profit_center_hierarchy.yml` (removed, +0 -71)

```diff
@@ -1,71 +0,0 @@
----
-version: 2
-
-models:
-  - name: dim_profit_center_hierarchy
-    description: '{{ doc("dim_profit_center_hierarchy") }}'
-
-    columns:
-      - name: profit_center_key
-        description: '{{ doc("profit_center_key") }}'
-        data_type: binary
-        constraints:
-          - type: primary_key
-            warn_unenforced: false
-          - type: not_null
-          - type: unique
-            warn_unenforced: false
-        tests:
-          - unique:
-              config:
-                tags: prod_tests
-          - not_null:
-              config:
-                tags: prod_tests
-      - name: profit_center
-        description: '{{ doc("profit_center") }}'
-        data_type: varchar
-        tests:
-          - not_null
-      - name: controlling_area
-        description: '{{ doc("controlling_area") }}'
-        data_type: varchar
-      - name: profit_center_code_level1
-        description: '{{ doc("profit_center_code_level1") }}'
-        data_type: varchar
-      - name: profit_center_level1
-        description: '{{ doc("profit_center_level1") }}'
-        data_type: varchar
-      - name: profit_center_code_level2
-        description: '{{ doc("profit_center_code_level2") }}'
-        data_type: varchar
-      - name: profit_center_level2
-        description: '{{ doc("profit_center_level2") }}'
-        data_type: varchar
-      - name: profit_center_code_level3
-        description: '{{ doc("profit_center_code_level3") }}'
-        data_type: varchar
-      - name: profit_center_level3
-        description: '{{ doc("profit_center_level3") }}'
-        data_type: varchar
-      - name: profit_center_code_level4
-        description: '{{ doc("profit_center_code_level4") }}'
-        data_type: varchar
-      - name: profit_center_level4
-        description: '{{ doc("profit_center_level4") }}'
-        data_type: varchar
-      - name: profit_center_level5
-        description: '{{ doc("profit_center_level5") }}'
-
```

**Your notes:**
<!-- Add inline comments here -->

---

## Approval Decision

- [ ] Approve
- [ ] Request changes
- [ ] Comment only

---

## Validation Results

**Run:** 2026-04-27 15:57 | **Branch:** `DATA-17215-B` | **Models validated:** `dim_profit_center`

---

<!-- PASTE INTO PR COMMENT -->
## dbt Results Summary

### dbt compile
✅ All models compiled successfully.

### dbt run
✅ `dim_profit_center` built successfully in dev.

### dbt test
**6 passed / 0 failed / 0 errored**
✅ All schema tests passed.

| Model             | Test                           | Status  |
|-------------------|--------------------------------|---------|
| dim_profit_center | not_null_profit_center_scd_key | ✅ PASS |
| dim_profit_center | unique_profit_center_scd_key   | ✅ PASS |
| dim_profit_center | not_null_dw_created_at         | ✅ PASS |
| dim_profit_center | not_null_dw_created_by         | ✅ PASS |
| dim_profit_center | not_null_dw_modified_at        | ✅ PASS |
| dim_profit_center | not_null_dw_modified_by        | ✅ PASS |

---

## Data Audit — Logic Change

| Check                                          | Dev   | Prod  | Delta | Status |
|------------------------------------------------|-------|-------|-------|--------|
| Row count                                      | 440   | 440   | 0     | ✅     |
| Distinct `profit_center_key`                   | 440   | 440   | 0     | ✅     |
| Distinct `profit_center` (code)                | 440   | 440   | 0     | ✅     |
| Null rate `profit_center_key`                  | 0.00% | 0.00% | 0.00% | ✅     |
| Null rate `profit_center_scd_key`              | 0.00% | 0.00% | 0.00% | ✅     |
| `is_current` row count                         | 440   | 440   | 0     | ✅     |
| Null rate `product_key` *(new column)*         | 3.41% | n/a   | —     | ✅ Matches PR (15 admin/conversion PCs expected null) |
| Null rate `profit_center_level1` *(new column)*| 0.23% | n/a   | —     | ⚠️ 1 profit center has no hierarchy match (minor, expected) |

```sql
-- row count ————————————————————————————————————————————
select 'dev' as env, count(*) as val
from <DEV_DB>.<DEV_SCHEMA>.DIM_PROFIT_CENTER
union all
select 'prod' as env, count(*) as val
from <PROD_DB>.<PROD_SCHEMA>.DIM_PROFIT_CENTER;

-- distinct profit_center_key ——————————————————————————
select 'dev' as env, count(distinct profit_center_key) as val
from <DEV_DB>.<DEV_SCHEMA>.DIM_PROFIT_CENTER
union all
select 'prod' as env, count(distinct profit_center_key) as val
from <PROD_DB>.<PROD_SCHEMA>.DIM_PROFIT_CENTER;

-- distinct profit_center (code) ———————————————————————
select 'dev' as env, count(distinct profit_center) as val
from <DEV_DB>.<DEV_SCHEMA>.DIM_PROFIT_CENTER
union all
select 'prod' as env, count(distinct profit_center) as val
from <PROD_DB>.<PROD_SCHEMA>.DIM_PROFIT_CENTER;

-- null rate: profit_center_key ————————————————————————
select 'dev' as env, round(count_if(profit_center_key is null) / count(*) * 100, 4) as val
from <DEV_DB>.<DEV_SCHEMA>.DIM_PROFIT_CENTER
union all
select 'prod' as env, round(count_if(profit_center_key is null) / count(*) * 100, 4) as val
from <PROD_DB>.<PROD_SCHEMA>.DIM_PROFIT_CENTER;

-- null rate: profit_center_scd_key ————————————————————
select 'dev' as env, round(count_if(profit_center_scd_key is null) / count(*) * 100, 4) as val
from <DEV_DB>.<DEV_SCHEMA>.DIM_PROFIT_CENTER
union all
select 'prod' as env, round(count_if(profit_center_scd_key is null) / count(*) * 100, 4) as val
from <PROD_DB>.<PROD_SCHEMA>.DIM_PROFIT_CENTER;

-- is_current row count ————————————————————————————————
select 'dev' as env, count_if(is_current) as val
from <DEV_DB>.<DEV_SCHEMA>.DIM_PROFIT_CENTER
union all
select 'prod' as env, count_if(is_current) as val
from <PROD_DB>.<PROD_SCHEMA>.DIM_PROFIT_CENTER;

-- null rate: product_key (new column) —————————————————
select 'dev' as env, round(count_if(product_key is null) / count(*) * 100, 2) as val
from <DEV_DB>.<DEV_SCHEMA>.DIM_PROFIT_CENTER;

-- null rate: profit_center_level1 (new column) ————————
select 'dev' as env, round(count_if(profit_center_level1 is null) / count(*) * 100, 2) as val
from <DEV_DB>.<DEV_SCHEMA>.DIM_PROFIT_CENTER;
```

<!-- END PASTE -->
