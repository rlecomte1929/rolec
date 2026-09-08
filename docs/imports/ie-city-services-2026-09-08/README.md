# ie-city-services-2026-09-08 — Ireland city-services harvest (draft)

First harvest of Otto's **city-services** backlog (see `docs/imports/OTTO_BACKLOG.md`). Proof of the
city-content pipeline for the new nested per-city format.

## What landed
- **24 `country_resources` rows** (4 cities × 6 services: housing, banking, schools, legal_admin,
  tax_finance, transport) — all `status='draft'`, `is_visible_to_end_users=false`.
- 5 `resource_sources` rows (one per distinct cited page).
- **Append-only verified:** IE `country_resources` 16→40; published 16→16, visible 16→16
  (existing served content untouched). New rows use a distinct `external_key` namespace
  `citysvc-ie-<city>-<service>`, so they never collide with the 16 pre-existing IE rows.

## Source & pipeline
- Source: Otto GCS `workspace-media` (public-read, permanent), cities waterford/swords/bray/navan
  (`src/*.ndjson`, curled 2026-09-08).
- Format: nested per-city record `{country, iso2, city, rank, population, services{…}}` — NOT the
  flat §3B shape, so it needed a new converter: **`scripts/gen_city_services_bundle.py`**
  (service→category map, all seven categories already seeded in prod; body = service `summary`).
- `gen_city_services_bundle.py --src-dir src --out bundle.json` → `import_resources.py --bundle
  bundle.json --mode draft_only` (Supabase admin client; `SUPABASE_URL`+`SUPABASE_SERVICE_ROLE_KEY`).

## Honesty notes
- 5 services carry `source_missing: true` (bray/navan/swords/waterford schools + navan transport) —
  landed with **no source** (`source_id` NULL), no invented citation. The flag is honoured.
- `retrieved_at` is absent from this delivery format, so sources omit it rather than fake a date.
- Publisher/trust classification is cautious (official state hosts → T1, else commercial → T2).

## Gate to serve
These are drafts. Promotion to `status='published'` + visible is the separate human step
(admin), never automated.
