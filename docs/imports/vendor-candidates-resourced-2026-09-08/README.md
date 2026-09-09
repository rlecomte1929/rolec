# Vendor candidates — RE-SOURCED (Option B) — 2026-09-08/09

The 235 tier-3 rejects from [`vendor-candidates-2026-09-08`](../vendor-candidates-2026-09-08/README.md)
routed back to Otto to be re-sourced against real registers (see that batch's
`otto_resourcing_brief.md`). Otto researches → writes NDJSON+manifest to GCS → the "ReloPass
corridor-data import automation" session relays the public GCS URLs → this (applier) session
re-verifies each source against its register, converts → CSV, and lands to the vetting queue
(`platform_vetting_status='pending'`, append-only, human approve-to-serve gate untouched).

This directory **accumulates** the re-sourced sub-batches (one `src/*.ndjson` per city×category)
as they arrive. Each sub-batch is landed with the append-only tripwire verified
(`supplier_service_capabilities` `approved` count + md5 unchanged).

## Sub-batches landed

### FR-NO movers — `vendor-resourced-fr-no-movers-2026-09-08` (landed 2026-09-09)
- Source (GCS, public-read): `1788906918368_362xcyp2.ndjson` (+ manifest `1788906927057_wrp9doza.json`).
- Otto manifest: **4 firms found on a register, 2 rejected** (NFB International Relocations —
  merged into Alfa Mobility Norway, its FIDI slug now resolves to the Alfa page; AGS Movers
  Norway — no NO entity on FIDI/EuRA). Rejects reported by name, not fabricated.
- **Independently re-verified**: all 4 `source_url`s are register per-entity pages that match the
  wired `entry_url_pattern` AND returned HTTP 200 with the firm named on the page (FIDI
  `/find-fidi-affiliate/…` ×3, EuRA `/members/relocation` ×1) — curled 2026-09-09.
- Landed: **+2 new suppliers** (Adams Express, Relocation.no — NO/movers), **+3 pending
  capabilities**; 1 deduped against an existing supplier (Alfa Mobility, already in prod), 0
  rejected by the tier gate. Tripwire: `ssc` `approved` **130 → 130**, md5 unchanged.
- **PSS International Removals** landed as **XX-GB** movers, not FR-NO: its register HQ is
  Croydon, UK, so the converter keys it to its true country (XX-GB). Kept honest rather than
  forced to Norway; it is a valid FIDI mover regardless. The vetter can note NO-corridor service.

### XX-GB movers (Aberdeen) — `vendor-resourced-xx-gb-movers-2026-09-08` (landed 2026-09-09)
- Source (GCS): `1788917900665_fz0ta7k4.ndjson` (+ manifest `1788917902083_ivvzb79f.json`).
- Otto manifest: **2 firms found on FIDI, 2 rejected** (Purdie Worldwide — Euromovers member only,
  not a published FIDI affiliate; Simpsons International Removals — Dartford/Kent, not Aberdeen, no
  FIDI/EuRA listing). Honest rejects, not fabricated.
- **Independently re-verified**: both `source_url`s are FIDI `/find-fidi-affiliate/…` per-entity
  pages returning HTTP 200 with the firm named (Shore Porters, Clark & Rose) — curled 2026-09-09.
- Landed: **+2 new suppliers** (The Shore Porters Society, Clark & Rose — GB/movers), +2 pending
  capabilities, 0 duplicates, 0 rejected. Tripwire: `ssc` `approved` **130 → 130**, unchanged.
- Label note: `accreditation_body` here is `FIDI-FAIM` (vs `FIDI` on FR-NO) — same register, a
  cosmetic label variant; the tier gate keys on the `fidi.org` domain, not the label, so it is
  immaterial. `accreditation_number` NULL on both (FIDI publishes only a FAIM expiry year).

