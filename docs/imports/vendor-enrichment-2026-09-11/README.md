# Vendor contact-enrichment — 2026-09-11

The harvest is saturated (see `../vendor-candidates-resourced-2026-09-08/README.md`), so the leverage
shifted to **enrichment**: filling the contact fields the product actually consumes on suppliers we
already hold. Priority = **`contact_email`** — 1,090 of ~1,166 `vc-*` harvest suppliers lacked one,
and the RFQ loop is blocked on supplier emails.

**Loop (per batch):** export a target list (approved `vc-*` in one country×category, missing email,
**with a website** — website-scrape only works where there's a site; movers are 08-31 FIDI entries with
no site → parked) → Otto scrapes each firm's own site for the **published** email/phone → NDJSON keyed
on `supplier_id` → I verify (keys ⊆ target · emails match the firm's own domain / are genuinely published
· no invented addresses) → map to the `enrich_suppliers.py` schema (`key` + per-field `*_source_url`) →
`enrich_suppliers.py --category <cat> --target-keys <target.csv> [--apply]`. **Fill-empty only: never
overwrites a non-empty value, never touches `platform_vetting_status`** (the script re-asserts the
approved-cap tripwire on every run).

## Batch #1 — ES/legal_admin contact (`enrich-xx-es-legal-contact-2026-09-11`)
- Source (GCS): `src/enrich-xx-es-legal-contact.ndjson` (+ `manifest_es-legal-contact.json`). Landing file:
  `src/enrich-xx-es-legal-contact.LANDING.ndjson` (schema-mapped, Marta Reina Grau excluded — see below).
- Target: `es-legal-target.csv` (20 approved ES/legal_admin suppliers missing `contact_email`; 17 with a
  website, 3 name-only individuals with no site).
- Otto: **17 attempted / 17 filled** (the 3 name-only skipped upstream, no website). Keys ⊆ target ✓.
- **Independent verification (the real risk = invented emails):** 13 emails matched the firm's own domain;
  2 non-domain but genuine (**Paula Schmid** `pschmid@icasevilla.org` = her official Seville-bar address;
  **Lexey** `lexeyabogados@gmail.com` = branded gmail, common for solo firms) → landed, noted; **3 left
  blank** (Calero, Rodríguez Calistro, Ventura — emails Cloudflare-obfuscated, Otto did NOT invent, phone
  filled). All 17 carried a +34 E.164 phone.
- **1 HELD — Marta Reina Grau (`vc-390f3e72`).** Her "website" is a Pleitex directory profile, and the
  returned `info@pleitex.com` / `+34919935168` are the **platform's**, not hers (Otto's own manifest note
  flags it). Filling them would misattribute an aggregator's inbox to the lawyer → excluded from the land.
  Her contact stays empty (honest); no personal contact is published.
- **Landed (fill-empty):** **28 fields across 16 suppliers** — 13 `contact_email` + 15 `contact_phone`.
  ES/legal_admin `vc-*` contact-email coverage **0 → 13** (of 20), phone **0 → 15**. 0 overwrites.
  **Approved-cap tripwire UNCHANGED: 1283** (vetting untouched); caps by status still approved 1283 /
  pending 8 / rejected 3.

## Batch #2 — NL/housing_agencies contact (`enrich-xx-nl-housing-contact-2026-09-11`)
- Source (GCS): `src/enrich-xx-nl-housing-contact.ndjson` (+ `manifest_nl-housing-contact.json`). Landing:
  `src/enrich-xx-nl-housing-contact.LANDING.ndjson` (schema-mapped, no exclusions). Target: `nl-housing-target.csv`
  (10 approved NL/housing_agencies makelaars missing `contact_email`, all own-domain).
- Otto: **10 attempted / 10 filled**. Keys ⊆ target ✓. Phones all +31 E.164.
- **Verification:** 5 emails domain-matched; **3 blank** (Broersma, Pim de Jong, Ramon Mossel — no published email /
  contact-form only, honestly left blank, phone filled); **2 landed with a vetter note** (genuine firm contacts, NOT
  third-party aggregators like the Pleitex case): **E&V Amsterdam Zuid** `netherlands@engelvoelkers.com` (E&V's own
  brand domain, but the NL *country* inbox, not office-specific) and **JLG Real Estate** `info@jlg.nl` (the firm's own
  `.nl`, published on its jlgrealestate.com site — cross-TLD but genuine). No holds.
- **Landed (fill-empty):** **17 fields across 10 suppliers** — 7 `contact_email` + 10 `contact_phone`.
  NL/housing_agencies `vc-*` contact-email coverage **1 → 8** (of 11), phone **→ 11**. 0 overwrites.
  **Approved-cap tripwire UNCHANGED: 1283**; caps by status still approved 1283 / pending 8 / rejected 3.

## Batch #3 — CZ/housing_agencies contact (`enrich-xx-cz-housing-contact-2026-09-11`)
- Source (GCS): `src/enrich-xx-cz-housing-contact.ndjson` (+ `manifest_cz-housing-contact.json`). Landing:
  `src/enrich-xx-cz-housing-contact.LANDING.ndjson` (schema-mapped; emails lowercased; MAXIMA dropped — no data).
  Target: `cz-housing-target.csv` (9 approved CZ/housing firms missing `contact_email`, all own-domain).
