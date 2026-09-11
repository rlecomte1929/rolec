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

## Enrichment progress (running)
Contact fills so far: **20 `contact_email` + 25 `contact_phone`** across 2 cells (ES/legal, NL/housing), on
already-approved/live suppliers, fill-empty, 0 overwrites, vetting untouched throughout. Queue: CZ/housing → AU/legal →
GB/legal → SE/housing → CA/tax → (banks last). Movers parked (FIDI, no websites to scrape). ~1,090 suppliers still
lack an email at the start of the pivot — this is the RFQ-loop unblock, one city×category batch at a time.
