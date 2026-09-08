# se-city-services-2026-09-08 — Sweden city services (draft)

Part of the Otto city-services fan-out (see `docs/imports/OTTO_BACKLOG.md` and
`ie-city-services-2026-09-08/README.md` for the pipeline).

- **30 `country_resources` rows** (cities: boras, gavle, jonkoping, norrkoping, umea; 6 services each) — all
  `status='draft'`, `is_visible_to_end_users=false`. 7 `resource_sources`.
- Append-only verified: Sweden published/visible unchanged (0→0); totals grew by the inserts.
- Source: Otto GCS `workspace-media` (public-read), curled 2026-09-08 → `src/*.ndjson`.
- Pipeline: `gen_city_services_bundle.py --src-dir src --out bundle.json` →
  `import_resources.py --bundle bundle.json --mode draft_only`.
- `source_missing` services landed source-less (no invented citations).
