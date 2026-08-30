# ADR-002: Catalog representation for multi-country same-name suppliers

**Status:** Accepted
**Date:** 2026-08-31
**Authors:** AI (AIQ-2195)
**Supersedes:** (none)
**Related:** AIQ-2095 (PRs #2125, #2133, #2135) — the promotion path this is a residual of

---

## Context

`public.service_catalog_items` is the master catalog every employee-facing surface reads
(HR vendor curation, the `vendor_proposal` seed, and the employee recommendations filter all
resolve masters by `supplier_id` / `external_id`; none read the supplier registry directly).

It carries a case-insensitive uniqueness guard:

```sql
CREATE UNIQUE INDEX uq_service_catalog_items_category_name_ci
    ON public.service_catalog_items (category, lower(trim(name)));
```

This index is deliberate — it fixed the "three Dublins" duplication (a `seed-twice` bug that
produced multiple masters for one supplier and hid curated vendors;
`20260925000000_dedupe_service_catalog_items.sql`). It must not simply be dropped.

The side effect: a supplier that serves **multiple countries under one name** can hold only
**one** master row, and is therefore offerable to employees in only **one** of the countries it
actually serves. The AIQ-2095 promotion writer
(`supplier_registry._ensure_catalog_master_for_capability`) already computes a per-country
`external_id` (`registry:{supplier}:{category}:{country}`), but its "keep the single
`(category,name)` master" branch returns without inserting a second row, so the master keeps
the `country` of whichever capability was **approved first**.

### Affected production rows (2026-08-31)

Approved capabilities where one supplier + category spans >1 distinct `country_code` under a
single name:

```sql
WITH multi AS (
  SELECT ssc.supplier_id, lower(btrim(ssc.service_category)) AS category,
         count(DISTINCT ssc.country_code) AS n_countries,
         string_agg(DISTINCT ssc.country_code, ',' ORDER BY ssc.country_code) AS approved_countries
  FROM supplier_service_capabilities ssc
  WHERE ssc.platform_vetting_status = 'approved'
    AND ssc.country_code IS NOT NULL AND btrim(ssc.country_code) <> ''
  GROUP BY ssc.supplier_id, lower(btrim(ssc.service_category))
  HAVING count(DISTINCT ssc.country_code) > 1
)
SELECT m.supplier_id, s.name, m.category, m.n_countries, m.approved_countries,
       sci.id AS master_id, sci.country AS master_country
FROM multi m
JOIN suppliers s ON s.id = m.supplier_id
LEFT JOIN service_catalog_items sci
       ON sci.supplier_id = m.supplier_id AND lower(btrim(sci.category)) = m.category;
```

| Supplier | Category | Approved for | Master tagged | Invisible to |
|---|---|---|---|---|
| AGS France (SOFDI) | movers | DE, NO | `DE` | NO |
| All World Transport | movers | DE, FR | `DE` | FR |
| Grospiron International | movers | DE, NO | `DE` | NO |

Three rows today (the ticket's "3 of 67 orphaned"); the separate country-mismatch case was
already neutralised to a graceful no-op by #2135. The count grows as corridors are added.

### The two serving readers diverge

- **`vendor_proposal`** (`backend/app/services/vendor_proposal.py`) already serves a
  country-agnostic master correctly: its predicate is
  `sci.country = :dest OR (sci.country IS NULL AND a supplier-linked approved capability with
  ssc.country_code = :dest or 'global')`. A `country IS NULL` master reaches **each** country
  its capabilities cover, and no others.
- **`employee_recommendations_filter._serves_destination`** gates only on the master's **own**
  `city`/`country` (`m_country == d_country`, else pass-through). A `country IS NULL` master
  therefore passes for **any** destination — it does not consult the supplier's capabilities.

This divergence is what decides the options below.

## Options considered

| Axis | A · per-country key | B · country-agnostic (`NULL`) | C · accept the limit |
|---|---|---|---|
| Idea | Widen the index to `(category, lower(trim(name)), country)` → one master per country | One master with `country = NULL` for multi-country suppliers; rely on the capability `country_code` gate at serving time | Keep one-per-name; document that these suppliers are offerable in one country only |
| Migration cost | **High** — rebuild a unique index on a hot table; must use `COALESCE`/`NULLS NOT DISTINCT` or `NULL`-country rows re-duplicate | **Low** — no schema change; `NULL` 3 rows + 1 reader fix | None |
| Reopens "three Dublins"? | **Risk** — and every `(category,name)` finder (`find_master_by_category_name`, the writer's own link path) now returns N rows and must learn `country` | **No** — index untouched | No |
| Served for *each* country? | Yes | **Yes**, once `_serves_destination` gates `NULL` masters on capability `country_code` (vendor_proposal already does) | **No** — one country only |
| HR curation UX | N rows per supplier (per-country control, more clutter) | **1 row per supplier** — coverage stays in capabilities, consistent with the existing model | 1 row, wrong/missing coverage |

## Decision

**Adopt Option B — the country-agnostic master.**

Per-country coverage is *already* modelled by `supplier_service_capabilities.country_code` and
*already* read by the serving layer. Option A duplicates that coverage into the catalog identity
key and drags a hot-table index migration plus a finder-wide change behind it, with a real risk
of reopening the duplication the index exists to prevent. Option B keeps the anti-duplication
guard intact, requires no schema change, and the primary serving path (`vendor_proposal`)
already behaves correctly for it.

## Consequences

- The `(category, lower(trim(name)))` unique index and the "three Dublins" protection are
  unchanged.
- A multi-country same-name supplier is represented by **one** master whose `country` is `NULL`;
  which countries it reaches is derived from its approved capabilities at serve time.
- **`_serves_destination` must be fixed in the same change.** Today those 3 rows are tagged `DE`,
  so the HR-curation gate surfaces them only for DE. Nulling `country` without teaching that gate
  to consult capabilities would let them over-surface for destinations the supplier does not
  cover. This reader fix is a hard precondition of the data change, not a nice-to-have.
- `external_id` stays `registry:{supplier}:{category}:{firstCountry}`. It is cosmetically stale
  once the row is country-agnostic but remains unique and correct as a key; regenerating it is
  optional cleanup, not required.

## Remediation plan (the scoped follow-up ticket)

One ticket, shipped atomically — no schema/index change:

1. **Writer** (`supplier_registry._ensure_catalog_master_for_capability`): when a *second
   distinct* approved-capability country appears for the same linked supplier under one
   `(category,name)` master, set the master's `country = NULL` (country-agnostic) instead of
   leaving the first country in place.
2. **Reader** (`employee_recommendations_filter._serves_destination`): when a master's
   `country IS NULL`, gate it on the linked supplier's approved-capability `country_code`
   (mirror `vendor_proposal`'s behaviour) rather than passing it through for every destination.
3. **Backfill** (idempotent, data-only — no DDL, runnable via `execute_sql`):
   ```sql
   UPDATE public.service_catalog_items sci
      SET country = NULL, updated_at = now()
     WHERE sci.source = 'registry_promoted'
       AND sci.country IS NOT NULL
       AND sci.supplier_id IN (
         SELECT ssc.supplier_id
         FROM supplier_service_capabilities ssc
         WHERE ssc.platform_vetting_status = 'approved'
           AND ssc.country_code IS NOT NULL AND btrim(ssc.country_code) <> ''
           AND lower(btrim(ssc.service_category)) = lower(btrim(sci.category))
         GROUP BY ssc.supplier_id
         HAVING count(DISTINCT ssc.country_code) > 1
       );
   ```
4. **Tests:** vendor_proposal serves the NULL-country master for each approved country and no
   other; `_serves_destination` returns False for a NULL-country master whose supplier has no
   approved capability in the destination; the writer nulls `country` on the second-country
   approval.

Human sign-off obtained (Romain, 2026-08-31, Option B) **before** any change ships. This ADR
authorises the follow-up implementation ticket only; it changes no schema and ships no code.
