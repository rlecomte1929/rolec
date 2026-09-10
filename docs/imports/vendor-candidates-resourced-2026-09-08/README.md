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

### XX-DE schools (Berlin) — `vendor-resourced-xx-de-schools-2026-09-09` (landed 2026-09-09)
- Source (GCS): `1788962235856_iwvdtr4c.ndjson` (+ manifest `1788962239364_gjn08ir3.json`).
- Otto manifest: **8 sourced, 2 rejected** — rejects honest: BBIS (campus in Kleinmachnow/Brandenburg,
  not Berlin), SIS Swiss (only a Kita/daycare registration, no school Schulnummer).
- **Register type = per-entity, SERVER-RENDERED (Berlin Schulportrait).** Each `source_url` is the
  official `bildung.berlin.de/schulverzeichnis/Schulportrait.aspx?IDSchulzweig=…` per-entity page, and
  `accreditation_number` is the público Berlin Schulnummer. Unlike the NSR SPA, these render
  server-side — independently verified all 8 by direct curl: HTTP 200, each page contains its own
  school name AND its own Schulnummer (JFK 06K01, Metropolitan 01E34, Kant/Berlin International 04P42,
  British-Sekundarschule 04P40, British-Grundschule 04P39, Phorms Berlin Mitte 01P18, Cosmopolitan
  01P22, Berlin Bilingual 02P11).
- `_name_key` predictor: all 7 distinct keys are new (0 prod collision — the existing DE schools are
  all Munich/Frankfurt, so "Berlin Metropolitan School" ≠ "Metropolitan School Frankfurt" and "Phorms
  Berlin Mitte" ≠ "Phorms Schule München"; different domains).
- **Berlin British School folded to one supplier (by design).** Its two registered units — Integrierte
  Sekundarschule (04P40) and Grundschule (04P39) — share one website (`berlinbritishschool.de`) and one
  `_name_key`, so the second was website-deduped at stage and capability-deduped at promote
  ("Duplicate capability: same service/coverage/country/city"). Result: ONE "Berlin British School
  (Integrierte Sekundarschule)" supplier — the right catalog unit (a family enrols at the institution,
  not one campus). The Grundschule's Schulnummer 04P39 is preserved in the committed NDJSON; the vetter
  can note both units / tidy the supplier name.
- Landed: **+7 new suppliers** (JFK, Berlin Metropolitan, Kant/Berlin International, Berlin British
  School, Phorms Berlin Mitte, Berlin Cosmopolitan, Berlin Bilingual — DE/schools, pending) — the first
  Berlin coverage. Tripwire: `ssc` `approved` **130 → 130** md5 unchanged; pending 1000 → 1007.
- Scope caveat (as with Oslo): country-scoped (DE) though schools are city-local — vetter reconciles.

### XX-DE schools (Frankfurt) — `vendor-resourced-xx-de-frankfurt-schools-2026-09-09` (landed 2026-09-09)
- Source (GCS): `1788964116130_vivoiagi.ndjson` (+ manifest `1788964117474_vpd6g2f9.json`).
- Otto manifest: **8 sourced, 2 rejected** — rejects honest: FIS + ISF (the two most famous — but
  they are *anerkannte Ergänzungsschule*, NOT in the searchable Hessische Schuldatenbank, so Otto
  refused to invent a school_no).
- **Register type = per-entity, SERVER-RENDERED (Hessische Schuldatenbank).** `source_url` =
  `schul-db.bildung.hessen.de/schul_db.html/details/?school_no=<id>` — Otto used the resolvable
  `/details/?school_no=` format (the `?_do=detail` variant returns the search form). **Confirmed it
  matches the #2191 Hessen `entry_url_pattern` (`schul_db\.html/details/\?school_no=\d+`) before
  landing** — all 8 pass the tier gate. Independently curl-verified all 8: HTTP 200, name + own
  school_no on each page.
- Landed: **+6 new suppliers** (International Bilingual Montessori, SIS Swiss International School
  Frankfurt, Europäische Schule RheinMain, accadis International School, ASB Erasmus Gymnasium, ASB
  Erasmus Grundschule — DE/schools, pending). Frankfurt was previously covered only by Metropolitan;
  these are net-new Rhein-Main coverage. Tripwire: `ssc` `approved` **130 → 130** md5 unchanged;
  pending 1007 → 1013.
- **Metropolitan School Frankfurt — true dup**, correctly skipped (already a prod supplier,
  `m-school.de`).
- **⚠️ Phorms Frankfurt HELD — `dedupe_key` false-positive (pipeline limitation).** `dedupe_key` is the
  **registrable domain** (eTLD+1), so Phorms Frankfurt (`frankfurt.phorms.de` → `phorms.de`) collides
  with the already-staged Phorms Berlin Mitte (`berlin-mitte.phorms.de` → `phorms.de`) and was
  skipped at stage — even though it is a **distinct** Frankfurt school (school_no 4383, different
  city). Not a true duplicate. Its evidence is preserved in the committed NDJSON; it needs a distinct
  landing (a per-campus dedupe_key refinement for multi-campus chains, or a manual add). Watch this on
  any chain that runs `<city>.<chain>.<tld>` subdomains (Phorms, SIS, etc.).
- ASB Erasmus's two units (Gymnasium 4390 + Grundschule 4381) landed as **two distinct suppliers**
  (different websites + the unit type is inline in the name, so distinct `_name_key`) — contrast Berlin
  British School, which folded (shared website + parenthetical unit).

### XX-SE banks (Stockholm) — `vendor-resourced-xx-se-banks-2026-09-09` (landed 2026-09-09) — first capital-first empty vein
- Source (GCS): `1788966088577_eiycrde7.ndjson` (+ manifest `1788966142028_0268tlqa.json`).
- Otto manifest: **7 sourced, 4 rejected** — rejects honest: Länsförsäkringar + Danske filial +
  Collector/Norion (no resolving `details?id=` page → refused to guess); and the Nordea **parent**
  (id 168253, foreign cross-border "saknas") — Otto correctly sourced the Swedish **filial** (id
  168257) instead.
- **Register type = per-entity, SERVER-RENDERED (Finansinspektionen företagsregister, HTTP_LISTING
  tier 2).** All 7 `source_url`s are the correct `fi.se/.../company-register/details?id=<n>` form
  (clears the #2191 `entry_url_pattern` gate — the framing fix we caught before dispatch worked).
  Independently verified all 7 by curl: HTTP 200, bank name + `orgnr` on each page. `orgnr` in
  `accreditation_number`.
- **⚠️ Swedbank HELD — national-arm collision.** `_name_key` predictor (pre-apply) flagged Swedbank
  AB (Sweden, orgnr 502017-7753) colliding with the EXISTING **Lithuanian** `"Swedbank", AB` (source
  `lb.lt`, capability LT) — the same Santander-class risk. Excluded from the CSV pre-apply to avoid
  mis-attaching a SE/banks cap onto the Lithuanian entity; evidence preserved in the committed NDJSON;
  held for a correct re-land. Nordea filial did NOT collide (distinct `_name_key`).
- Landed: **+6 new suppliers** (SEB, Svenska Handelsbanken, SBAB, ICA Banken, Avanza, Nordea Bank Abp
  filial i Sverige — SE/banks, pending), 0 mis-attach (post-apply promoted_supplier_id-vs-country
  check empty). Tripwire: `ssc` `approved` **130 → 130** md5 unchanged; pending 1013 → 1019.

### XX-ES legal_admin (Madrid immigration lawyers) — `vendor-resourced-xx-es-legal-2026-09-09` (landed 2026-09-09) — first ES/legal vein
- Source (GCS): `1788969218371_jl39jitv.ndjson` (+ manifest `1788969222290_d9z23d5n.json`).
- Otto manifest: **7 sourced, 6 rejected** — rejects honest, all "no ICAM colegiado número published"
  (JD Immigration, Sterna, AGM, Ceca Magán, García de Ceca, IG Abogados Extranjería). All 7 sourced
  are extranjería (immigration) firms — on-scope.
- **Register type = PUBLIC_REGISTER (abogacia.es — Censo General de Letrados / ICAM).** Confirmed
  independently: **all 7 `source_url`s are the wired `abogacia.es` Censo page** (0 `icam.es`, 0
  firm-site → no tier-3 reject). `accreditation_number` = a real ICAM **colegiado número** tied to one
  named immigration lawyer per firm (PFBernal 68283, LG/Lino García 138891, MigrationLaw 97778,
  Iturralde García 56732, Lacaci & Delgado 95851, Lexey 118271, Ágreda 108649). Founder-approved
  PUBLIC_REGISTER lane → pending, vetter confirms.
- **Vetter provenance note:** 5 of 7 colegiado números were read off the firm's own about/team page;
  **2 — Lacaci & Delgado (95851) and Ágreda Abogadas (108649) — were read from the APAEM member
  directory (apaem.net/asociados/)**, not the firm's own site (still real ICAM números, documented in
  the manifest notes). Confirm all 7 against icam.es at /admin/vetting-queue.
- `_name_key` predictor: all 7 new (0 prod collision — ES/legal was an empty vein). Landed: **+7 new
  suppliers** (ES/legal_admin, pending), 0 mis-attach. Tripwire: `ssc` `approved` **130 → 130** md5
  unchanged; pending 1019 → 1026.

### XX-IT housing_agencies (Rome real-estate agencies) — `vendor-resourced-xx-it-housing-rome-2026-09-09` (landed 2026-09-09) — first vein through the throttle
- Source (GCS): `1788980836418_vuknxcci.ndjson` (+ manifest `1788980840083_fdjnn0e3.json`).
- Otto manifest: **4 sourced, 11 rejected** — strong honest rejects: wrong-province REA (Renting
  Rome=Milan, Agenzia Roma=Padova, Professional Relo=Vimercate/MB), law-firm category mismatch
  (Boschetti — had a Rome REA but is not an agenzia), US-based (Roma Rentals SPQR), Florence
  (Lionard), no REA published (Battisti, Easy Living, Great Properties, Impatria, Gabetti franchisor).