### FR-DE movers (Frankfurt) — `vendor-resourced-fr-de-movers-2026-09-08` (processed 2026-09-09)
- Source (GCS): `1788921051328_bmh0husu.ndjson` (+ manifest `1788921077900_oz4xrsov.json`).
- Otto: **1 firm found, 2 rejected** (Zapf Umzüge, Arnold & Hanl — small local German movers,
  legitimately not FIDI/EuRA members; international-relocation networks don't list local firms —
  expect similar low yield on other local-mover batches).
- **NO new supplier landed.** The one firm, **Crown Relocations Frankfurt**, is a DUPLICATE —
  already a supplier in prod, so the tier gate/dedupe staged 0 (dry-run: staged 0, duplicates 1,
  rejected 0). No prod write done — nothing new to stage, and re-recording a duplicate adds no
  queue-visible candidate. The re-sourced EuRA evidence is preserved here in the committed NDJSON.
- **Vetter caveat (flagged honestly by Otto):** the EuRA `source_url`
  (`/members/crown-worldwide-group`) is the GLOBAL PARENT (Crown Worldwide Group), not a
  Frankfurt-specific listing. It clears the shape gate (a real EuRA per-entity page), but whether
  the parent's EuRA membership evidences the Frankfurt office is a vetter judgment at
  `/admin/vetting-queue` — recorded here, not auto-decided.

### XX-IE movers (Dublin) — `vendor-resourced-xx-ie-movers-2026-09-09` (landed 2026-09-09)
- Source (GCS): `1788940289394_ug4b14d3.ndjson` (+ manifest `1788940293455_itqle5rs.json`).
- Otto manifest: **4 sourced, 12 rejected** — rejects honest by name: 5 FIDI pages whose address
  is not Dublin (Farmington Hills MI, Dartford, Brandon, Montreal, Uxbridge), Crown 404, and 6 EuRA
  members that are DSP/RMC/serviced-apartment providers or Cork/Kinsale-based, not Dublin removal
  movers. Reported, not fabricated.
- **Independently re-verified 2026-09-09**: all 4 `source_url`s are FIDI `/find-fidi-affiliate/…`
  (×3) or EuRA `/members/…` (×1) per-entity pages returning HTTP 200 with the firm named. Guarded
  against a directory-template false positive with a cross-contamination check — each FIDI page
  contains ONLY its own firm (Cronin 11/0/0, Irish Relo 0/3/0, Get Cracking 0/0/4), all
  Dublin/Ireland; FIDI `<title>` = `CRONIN RELOCATIONS IRELAND | FIDI`.
- **Cronin de-duplicated:** the batch listed the same firm twice — "Cronin Relocations Ireland"
  (FIDI) and "Cronin Ireland Relocations" (EuRA), same website `ireland-relocations.com` and phone.
  Kept the FIDI-FAIM row (stronger register for a mover), dropped the EuRA row from the CSV — its
  evidence is preserved in `src/xx-ie-movers.ndjson`. Moot in the end: Cronin was **already staged
  + promoted** in prod (`vendor_candidates` ES-IE/movers, dedupe_key `ireland-relocations.com`) from
  earlier work, so the pipeline skipped it regardless (dry-run: read 3, staged 2).
- Landed: **+2 new suppliers** (Irish Relo, Get Cracking Relocations — IE/movers), **+2 pending
  capabilities**, 0 duplicates, 0 tier-gate rejects (Cronin skipped as already-staged). Tripwire:
  `ssc` `approved` **130 → 130**, md5 `1c4c3899…` unchanged; total pending **982 → 984** (+2).
  FIDI `source_url` persisted verbatim on both new suppliers.
- Corridor-label note: the converter maps destination `IE → ES-IE` (its hardcoded corridor) and
  `_dest_iso_from_corridor` recovers `country_code=IE`, so both capabilities scope to **destination
  IE** (`coverage_scope_type='country'`) — the label is cosmetic, the scope is Ireland.
  `accreditation_number` NULL (FIDI publishes only a FAIM expiry year).

