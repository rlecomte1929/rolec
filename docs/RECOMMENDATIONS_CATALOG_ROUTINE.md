# Recommendations catalog — keeping it warm as cases land

## Authority model

Three tiers, top-down. Each tier filters from the one above; nothing
bubbles up.

```
   ┌─────────────────────────────────────────────────────────┐
   │  ADMIN — owns the master catalog of vendors per city.   │
   │  Source: scraper output + manual additions/overrides.   │
   │  No employee or HR can change this directly.            │
   └─────────────────────────────────────────────────────────┘
                              ▼  HR sees + curates
   ┌─────────────────────────────────────────────────────────┐
   │  HR — for their own company, decides which admin       │
   │  vendors are visible to their employees, and may add    │
   │  their own preferred vendors not in the master list.    │
   │  Per category, per destination.                         │
   └─────────────────────────────────────────────────────────┘
                              ▼  Employee sees the curated set
   ┌─────────────────────────────────────────────────────────┐
   │  EMPLOYEE — picks ONLY from what HR has approved for    │
   │  their company. Cannot reach the admin master directly. │
   └─────────────────────────────────────────────────────────┘
```

## Goal

When a new case lands for a destination we don't have providers for,
**the scraper runs once for that (city, country)** to seed the admin
master catalog (max 10 per category). HR then has something to curate.
Until HR curates, the employee sees an empty / "coming soon" state.

The scraper is **not** invoked on every case — only the first time a
destination is encountered that has zero rows in the master catalog.

## What ships today (Phase 1)

1. **Coverage report** — read-only inspection of master catalog depth
   per destination city, exposed in Python and as a CLI:
   ```
   python scripts/recommendations_coverage.py Munich --country Germany
   ```
   Exits non-zero when any category has fewer than 10 items, so the
   script can guard CI for demo destinations.

2. **Detection hook** — `backend/services/catalog_coverage.py
   ::ensure_destination_catalog(category, destination_city, country)`
   logs a structured `catalog_gap_detected` event whenever a case
   touches an under-populated (category, city) pair. We get a metric
   stream to rank which gaps to close first **before** building any
   scrapers.

3. **Munich seed** — concrete entries added to `schools.json` (6) and
   `living_areas.json` (6) so the prospect demo for `UK → Germany`
   actually has admin-tier providers to choose from.

The HR curation tier and employee filter are **not** in this PR; they
land in Phase 2 (see below).

## Phase 2 — what this routine becomes

Sequence to build, in order.

| Step | What | Why |
|---|---|---|
| 2a | Move admin master from JSON → `service_catalog_items` table (writable at runtime, scoped by `city`/`country`) | JSON is git-only; scrapers need to write at runtime, ops needs to override |
| 2b | First-encounter trigger: when a case is created with `(destination_city, country)` that has **0 rows for any category** in the master, dispatch one scraper run per category. Subsequent cases for the same destination are no-ops. | Don't re-scrape on every case; one scrape per (category, city), ever |
| 2c | Per-category scraper modules. Start with the categories whose `catalog_gap_detected` log volume is highest after Phase 1 ships. Cap at 10 items per (category, city). | Don't pre-build scrapers no one needs |
| 2d | `company_vendor_selections` table — HR picks per (company_id, category, destination): which admin items are visible + custom HR-added vendors not in the master | The HR curation tier — the actual authority gate between admin and employee |
| 2e | HR UI per category: list admin master items with on/off toggle, plus an "Add own vendor" form for company-specific picks | Where HR exercises the authority |
| 2f | Employee recommendations API filters strictly by `company_vendor_selections` for the employee's company; if HR hasn't curated a category, employee sees a "Your HR has not yet selected providers for this category" empty state — never the raw admin list | The employee-facing filter; never leak unvetted master rows |
| 2g | Async dispatch from `ensure_destination_catalog()` so case creation doesn't block on scrape | Demo experience: case creation must stay snappy |
| 2h | Admin UI for one-click promote / demote / remove of scraped items, plus per-row provenance (scraper / manual / HR-promoted) | Human override on bad scrapes; debuggability |

## Cross-cutting

- **Cap at 10 items per (category, city)** in the admin master. Keeps
  curation surface manageable; matches "minimum to propose" intent.
- **Geo-bound vs geo-agnostic** datasets coexist. Geo-bound categories
  (today: `schools`, `living_areas`) are the ones that need per-city
  seeding. Geo-agnostic ones (banks, insurance, etc.) work everywhere
  out of the box at the master tier — but HR still curates which of
  the 10 are visible to their employees.
- **Empty employee view is OK and explicit.** Until HR curates a
  category, the employee sees "Your HR is finalizing providers for
  {category}" — never silent zero, never raw master list.
- **Scrape-once, never on demand.** A destination's first case
  triggers the scrape; cases #2…∞ for the same destination read from
  the existing master rows. Operationally cheap and keeps the catalog
  stable for HR's curation work.

## When you add a new demo destination today (manual, until 2a-2c land)

1. Run `python scripts/recommendations_coverage.py "<city>"` to see gaps.
2. Add 5-10 entries per geo-bound category to the JSON datasets.
3. Add the city to the `_CITY_ALIASES` and `_CITY_CURRENCY` maps in the
   relevant plugins (`schools.py`, `living_areas.py`).
4. Re-run the coverage script to confirm OK.
5. Commit.

Phase 2 replaces steps 2-4 with the auto-backfill on first user landing.
