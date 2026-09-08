# Otto delivery backlog — full inventory (2026-09-08)

Source: Otto's own complete delivery manifest (requested + returned 2026-09-08). This is the durable
record of **everything Otto has produced for ReloPass**, so nothing researched is lost. Reconcile
against `docs/imports/` (what's imported) before harvesting each item.

## Storage & access — VERIFIED
- **GCS base:** `https://storage.googleapis.com/audos-images/workspace-media/d0c29613-9cb5-4652-9c6a-494eeed352e5/`
- **Policy:** permanent **public-read**, no signing, no expiry — **verified 2026-09-08** (HTTP 200 on
  the vehicle-import manifest + Sydney city NDJSON). Harvest directly with `curl`; no browser needed.
- Files are named `<epoch_ms>_<slug>.{ndjson,json,zip}` under that base.
- **NOTE:** this is a *different* bucket path from the expiring signed `…/spaces/workspace-776786/data/
  corridors/ie/` URLs seen earlier — those (the "IE-P0 corridor knowledge, JOB 1/14") remain signed/
  expiring and are a separate recovery.

## Two storage classes
1. **GCS files** (public, curl-able now) — vehicle-import, vendor candidates, city services, ICP, demo brief.
2. **WorkspaceDB-only** — corridor facts, ARBs, KG, vendor_providers, and supporting tables. These are
   in Otto's Audos WorkspaceDB and **never reached production Supabase** because **Bridge B (the
   OTTO_LOADER edge function) returns HTTP 401** (token mismatch). This is the single biggest blocker.

---

## A. GCS-delivered (directly harvestable via curl)

### A1. Vehicle-import facts v2 — 108 records, 7 files (NEW category, not in prod)
18 countries × 6 rule types (eligibility_window / customs_duty / vat_treatment / registration /
required_docs / timeline). `topic_key=veh-{ISO2}-{rule_type}`.
- manifest `1786974041647_hovhsquf.json`
- b1 FR/NO/DE `1786973990930_f0fe3vj1.ndjson` · b2 ES/IE/NL `1786973992815_0cwjpxd6.ndjson`
- b3 GB/CH/IT `1786973994665_pp8nz9w9.ndjson` · b4 JP/KR/AU `1786973999001_1okyito8.ndjson`
- b5 US/CA/SG `1786974001018_5eh5c1r9.ndjson` · b6 AE/IN/PL `1786974002129_cv7y9adh.ndjson`

### A2. Vendor candidates — 6 flywheel batches, ~248 clean records (import to vendor_providers NOT confirmed)
- **B1 Paris/Oslo** (44): manifest `1786973835754_14vg1tca.json`, paris `1786973822443_2wu5xuu9.ndjson`, oslo `1786973823979_flxke73l.ndjson`, combined `1786973825603_nlk1i9ly.ndjson`
- **B2 Madrid/Dublin** (43): manifest `1786973557688_pz5vonwn.json`, madrid `1786973545391_gsxsb04h.ndjson`, dublin `1786973547426_du51f0w0.ndjson`, combined `1786973548495_urc8afl7.ndjson`
- **B3 Stavanger/Aberdeen** (45): manifest `1786973538170_wkri8agj.json`, stavanger `1786973525113_aandhdg8.ndjson`, aberdeen `1786973526610_1biiy657.ndjson`, combined `1786973528302_93z03j6q.ndjson`
- **B4 Stockholm/Copenhagen** (42): manifest `1786974137036_94rli07e.json`, stockholm `1786974121946_l4byndgn.ndjson`, copenhagen `1786974123083_vfrwb776.ndjson`, combined `1786974127011_k4fzwzmc.ndjson`
- **B5 Helsinki/Berlin** (36): manifest `1786973442900_r2nvhsm2.json`, helsinki `1786973429865_wgbskxg3.ndjson`, berlin `1786973431383_75ifo1wt.ndjson`, combined `1786973432524_leuwncn1.ndjson`
- **A2a Frankfurt/Milan** (40 clean / 11 rejected, "yellow" — T2 verify <80%): manifest `1786976294051_2nmzmq26.json`, frankfurt-clean `1786976258278_r01j557o.ndjson`, frankfurt-rejected `1786976259946_qi6hatiu.ndjson`, milan-clean `1786976265316_3w5rio37.ndjson`, milan-rejected `1786976268452_hym750d4.ndjson` (+ per-city qa.json)

