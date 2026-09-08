# HR vendor curation — filter master vendors by service type

**Date:** 2026-06-15
**Status:** Approved (design)
**Surface:** `/hr/vendor-curation` ("Service providers"), HR persona

## Problem

On the HR Service-providers page, the master-vendor list for a (category, destination)
shows a flat list with no way to narrow it. Romain wants to filter vendors by the
**type of service they offer**. Two underlying issues block this today:

1. **No service-type data.** Every `service_catalog_items` row has empty
   `attributes_json` — there is nothing to filter on.
2. **Duplicate rows.** Each vendor appears twice: two seed batches inserted the same
   names with different `external_id` (one `m-N` slug, one UUID), so the
   `UNIQUE(category, external_id)` constraint never collapsed them. e.g. movers/Oslo
   shows 22 rows = 11 unique × 2.

## Decisions (from brainstorming)

- **Tag source:** the existing "Populate with AI" path assigns service types.
- **Taxonomy:** **free-form** AI tags (no fixed vocabulary). The filter dropdown is
  built dynamically from the tags present, grouped case-insensitively for display.
- **Backfill:** re-clicking "Populate with AI" tags vendors that currently lack
  `service_types` (so already-populated destinations like Oslo become filterable).
- **Dedupe:** fix the duplicate vendors in this same change.

## Design

### 1. Data model — no migration
Store `service_types: string[]` inside the existing `service_catalog_items.attributes_json`
(jsonb). The curation endpoint already returns per-row `attributes`, so tags reach the
frontend with no API-shape change. `CurationRow.attributes` already carries it.

### 2. AI tagging (backend, `service_catalog` / populate path)
- Extend the populate LLM prompt/schema so each generated vendor includes
  `service_types: string[]` (free-form, e.g. `["international","storage"]`). Vendor
  names + service types are published, non-personal data → no `pii_masker` needed.
- Persist `service_types` into `attributes_json` on insert.
- **Backfill:** the populate handler (`populate-with-ai` / `populate-destination-with-ai`),
  when a (category, destination) already has vendors, runs a tagging pass over rows whose
  `attributes_json` lacks a non-empty `service_types` and writes the tags in place
  (instead of the current "nothing added" no-op). Counts toward the AI quota only when it
  actually calls the model.

### 3. Dedupe (data cleanup + defensive view)
- **One-time data cleanup** (backfill via `execute_sql`, no schema change — permitted):
  for each (category, name) with >1 active row, keep ONE and deactivate the rest.
  Keep-priority: (a) a row referenced by any `company_vendor_selections.master_item_id`,
  else (b) the `m-N`-style `external_id` (original seed), else (c) lowest `created_at`.
  Re-point any selection that referenced a removed row to the kept row first, so no HR
  selection is orphaned. Deactivate (`active = false`) rather than hard-delete, to be
  reversible.
- **Defensive dedupe in the view:** `get_curation_view` collapses master rows by name
  (first occurrence wins) so the UI never shows duplicates even if data regresses.

### 4. Filter UI (frontend, `HrVendorCuration.tsx`)
- A "Service type" `<select>` above the Admin master vendors list. Options = `All` +
  the case-insensitively-grouped union of `service_types` across the loaded rows
  (label shown in Title Case; value matched case-insensitively).
- Selecting a type filters the displayed **master + custom** rows to those whose
  `attributes.service_types` includes it. `All` (default) shows everything; vendors with
  no tags appear only under `All`.
- Client-side only (list is ≤ ~22 rows); no new backend query param.
- `DossierSource`-style: extend the frontend curation row type to surface
  `attributes.service_types?: string[]`.

## Rollout record (executed 2026-06-15/16)
- **Dedupe data cleanup — DONE on prod.** 10 duplicate `movers` rows (the
  UUID-`external_id` twin of each `m-N` seed) deactivated (`active=false`, reversible).
  Verified: zero selections referenced them (no orphans); live curation now returns
  12 master movers, no duplicates. The 2 non-duplicate singletons (Supplier Test,
  testsupplier) were left untouched by an `EXISTS(... m-N twin ...)` guard.
- **Deploy dependency — `CATALOG_SCRAPER_ENABLED` is NOT set in prod.** Both the new
  populate tagging and `backfill_service_types` are gated on `catalog_scraper._enabled()`,
  which is off. Until that env var is `true` (+ backend redeploy), the AI tagging
  no-ops and the Service-type dropdown stays hidden (graceful: the list just renders
  unfiltered, as today). Enabling it turns on HR-triggered AI vendor synthesis (OpenAI
  cost) — a product decision for Romain, mirroring the `VITE_FEATURE_DYNAMIC_DOSSIER`
  enablement.

## Out of scope / follow-ups
- Editing/normalising free-form tags into a canonical set (free-form was chosen).
- Tagging HR custom vendors via the "add your own" form (could be a later add).

## Testing
- **Backend:** populate persists `service_types`; backfill tags existing untagged rows;
  `get_curation_view` dedupes by name. (`test_hr_catalog_router.py`, already in CI.)
- **Frontend:** `tsc --noEmit`; a unit test that the filter narrows rows by service type
  and `All` shows everything.
- **Live (post-deploy):** re-click Populate for Oslo/movers → vendors gain tags; the
  Service-type dropdown appears and filters; list shows 11 unique movers, not 22.