- Otto: **9 attempted / 8 filled**. Keys ⊆ target ✓. Phones +420 E.164.
- **Verification:** all 6 emails domain-matched (no aggregator hits). E&V Prague + Svoboda & Williams = phone-only
  (brand-office / form-only email — honest). **MAXIMA REALITY** returned no email *and* no phone → dropped (fill-empty
  would no-op; honestly empty, not invented). Normalised `Hello@MHrelocations.cz` → lowercase at land.
- **Landed (fill-empty):** **14 fields across 8 suppliers** — 6 `contact_email` + 8 `contact_phone`.
  CZ/housing_agencies `vc-*` contact-email coverage **→ 6** (of 9), phone **→ 8**. 0 overwrites.
  **Approved-cap tripwire UNCHANGED: 1283**; caps by status still approved 1283 / pending 8 / rejected 3.

## Batch #4 — AU/legal_admin contact (`enrich-xx-au-legal-contact-2026-09-11`)
- Source (GCS): `src/enrich-xx-au-legal-contact.ndjson` (+ `manifest_au-legal-contact.json`). Landing:
  `src/enrich-xx-au-legal-contact.LANDING.ndjson` (schema-mapped; emails lowercased). Target: `au-legal-target.csv`
  (8 approved AU migration firms missing `contact_email`, all own-domain).
- Otto: **8 attempted / 7 filled**. Keys ⊆ target ✓. Phones +61 E.164.
- **Verification:** all 5 emails domain-matched (incl. the `.com.au` firms — #2263 keys them distinctly). Ajuria +
  Australian Immigration Centre = phone-only (form-only email). **Bay Migration Solution** omitted upstream (no email
  *or* phone on baymigration.com.au — Otto dropped the row rather than emit blanks; not invented). No aggregator hits.
- **Landed (fill-empty):** **12 fields across 7 suppliers** — 5 `contact_email` + 7 `contact_phone`.
  AU/legal_admin `vc-*` contact-email coverage **→ 5** (of 8), phone **→ 7**. 0 overwrites.
  **Approved-cap tripwire UNCHANGED: 1291** (the founder approved the prior 8 pending — BR/legal 3 + FI/housing 5 —
  between batches #3 and #4, so the approved baseline moved 1283 → 1291 and pending drained to 0; enrichment itself
  changed no vetting state).

## Batch #5 — GB/legal_admin contact (`enrich-xx-gb-legal-contact-2026-09-11`)
- Source (GCS): `src/enrich-xx-gb-legal-contact.ndjson` (+ `manifest_gb-legal-contact.json`). Landing:
  `src/enrich-xx-gb-legal-contact.LANDING.ndjson` (schema-mapped; emails lowercased). Target: `gb-legal-target.csv`
  (7 approved UK immigration firms missing `contact_email`, all own-domain).
- Otto: **7 attempted / 6 filled**. Keys ⊆ target ✓. Phones +44 E.164.
- **Verification:** all 3 emails domain-matched (A Y & J, Bindmans, Gherson). Laura Devine / Magrath Sheldrick / RLegal
  = phone-only (form-only email). **Fragomen LLP** omitted upstream (global site, no extractable direct London-entity
  contact — Otto dropped it rather than attribute a general/wrong address; as anticipated). No aggregator hits.
- **Landed (fill-empty):** **9 fields across 6 suppliers** — 3 `contact_email` + 6 `contact_phone`.
  GB/legal_admin `vc-*` contact-email coverage **→ 4** (of 8), phone **→ 7**. 0 overwrites.
  **Approved-cap tripwire UNCHANGED: 1291**; caps by status approved 1291 / pending 0 / rejected 3.

## Batch #6 — SE/housing_agencies contact (`enrich-xx-se-housing-contact-2026-09-11`)
- Source (GCS): `src/enrich-xx-se-housing-contact.ndjson` (+ `manifest_se-housing-contact.json`). Landing:
  `src/enrich-xx-se-housing-contact.LANDING.ndjson` (schema-mapped; emails lowercased). Target: `se-housing-target.csv`
  (7 approved SE/housing firms missing `contact_email`, all own-domain).
- Otto: **7 attempted / 5 filled**. Keys ⊆ target ✓. Phones +46 E.164.
- **Verification:** 3 emails domain-matched (Estate, Quality Living, Victory); **Öresund** `info@oresundfast.se` = the
  firm's own short-form domain (vs the longer oresundfastighetsformedling.se site) — genuine, landed with a note (like
  JLG). Våningen & Villan phone-only. **Nordic Relocation Group** + **Residensportalen** omitted upstream (no data,
  dropped not invented). No aggregator hits.
- **Landed (fill-empty):** **9 fields across 5 suppliers** — 4 `contact_email` + 5 `contact_phone`.
  SE/housing_agencies `vc-*` contact-email coverage **→ 4** (of 7), phone **→ 5**. 0 overwrites.
  **Approved-cap tripwire UNCHANGED: 1291**; caps by status approved 1291 / pending 0 / rejected 3.