### A3. City services (destination content → `import_resources.py --bundle`, draft)
Per-city `ndjson_url` + `manifest_url` under the GCS base (filenames in Otto's manifest; all public-read).
- **AU** 12: sydney/melbourne/brisbane/perth/adelaide/canberra/gold-coast/newcastle/hobart + gap-fills sunshine-coast/darwin/wollongong
- **CA** 5: regina/mississauga/burnaby/windsor/gatineau
- **IE** 4: waterford/swords/bray/navan
- **CH** 10: zurich/geneva/basel/lausanne/bern/winterthur/lucerne/zug/st-gallen/lugano
- **SE** 5 confirmed (norrkoping/jonkoping/umea/gavle/boras) — ⚠️ malmö, västerås uncertain
- **DK** roskilde confirmed — ⚠️ odense uncertain
- **BE** 4 (Sep 8 gap-fills): antwerp/bruges/brussels/ghent (have .zip bundles too)
- **FI** 7: manifests present, ⚠️ NDJSON URLs not in the top-100 window — Audos-gated recovery (see §D.2; not a CLI `psql` query)
- **IT/PL** (bergamo/brescia/modena/torun/genoa/florence + houston-US): ⚠️ validated in cursor tasks but **no standalone workspace-media URL** — live only in the original attachment path

### A4. Other GCS
- **ICP research** (13 records): `1788824530010_t44l1k2q.ndjson` + manifest `1788824552512_ff6tkvq4.json`
- **Demo Day brief** (23 records): `1788825247748_mshqn6ei.ndjson` + manifest `1788825284608_wr11bwm1.json`
- **Technical/business roadmap** (.docx): ⚠️ URL truncated in Otto's manifest — Audos-gated recovery (see §D.2; not a CLI `psql` query)

---

## B. WorkspaceDB-only — the big prize, blocked on Bridge B (HTTP 401)

All of the below live in Otto's Audos WorkspaceDB and are **NOT in production Supabase**. They cannot
be `curl`-ed (no GCS file); they land in prod only through the OTTO_LOADER edge function ("Bridge B"),
which returns 401 (OTTO_LOADER_TOKEN mismatch). Fixing that token is the key that unlocks this whole
column.

| Table | Rows | Note |
|---|---|---|
| `requirement_entities` | 316 | corridors: FR-NO 74, NO-FR 54, ES-IE 38, NL 30, GB-NO 29, CH 21, IT 13, JP 14, KR 13, AE 13, DE 14, FR-DE 3 |
| `requirement_facts` | 878 | dual-purpose: `fact_text NOT NULL` = compliance facts; NULL = form-field defs |
| `requirement_blocks` (ARBs) | 76 | NO 30, IE 29, FR 17 |
| `corridor_requirements` | 76 | join corridors↔blocks |
| `kg_corridor_requirements` | 6 | FR-NO only (+ candidates 35 pending-review, sources 7, attestation_claims 23, attestations **0**) |
| `vendor_providers` | 1825 | research-staging, unverified; ~50 batch_labels |
| `readiness_templates` | 709 | |
| `geo_city_content` | 225 | |
| `city_capabilities` | 55 | |
| `pet_import_rules` | 85 | |
| `events_calendar` | 514 | |
| `i18n_glossary` | 609 | |
| `competitive_reports` | 14 | |
| `linked_references` | 9920 | |

**Reconciliation caveat:** my coverage campaign (merged PR #2138) imported corridor facts to prod
`requirement_items` (pending) via the confirm_quotes→import→promote path — a *separate* copy from
Otto's WorkspaceDB `requirement_facts`. Overlap is likely; a dedup by (country, title) is required
before loading any WorkspaceDB facts, or we double-write.

---

## C. Never-landed / gaps (Otto-flagged)
- **Bridge B → production Supabase** — 401 auth on both 2026-08-17 attempts. Blocks ALL of section B.
- **attestations = 0** — no lawyer sign-off on any corridor; nothing sellable.
- **app_vendor_providers = 0** — no vendor promoted to the live catalogue (HR users see none).
- **kg candidates (35)** — pending human review by design; must not be served.
- Uncertain city files: SE/malmö, SE/västerås, DK/odense, US/houston (tasks done, files not in top-100).
- FI NDJSON URLs + roadmap URL — Audos-gated recovery (see §D.2; `workspace_media` is not in prod, so this is not a CLI `psql` query).

---

## D. Recovery actions Otto flagged (to prevent loss)
1. **Fix `OTTO_LOADER_TOKEN`** → dry_run → apply Bridge B, to load all of section B into prod.
2. **Recover the missing GCS URLs — this is an Audos-side query, NOT runnable from a CLI checkout.**
   An earlier revision of this list said to run `psql "$DATABASE_URL"` on a `workspace_media` table.
   That premise is **false and was verified so 2026-09-08**: `workspace_media` does **not** exist in
   prod Supabase (it is an Audos WorkspaceDB table, unreachable via `DATABASE_URL` — only
   `public.workspace_stats` matches), and the `audos-images` GCS bucket **denies anonymous LIST**
   (`storage.objects.list` 401; individual-object read is public, but the `<epoch_ms>_<slug>` names
   can't be enumerated without the index). The committed export
   `data/workspace-db-export/2026-08-18/linked_references.*` is a fetched-URL cache, not the object
   index. So the missing city NDJSON URLs (FI×7, IT/PL, SE malmö/västerås, DK odense) and the roadmap
   `.docx` URL can only be recovered **inside Audos**: query the WorkspaceDB index there
   (`SELECT filename, gcs_url FROM workspace_media WHERE filename ILIKE '%malmo%' …`) or have Otto
   re-emit the master city manifest, then hand the URLs to the applier to `curl` + import. **Do not
   guess-construct GCS filenames.**
3. Everything already in GCS is safe (permanent public-read).