### XX-DK movers (Copenhagen) — `vendor-resourced-xx-dk-movers-2026-09-09` (processed 2026-09-09)
- Source (GCS): `1788945180783_bxsm8eca.ndjson` (+ manifest `1788945209670_yslukdgc.json`).
- Otto manifest: **2 sourced, 8 rejected** — thin but honest market. Rejects by name: 2 with no
  verifiable per-entity page (Inter Express, A.J. Mauritzen), 2 FIDI-FAIM but wrong country (Bergen
  = Türkiye, Globas = Düsseldorf DE), 4 EuRA DSP/RMC/serviced-apartment firms (Copenhagen
  Relocations, Deloitte, Gateway to Denmark, GTS Nordic) — not removal movers.
- **Independently re-verified 2026-09-09**: both `source_url`s are FIDI per-entity pages, HTTP 200,
  firm named, no cross-contamination (alfa 14 / aspire 0, and vice versa). Alfa's slug
  `alfa-mobility` carries no country suffix, so I verified the page body explicitly: it shows
  `ALFA MOBILITY DENMARK A/S`, Company address **COPENHAGEN, Denmark**, `+45 43 53 06 40`,
  `info@alfamoving.dk`, FAIM — the Denmark entity, distinct from the Norway/Sweden Alfa offices
  (whose prod records use their own slugs `alfa-mobility-5` / `alfa-mobility-0`). Aspire page:
  `ASPIRE MOBILITY GROUP | FIDI`, Rødovre, Denmark.
- **NO new supplier landed — 100% duplicate.** Both firms are ALREADY in prod as suppliers with
  `movers`/`DK` capabilities at `pending` (created 2026-08-31 in an earlier XX-DK landing) and
  already staged as XX-DK/movers candidates. Dry-run: read 2, **staged 0** (both skipped as
  already-staged), 0 duplicates, 0 rejected. No prod write done. The re-sourced FIDI evidence is
  preserved in the committed NDJSON — it corroborates the existing records.
- Tripwire: no write, so `ssc` `approved` **130 → 130** unchanged (pending unchanged at 984).
- Heads-up: an existing multi-country Alfa set is in prod (Norway `alfa-mobility-5`, Sweden
  `alfa-mobility-0`, Denmark `alfa-mobility`, + a generic `ALFA MOBILITY`), so the queued
  **Helsinki (XX-FI)** and **Stockholm (XX-SE)** batches will likely also hit Alfa duplicates.

### XX-FI movers (Helsinki) — `vendor-resourced-xx-fi-movers-2026-09-09` (processed 2026-09-09)
- Source (GCS): `1788945768426_eisbb6f0.ndjson` (+ manifest `1788945793441_oqvjw2o8.json`).
- Otto manifest: **4 sourced, 4 rejected** — rejects honest: 4 EuRA advisory/DSP firms with zero
  Household Goods Movement tag (Finland Relocation Services, KEY Relocation Finland, KPMG Oy Ab,
  Vialto Partners) — not removal movers.
- **Independently re-verified 2026-09-09**: all 4 `source_url`s are FIDI per-entity pages, HTTP 200,
  firm named, clean cross-contamination matrix (Travelcargo 5 / Niemi 9 / Victor Ek 4 / Alfa 4 —
  diagonal only), all Finland/Helsinki. Alfa Finland uses slug `alfa-mobility-4` (distinct from DK
  `alfa-mobility` / NO `-5` / SE `-0`).
- **NO new supplier landed — 100% duplicate.** All 4 firms are already in prod as XX-FI/movers
  candidates + suppliers (Travelcargo, Niemi, Victor Ek by name; Alfa Finland deduped by website
  `alfamoving.com` against the existing XX-FI Alfa) from the 2026-08-31 Nordic landing. Dry-run:
  read 4, **staged 0**, 0 duplicates, 0 rejected. No prod write. Re-sourced FIDI evidence preserved
  in the committed NDJSON.
