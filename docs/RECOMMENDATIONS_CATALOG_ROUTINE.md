# Recommendations catalog — keeping it warm as cases land

## Goal

When a new case lands for a destination we don't have curated providers
for, the system should **lazy-populate** a baseline list (max 10 per
category) so the employee never sees an empty Recommendations page. Over
time, the items employees shortlist + items HR approves through
exception requests earn quality signal; never-shortlisted items decay.

The bigger the user base, the better the catalog triages itself.

## What ships today (Phase 1)

1. **Coverage report** — read-only inspection of catalog depth per
   destination city, exposed both in Python and as a CLI script.
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
   actually has providers to choose from.

## What's deferred (Phase 2)

The hook today is a stub: it logs the gap but does not actually
backfill. Phase 2 wires real per-category scrapers and a DB-backed
catalog. Sequence:

| Step | What | Why |
|---|---|---|
| 2a | Move catalog from JSON to a `service_catalog_items` table | JSON is git-only; scrapers need to write at runtime |
| 2b | Per-category scraper modules (start with the 5 biggest gap categories from real telemetry) | Don't pre-build scrapers no one needs |
| 2c | Async dispatch from `ensure_destination_catalog()` | Don't block case creation on a scrape |
| 2d | Quality scoring from user signals (shortlist, exception accepted, click-through) | Implicit triage, not manual curation |
| 2e | Admin UI for one-click promote/demote/remove of scraped items | Human override on bad scrapes |

## Cross-cutting

- **Cap at 10 items per (category, city)**. Keeps curation surface
  manageable; matches "minimum to propose to the user" intent.
- **Geo-bound vs geo-agnostic** datasets coexist. Geo-bound categories
  (today: `schools`, `living_areas`) are the ones that need per-city
  seeding. Geo-agnostic ones (banks, insurance, etc.) work everywhere
  out of the box.
- **Quality decay**: items that appear in 0 shortlists across N cases
  get hidden from new recommendations until re-promoted. (Phase 2.)

## When you add a new demo destination

1. Run `python scripts/recommendations_coverage.py "<city>"` to see gaps.
2. Add 5-10 entries per geo-bound category to the JSON datasets.
3. Add the city to the `_CITY_ALIASES` and `_CITY_CURRENCY` maps in the
   relevant plugins (`schools.py`, `living_areas.py`).
4. Re-run the coverage script to confirm OK.
5. Commit.

Phase 2 replaces steps 2-4 with the auto-backfill on first user landing.
