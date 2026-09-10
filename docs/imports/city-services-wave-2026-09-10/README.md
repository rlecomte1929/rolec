# city-services-wave-2026-09-10 — hub cities (draft)

Follow-on to the Paris one-city test (`fr-city-services-2026-09-10`). Same pipeline as
`ie-city-services-2026-09-08`: nested per-city NDJSON → `gen_city_services_bundle.py` →
`import_resources.py --mode draft_only`. **Not published.**

## What landed
- **216 `country_resources` rows** (36 cities × 6 topics: housing, banking, schools,
  legal_admin, tax_finance, transport) — `status='draft'`, `is_visible_to_end_users=false`.
- Inserted 216 / updated 0 on resources. 24 new `resource_sources` (1 existing host upsert).
- **Append-only verified:** published 73→73, visible 73→73. Totals 342→558.

Cities: Brussels; Berlin, Frankfurt, Hamburg, Munich; Barcelona, Madrid; Espoo, Helsinki,
Jyvaskyla, Oulu, Tampere, Turku, Vantaa; Lyon; London, Manchester; Cork, Dublin; Bengaluru,
Delhi, Mumbai; Florence, Genoa, Milan, Pisa, Rome, Turin; Amsterdam, Rotterdam; Bergen, Oslo;
Singapore; Los Angeles, New York, San Francisco.

Paris FR was already imported and is **not** in this bundle.

## Honesty
- 184 of 216 services had `source_missing` (or no URL) and landed with `source_id` NULL.
  No invented citations.
- 11 other Otto files on disk (mostly Italy secondaries + Bergamo) use a different shape
  with no `summary` and were **not** imported.

## Review later (not required now)
Admin → Catalog → **Resources CMS** → Resources list → status **Draft**. Filter by country
or search the city name. Edit any row; promotion to published is a separate human step.