- Tripwire: no write, `ssc` `approved` **130 → 130** unchanged (pending 984).
- **Nordic coverage finding:** the 2026-08-31 landing already populated movers capabilities for
  DK (3), FI (4), SE (3) — plus NO (10). That is why Copenhagen AND Helsinki both returned 0-new,
  and why **Stockholm (XX-SE) is a near-certain duplicate** (3 XX-SE candidates already staged: Alfa
  Sweden, SBK Moving ×2). Milan (XX-IT) is the one remaining movers batch likely to be genuinely
  new; the higher-yield remaining work is the still-unlanded non-movers register pairs from #2191.

### XX-IT movers (Milan) — `vendor-resourced-xx-it-movers-2026-09-09` (processed 2026-09-09)
- Source (GCS): `1788946859759_d8gou8ty.ndjson` (+ manifest `1788946909025_n351lk78.json`).
- Otto manifest: **3 sourced, 11 rejected** — sharp, honest rejects: V&S-by-FERCAM (post-acquisition
  absorbed entity, same Vignate address/phone as FERCAM), four Rome-metro firms (Giovaruscio, Bliss,
  Bolliger Roma, Gosselin), the Franzosini **Naples** branch (separate slug `-1`), + EuRA
  DSP/furniture-rental. Good dedup discipline.
- **Independently re-verified 2026-09-09**: all 3 `source_url`s are FIDI per-entity pages, HTTP 200,
  own firm only (contamination 6/7/6, diagonal), Milan-metro confirmed on the page body — Franzosini
  `20008 INVERUNO` + `franzosini.milano@franzosini.it`, Bolliger `MILAN` + `bolliger@bolligermilano.com`,
  FERCAM `MILAN` — zero Rome/Naples signals, phones match the NDJSON. Correctly the Milan entities,
  not the rejected Rome/Naples siblings.
- **NO new supplier landed — 100% duplicate.** All 3 already in prod as XX-IT/movers suppliers +
  candidates from the 2026-08-31 landing, under their legal-entity names (`FMN LOGISTICS S.R.L.
  (Franzosini International Movers)`, `BOLLIGER S.P.A.`, `FERCAM S.P.A. (Fercam Removals & Relocation)`),
  deduped by website. Dry-run: read 3, **staged 0**, 0 duplicates, 0 rejected. No prod write.
  Re-sourced FIDI evidence preserved in the committed NDJSON.
- Tripwire: no write, `ssc` `approved` **130 → 130** unchanged (pending 984).

## Run finding — the movers lane is largely exhausted

Prod already holds `movers` capabilities for **~60 countries**, the bulk landed **2026-08-31** in a
global movers pass. This re-sourcing run (re-sourcing the 235 tier-3 rejects) added NEW movers only
for **Dublin (IE, +2 — Irish Relo, Get Cracking)**. Copenhagen (DK), Helsinki (FI) and Milan (IT)
were each verified-correct but **already in prod**; Stockholm (SE) was skipped as a known dup. So the
per-city movers batches are hitting a catalog that is already comprehensive except for fresh-market
gaps (IE was the one this run). **The remaining real yield is the non-movers register pairs**
(schools / legal / tax / banks / housing) wired in #2191, which are entirely unlanded — the pivot now
underway (first batch: SE legal via advokatsamfundet per-entity pages).

## Non-movers sub-batches (register pairs from #2191)

### XX-NO schools (Oslo) — `vendor-resourced-xx-no-schools-2026-09-09` (landed 2026-09-09) — FIRST non-movers
- Source (GCS): `1788951048473_heugp5z4.ndjson` (+ manifest `1788951050007_wu2n3j8o.json`).
- Otto manifest: **3 sourced, 9 rejected** — all sourced are IB World / English-medium schools active
  in the Nasjonalt skoleregister (NSR/Udir). Rejects honest: British School of Oslo (closed / in
  liquidation), Manglerud (IB closed Aug 2026), ISoO (alias of OIS — deduped), + Norwegian/German/
  French-medium and non-Oslo-metro schools.
