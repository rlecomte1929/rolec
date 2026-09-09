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