- **Register type = PUBLIC_REGISTER (Registro Imprese / REA — Camere di Commercio).** Confirmed
  independently: all 4 `source_url`s = the wired `registroimprese.it` (0 firm-site). REA número in
  `accreditation_number` (Boom Rome/Egidi RM-1710623, Roma Real Estate/Studio Fori RM-919320,
  Exclusive RE/Christie's/Loyal Immobili 1434347, Coldwell Banker Italy/Daisy56 RM-1388520).
- **Vetter flags:** (1) Exclusive RE's REA `1434347` is published WITHOUT the `RM-` prefix — confirm
  it's a Roma CCIAA number against the live Registro Imprese; (2) registroimprese.it is captcha-walled,
  so REA numbers were read off each firm's OWN site footer/about — vetter confirms each against the
  live register before pending→verified.
- `_name_key` predictor: all 4 new (the international brands carry local legal entities — Daisy56,
  Loyal Immobili, Egidi, Studio Fori — so Coldwell Banker/Christie's don't collide with any bare-brand
  supplier). Landed: **+4 new suppliers** (IT/housing_agencies, pending), 0 mis-attach. Tripwire: `ssc`
  `approved` **130 → 130** md5 unchanged; pending 1026 → 1030.

### XX-IT housing_agencies (Milan real-estate agencies) — `vendor-resourced-xx-it-housing-milan-2026-09-09` (landed 2026-09-09)
- Source (GCS): `1788982852398_bbu6oi1w.ndjson` (+ manifest `1788982853189_mnk7p34y.json`).
- Otto manifest: **5 sourced, 8 rejected** — honest rejects: no self-published REA (Milano Relocation,
  Milanhouses, RossoMattone), national coordinator not a Milan agenzia (Impatria), UK-registered (Casa
  Londra), Engel & Voelkers (only P.IVA self-published), Bonola (no MI- prefix). Notably **Habitare
  Service was REJECTED** — its REA MI-1928391 exists on a third-party billing site but is NOT
  self-published on its own site → correctly rejected per the firm-published rule (no fabrication).
- **PUBLIC_REGISTER (registroimprese.it / REA).** All 5 `source_url`s = wired `registroimprese.it`
  (0 firm-site). All 5 REA numbers are province **MI** (Otto respected the MI hint): Housy Milano/Up-Town
  MI-2106000, Mihouz/Andreoni MI-2719490, Wolf and Wolf MI-2052329, Smith Agency MI-2027818, Welcome
  Home/Sforza MI-1945017.
- Same vetter note as Rome: registroimprese.it captcha-walled → REA read off each firm's own site →
  vetter confirms against the live register.
- `_name_key` predictor: all 5 new. Landed: **+5 new suppliers** (IT/housing_agencies, pending), 0
  mis-attach. Tripwire: `ssc` `approved` **130 → 130** md5 unchanged; pending 1030 → 1035.

### XX-IT housing_agencies (Florence real-estate agencies) — `vendor-resourced-xx-it-housing-florence-2026-09-09` (landed 2026-09-09)
- Source (GCS): `1788984120203_ns5bmvur.ndjson` (+ manifest `1788984168939_dmaxj0i3.json`).
- Otto manifest: **6 sourced, 4 rejected** — honest rejects: Pitcher & Flaccomio (P.IVA only), Move to
  Florence (individual concierge), Dreamer RE (3rd-party-only REA + luxury-not-expat), Smart Move
  (visa consulting, not an agenzia).
- **PUBLIC_REGISTER (registroimprese.it / REA).** All 6 `source_url`s = wired `registroimprese.it`
  (0 firm-site); REA province FI (Florence and Abroad FI-357907, Apartments Florence FI-602633,
  Apartments in Florence/Konnettiamo FI-656840, Apartments Florence Real Estate FI-640122, Tuscan
  Feeling FI-656381). **Vetter note:** House in Florence (E.T. di Federico Pieri) cites a *Ruolo
  Agenti Immobiliari* roll number "Nr. 2807 CCIAA Firenze" (not a REA) — still a Firenze CCIAA
  registration; vetter confirms. Same captcha-walled caveat as Rome/Milan (REA read off firm sites).
- `_name_key` predictor: all 6 distinct + new — the three "Apartments Florence" variants key
  distinctly (`apartmentsflorencesrl` / `apartmentsinflorence` / `apartmentsflorencerealestate…`), no
  false merge. Landed: **+6 new suppliers** (IT/housing_agencies, pending), 0 mis-attach. Tripwire:
  `ssc` `approved` **130 → 130** md5 unchanged; pending 1035 → 1041. (IT housing now 15: Rome 4 +
  Milan 5 + Florence 6.)

### XX-SE housing_agencies (Stockholm estate agents) — `vendor-resourced-xx-se-housing-stockholm-2026-09-09` (landed 2026-09-09) — first SE/housing vein
- Source (GCS): `1788986908070_qkymoni4.ndjson` (+ manifest `1788986913359_ulyhqh6r.json`).
- Otto manifest: **4 sourced, 7 rejected** — honest rejects: agents no longer on the FMI register,
  Danish co, relocation-consulting with no FMI-registered agent, HR-relo (not a broker), booking
  platform, furnished-apt manager, one unreachable.
- **Register type = PUBLIC_REGISTER (Fastighetsmäklarinspektionen / FMI — statutory estate-agent
  register).** All 4 `source_url`s = wired `fmi.se` (0 firm-site). Individual-registration shape
  (like abogacia): each agency cites a NAMED agent's FMI registreringsnummer in `accreditation_number`
  (Residensportalen/Foxen 32848, Estate Fastighetsbyrå/Gergils Brännhult 31950, Victory Stockholm/
  Magnusson 44637, Quality Living/Öberg 32803); named agent in notes. Otto cross-confirmed each FMI
  number via maklarupplysning.se / maklarkontroll.se (both pull from the FMI register).
- `_name_key` predictor: all 4 new. Landed: **+4 new suppliers** (SE/housing_agencies, pending), 0
  mis-attach. Tripwire: `ssc` `approved` **130 → 130** md5 unchanged; pending 1041 → 1045. (Converter
  note: the record's lowercase `xx-SE` corridor is harmless — convert derives the corridor from
  `country=SE` → XX-SE, country_code SE.)

### XX-IT housing_agencies (Turin real-estate agencies) — `vendor-resourced-xx-it-housing-turin-2026-09-09` (landed 2026-09-10)
- Source (GCS): `1788991408705_yso6051y.ndjson` (+ manifest `1788991411714_5z9l07gq.json`).
- Otto manifest: **8 sourced, 6 rejected** — sharp province/eligibility rejects: Turin Relocation
  (self-declares *"non siamo ne broker ne un agenzia immobiliare"* — not a licensed agency), Italia
  Affitti Torino (franchise page shows Abruzzo parent P.IVA 02241270681, no Turin REA), Habitare
  Service (Milan HQ, province MI not TO), Urban House Hub (site returned no text, unverifiable),
  Gruppo Il Sestante (REA 1096606 with no province prefix — could not confirm TO), ItaliaCasa
  (REA MC 193326 = Macerata, not Turin).
- **PUBLIC_REGISTER (registroimprese.it / REA).** All 8 `source_url`s = wired `registroimprese.it`
  (0 firm-site). All 8 REA numbers province **TO**: Italian Property Group TO-1278035, Rubiolo
  Immobiliare TO 1189434, Studio Gran Madre TO 835822, Chiusano & C. Immobiliare TO 791891, Fasano
  Immobiliare TO-1214239, SIV Real Estate TO-1236771, Krea Immobiliare TO 1329662, IO Immobiliare
  Ottaviani TO 1265282. Same vetter note as Rome/Milan/Florence: registroimprese.it is captcha-walled
  → REA read off each firm's own site → vetter confirms against the live register at
  `/admin/vetting-queue`.
- Dedup: 0 existing (a spurious `%siv%` substring hit on `exclusi**v**ere.it` is not a real match —
  the actual SIV firm `sivtorino.it` is new). `_name_key` predictor: all 8 distinct + new. Landed:
  **+8 new suppliers** (IT/housing_agencies, pending), 0 mis-attach. Tripwire: `ssc` `approved`
  **130 → 130** md5 `1c4c3899925c5a8c4b3c168abcfbfc22` unchanged; pending 1045 → 1053. (IT housing
  now 23: Rome 4 + Milan 5 + Florence 6 + Turin 8.)

### XX-IT housing_agencies (Naples real-estate agencies) — `vendor-resourced-xx-it-housing-naples-2026-09-09` (landed 2026-09-10)
- Source (GCS): `1788993143006_yd0ghooc.ndjson` (+ manifest `1788993146697_uaw9p2z8.json`).
- Otto manifest: **6 sourced, 6 rejected** — honest rejects: My Place (Airbnb host, not agency),
  Edilblu (Capri not Naples), Casagency (REA only in aggregators, not self-published),
  L'Immobiliare (P.IVA only), Grimaldi/Faggella (no verifiable REA).
- **PUBLIC_REGISTER (registroimprese.it / REA).** All 6 `source_url`s = wired `registroimprese.it`
  (0 firm-site). All REA numbers province **NA**: Knight Immobiliare NA-648197, 360° Real Estate/
  360RES NA-973451, RE/MAX Immobiliari Uniti NA-806141, FGIMMOBILIARE (REPLAT Affiliato Bagnoli)
  NA-1055730, Erre Emme NA-725632, Coldwell Banker 24RE NA-1562255. Same captcha-walled caveat as
  Rome/Milan/Florence/Turin (REA read off firm sites; vetter confirms on the live register).
- `_name_key` predictor: all 6 distinct + new (RE/MAX and Coldwell Banker franchise names key with
  their local qualifiers — `remaximmobiliariuniti`, `coldwellbanker24re` — so no false merge onto a
  bare brand). **Landed: +5 new suppliers** (IT/housing_agencies, pending), 0 mis-attach.
- **⚠ 1 dropped (domain-dedup, not a reject): Coldwell Banker 24RE.** Its registrable domain
  `coldwellbanker.it` was already staged+promoted by a *different* Coldwell Banker franchisee
  (`Coldwell Banker Italy — Daisy56 S.r.l.`, id `vc-5d3c6032…`, pending). `stage()` keys on the
  registrable domain, so the second franchisee on the same corporate domain is treated as
  already-held and not re-inserted (no candidate row written). It is a genuinely distinct entity
  (own REA NA-1562255, Naples) but was **not force-landed** — inventing a distinct domain to defeat
  the dedup would game the gate. A vetter who wants the Naples office can add it as a location on the
  existing Coldwell Banker supplier. Tripwire: `ssc` `approved` **130 → 130** md5
  `1c4c3899925c5a8c4b3c168abcfbfc22` unchanged; pending 1053 → 1058. (IT housing now 28: Rome 4 +
  Milan 5 + Florence 6 + Turin 8 + Naples 5.)

### XX-IT housing_agencies (Bologna real-estate agencies) — `vendor-resourced-xx-it-housing-bologna-2026-09-09` (landed 2026-09-10)
- Source (GCS): `1788994596099_g90e7swq.ndjson` (+ manifest `1788994597786_dtfzd5iw.json`).
- Otto manifest: **7 sourced, 8 rejected** — honest rejects: Relocate (consultant, no REA),
  Engel&Völkers / Coldwell Banker / Malossini / Abitare (P.IVA-only), Giordani / Immobiliare Maggiore
  (no own-site REA), Felsina (branch-only).
- **PUBLIC_REGISTER (registroimprese.it / REA).** All 7 `source_url`s = wired `registroimprese.it`
  (0 firm-site). All REA province **BO**: Mondore BO-513838, InquiliniDOC/Daniele Castagna BO-541703,
  Casa dei Professionisti BO-425339, Studio Giannerini BO-426997, Realkasa RK Andrea Costa BO-504653,
  Realkasa RK Azeglio BO-514022, Appartamenti Bologna/Andrea Cerasi BO-495281. Vetter note:
  Appartamenti Bologna's REA was read from a Google snippet (site fetch-blocked) — vetter confirms on
  the live site; same captcha-walled register caveat as the other IT/housing cities.
- **Corridor note:** the records carried `corridor="INTL-IT"` (Otto's mid-run choice for "generic
  international→Italy"), **harmless** — the converter derives the corridor from `country=IT` → `XX-IT`
  and ignores the record's corridor field (same as the earlier `xx-SE` case). CSV corridor = XX-IT,
  country_code IT, correctly scoped.
- **Two Realkasa offices share `realkasa.it` but BOTH landed** (RK Andrea Costa `vc-5fd19ca1…`, RK
  Azeglio `vc-c4797a71…`). This refines the [[franchise domain-dedup]] rule: the domain collision is
  **within this one run**, so the 2nd is staged `status='duplicate'` **but still promoted** — promote()
  creates by `_name_key` (distinct: `…rkandreacostasrl` vs `…rkazegliosrl`) and `create_supplier`
  dedups on exact NAME (distinct), so both become separate suppliers. The Naples Coldwell drop was
  different: that domain was held by a *prior run's* candidate, which `stage()` drops before insert.
  **Rule of thumb: same-domain firms in the SAME batch both land; a firm whose domain a PRIOR batch
  already landed is dropped.**
- `_name_key` predictor: all 7 distinct + new. Landed: **+7 new suppliers** (IT/housing_agencies,
  pending), 0 mis-attach. Tripwire: `ssc` `approved` **130 → 130** md5
  `1c4c3899925c5a8c4b3c168abcfbfc22` unchanged; pending 1058 → 1065. (IT housing now 35: Rome 4 +
  Milan 5 + Florence 6 + Turin 8 + Naples 5 + Bologna 7.)

### XX-IT housing_agencies (Genoa real-estate agencies) — `vendor-resourced-xx-it-housing-genoa-2026-09-09` (landed 2026-09-10)
- Source (GCS): `1788996167965_9xi25ne9.ndjson` (+ manifest `1788996171995_nc59d6mg.json`).
- Otto manifest: **5 sourced, 5 rejected**. Franchise-preference now working: Engel & Völkers Genova
  rejected (shared `engelvoelkers.com`, no local REA published).
- **PUBLIC_REGISTER (registroimprese.it / REA).** All 5 `source_url`s = wired `registroimprese.it`
  (0 firm-site); corridor **XX-IT** explicit (no more INTL-IT drift). REA province **GE**: Genova
  International/Karolina Loshuk GE-520864, Immobiliare Z.B. GE-377204, Lo Presti Immobiliare GE-514379,
  Luisa Casareto GE-504866. **Vetter notes:** (a) Studio Immobiliare AG carries a *Ruolo Agenti
  Immobiliari CCIAA Genova* number (n. 1526 del 26/09/1995), not a REA GE-XXXXXX — a valid Genova CCIAA
  agent registration (same shape as Florence's "House in Florence"); vetter confirms at CCIAA Genova
  sezione agenti immobiliari. (b) Luisa Casareto + Immobiliare Z.B. REAs were read from CCIAA data
  (ufficiocamerale.it), not the firm footer — a standard registroimprese lookup confirms both.
- Two firms (Studio Immobiliare AG, Luisa Casareto) publish no website → keyed by name (the harvest's
  documented no-domain fallback), not by domain; both staged + promoted fine.
- `_name_key` predictor: all 5 distinct + new. Landed: **+5 new suppliers** (IT/housing_agencies,
  pending), 0 mis-attach. Tripwire: `ssc` `approved` **130 → 130** md5
  `1c4c3899925c5a8c4b3c168abcfbfc22` unchanged; pending 1065 → 1070. (IT housing now 40: Rome 4 +
  Milan 5 + Florence 6 + Turin 8 + Naples 5 + Bologna 7 + Genoa 5.)

### XX-IT housing_agencies (Verona real-estate agencies) — `vendor-resourced-xx-it-housing-verona-2026-09-09` (landed 2026-09-10)
- Source (GCS): `1788997711202_s4bga7kw.ndjson` (+ manifest `1788997766496_72r73yca.json`).
- Otto manifest: **7 sourced, 7 rejected** (counts reconcile: 7 ndjson objects = total_sourced 7).
  Honest rejects: commercial-only, industrial-only, residential-sales-only, out-of-city
  (Tregnago/Villafranca/Castel d'Azzano); Engel & Völkers Verona City (GBSRE S.r.l.) rejected —
  franchise, no firm-published REA; Immobiliare Castello excluded (REA present but out of target city).
- **PUBLIC_REGISTER (registroimprese.it / REA).** All 7 `source_url`s = wired `registroimprese.it`
  (0 firm-site); corridor **XX-IT** explicit. REA province **VR**: Area Affari VR-354521, Finalmente
  Casa Verona VR-396194, Immobiliare Verona Centrale VR-383018, Caloi Immobiliare VR-420849,
  Immobiliare Maffei VR-389338, Puccio Case VR-418952, Veronahome VR-422119. Same captcha-walled
  register caveat — vetter confirms on the live register.
- `_name_key` predictor: all 7 distinct + new; no franchise/multinational, no domain collisions.
  Landed: **+7 new suppliers** (IT/housing_agencies, pending), 0 mis-attach. Tripwire: `ssc`
  `approved` **130 → 130** md5 `1c4c3899925c5a8c4b3c168abcfbfc22` unchanged; pending 1070 → 1077.
  (IT housing now 47: Rome 4 + Milan 5 + Florence 6 + Turin 8 + Naples 5 + Bologna 7 + Genoa 5 +
  Verona 7.)

### XX-SE housing_agencies (Gothenburg estate agents) — `vendor-resourced-xx-se-housing-gothenburg-2026-09-09` (landed 2026-09-10) — THIN
- Source (GCS): `1788998901052_vnkey404.ndjson` (+ manifest `1788998902611_yiv6qa33.json`).
- Otto manifest: **1 sourced, 6 rejected** (counts reconcile). Honest rejects: Key Relocation Center,
  Human Entrance, Residensportalen (relocation/destination-service, no FMI reg), Solveria + Rentaborg
  (rental booking/listing platforms, not licensed mäklarföretag), Sweden Relocators (Malmö immigration
  consultancy, no FMI).
- **PUBLIC_REGISTER (FMI / fmi.se).** The 1 `source_url` = wired `fmi.se`, corridor **XX-SE**. Nordic
  Relocation Group AB, **FMI reg# 40955**, body Fastighetsmäklarinspektionen. **Shape note for vetter:**
  40955 is the FMI *firm* (mäklarföretag) registration — Otto searched the företag register — NOT a
  named-individual mäklare reg# as in the Stockholm batch. Valid + verifiable, firm-level. The applier
  stores `accreditation_number` verbatim and does not require the individual shape, so it lands fine;
  vetter confirms on the FMI register.
- `_name_key` predictor: `nordicrelocationgroupab` new; no existing "Nordic Relocation" in prod (no
  mis-attach into the movers/relocation catalog). Landed: **+1 new supplier** (SE/housing_agencies,
  pending), 0 mis-attach. Tripwire: `ssc` `approved` **130 → 130** md5
  `1c4c3899925c5a8c4b3c168abcfbfc22` unchanged; pending 1077 → 1078. (SE housing now 5: Stockholm 4 +
  Gothenburg 1.)
- **⚠ STRUCTURAL SIGNAL (founder decision, held) —** FMI ≈ estate agents who mainly handle SALES, so
  the fmi.se gate is structurally thin for the *rental-relocation* use case (expat rental home-finding
  in SE is dominated by relocation consultancies + rental platforms that are NOT FMI-registered).
  Expect ~1–3/city, not 5–12. Decision to take **after Malmö**: (a) keep mining SE/housing via FMI
  (clean but thin), or (b) pivot the SE-housing accreditation — accept relocation firms under a
  Bolagsverket org-nummer, or target a rental-specific register. Surfaced to the founder; not decided
  by the applier.

### XX-SE housing_agencies (Malmö estate agents) — `vendor-resourced-xx-se-housing-malmo-2026-09-09` (landed 2026-09-10) — completes SE/housing pivot
- Source (GCS): `1789001315964_ncs13r95.ndjson` (+ manifest `1789001319407_t6xymj9a.json`). (This one
  was wiped by an Audos reload mid-research, revived clean by a nudge — the delivered artifacts verify.)
- Otto manifest: **2 sourced, 4 rejected** (counts reconcile). Both firm-level FMI reg#,
  `source_url`=wired `fmi.se`, corridor **XX-SE**: Öresund Fastighetsförmedling AB 41270, Våningen &
  Villan Sverige AB 42969. Honest rejects: VF Malmö/Croisette (FMI firm #39659 CONFIRMED but
  commercial-only lokalförmedling, no residential — sharp reject), Sweden Relocators (no FMI), Hej
  Relocation (DSP, no FMI), Homii (rental platform, no FMI).
- `_name_key` predictor: both new; no existing Öresund/Våningen in prod (no mis-attach). Landed:
  **+2 new suppliers** (SE/housing_agencies, pending), 0 mis-attach. Tripwire: `ssc` `approved`
  **130 → 130** md5 `1c4c3899925c5a8c4b3c168abcfbfc22` unchanged; pending 1078 → 1080. **SE/housing
  pivot complete tonight: Stockholm 4 + Gothenburg 1 + Malmö 2 = 7 across 3 cities, all FMI-gated.**
  No more SE/housing until the founder rules on the FMI-vs-Bolagsverket gate decision above.

### XX-ES legal_admin (Barcelona immigration/extranjería lawyers) — `vendor-resourced-xx-es-legal-barcelona-2026-09-09` (landed 2026-09-10)
- Source (GCS): `1789002997489_vrohp8lq.ndjson` (+ manifest `1789003001606_i7j2rr12.json`). (Recovered
  from an Audos wipe via nudge; delivered artifacts verify.)
- Otto manifest: **4 sourced, 9 rejected** (counts reconcile). All 4 `source_url`=wired
  `www.abogacia.es` (censo de letrados), corridor **XX-ES**, category legal_admin, ICAB body,
  named-lawyer colegiado número: Rodríguez Calistro Abogados 36453 (María Elisa Rodríguez Calistro),
  Ventura Extranjería Abogados 46337 (Pau Ventura), Calero Legal Abogados 47049 (Domingo Calero),
  Català Reinón Abogados 19731 (Jordi Català Soriano).
- **Vetter notes (carried to pending):** (1) **Colegiado 19731 attribution conflict** — Otto sourced
  Català Reinón with 19731 for Jordi Català Soriano and rejected "BCN Extranjería" which claims 19731
  for Gemma Reinón Tardáguila (catala-reinon.es puts Gemma at 22600). Conservative attribution; vetter
  confirms 19731's true holder against the ICAB census before serve. (2) **36453 single-count** — the
  rejected national directory "Extranjería al Día" lists the same lawyer (Rodríguez Calistro, 36453)
  already sourced under Rodríguez Calistro Abogados; not double-counted (only the firm row is in the 4).
- `_name_key` predictor: all 4 distinct + new; no prod dup, no mis-attach. Landed: **+4 new suppliers**
  (ES/legal_admin, pending). Tripwire: `ssc` `approved` **130 → 130** md5
  `1c4c3899925c5a8c4b3c168abcfbfc22` unchanged; pending 1080 → 1084. (ES legal now 11: Madrid 7 +
  Barcelona 4.)

### XX-ES legal_admin (Seville immigration/extranjería lawyers) — `vendor-resourced-xx-es-legal-seville-2026-09-09` (landed 2026-09-10)
- Source (GCS): `1789009147649_r1p5zb4y.ndjson` (+ manifest `1789009149297_2xwwrokk.json`). (Completed
  after surviving the ~3-4AM Audos wipe window, nudge-revived; delivered artifacts verify.)
- Otto manifest: **5 sourced, 4 rejected** (counts reconcile). All 5 `source_url`=wired
  `www.abogacia.es`, corridor **XX-ES**, category legal_admin, ICAS named-lawyer colegiado: Bolonia
  Abogacía 8.538 (Max Adam Romero), Peralta Rojas Abogados 15.174 (Nilson David Peralta Rojas),
  Extranjería al Día — Germán Saldaña Espejo 8086, Despacho Paula Schmid Porras 13.737, Marta Reina
  Grau 16.931. Honest rejects: Lexpats/Sandra Stojakovic (no número), Abogado Extranjería Sevilla (no
  named lawyer), QD Abogados (no número + Huelva), Miguel Ángel Lechuga (número only in a pleitex
  aggregate, not self-published).
- **Vetter notes (carried to pending):** (1) Marta Reina Grau 16.931 — número sourced from a
  self-submitted Pleitex directory profile (`pleitex.com`), no standalone firm site; verify against the
  ICAS register before serve. (2) "Extranjería al Día" appears here **sourced** as a specific named
  Sevilla lawyer (Germán Saldaña Espejo, ICAS 8086), whereas in Barcelona the same brand was **rejected**
  as a national directory — here it is a valid named-lawyer attribution (distinct `_name_key`, no
  double-count).
- `_name_key` predictor: all 5 distinct + new; no prod dup, no mis-attach. Landed: **+5 new suppliers**
  (ES/legal_admin, pending). Tripwire: `ssc` `approved` **130 → 130** md5
  `1c4c3899925c5a8c4b3c168abcfbfc22` unchanged; pending 1084 → 1089. (ES legal now 16: Madrid 7 +
  Barcelona 4 + Seville 5.)

### XX-ES legal_admin (Valencia) — `vendor-resourced-xx-es-legal-valencia-2026-09-09` — ⛔ PARKED, NOT LANDED (no artifact)
- **Nothing landed.** The ~3-5AM Audos reload window wiped this thread **6×**, each time before file
  assembly, so **no GCS NDJSON/manifest was ever produced**. The applier does not hand-land firms from
  a relayed text list — no artifact = no auditable hash/count to verify, which is the guarantee this
  harvest exists to uphold (same call as the parked Rome IT/tax row).
- **2 firms CONFIRMED by the generator, recorded here for a calm rerun** (abogacia.es / ICAV / XX-ES /
  legal_admin): Joaquín García Pastrana — ICAV 20503; Inmaculada Moncho Giner — ICAV 14318 (immigration
  specialist). Also seen mid-research: Díaz & Asociados; sharp reject noted: Gloria Ferrandis (Sueca
  bar #172, not ICAV). **To land:** re-run the ICAV brief when Audos is calm → get the clean
  NDJSON+manifest on GCS → curl+verify+`--apply --promote` like the other ES/legal cities (expect 5-8).
- Tripwire untouched (no write): `ssc` `approved` **130 | 1c4c3899925c5a8c4b3c168abcfbfc22**. ES legal
  stays 16 (Madrid 7 + Barcelona 4 + Seville 5) until Valencia is re-sourced with an artifact.

### XX-GB legal_admin (London immigration solicitors) — `vendor-resourced-xx-gb-legal-london-2026-09-10` (landed 2026-09-10) — first new-country (GB) batch
- Source (GCS): `1789017875150_4hx31ej8.ndjson` (+ manifest `1789017876612_dspdombz.json`).
- Otto manifest: **6 sourced, 2 rejected** (counts reconcile). Honest rejects: Reiss Edwards (no
  readable SRA# on own site), Colman Coyle (general practice, not work-visa specialised).
- **HTTP_LISTING (SRA / sra.org.uk).** All 6 `source_url`s are **per-entity** register pages matching
  the tier gate's `sraNumber=\d+` pattern (0 root fallbacks — see the GB pre-flight below), domain
  `www.sra.org.uk`, corridor **XX-GB**, category legal_admin, SRA number in `accreditation_number`:
  Bindmans LLP 484856, Fragomen LLP 459836, Gherson Solicitors LLP 824641, Magrath Sheldrick LLP
  484817, RLegal 380691, A Y & J Solicitors 633686. Vetter note: RLegal `accreditation_number` is
  zero-padded `00380691` (SRA number is 380691, leading zeros spurious) — vetter normalizes.
- **Dedup — Fragomen LLP already held, dropped safely (net +5, not +6).** Prod already had
  "Fragomen LLP" (GB/legal/**pending**, `vc-c3f90216`) AND "Fragomen Worldwide" (NO/legal/**approved**,
  served), both on `fragomen.com`. The candidate's dedupe_key `fragomen.com` matched → `stage()` dropped
  it (already held); it did NOT create a duplicate and did NOT touch the approved NO row (its `_name_key`
  `fragomen` matches the GB "Fragomen LLP", not `fragomenworldwide`). **Approved tripwire verified frozen
  across the write.**
- `_name_key` predictor: the 5 landed all distinct + new. Landed: **+5 new suppliers** (GB/legal_admin,
  pending), 0 mis-attach. Tripwire: `ssc` `approved` **130 → 130** md5
  `1c4c3899925c5a8c4b3c168abcfbfc22` unchanged; pending 1089 → 1094. (GB legal now 8: 3 prior — Fragomen,
  Kingsley Napley, Laura Devine — + Bindmans, Gherson, Magrath Sheldrick, RLegal, A Y & J.)

### GB pre-flight (2026-09-10) — all 5 GB registers are HTTP_LISTING, register-root REJECTS
Ran the tier gate from the live worktree before the GB phase. sra.org.uk/icaew.com/fca.org.uk/
get-information-schools.service.gov.uk/propertymark.co.uk are all wired (XX-GB), all
`Acquisition.HTTP_LISTING`, and `validate()` (vendor_harvester.py:214) rejects any `source_url` that
does not match the source's `entry_url_pattern`. So a **register-root URL bounces** — every GB row needs
its per-entity page. Required regex per register: **SRA** `sraNumber=\d+` · **ICAEW** `/firms/` · **FCA**
`/s/firm` · **GIAS** `/Establishment/Details/\d+` · **ARLA Propertymark** `/company/`. Flagged to the
generator before the first batch; London GB legal came back with per-firm URLs on all 6.

### XX-GB housing_agencies (London estate/lettings agents) — `vendor-resourced-xx-gb-housing-london-2026-09-10` (landed 2026-09-10)
- Source (GCS): `1789021761849_85a8cmgv.ndjson` (+ manifest `1789021795428_8sv6brzx.json`). (A reconnect
  caused a re-upload; the earlier `1789020730496` pair was superseded and ignored.)
- Otto manifest: **6 sourced, 2 rejected** (counts reconcile). Rejects: Chestertons, Savills (no London
  `/company/` page found).
- **HTTP_LISTING (ARLA Propertymark / propertymark.co.uk).** All 6 `source_url`s are per-entity
  `/company/` pages (0 root), domain `www.propertymark.co.uk`, corridor **XX-GB**. **Vetter note:**
  `accreditation_number` is the Propertymark branch **slug** (e.g. `knight-frank-9`) — Propertymark's
  `/company/` pages publish no numeric membership number; the vetter confirms each against the directory.
- **Franchise/chain dedup — net +2 of 6** (all six are big London chains): **Knight Frank** and **John D
  Wood & Co.** landed new. The other four were already held from an earlier GB/housing harvest and
  correctly did NOT duplicate:
  - **Hamptons International**, **Marsh & Parsons**, **Dexters** — domain-dedup dropped at stage (their
    firm domains `hamptons.co.uk` / `marshandparsons.co.uk` / `dexters.co.uk` already in prod).
  - **Foxtons** — its Tower-Bridge-branch site (`goandco.co.uk`) is a new domain so it staged, but
    `_name_key` `foxtons` matched the existing GB Foxtons at promote → attached (cap already present →
    absorbed), no duplicate created (Foxtons stays a single supplier).
- Landed: **+2 new suppliers** (GB/housing_agencies, pending), 0 mis-attach. Tripwire: `ssc` `approved`
  **130 → 130** md5 `1c4c3899925c5a8c4b3c168abcfbfc22` unchanged; GB/housing 4 → 6.

### XX-GB tax_finance (London expat-tax / chartered accountants) — `vendor-resourced-xx-gb-tax-london-2026-09-10` (landed 2026-09-10)
- Source (GCS): `1789023450599_aprmxtp4.ndjson` (+ manifest `1789023452196_cf3ge6ti.json`).
- Otto manifest: **7 sourced, 1 rejected** (counts reconcile). Reject: Tax Partners Ltd (generic SME, no
  expat specialisation).
- **HTTP_LISTING (ICAEW / find.icaew.com).** All 7 `source_url`s are per-entity `/firms/` pages (0 root),
  registrable domain `icaew.com`, corridor **XX-GB**, category tax_finance; `accreditation_number` = the
  ICAEW firm id from the URL.
- **Net +5 of 7** (dedup on marquee multi-office firms, all already held from an earlier GB/tax harvest):
  **Blick Rothenberg** (name + `blickrothenberg.com` domain match) and **Buzzacott Livingstone**
  (its `buzzacott.co.uk` domain already held by the existing "Buzzacott LLP") both domain-dedup dropped —
  no duplicate. Landed new: **Saffery LLP, Alliotts LLP, Gerald Edelman LLP, Moore Kingston Smith &
  Partners LLP, HaysMac LLP** (Moore Kingston Smith was flagged as a possible dedup but is genuinely new).
- `_name_key` predictor: the 5 landed all distinct + new. Landed: **+5 new suppliers** (GB/tax_finance,
  pending), 0 mis-attach. Tripwire: `ssc` `approved` **130 → 130** md5
  `1c4c3899925c5a8c4b3c168abcfbfc22` unchanged; GB/tax 2 → 7.

### XX-NL legal_admin (Amsterdam immigration/vreemdelingenrecht lawyers) — `vendor-resourced-xx-nl-legal-amsterdam-2026-09-10` (landed 2026-09-10) — first XX-NL land, FINAL cell of the run
- Source (GCS): `1789026083313_essmy5ik.ndjson` (+ manifest `1789026112888_iuo9wb9i.json`).
- Otto manifest: **6 sourced, 0 rejected** (counts reconcile).
- **PUBLIC_REGISTER (NOvA / advocatenorde.nl).** All 6 `source_url`s = wired `advocatenorde.nl`
  (`zoekeenadvocaat.advocatenorde.nl` subdomain, matched by suffix — no per-entity pattern needed for a
  PUBLIC_REGISTER), corridor **XX-NL**, category legal_admin. `accreditation_number` carries the named
  advocaat + their **real NOvA registration number** (Otto pulled the actual register numbers), e.g.
  Everaert/T.E. van Houwelingen-Boer 11613905609, Matpanözer/L.K. Matpanözer 11017333435, Spuistraat 10/
  B. Aydin 11831901571, Prakken d'Oliveira/E.E.M. Bezem 12075067103.
- **Net +4 of 6** — landed new: Everaert Advocaten, Matpanözer Advocatuur, Spuistraat 10 Advocaten,
  Prakken d'Oliveira Human Rights Lawyers. **De Vreede Immigration Law** and **Kroes Advocaten** were
  already held (NL/legal, from an earlier NL harvest) — `_name_key` collision → deduped, no duplicate.
- Landed: **+4 new suppliers** (NL/legal_admin, pending), 0 mis-attach. Tripwire: `ssc` `approved`
  **130 → 130** md5 `1c4c3899925c5a8c4b3c168abcfbfc22` unchanged; NL/legal 3 → 7.

### XX-NL housing_agencies (Amsterdam expat-rental brokers) — `vendor-resourced-xx-nl-housing-amsterdam-2026-09-10` (landed 2026-09-10)
- Source (GCS): `1789029500169_sx3v6325.ndjson` (+ manifest `1789029504879_m0my12gu.json`).
- Otto manifest: **8 sourced, 3 rejected** (counts reconcile). Rejects used the MVA "Certified Expat
  Broker" gate well: Ellen Mouthaan (Naarden, not Amsterdam), The Agency Amsterdam + CSV Makelaars
  (sales-only, no expat-broker designation).
- **PUBLIC_REGISTER (MVA / mva.nl).** All 8 `source_url`s = wired `www.mva.nl`, corridor **XX-NL**,
  category housing_agencies; `accreditation_number` = the named **MVA Certified Expat Broker** (a real
  expat-rental quality designation), e.g. Dutch Housing Centre/Jeroen de Bruijn KRMT, JLG/Dimitry Jansen
  RM, Ramon Mossel/Dianne van Vlerken KRMT.
- **Net +8 (all 8 landed).** Firms: Dutch Housing Centre, JLG Real Estate, De Graaf & Groot Makelaars,
  Engel & Völkers Amsterdam Zuid, Ramon Mossel Makelaardij, Broersma Werken en Wonen, Eefje Voogd
  Makelaardij, Forte Makelaars.
- **Franchise-domain refinement (important):** Engel & Völkers Amsterdam Zuid uses the global
  `engelvoelkers.com` domain, which prod already holds via E&V **Prague (CZ)** and E&V **Luxembourg (LU)**.
  It was therefore classified `status='duplicate'` at stage (domain seen in prod, cross-corridor) — BUT it
  **still landed as a NEW distinct NL supplier**, because the stage *drop* filter (`_staged_keys`) is
  **corridor+category-scoped**: `engelvoelkers.com` was staged under XX-CZ/XX-LU, not XX-NL, so it was not
  dropped; promote() then created it new via its distinct `_name_key` (`engelvolkersamsterdamzuid`), and
  the CZ/LU E&V rows were untouched (no mis-attach). This refines the Naples-Coldwell note: a same-domain
  franchise sibling drops **only** when the prior one was in the SAME corridor+category; a **cross-corridor**
  same-domain office lands as its own supplier.
- `_name_key` predictor: all 8 distinct + new. Landed: **+8 new suppliers** (NL/housing_agencies,
  pending), 0 mis-attach. Tripwire: `ssc` `approved` **130 → 130** md5
  `1c4c3899925c5a8c4b3c168abcfbfc22` unchanged; NL/housing 3 → 11.

### XX-NL banks (Amsterdam) — `vendor-resourced-xx-nl-banks-amsterdam-2026-09-10` — ⛔ PARKED, NOT LANDED (no artifact)
- **Nothing landed.** Audos instability across ~4 attempts / 40 min (a wipe/reset + transient "something
  went wrong" errors) — the research reached real DNB register codes but never uploaded a GCS file. No
  artifact = no hash/count to verify, so no hand-landing from a text list (same call as Valencia ES/tax).
- **Confirmed DNB-registered banks recorded for a calm rerun** (dnb.nl root, XX-NL, banks): ING B0163,
  ABN AMRO B0149, Triodos Bank B0195, bunq R127999; + Rabobank and Knab/Aegon Bank to confirm. **To land:**
  rerun the DNB brief when Audos is calm → clean NDJSON+manifest → curl+verify+`--apply --promote`.
  Expect net low after ABN/ING/Rabo multinational dedup, and run the `_name_key` national-arm predictor.
- Also parked (register issue, not Audos): **NL tax** — `afm.nl` is a financial-services register, not a
  tax-adviser bar; NBA/RB/NOB unwired → skipped until a real NL-tax register is wired (founder-flagged).
- Tripwire untouched (no write): `ssc` `approved` **130 | 1c4c3899925c5a8c4b3c168abcfbfc22**. NL banks
  stays at its prior count until re-sourced with an artifact.

### XX-AU legal_admin (Sydney migration agents) — `vendor-resourced-xx-au-legal-sydney-2026-09-10` (partial land 2026-09-10) — first XX-AU; ⚠ exposed a normalise_domain bug
- Source (GCS): `1789034426741_tydus30r.ndjson` (+ manifest `1789034430487_jxbmaqkp.json`).
- Otto manifest: **5 sourced, 8 rejected** (counts reconcile). All 5 `source_url`=wired `portal.mara.gov.au`
  (`mara.gov.au`, OMARA PUBLIC_REGISTER), corridor **XX-AU**, category legal_admin, `accreditation_number`
  = 7-digit MARN: WIDEN Migration Experts 1576536, DMA Migration 1798821, IME Advisors 2217902, Bay
  Migration Solution 1799395, KAN Migration Services 1807176.
- **Landed: +1 only (IME Advisors).** The other 4 were WRONGLY dropped as duplicates by a
  `normalise_domain()` bug — **not real dups.** `_COMPOUND_SUFFIXES` (vendor_harvester.py) lists `.co.uk`
  (so GB keyed correctly) but is **missing `.com.au`**, so every `*.com.au` site collapses to the bare
  registrable key `com.au`. WIDEN/DMA/Bay/KAN (all `.com.au`) therefore all keyed to `com.au`, which the
  2026-08-30 AU pass had already staged (it mis-keyed "Migration Centre of Australia" +
  "Australian Immigration Centre" to `com.au` too, and wrongly marked one `status='duplicate'`). IME
  Advisors survived only because it is `.com`, not `.com.au`.
- **Impact + fix:** every AU firm on a `.com.au` domain collapses to one key per corridor+category → AU
  housing/tax/banks would all drop to ~1/cell. Fix = add `com.au` (+ `.net.au`/`.org.au` and other
  multi-part ccTLD suffixes) to `_COMPOUND_SUFFIXES` + test.
- **RESOLVED 2026-09-10 — fix PR #2263 merged to main (`79cf9031`)**, `_COMPOUND_SUFFIXES` now includes
  `com.au` (+ the corridor ccTLD set; the PR also bundled a reference `manifest.json` on this dir so the
  fact-citation ratchet correctly excludes vendor batches — see that fix in the delivery notes). The 4
  held firms were **re-landed from this same CSV** (no re-research): with the fix they key distinctly
  (`widen.com.au` / `dmamigration.com.au` / `baymigration.com.au` / `kanmigration.com.au`) → **staged 4,
  promote 4** (IME correctly skipped as already-staged). **AU legal batch total = +5** (IME +1 then +4);
  fix confirmed live in the land env by the +4 (vs the buggy +1).
- Create-only guard held on both lands (approved count unchanged across each op): 130 across the IME
  land; **218 before and after the +4 re-land** (the founder's concurrent vetting had moved the approved
  baseline 130 → 218 — see the Valencia entry; the old fixed-md5 tripwire is retired). AU/legal
  **3 → 4 (IME) → 8 (+4 re-land)**.

### XX-ES legal_admin (Valencia extranjería lawyers) — `vendor-resourced-xx-es-legal-valencia-2026-09-10` (landed 2026-09-10) — UN-PARKS the earlier Valencia hold
- Source (GCS): `1789037619004_hp0369jo.ndjson` (+ manifest `1789037699891_e2puiit2.json`). Clean re-run
  after the earlier Audos-wipe park; `.es` domain → unaffected by the `.com.au` normalise bug.
- Otto manifest: **4 sourced, 10 rejected** (counts reconcile). All 4 `source_url`=wired `www.abogacia.es`,
  corridor **XX-ES**, category legal_admin, ICAV named-lawyer colegiado: Olguín Abogados 14262, Fernando
  Ortega Cano 17582, Romina María Chiquini Laude 19598, Modesto Martínez Vizuete 11729. Good discipline:
  the two parked SEEDS were **honestly rejected** on re-verification (García Pastrana ICAV 20503 =
  *derechos fundamentales*, not extranjería; Moncho Giner = Gandía not Valencia city, número unpublished),
  so all 4 are genuinely-verified NEW firms. 3 are individual advocates with no firm site → name-keyed.
- `_name_key` predictor: all 4 distinct + new; no prod dup, no mis-attach. Landed: **+4 new suppliers**
  (ES/legal_admin, pending). ES legal now 20 (Madrid 7 + Barcelona 4 + Seville 5 + Valencia 4).
- **Tripwire — invariant change (2026-09-10 ~11:01):** the campaign-long fixed `approved = 130 |
  1c4c3899925c5a8c4b3c168abcfbfc22` is now **RETIRED**: the founder began working `/admin/vetting-queue`
  and `admin@relopass.com` approved 86 caps in a bulk pass (approved pool 130 → 218; 139 harvest
  suppliers now live). That is the human gate working as designed, unrelated to this append-only land.
  The applier invariant is now **create-only**: each land only INSERTs new `pending` caps and never
  mutates an existing/approved cap. This land satisfied it — the approved count did not drop across the
  op, and the 4 new Valencia caps are `pending` (verified). Going forward the check is "my N caps landed
  pending + approved count did not decrease," not a fixed md5.

### XX-AU housing_agencies (Sydney) via NSW Fair Trading — `vendor-resourced-xx-au-housing-sydney-2026-09-10` (landed 2026-09-10) — THIN
- Source (GCS): `1789041729806_8fx5ydrh.ndjson` (+ manifest `1789041773132_2xgxc63n.json`).
- Otto manifest: **1 sourced, 8 rejected** (counts reconcile). Rejects: firm doesn't publish a NSW Fair
  Trading licence number on its site (Urban Renters, Property Providers, SydneySlice, Hunter James,
  Sydney Rental Search, Home Hunters Relocations) or holds the wrong state's licence (Relocate Sydney =
  Victorian REIV, Australian Relocation Managers = VIC).
- **PUBLIC_REGISTER (NSW Fair Trading / verify.licence.nsw.gov.au).** The 1 `source_url`=wired
  `verify.licence.nsw.gov.au`, corridor **XX-AU**, category housing_agencies. Find My Rental Property,
  NSW licence **20111067**. Its site is `findmyrentalproperty.com.au` and it keyed/staged distinctly —
  **another end-to-end confirmation the com.au fix (#2263) works** (a `.com.au` firm no longer collapses).
- Landed: **+1 new supplier** (AU/housing_agencies, pending). Create-only guard held: approved count
  **218 unchanged** across the op. AU/housing 4 → 5.
- **⚠ STRUCTURAL LEARNING (brief refinement, flagged not re-run):** the brief required the firm to
  *self-publish* its NSW licence number, but most Sydney agencies just say "fully licensed" → thin
  yield. Better future AU-housing brief: look each agency up **by name** on
  `verify.licence.nsw.gov.au` to obtain its licence#, rather than requiring self-publication (vetter
  confirms). Same shape as the SE/housing FMI thinness — the register is fine; the sourcing predicate
  was too strict.

### XX-AU tax_finance (Sydney) via TPB — `vendor-resourced-xx-au-tax-sydney-2026-09-10` — ⛔ PARKED, NOT LANDED (no artifact)
- **Nothing landed.** Audos errored right before upload across 3 attempts (research reached real TPB
  numbers each time). No GCS artifact → no hand-landing from a text list (same discipline as Valencia/
  NL banks/AU tax). Not a data or com.au-fix problem — purely Audos instability.
- **Confirmed TPB firms recorded for a calm rerun** (tpb.gov.au root, XX-AU, tax_finance): Murphy Tax /
  Bradley Murphy TPB 25999083 (⚠ registered Black Rock VIC but has a Sydney office — vetter's call on
  Sydney inclusion); HLB Mann Judd (NSW) Pty Ltd (ABN 32 001 500 358, Sydney expat-tax, TPB# to confirm);
  Expat Tax Specialists Pty Ltd (Sydney expat-tax); Pitcher Partners Sydney (TPB# to confirm). One clean
  TPB rerun should get 3-5.
- Tripwire untouched (no write): create-only invariant, approved count unchanged (no op). AU/tax stays
  at its prior count until re-sourced with an artifact.

### XX-AU banks (Sydney) via APRA — `vendor-resourced-xx-au-banks-sydney-2026-09-10` — ⛔ PARKED, NOT LANDED (no artifact)
- **Nothing landed.** Audos errored within ~4 min on 2 back-to-back attempts; no GCS artifact → no
  hand-landing (same discipline as Valencia / NL banks / AU tax). Lowest-value AU cell anyway — the
  major ADIs heavily dedup against the 2026-08-31 AU/global banks already in prod.
- **Confirmed APRA ADIs recorded for a calm rerun** (apra.gov.au ADI register root, XX-AU, banks):
  CBA/Commonwealth Bank, Westpac, ANZ, NAB, Macquarie Bank, ING Australia (ING Bank Australia Ltd),
  HSBC Australia, Bendigo & Adelaide Bank. Expect net low after dedup; run the `_name_key`+domain
  predictor + the #2219 national-arm guard on the foreign subs (ING/HSBC AU) before landing.
- Tripwire untouched (no write): create-only invariant, approved count unchanged (no op).
- **AU front summary:** legal **8** (5 net-new incl. the +4 com.au re-land) + housing **5** (+1) landed;
  **tax + banks PARKED** (Audos flakiness — firms recorded above). Next front: Canada (pre-flighted,
  all 5 registers wired PUBLIC_REGISTER).

### XX-CA legal_admin (Toronto immigration lawyers) via LSO — `vendor-resourced-xx-ca-legal-toronto-2026-09-10` (landed 2026-09-10) — first XX-CA; THIN
- Source (GCS): `1789050291683_u1h5z7v1.ndjson` (+ manifest `1789050295240_yb8h14ho.json`).
- Otto manifest: **1 sourced, 3 rejected** (counts reconcile; Audos flakiness forced an early wrap before
  more LSO#s could be confirmed). The 1 `source_url`=wired `lso.ca`, corridor **XX-CA**, category
  legal_admin: Sobirovs Law Firm, LSO **82485Q** (Mariam Jammal). Site sobirovs.com (`.com`).
- Rejects (real Toronto immigration firms, LSO# unconfirmed at close — candidates for a calm re-run):
  Bellissimo Law Group (Mario Bellissimo), CILF / Canadian Immigration Law Firm (Jacqueline Bonisteel),
  Bart Law. Same LSO#-in-footer extraction difficulty as the AU licence/TPB registers.
- `_name_key` predictor: new; no prod dup, no mis-attach. Landed: **+1 new supplier** (CA/legal_admin,
  pending). Create-only guard held: approved count **218 unchanged** across the op. CA/legal 3 → 4.
  First Canada land — the LSO register + XX-CA corridor confirmed working end-to-end (`.ca` bug-unaffected).

### XX-CA housing_agencies (Toronto) via RECO — `vendor-resourced-xx-ca-housing-toronto-2026-09-10` — ⛔ PARKED, NOT LANDED (no artifact) — STRUCTURALLY THIN
- **Nothing landed.** Otto's RECO Registrant Search lookup stalled on all 3 in-chat attempts (the
  reconnect-drops-the-in-progress-run Audos flakiness, ×3 across a pause). Per the "never invent an
  accreditation number" rule Otto refused to fabricate RECO registration numbers → **0 sourced /
  10 rejected**, no GCS artifact → no hand-landing from a text list (same discipline as Valencia /
  NL banks / AU tax / AU banks). `reco.on.ca` is a wired PUBLIC_REGISTER; the block was verifying each
  firm's RECO#, not the register wiring or the XX-CA corridor (both confirmed by the CA/legal land above).
- **10 real Toronto brokerages recorded for a calm re-run** (reco.on.ca register, XX-CA,
  housing_agencies — all rejected "RECO# not verified", NOT landable without a verified number):
  Brookfield, Weichert, Dwellworks, SIRVA, Benecke, Royal LePage, RE/MAX Hallmark, Engel & Völkers
  Toronto Central, Harvey Kalles, Chestnut Park.
- **⚠ STRUCTURAL LEARNING:** Toronto RECO housing is thin the same way AU housing (self-published
  licence#) and SE housing (FMI sales-agents-only) are — brokerages rarely self-publish their RECO#.
  Better future CA-housing predicate: look each firm up **by name** in RECO Registrant Search to obtain
  its number (vetter confirms), rather than requiring self-publication. A background-task retry
  (web_fetch vs RECO Registrant Search, no reply-timeout) was offered by Otto and flagged to the
  founder — not run.
- Tripwire untouched (no write): create-only invariant, approved count unchanged (no op). CA/housing
  stays at 0 until re-sourced with an artifact.

### XX-CA tax_finance (Toronto CPA firms) via CPA Ontario — `vendor-resourced-xx-ca-tax-toronto-2026-09-10` (landed 2026-09-10)
- Source (GCS): `1789066350927_te8pi4dr.ndjson` (+ manifest `1789066387283_cmgzej9h.json`).
- Otto manifest: **4 sourced, 6 rejected** (counts reconcile: 4 NDJSON rows = 4 sourced; 6 named rejects).
  All 4 `source_url`=wired `www.cpaontario.ca` (PUBLIC_REGISTER, register-root OK), corridor **XX-CA**,
  category tax_finance, CPA Ontario firm ID in `accreditation_number`: Trowbridge Professional Corporation
  **5TTDAC** (trowbridgeglobal.com), GTA Accounting Professional Corporation **MA06WI** (gtaaccounting.ca),
  Maroof HS Cross Border Tax Professional Corporation **4UAC65** (maroofhs.com), Fuller Landau LLP
  **5LIJQB** (fullerllp.com). Distinct registrable domains → no franchise-domain drop.
- Rejects honest: North American Tax Services / Soussan (member# unverifiable — directory page empty),
  A Garg CPA (Burlington not Toronto), Andersen in Canada (no CPA Ontario firm-directory entry — it's a
  network), Bazar McBean LLP (Oakville not Toronto), Akif CPA (no directory entry), CBTA (network/
  association, not a single registered firm).
- **Register bot-walled** (cpaontario.ca returns HTTP 403 + anti-bot JS on both the root and per-firm
  directory pages — same as bde.es / abogacia.es / LSO), so per-entity curl can't confirm; the CPA
  público IDs are well-formed 6-char and match the manifest directory slugs → PUBLIC_REGISTER lands to
  **pending** for the vetter to confirm at /admin/vetting-queue.
- `_name_key` predictor: all 4 distinct + NEW; **no prod "Trowbridge" / Fuller / Maroof / GTA at all**
  (the cross-border-Trowbridge multinational-arm risk is moot — no existing arm to mis-attach to). Dry-run:
  staged 4, duplicates 0, promote 4.
- Landed: **+4 new suppliers** (CA/tax_finance, pending). CA/tax **3 → 7** (the prior 3 are 08-31 global-pass caps).
- **Create-only guard held.** The approved baseline has moved far past the retired 218: `admin@relopass.com`
  (vetted_by `4e275218…`) bulk-approved essentially the whole pending queue — **approved 1254 / pending 0 /
  rejected 3 immediately before this land** (that includes the CA/legal Sobirovs cap, approved 14:57). This
  op only INSERTed: **approved 1254 UNCHANGED across the op; pending 0 → 4** (my 4 caps), all `vc-*`, CA,
  tax_finance, vetted_by NULL, created 19:04. No mis-attach.

### XX-CA banks (Toronto major banks) via CDIC — `vendor-resourced-xx-ca-banks-toronto-2026-09-10` (landed 2026-09-10) — HEAVY-DEDUP, +2 net
- Source (GCS): `1789066979417_9d3y0b6h.ndjson` (+ manifest `1789067017154_tyyxjdfj.json`).
- Otto manifest: **7 sourced, 3 rejected** (counts reconcile: 7 NDJSON = 7 sourced). All 7 `source_url`=wired
  `www.cdic.ca` (PUBLIC_REGISTER, register-root OK), corridor **XX-CA**, category banks. CDIC issues no
  public member number → `accreditation_number` = the CDIC member legal name (name-keyed identifier; vetter
  confirms on the CDIC member list). Rejects honest: HSBC Bank Canada (merged into RBC Mar-2024, no longer a
  separate CDIC member), Simplii (CIBC division, insured under CIBC), EQ Bank (no newcomer/expat programme).
- **Ran the #2219 `_name_key` + national-arm predictor HARD (banks = the mis-attach-prone category).** The
  inverted risk the relay flagged did NOT materialize — every prod collision is the canonical **CA** entity
  from the 08-31 CA-banks pass, not a foreign arm:
  - **RBC — HELD.** `_name_key` (`royalbankofcanada`) matches existing CA supplier `vc-e1c940db 'Royal Bank
    of Canada (RBC)'` (already has a CA/banks cap). Its prod candidate uses a non-`rbc.com` domain, so
    stage() would NOT domain-drop it → promote() would attach a **duplicate** CA/banks cap to the same RBC.
    Same entity, nothing to add → dropped from the land (not a mis-attach; already covered).
  - **Scotiabank / BMO / CIBC / TD — dropped by stage() cross-run domain-dedup** (their domains already
    carry a CA/banks cap: 'The Bank of Nova Scotia (Scotiabank)', 'Bank of Montreal (BMO)', 'CIBC', 'The
    Toronto-Dominion Bank (TD)'), so `_staged_keys` skips them pre-insert (they don't even show as duplicates).
  - **National Bank of Canada + Tangerine Bank** — no `_name_key` match, no domain dup → genuinely NEW.
- Landed: **+2 new suppliers** — National Bank of Canada (`vc-0938b4c8`), Tangerine Bank (`vc-f3c8f672`),
  CA/banks pending. CA/banks caps **5 → 7**. 2-row dry-run: staged 2 / duplicates 0 / promote 2.
- **Create-only guard held:** approved **1254 UNCHANGED** across the op; pending 4 → 6 (CA-tax 4 + CA-banks
  2), all `vc-*`, CA, banks, vetted_by NULL. No mis-attach. The full-7 CSV + rejects worklist are on disk;
  only the 2 net-new rows were promoted.
- **✅ CA FRONT WRAPPED:** legal **+1** (Sobirovs) · housing **PARKED** (RECO thin, no artifact) · tax **+4**
  (CPA Ontario) · banks **+2** (CDIC, 5 already-in-prod deduped/held). **Canada net-new = 7 suppliers** across
  3 landed cells; housing parked for a calm re-run.

### XX-DK legal_admin (Copenhagen immigration lawyers) via Advokatnøglen — `vendor-resourced-xx-dk-legal-copenhagen-2026-09-10` (landed 2026-09-10) — first XX-DK this campaign; +2 (1 held)
- Source (GCS): `1789069055385_5s68gc2q.ndjson` (+ manifest `1789069118779_l293say0.json`).
- Otto manifest: **3 sourced, 10 rejected** (counts reconcile: 3 NDJSON = 3 sourced). All 3 `source_url`=wired
  `www.advokatnoeglen.dk` (Advokatnøglen — the Danish Bar register; PUBLIC_REGISTER, register-root OK; ✓ **not**
  advokatsamfundet.dk, which is unwired), corridor **XX-DK**, category legal_admin, Copenhagen. `accreditation_number`
  = CVR + Advokatnøglen firm/advokat UUID (+ beskikkelse year for an individual advokat). Distinct independent
  domains (globeadvokater.dk / holmthomsenlaw.com / advokatnehansen.dk) → no franchise drop.
- Rejects honest & well-scoped: Poul Schmith (represents the immigration authority — conflict), immigration-
  denmark.com / Gateway to Denmark / VisaGuiden / NMD Law Group (non-advokat consultants, no Advokatnøglen entry),
  Karoline Normann (criminal-defence focus), Piroz / Grotkjær Elmstrøm / KQOMANN / Homann (Aarhus/Charlottenlund —
  not Copenhagen).
- **`_name_key` collision caught — 1 HELD.** "Holm Thomsen Law Advokatanpartsselskab" exact-matches existing
  `vc-4c56ac7b` — a DK/legal_admin supplier from the **08-31 global DK pass** (already approved/live). stage() did
  NOT domain-drop it (its 08-31 record carries no website), so promote() would have attached a **duplicate** DK/legal
  cap. Same firm, already covered → **held** (dropped from the land; not a mis-attach). ⚠ Diverged from the relay's
  "staged 3" expectation — the independent `_name_key` predictor caught it (the relay didn't see the 08-31 DK supplier).
- Landed: **+2 new suppliers** — Globe Advokater (`vc-3fc5204d`), Advokatkontoret Niels-Erik Hansen (`vc-baec3895`),
  DK/legal pending. DK/legal caps **4 → 6**. 2-row dry-run: staged 2 / duplicates 0 / promote 2.
- **Create-only guard held:** approved **1254 UNCHANGED** across the op; pending 6 → 8, all `vc-*`, DK, legal_admin,
  vetted_by NULL. No mis-attach.

### XX-DK tax_finance (Copenhagen expat-tax revisorer) via FSR — `vendor-resourced-xx-dk-tax-copenhagen-2026-09-10` (landed 2026-09-10) — +3, no overlap
- Source (GCS): `1789070936430_4i9dgyr8.ndjson` (+ manifest `1789070967771_96dh0dxz.json`). (Otto hit a transient
  Audos error mid-run; the relay retried once → recovered clean.)
- Otto manifest: **3 sourced, 6 rejected** (counts reconcile). All 3 `source_url`=wired `www.fsr.dk` (FSR — danske
  revisorer; PUBLIC_REGISTER, register-root OK), corridor **XX-DK**, category tax_finance, Copenhagen.
  `accreditation_number` = statsautoriseret/godkendt revisor firm legal name + CVR. Distinct domains
  (skatteinform.dk / bakertilly.dk / bdo.dk) → no franchise drop.
- Rejects honest: PrivatRevision, Crossbord ApS, expatfinance.dk (finance blog), Northern Partners / GTS Nordic
  (EOR firms, not FSR revisorer), Vialto Partners (UK-mobility, not a DK revisor).
- **Predictor vs prod + the 08-31 DK/tax 4 — NO overlap.** The existing 08-31 DK/tax set is Christensen Kjærulff,
  Deloitte, Grant Thornton, Kreston CM — a *different* four. BDO / Baker Tilly (the relay's suspected repeats) are
  NOT in prod under any `_name_key`, and no candidate domain hits DK/tax → all 3 genuinely new. Dry-run: staged 3 /
  duplicates 0 / promote 3.
- Landed: **+3 new suppliers** — SkatteInform (`vc-24b6f7f1`), Baker Tilly Denmark (`vc-513d20da`), BDO Danmark
  (`vc-9ac9e1c4`), DK/tax pending. DK/tax caps **4 → 7**.
- **Create-only guard held:** approved **1262 UNCHANGED** across the op (the founder had just approved the prior 8
  pending — CA-tax 4 + CA-banks 2 + DK-legal 2, so approved 1254 → 1262 and pending fell back to 0 before this land);
  pending 0 → 3, all `vc-*`, DK, tax_finance, vetted_by NULL. No mis-attach.

### XX-DK banks (Copenhagen major banks) via Finanstilsynet — `vendor-resourced-xx-dk-banks-copenhagen-2026-09-10` (landed 2026-09-10) — +3 net (3 overlaps deduped)
- Source (GCS): `1789071993862_yqr0y1tr.ndjson` (+ manifest `1789072023124_ze4pivtu.json`).
- Otto manifest: **6 sourced, 2 rejected** (counts reconcile). All 6 `source_url`=wired `www.finanstilsynet.dk`
  (PUBLIC_REGISTER, register-root OK), corridor **XX-DK**, category banks, Copenhagen. `accreditation_number` =
  Finanstilsynet FT-nummer (AL Sydbank carries a merger-successor prose note instead of a bare FT-nr — stored
  verbatim; fine for pending-for-vetter). Distinct domains → no franchise drop.
- Rejects honest: Sydbank A/S + Arbejdernes Landsbank (both merged into AL Sydbank, Finanstilsynet-approved
  Dec 2025) — Otto sourced the merged successor instead, no dead/dup rows.
- **Predictor HARD vs the 08-31 DK/banks 3 (Danske / Nordea / Nykredit).** All three overlaps carry their matching
  domain in DK/banks, so stage() cross-run domain-dedup DROPS them pre-insert — no `_name_key` attach risk here
  (unlike the CA RBC case, where the prod domain differed so it had to be held by hand). Genuinely new: Jyske Bank,
  AL Sydbank, Spar Nord.
- Landed: **+3 new suppliers** — Jyske Bank A/S (`vc-7764657e`), AL Sydbank A/S (`vc-121f0133`), Spar Nord Bank A/S
  (`vc-db76ff38`), DK/banks pending. DK/banks caps **3 → 6**. Full-6 dry-run: staged 3 / duplicates 0 / promote 3.
- **Create-only guard held:** approved **1262 UNCHANGED** across the op; pending 3 → 6 (DK-tax 3 + DK-banks 3), all
  `vc-*`, DK, banks, vetted_by NULL. No mis-attach.

### XX-DK housing_agencies (Copenhagen MDE estate agents) via de.dk — `vendor-resourced-xx-dk-housing-copenhagen-2026-09-10` (landed 2026-09-10) — LAST DK cell; +1 net (2 deduped)
- Source (GCS): `1789073029123_eanpj0p0.ndjson` (+ manifest `1789073030801_rv5ag4eo.json`).
- Otto manifest: **3 sourced, 7 rejected** (counts reconcile). All 3 `source_url`=wired `www.de.dk` (MDE — Dansk
  Ejendomsmæglerforening; PUBLIC_REGISTER, register-root OK), corridor **XX-DK**, category housing_agencies,
  Copenhagen. `accreditation_number` = MDE membership prose (verbatim "…medlemmer af Dansk Ejendomsmæglerforening")
  + CVR. Distinct domains (home.dk / danbolig.dk / estate.dk).
- **Not thin in the SE/FMI sense:** Otto kept the MDE ejendomsmæglere that do rental relo and rejected the non-MDE
  expat consultancies (CopenhagenExpats, Copenhagen Relocations, RelocationDK, EasyHousing, Movinn). ⚠ Retry seed:
  Toscana Bolig ApS (Peter Simmering, Ejendomsmægler MDE, CVR confirmed) was rejected on a truncated reason — worth
  a look if it's Copenhagen + rental.
- **Predictor vs the 08-31 DK/housing 4 (danbolig Østerbro / EDC / home Østerbro / Nybolig Østerbro).** home a/s
  (home.dk) and danbolig (danbolig.dk) share the 08-31 chains' corporate domains → stage() cross-run domain-dedup
  DROPS both pre-insert. Genuinely new: Estate Mæglerne (estate.dk).
- Landed: **+1 new supplier** — Estate Mæglerne City & Christianshavn (`vc-461aa91e`), DK/housing pending.
  DK/housing caps **4 → 5**. Dry-run: staged 1 / duplicates 0 / promote 1.
- **Create-only guard held:** approved **1262 UNCHANGED**; pending 6 → 7, `vc-*`, DK, housing_agencies, vetted_by
  NULL. No mis-attach.
- **✅ DK FRONT WRAPPED:** legal **+2** (1 held: Holm Thomsen already in prod) · tax **+3** · banks **+3** (Danske/
  Nordea/Nykredit deduped) · housing **+1** (home/danbolig deduped). **Denmark net-new = 9 suppliers** across 4
  landed cells; all four DK registers (advokatnoeglen.dk / fsr.dk / finanstilsynet.dk / de.dk) confirmed working
  end-to-end. Next front: Czech Republic or Cyprus (legal-first) — PT legal is unwired (Ordem dos Advogados has no
  firm listing; PT's other categories already 08-31-covered), CZ `cak.cz` + CY `cyprusbar.org` are wired PUBLIC_REGISTER.

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