- **Register type = SPA — verified via the machine-readable API, NOT a name-on-page curl.** The stored
  `source_url` `nsr.udir.no/enheter/<orgnr>` is a JS SPA (HTTP 200 but the name is not in the raw
  HTML). Independently confirmed each via the NSR data-API `https://data-nsr.udir.no/enhet/<orgnr>`:
  971845635 → "Oslo International School" (Bærum, ErAktiv=true, ErSkole=true); 915601618 → "Norlights
  International School Oslo AS" (Oslo, active); 998258383 → "Stiftelsen Asker International School"
  (Asker, active). The orgnr is carried in `accreditation_number`. General rule for SPA registers:
  **verify by the machine-readable id/API, not a human-URL curl.**
- Tier gate: the NSR per-entity register is wired (#2191), so all 3 passed at tier 1 (0 rejects).
- Landed: **+2 new suppliers** (Norlights International School Oslo, Asker International School). Oslo
  International School was a dup (already a prod supplier). Net **+3 pending capabilities** (the two
  new suppliers + one capability added to the existing Oslo International School supplier). Tripwire:
  `ssc` `approved` **130 → 130**, md5 unchanged; pending 984 → 987.
- **Vetter caveat — scope:** the converter scopes these at **country** (NO) via the corridor mapping
  (NO → FR-NO → `country_code=NO`, `coverage_scope_type='country'`). Oslo International School already
  holds an **approved city-scope** NO/schools capability (created 2026-03-13); this run added a
  **pending country-scope** one alongside it. International schools are city-local, so the vetter at
  /admin/vetting-queue may prefer city scope and should reconcile the Oslo double (approved city +
  pending country). Norlights and Asker likewise landed country-scope. `FR-NO` is the converter's
  hardcoded NO corridor label; the effective destination scope is NO.

### XX-ES banks (Madrid) — `vendor-resourced-xx-es-banks-2026-09-09` (landed 2026-09-09) — first PUBLIC_REGISTER
- Source (GCS): `1788955805662_bmioisu7.ndjson` (+ manifest `1788955838735_2j2cx2xs.json`).
- Otto manifest: **7 sourced, 4 rejected** — rejects honest: Wise (Belgian EMI, not a credit
  institution), Revolut Bank UAB (Lithuanian EMI), N26 AG (passporting, no BdE código), Openbank
  (0073 aggregator-cited only, not BdE-confirmed → rejected rather than asserted).
- **Register type = PUBLIC_REGISTER (search-form, no per-entity URL).** The Banco de España
  "Registro de Entidades" is a JS app; the `source_url` (`app.bde.es/ren_www/.../Arranque.html`) is
  the register root, SHARED by all rows — it evidences no single entity, and bde.es bot-walls curl
  (403), so a source-page name check is impossible. The verifiable key is the **código de entidad**
  in `accreditation_number`. Per #2191, bde.es is wired as PUBLIC_REGISTER (tier 2); the human vetter
  confirms each código against the register at /admin/vetting-queue. The 7 códigos are the canonical
  major Spanish banks (Santander 0049, BBVA 0182, CaixaBank 2100, Sabadell 0081, Bankinter 0128,
  Deutsche Bank SAE 0019, ING España 1465). Founder approved landing this class to pending
  (vetter-confirmed) since no independent per-entity verification is possible for search-form registers.
- Landed: **+6 new suppliers** (BBVA, Banco de Sabadell, CaixaBank, Bankinter, Deutsche Bank S.A.E.,
  ING Bank N.V. Sucursal en España — ES/banks, pending). Tripwire: `ssc` `approved` **130 → 130** md5
  unchanged; pending 987 → 993.
- **⚠️ Santander HELD — promote() name-collision (defect found + corrected).** "Banco Santander, S.A."
  (código 0049, Spain) was mis-promoted: promote()'s normalized-name matching collapsed it onto the
  EXISTING "Banco Santander (Brasil) S.A." supplier, attaching an ES/banks código-0049 pending cap to
  the *Brazilian* entity. Caught immediately; deleted the mis-created pending cap and reset the
  candidate (`status='pending'`, `promoted_supplier_id=NULL`) — the Brazilian supplier is back to its
  prior BR+UY caps and the tripwire is unchanged. **Santander (Spain) is held** for a correct re-land
  once the name-match is handled (a promote() fix, or a manual correct supplier). **Systemic:** any
  bank whose name normalizes to an existing multinational's name will mis-attach — watch future bank
  batches (this is the whole reason the vetter gate exists, but a wrong-entity row is worth catching
  at land time).

### XX-IT banks (Milan) — `vendor-resourced-xx-it-banks-2026-09-09` (landed 2026-09-09) — PUBLIC_REGISTER
- Source (GCS): `1788960997468_obgmzy76.ndjson` (+ manifest `1788961002138_flmz8eit.json`).
- Otto manifest: **7 sourced, 4 rejected** — rejects honest: Wise/Revolut/N26 (EMI or EU-passported
  foreign banks, not on the Italian Albo), ING (ABI 03239 could not be confirmed against the register
  → excluded on honesty-over-volume). Otto also caught its own `+49`→`+39` phone typo on Intesa
  mid-upload and self-corrected.
- **Register type = PUBLIC_REGISTER (Banca d'Italia — Albo delle banche).** `source_url` is the Albo
  register root (`bancaditalia.it/servizi-cittadino/.../albi-elenchi`), shared by all rows; the
  verifiable key is the **ABI code** in `accreditation_number`. Founder-approved class → pending,
  vetter confirms. Independently checked: all 7 phones are `+39` (the Intesa self-correction took —
  0 `+49` in the final NDJSON), ABI codes are the canonical Italian codes (UniCredit 02008, Intesa
  03069, Banco BPM 05034, FinecoBank 03015, Banca Mediolanum 03062, Deutsche Bank S.p.A. 03104, BNL
  01005).
- **Collision re-check — predicted AND confirmed clean (0 mis-attach).** The Santander-class risk was
  flagged for Deutsche Bank S.p.A. (IT) vs the Madrid "Deutsche Bank, S.A.E." (ES). Computed
  `_name_key` (from `vendor_harvester`, the exact function promote() uses) for all 7 against every prod
  supplier: **no matches** — `_name_key` keeps the legal-form token, so `deutschebankspa` ≠
  `deutschebanksae` (contrast Santander, where ", S.A." + "(Brasil)" both stripped to
  `bancosantander`). Post-apply, all 7 candidates promoted onto **new IT suppliers** created today (the
  promoted_supplier_id-vs-country query returned empty). No correction needed.
- Landed: **+7 new suppliers** (UniCredit, Intesa Sanpaolo, Banco BPM, FinecoBank, Banca Mediolanum,
  Deutsche Bank S.p.A., BNL — IT/banks, pending). Tripwire: `ssc` `approved` **130 → 130** md5
  unchanged; pending 993 → 1000.

## Honesty notes
- `accreditation_number` is NULL on all 4 — FIDI publishes only a FAIM expiry year and EuRA no
  number, so Otto invented none. `accreditation_expiry` column is always blank (the NDJSON carries
  no expiry). The vetter confirms each firm on the register at `/admin/vetting-queue`.
- Nothing here is served. Promotion to served is the separate human approve-to-serve gate.

## Pipeline (per sub-batch)
```bash
PY=.venv311/bin/python
$PY scripts/convert_vendor_ndjson_to_csv.py <dir>/vendor_candidates.csv <dir>/src/*.ndjson
# re-verify each source_url against its register (HTTP 200 + name on page), then:
$PY scripts/land_vendor_candidates.py <dir>/vendor_candidates.csv --apply --promote
```
