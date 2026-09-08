# Athens, Greece — register-verified service providers (2026-08-31)

Corridor tag: `XX-GR` on every row. Every provider in `providers.csv` is evidenced by an
official statutory register or recognized accreditation body page (`source_url`), never a
firm's own marketing site. Firms not verifiable on a real register were excluded, and two
categories with no reachable per-firm official register were SKIPPED.

All rows were browser-grounded or direct-fetched against the live register on 2026-08-31.

## Categories

### movers — 3 firms
- **Register:** FIDI Global Alliance, "Find a FIDI Affiliate" (fidi.org). Cited per-affiliate
  DETAIL page, not the search URL.
- **Accreditation body:** FIDI Global Alliance (FAIM / FIDI-FAIM Plus). Expiry = the FAIM
  certificate year shown on the affiliate page. FIDI does not publish a numeric FAIM cert
  number on these pages, so `accreditation_number` is blank.
- Firms: Matrix Relocations EPE (Athens, FAIM 2028), Attica Movers S.A. (Athens, FAIM Plus
  2028), Orphee Beinoglou Intl S.M. S.A. (Athens/Elefsina, FAIM Plus 2029).
- Note: a fourth Athens affiliate, Celebrity International Movers S.A.
  (fidi.org/find-fidi-affiliate/celebrity-international-movers-sa, FAIM 2026), is indexed by
  FIDI but its detail page returned HTTP 403 on every direct fetch this session, so it was
  left out pending a clean grounding.

### banks — 4 firms
- **Register:** ECB List of Supervised Entities (Single Supervisory Mechanism), Greece
  section — the four significant credit institutions directly supervised by the ECB. Verified
  by extracting the Greece (GR) rows from the ECB PDF (cut-off 1 January 2025).
- **Accreditation body:** European Central Bank (SSM).
- **`accreditation_number`:** the entity's LEI code exactly as printed in the ECB list (the
  register's per-entity identifier — there is no separate "licence number" in the ECB list).
- Firms: National Bank of Greece S.A., Piraeus Bank S.A., ALPHA BANK S.A., Eurobank S.A.
- Note: the Bank of Greece supervised-institutions register (bankofgreece.gr) returned HTTP
  403 to automated fetching; the ECB SSM list is the permitted alternative and was used.

### schools — 3 firms
- **Register:** IBO "Find an IB World School" (ibo.org/en/school/<id>). Cited the IBO detail
  page + IB School code for each.
- **Accreditation body:** International Baccalaureate Organization (IB).
- **`accreditation_number`:** IB School code.
- Firms: American Community Schools of Athens (000066, Halandri/Athens), International School
  of Athens (001208, Kifissia/Athens), Doukas School (001346, Marousi/Athens).
- Note: HAEF / Athens College (ibo.org/en/school/051958, Psychiko/Athens) is a genuine IB
  World School but its IBO page sat behind an unclearing Cloudflare "Just a moment" challenge
  all session, so it was left out pending a clean grounding.

### tax_finance — 4 firms
- **Register:** ELTE / HAASOB (Hellenic Accounting and Auditing Standards Oversight Board)
  Public Register of Audit Firms — the statutory register at dbapplication.elte.org.gr. Cited
  the per-firm `companyDetails` page, which shows the Company ELTE ID and headquarter city.
- **Why ELTE instead of OEE/SOEL:** the task named the Economic Chamber (oe-e.gr) or SOEL.
  ELTE is the statutory oversight body that maintains the public register of statutory
  auditors and audit firms and is the only one of the three exposing a reachable, citable
  per-firm register page; SOEL (soel.gr) exposed no per-firm public list this session.
- **Accreditation body:** ELTE (HAASOB). **`accreditation_number`:** Company ELTE ID.
- Firms (all HQ in Athens/Attica): Deloitte Certified Public Accountants S.A. (ELTE ID 5,
  Marousi), Ernst & Young Certified Auditors SA (ELTE ID 23, Marousi), Grant Thornton (ELTE
  ID 7, Athens), KPMG (ELTE ID 57, Athens).

## SKIPPED categories

### legal_admin — SKIPPED
Athens Bar Association (Δικηγορικός Σύλλογος Αθηνών, dsa.gr) exposes a member/law-firm search
(`/dsa_members`, tabs ΜΕΛΗ and ΔΙΚΗΓΟΡΙΚΕΣ ΕΤΑΙΡΕΙΕΣ) but only as a live contact-lookup form
with no stable, citable per-lawyer/per-firm permalink (and the page restricts use of the
data). With no citable per-firm register page reachable, the category was skipped rather than
fall back to firms' own sites.

### housing_agencies — SKIPPED
There is no reachable official per-firm real-estate-agent register with citable permalinks.
GEMI publicity (publicity.businessportal.gr) is a general commercial-registry search (by VAT
/ GEMI number / company name), not a realtor accreditation register, and returns
session/dynamic results rather than stable per-firm URLs. Per the rules, skipped rather than
cite firm marketing sites.

## Summary
- movers: 3 (FIDI)
- banks: 4 (ECB SSM list, Greece section)
- schools: 3 (IBO)
- tax_finance: 4 (ELTE/HAASOB)
- legal_admin: SKIPPED (no citable per-firm register)
- housing_agencies: SKIPPED (no citable per-firm register)
- Total rows: 14
