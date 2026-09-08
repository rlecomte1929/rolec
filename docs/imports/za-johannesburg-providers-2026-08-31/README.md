# Johannesburg, South Africa — provider sourcing (register-verified)

Date: 2026-08-31 · corridor tag: `XX-ZA` (every row) · 20 rows across 5 categories · 1 category SKIPPED

Every row is evidenced by an **official statutory register or recognized accreditation body**
(the `source_url`), never the firm's own marketing site. `accreditation_number` is populated only
where the register itself displays a number. No numbers, expiries, or websites were invented.

## Registers used, by category

### movers — 4 firms · FIDI Global Alliance (FAIM)
- Register: FIDI "Find a FIDI Affiliate". Each row cites the **per-affiliate detail page**
  (`fidi.org/find-fidi-affiliate/<slug>`), not the search page.
- All four confirmed with a Johannesburg office address and a current FIDI-FAIM certificate on the
  detail page. `accreditation_expiry` = the FAIM certificate expiry year shown (2027/2028).
  FIDI shows no per-affiliate certificate number, so `accreditation_number` is blank.
- Note: Stuttaford Van Lines, AGS Worldwide Movers and Pickfords Removals are three separate FIDI
  affiliate listings (separate detail pages, separate Johannesburg addresses) operated by one legal
  entity, **The Laser Transport Group (Pty) Ltd**. Elliott International is independent.

### banks — 5 firms · South African Reserve Bank (SARB) Prudential Authority
- Register: SARB "SA registered banks and representative offices" → the **Locally Controlled Banks
  (as at Jan 2026)** PDF, which lists each bank's registered name, address and website. `source_url`
  is that PDF. Register landing page:
  https://www.resbank.co.za/en/home/what-we-do/Prudentialregulation/sa-registered-banks-and-representative-offices
- All five requested banks confirmed on the register with Johannesburg / Sandton (City of
  Johannesburg) head-office addresses: Standard Bank (Johannesburg), FirstRand Limited (Sandton;
  FNB is its retail division), Absa (Johannesburg), Nedbank (Sandton, Johannesburg), Investec
  (Sandown, Sandton). SARB assigns no public per-bank number, so `accreditation_number` is blank.

### schools — 4 firms · International Baccalaureate Organization (IBO)
- Register: IBO "Find an IB World School". `source_url` = `ibo.org/en/school/<id>`;
  `accreditation_number` = the IB school code.
- South Africa has 12 IB World Schools total (from the ZA-filtered directory); the four here are the
  Johannesburg-area ones, address-confirmed on the IBO detail page:
  - American International School of Johannesburg — 000756 — Midrand, Johannesburg (PYP/MYP/DP)
  - Redhill School — 050584 — 20 Summit Road, Morningside (Sandton), Johannesburg (MYP/DP)
  - Crawford International Ruimsig — 061794 — Ruimsig, Roodepoort, Johannesburg
  - IIE Crawford International Fourways — 061254 — Craigavon, Fourways, Johannesburg
- Excluded ZA IB schools that are NOT Johannesburg: Crawford Prep La Lucia / North Coast & IES Hout
  Bay (KZN/Cape Town), Mokopane Destiny Academy (Limpopo).

### tax_finance — 4 firms · Independent Regulatory Board for Auditors (IRBA)
- Register: IRBA "Find a Firm" (`irba.co.za/find-a-ra/`, Firm tab). The search is an AJAX form (no
  per-firm permalink), so `source_url` is the register search page; the hard evidence is the
  **Practice Number** captured in `accreditation_number`.
- All four Big-Four audit firms confirmed registered with a Johannesburg-area office:
  PwC Inc – Johannesburg (901121-0000), Deloitte & Touche – Johannesburg (902276-0001, Waterfall),
  KPMG Inc – Johannesburg (900133-0000), Ernst and Young Inc – Head Office/Johannesburg
  (918288-0000). IRBA lists website as "N/A" for all, so `website_url` is blank.

### housing_agencies — 3 firms · Property Practitioners Regulatory Authority (PPRA)
- Register: PPRA "Practitioner Search" (`theppra.org.za/practitioner-search/`, "Firm Name" mode).
  The FFC is returned per firm via the register's "Check Status" call (`admin-ajax`), which yields
  the **Fidelity Fund Certificate number** and a validity flag `ISVALID`. `source_url` is the
  register search page (AJAX search, no per-firm permalink); `accreditation_number` = the FFC number.
- Searched by Johannesburg suburb ("Sandton", "Bryanston") so results are register-sourced to
  Johannesburg. Only firms whose live FFC status returned **ISVALID = 1 (active)** were kept:
  - Sandton Signature Properties (Pty) Ltd, t/a Fine and Country Sandton — FFC 202614022110000
  - Enzimart (Pty) Ltd, t/a Century 21 Bryanston — FFC 202401016400357
  - Jamieson Rentals & Sales Bryanston — FFC 202615048150000
- The register returns a validity flag, not an explicit expiry date, so `accreditation_expiry` is
  left blank (not invented). Firms searched whose FFC status returned "No Records" or `ISVALID = 0`
  (expired) were excluded — e.g. Rawson Properties Bryanston, Realnet Bryanston, Sandton Homes CC,
  Sandton Executive Real Estate.

## SKIPPED

### legal_admin — SKIPPED · Legal Practice Council (LPC)
The LPC public register (`lpc.org.za/members-of-the-public/search-practitioners/`) is keyed by
**individual legal practitioner** (name / enrolment number / province / type), not by law firm.
There is no reliable per-firm firm search, and producing "law firm" rows would require guessing
individual attorney names to search — which risks fabrication and mis-attribution. Per the task rule
("if reachable per-firm, cite it; else SKIP"), this category is skipped rather than populated from
self-declared firm sites or guessed names.

## Method notes
- `ibo.org`, `irba.co.za` and `theppra.org.za` all sit behind a Cloudflare/WAF JS challenge and 403
  a plain fetch/curl; they were browser-grounded. The SARB bank list was read from the register PDF.
- FIDI detail pages and the SARB PDF were fetched directly (no challenge).
