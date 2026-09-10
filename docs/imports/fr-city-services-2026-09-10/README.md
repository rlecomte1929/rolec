# fr-city-services-2026-09-10 — Paris FR city services (draft, one-city test)

One-city proof of the nested city-services pipeline for France (see
`docs/imports/ie-city-services-2026-09-08/README.md`). **Not published.**

- **6 `country_resources` rows** (Paris × housing, banking, schools, legal_admin,
  tax_finance, transport) — all `status='draft'`, `is_visible_to_end_users=false`.
- 5 `resource_sources` rows (one per distinct cited host).
- **Append-only verified:** FR `country_resources` 18→24; published 18→18, visible 18→18.
  Inserted 6 / updated 0. New rows use `citysvc-fr-paris-<service>` (no collision with the
  existing 18 served FR rows; none of those are Paris).
- Source: Otto GCS `workspace-media` (public-read), citation-rework object
  `1789042422706_ued7ojyp.ndjson` (SHA-256 `4efbfc31c3747cda5bbf439ffbc5095d5fa3821c79fd5d10e6c728efd1af2c80`).
  **Not** the pre-rework dump `1789027594250_zi7at529.ndjson`.
- Pipeline: `gen_city_services_bundle.py --src-dir src --out bundle.json` →
  `import_resources.py --bundle bundle.json --mode draft_only`.
- Publisher/trust classification is the converter's cautious default (hosts without
  `OFFICIAL_HINTS` land commercial/T2, including `.gouv.fr` until that list is extended).

## Gate to serve

These are drafts. Promotion to `status='published'` + visible is a separate human step
(admin), never this import.
