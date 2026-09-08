# Otto city-services gap recovery brief — 2026-09-08

**For:** an Otto / Audos session (the applier cannot run this — see §Why).
**Goal:** get the applier the GCS NDJSON URLs for the city-services cities that never landed, so it
can `curl` → convert → draft-import them to `country_resources` (draft, invisible) behind the human
publish gate. Nothing here serves anything.

## Why this is an Audos task, not a CLI one (verified 2026-09-08)

The missing cities can't be recovered from a repo checkout, so this brief exists to be run where the
data lives:
- `workspace_media` (the GCS filename↔slug index) is **not in prod Supabase** — it is an Audos
  WorkspaceDB table, unreachable via `DATABASE_URL`.
- The `audos-images` GCS bucket is public-**read** of individual objects but **denies anonymous
  LIST**, so the `<epoch_ms>_<slug>.ndjson` filenames can't be enumerated without the index.
- The already-landed cities (PR #2167) had their URLs at build time, but the source URLs were never
  recorded in the repo.

So only Otto/Audos can produce the URLs. See `docs/imports/OTTO_BACKLOG.md` §D.2.

## What already landed — do NOT redo these (PR #2167, 39 cities)

| Country | Landed cities |
|---|---|
| AU | adelaide, brisbane, canberra, darwin, gold-coast, hobart, melbourne, newcastle, perth, sunshine-coast, sydney, wollongong (12) |
| BE | antwerp, bruges (2) |
| CA | burnaby, gatineau, mississauga, regina, windsor (5) |
| CH | basel, bern, geneva, lausanne, lucerne, lugano, st-gallen, winterthur, zug, zurich (10) |
| DK | roskilde (1) |
| IE | bray, navan, swords, waterford (4) |
| SE | boras, gavle, jonkoping, norrkoping, umea (5) |

## What is missing — recover these

Two failure modes; handle each the way it says.

### Mode A — URL recovery (the file exists; just return its URL)
These were researched and the NDJSON exists in WorkspaceDB/GCS, but the URL fell outside the
top-100 window Otto pasted. **Do not re-research — just return the existing object's `gcs_url`.**

| Country | Cities | Note |
|---|---|---|
| FI | all 7 in the FI city-services batch | Otto's FI city-services **manifest is present** — return it plus each of its 7 per-city `ndjson_url`s (the manifest is authoritative for the city names). |
| SE | malmö, västerås | "tasks done, files not in top-100" |
| DK | odense | "tasks done, files not in top-100" |

Query the WorkspaceDB index in Audos and return `filename` + `gcs_url` for each:
```sql
SELECT filename, gcs_url FROM workspace_media
WHERE filename ILIKE '%malmo%' OR filename ILIKE '%malmö%'
   OR filename ILIKE '%vaster%' OR filename ILIKE '%väster%'
   OR filename ILIKE '%odense%'
   OR filename ILIKE '%helsinki%' OR filename ILIKE '%espoo%' OR filename ILIKE '%tampere%'
   -- …and the other FI city slugs the FI manifest names
ORDER BY filename;
```
(or re-emit the master city manifest, which lists every city's `ndjson_url` + `manifest_url`).

### Mode B — re-export / re-deliver (no standalone URL, or corrupted)
These need a fresh, curl-able GCS object written — not just a lookup.

| Country | Cities | Why | Action |
|---|---|---|---|
| IT | bergamo, brescia, modena, genoa, florence | "validated in cursor tasks but **no standalone workspace-media URL** — live only in the original attachment path" | Re-export the validated per-city NDJSON to a fresh **public-read** `workspace-media` object; return the URL. |
| PL | torun | same as IT | same |
| US | houston | same as IT (optional — not a priority destination) | same |
| BE | brussels, ghent | **source-corrupted** — a stray-byte JSON break; the applier's byte-clean did **not** recover them | **Re-generate/re-export clean** NDJSON at source. Do not hand back a hand-patched file — fix the break where it is produced. |

## The delivery contract (so a re-export is consumable as-is)

The applier feeds these to `scripts/gen_city_services_bundle.py --src-dir <src> --out bundle.json`
→ `scripts/import_resources.py --bundle bundle.json --mode draft_only`. That converter expects Otto's
**nested per-city** shape — one JSON object per city, one line per city:

```json
{"country":"Sweden","iso2":"SE","city":"Umeå","rank":12,
 "population":{"value":null,"source_url":null,"source_missing":true},
 "services":{
   "housing":{"summary":"<verbatim narrative — becomes the resource body>", "...structured fields":"...",
              "source_url":"https://…","source_missing":false},
   "banking":{...}, "schools":{...}, "legal_admin":{...}, "tax_finance":{...},
   "transport":{...}, "healthcare":{...}, "cost_of_living":{...}
 }}
```

Rules the converter enforces — match them or the row drops or the load errors:
- **Service keys must be from this set** (the converter raises on an unmapped key):
  `housing, banking, schools, legal_admin, tax_finance, transport, healthcare, cost_of_living`.
- Each service's **`summary` is published verbatim** as the resource body, so it must be a complete,
  self-contained narrative (the structured fields are for context, not the body).
- **`source_missing: true` (or no `source_url`) lands the row source-less** — that is correct and
  wanted. **Never invent a citation** to fill it. Honour the flag.
- A service with an empty/absent `summary` is simply skipped (nothing to publish) — fine.
- Canonical template to copy: any already-landed file, e.g.
  `docs/imports/se-city-services-2026-09-08/src/umea.ndjson`.

Return, per city: the `ndjson_url`, and the per-city `manifest_url` if one exists (the applier uses
it to reconcile record counts).

## Guardrails (unchanged)
- Never fabricate a URL, a number, or a source. `source_missing` stays source-less.
- Re-exports must be **public-read + permanent** `workspace-media` objects (curl-able, no signing).
- The corrupted BE files must be fixed at generation, not guessed.
- The applier lands everything at `status='draft'`, `is_visible_to_end_users=false`; a human
  publishes. Nothing Otto returns here is served.

## Then (applier, once URLs are in hand)
`curl` each URL → `docs/imports/<iso2>-city-services-2026-09-08/src/<city>.ndjson` →
`gen_city_services_bundle.py` → `import_resources.py --bundle --mode draft_only` → append-only verify
(published/visible counts unchanged) → batch doc + gate, one PR per country.
