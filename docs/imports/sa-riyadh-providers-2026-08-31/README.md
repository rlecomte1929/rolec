# Riyadh, Saudi Arabia — register-verified service providers

Corridor: `XX-SA` (destination Saudi Arabia / Riyadh). Sourced 2026-08-31.

Every row in `providers.csv` was confirmed by opening the official statutory register or
recognized accreditation body and finding the firm listed. No firm was taken from its own
marketing site. Accreditation numbers were only filled where the register itself displays one
(e.g. IB school code); none were invented.

## movers — 1 firm
- **Register used:** FIDI Global Alliance affiliate directory (fidi.org/find-fidi-affiliate),
  filtered to Saudi Arabia (`?country=241`).
- **Full Saudi FIDI list (4 affiliate entries, all browser-confirmed):**
  Four Winds Saudi Arabia Ltd — Riyadh; Four Winds Saudi Arabia Ltd — Jeddah; Four Winds Saudi
  Arabia Ltd — Dammam; Cargo Track Relocations (Jeddah).
- **With a Riyadh office → 1:** Four Winds Saudi Arabia, Ltd — Riyadh (FAIM certified, expiry 2027).
  Cargo Track (FAIM, expiry 2028) is Jeddah-only; the other two Four Winds entries are the same
  company's Jeddah and Dammam branches. This is the honest ceiling for movers with a *Riyadh*
  office on the FIDI register — not padded.

## banks — 4 firms
- **Register used:** Saudi Central Bank (SAMA), Licensed Entities → Local Banks
  (https://www.sama.gov.sa/en-US/Supervision/LicenseEntities/Pages/LocalBanks.aspx).
- **Full local-banks list on the register (browser-confirmed):** The National Commercial Bank
  (now Saudi National Bank), The Saudi British Bank, Saudi Investment Bank, alinma bank, Riyad
  Bank, Al Rajhi Bank, Arab National Bank, Bank AlBilad, Bank AlJazira, Gulf International Bank
  Saudi Arabia (GIB-SA).
- **Selected 4** major retail banks, all HQ'd/branched in Riyadh: Al Rajhi Bank, Riyad Bank,
  The Saudi British Bank (SABB), Arab National Bank. (More could be added from the same list if
  desired — all 10 are SAMA-licensed.)
- SAMA does not publish a per-bank licence number/expiry on this list, so those fields are blank.

## schools — 4 firms
- **Register used:** International Baccalaureate, "Find an IB World School"
  (ibo.org), country = Saudi Arabia, keyword Riyadh → 20 IB World Schools returned.
- **Selected 4** established international schools, each detail page confirmed Riyadh + IB code:
  - American International School - Riyadh — IB code 001218
  - British International School Riyadh — IB code 062374
  - Advanced Learning Schools — IB code 004364
  - SEK International School Riyadh — IB code 062477
- Source URL is each school's own IBO page (`ibo.org/school/<id>/`); IB code captured as
  `accreditation_number`. IBO does not publish an expiry, so that field is blank. 16 more Riyadh
  IB World Schools are available from the same search if more depth is wanted.

## legal_admin — 4 firms
- **Register used:** Saudi Bar Association public directory, Legal Firms tab
  (https://eservice.sba.gov.sa/en/lawyers → "المنشآت القانونية"). Each firm has a public entry
  at `eservice.sba.gov.sa/directory/<id>` showing name, national address (city/district), and
  contact. The roll is fully reachable and browsable (it also has an individual-lawyer view that
  shows licence number + expiry + status per lawyer, filterable by city).
- **Selected 4**, each detail page confirmed to be in Riyadh:
  - Al-Jehani Law Office (مكتب خليل جابر خليل الجهني للمحاماة) — directory/38 — Al Olaya, Riyadh
  - Ali Abdullah Al-Shareef Law Firm (شركة علي عبدالله سعود الشريف للمحاماة) — directory/3507 — Riyadh
  - Al Kheraiji Lawyers and Consultants (شركة الخريجي محامون ومستشارون) — directory/84 — Riyadh
  - Worth Law Consultants (شركة وورث لو كونسلتانتس) — directory/1461 — Riyadh
- The firm-level directory page does not display a firm licence number, so
  `accreditation_number`/`expiry` are blank. (Per-lawyer licence numbers + expiry are available on
  the individual-lawyer view if a person-level entry is preferred over a firm-level one.)

---

## SKIPPED categories (re-source worklist)

### housing_agencies — SKIPPED
- REGA (Real Estate General Authority) / Ejar / FAL exposes only a **verify-by-known-number**
  service ("Real Estate Broker Inquiry": lookup by broker licence number, brokerage contract
  number, or ownership-document number —
  https://rega.gov.sa/en/rega-services/eservices/real-estate-broker-inquiry/). It is **not** a
  browsable/searchable per-firm register: you cannot list or find brokerage offices by name or
  city, only validate a licence you already hold. No enumerable public per-firm register exists,
  and firm marketing sites are disallowed → skipped per instructions.
- **Re-source:** obtain broker licence numbers out-of-band (e.g. from HR-supplied shortlists or
  Ejar contracts) and validate each via the FAL inquiry, or check whether the FAL platform
  (`sa.rega.gov.sa`) later exposes a public licensed-office directory.

### tax_finance — SKIPPED
- SOCPA's public "List of licensed firms and services providers"
  (https://socpa.org.sa/Socpa/LQ/L/Accounting-Offices.aspx?lang=en-us) **exists** but was
  **unreachable from this environment** — every attempt (2× browser navigate, 2× WebFetch) failed
  with `ECONNREFUSED 66.9.136.167:443`, i.e. the server actively refused the connection (looks
  like a geoblock/firewall on non-Saudi egress, not a transient outage; retried per policy).
- ZATCA's only public firm list is approved e-invoicing (Fatoora) *solution providers* — software
  vendors, not audit/tax firms — so it does not satisfy this category.
- **Re-source:** retry the SOCPA licensed-firms directory from a Saudi/allowed egress (or via a
  proxy that reaches socpa.org.sa), then pull Riyadh audit/tax firms with their SOCPA firm-licence
  numbers.