## Batch #7 — CA/tax_finance contact (`enrich-xx-ca-tax-contact-2026-09-11`)
- Source (GCS): `src/enrich-xx-ca-tax-contact.ndjson` (+ `manifest_ca-tax-contact.json`). Landing:
  `src/enrich-xx-ca-tax-contact.LANDING.ndjson` (schema-mapped; emails lowercased). Target: `ca-tax-target.csv`
  (7 approved CA/tax firms missing `contact_email`, all own-domain).
- Otto: **7 attempted / 5 filled**. Keys ⊆ target ✓. Phones +1 E.164.
- **Verification:** Fuller Landau + Maroof (after lowercasing `Canada@MaroofHS.com`) domain-matched; **GTA Accounting**
  `tax@gtaaccountinggroup.com` (group domain vs gtaaccounting.ca site) and **Trowbridge** `info@trowbridge.ca` (CA domain
  vs trowbridgeglobal.com site) = firm-owned alternate domains, genuine, landed with a note. MNP phone-only. **Baker
  Tilly Canada + BDO Canada** omitted upstream (big-firm national sites, no direct contact — not invented). No aggregators.
- **Landed (fill-empty):** **9 fields across 5 suppliers** — 4 `contact_email` + 5 `contact_phone`.
  CA/tax_finance `vc-*` contact-email coverage **→ 4**, phone **→ 5**. 0 overwrites.
  **Approved-cap tripwire UNCHANGED: 1291**.
- ⚠ Landed after an out-of-band removal of the landing worktree (recreated from `origin` at 98bb8e2b — nothing lost,
  every prior batch was already pushed; re-fetched CA/tax and re-verified before landing).

## ✅ Register-cell enrichment queue COMPLETE (7 cells)
Contact fills: **42 `contact_email` + 56 `contact_phone`** across 7 cells (ES/legal, NL/housing, CZ/housing, AU/legal,
GB/legal, SE/housing, CA/tax), on already-approved/live suppliers, fill-empty, 0 overwrites, vetting untouched
throughout. **113 of ~1,166 `vc-*` suppliers now carry a contact_email** (up from ~76 at the pivot). The clean
register cells (legal / housing / tax — the RFQ-relevant categories) are done. **Only BANKS remain** (deprioritised:
big institutions, generic/country addresses) — held for a founder banks-vs-pause decision. Movers parked (FIDI, no
websites to scrape).

## Capitals wave (2026-09-11) — founder call: don't pause, enrich the main capitals
Founder's direct call (via the relay thread): resume the lane targeting the main-capital countries, RFQ categories
(legal/housing/tax), skip banks/movers, skip the 7 done cells. **Wave size: 21 cells / ~122 suppliers** (website +
missing email). Biggest: **Rome IT/housing = 45** (chunked ~15 to avoid a big-batch stall), then CZ/tax 8, GB/tax 6,
CZ/legal 5, GB/housing 5, DK/tax 5, FI/housing 5, and a 1-4 tail across FI/FR/PT/DK/NL/AT/IE/NO/CZ.
**New aggregator rule (IT):** an `immobiliare.it` / `idealista.it` / `casa.it` "website" is a PORTAL PROFILE → skip
(portal contact, not the firm's), same as Pleitex. Firm-OWNED alternate domains (branded gmail, hyphen/short variants,
brand-office inboxes like Coldwell/E&V) are landed; THIRD-PARTY network domains (REPLAT) are held like portals.

### Batch #8 — IT/housing_agencies contact, chunk 1/3 (`enrich-xx-it-housing-contact-2026-09-11-c1`)
- Source (GCS): `src/enrich-xx-it-housing-c1-contact.ndjson` (+ `manifest_it-housing-c1-contact.json`). Landing:
  `src/enrich-xx-it-housing-c1-contact.LANDING.ndjson`. Target: `it-housing-target.csv` (full 45-firm IT/housing list).
- Otto: **14 attempted / 13 filled**. Keys ⊆ target ✓. Phones +39 E.164.
- **Verification:** portal rule WORKED — **Erre Emme** (immobiliare.it profile) correctly skipped upstream. 9 emails
  domain-matched; 360° (`studio360res@gmail.com`, branded gmail) + Boom Rome (`valentino@boom-rome.com`, hyphen variant)
  + Coldwell Banker (`info@coldwellbanker.it`, brand-office inbox) landed as genuine; Appartamenti Bologna phone-only;
  Chiusano omitted (no data). **FGIMMOBILIARE email HELD** — `replat45301@replat.com` is a third-party REPLAT network
  domain (agent-specific but not firm-owned), same bar as portals; its phone was kept.
- **Landed (fill-empty):** **23 fields across 13 suppliers** — 11 `contact_email` + 12 `contact_phone`. IT/housing_agencies
  `vc-*` contact-email coverage **→ 11**, phone **→ 12**. 0 overwrites. **Approved-cap tripwire UNCHANGED: 1291.**
- **Wave running total: 53 `contact_email` + 68 `contact_phone`; 124 of ~1,166 `vc-*` suppliers now carry an email.**
