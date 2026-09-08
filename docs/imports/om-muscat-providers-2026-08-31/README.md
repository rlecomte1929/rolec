# Muscat, Oman — service provider sourcing (2026-08-31)

Corridor tag: `XX-OM`. Every row is evidenced by an official statutory register or
recognised accreditation body via `source_url` — never a firm's own marketing site.
`website_url` is the firm site for reference only; the register in `source_url` is the proof.

## Categories included

### movers — 2 rows
- **Register:** FIDI Global Alliance, "Find a FIDI Affiliate" — cited per-affiliate DETAIL page.
- **Body:** FIDI Global Alliance (FAIM / FAIM Plus quality certification).
- Oman has only two FIDI affiliates; both are in Muscat and both are FAIM Plus certified. Not padded.
  - Gulf Agency Co (Oman) L.L.C. — GAC Building, Al Khuwair, Muscat — FAIM Plus, expiry 2027 —
    https://www.fidi.org/find-fidi-affiliate/gulf-agency-co-oman-llc
  - Premium Move Services LLC (trading as "The Movers") — Azaiba, Muscat — FAIM Plus, expiry 2026 —
    https://www.fidi.org/find-fidi-affiliate/movers
- FIDI does not publish a per-affiliate numeric certificate ID on the detail page, so
  `accreditation_number` is blank; `accreditation_expiry` carries the FAIM validity year shown.

### banks — 5 rows
- **Register:** Central Bank of Oman, "Licensed Banks" — https://cbo.gov.om/Pages/LicensedBanks.aspx
- **Body:** Central Bank of Oman.
- The CBO page is a SharePoint app that returns HTTP 403 to WebFetch on a TLS-verify error;
  fetched successfully with `curl` (real UA). The licensed-bank names are present in the served HTML.
  All five selected banks appear on the register: Bank Muscat SAOG, National Bank of Oman SAOG,
  Bank Dhofar SAOG, Sohar International Bank SAOG, and HSBC Bank Middle East Limited – Oman Branch.
- CBO's page lists banks without a public per-bank licence number or expiry, so those columns are blank.
- The register lists ~20 licensed banks total (also Oman Arab Bank, Ahli Bank, Bank Nizwa,
  Al Izz Islamic, Standard Chartered, State Bank of India, First Abu Dhabi Bank, Qatar National Bank,
  Mashreq, Gulf International Bank, etc.) — the 5 chosen are the primary retail banks a relocating
  employee would use. Others can be added from the same register if wider coverage is wanted.

### schools — 4 rows
- **Register:** International Baccalaureate Organization, "Find an IB World School" (ibo.org/en/school/<id>).
- **Body:** International Baccalaureate Organization; `accreditation_number` = the IB school code.
- ibo.org school pages are Cloudflare-gated to direct curl/WebFetch (returns "Just a moment…" / 403).
  Each school's exact name, IB school code, and Muscat address were confirmed from the IBO register
  pages themselves as indexed (title "International Baccalaureate®", full Muscat street addresses,
  IB school codes). Data is from the IBO register, not firm marketing sites.
  - ABA Oman International School (American British Academy) — IB code 000510 — Muscat — https://www.ibo.org/en/school/000510
  - OURPLANET International School Muscat — IB code 050591 — AL-Inshirah Street, Muscat — https://www.ibo.org/en/school/050591
  - MySchool — IB code 052356 — Al Hail South / Al Seeb, Muscat — https://www.ibo.org/en/school/052356
  - Al Sahwa Schools — IB code 004371 — Mina Al Fahal (PC 116), Muscat — https://www.ibo.org/en/school/004371
- Additional Muscat IB World Schools exist on the register if more coverage is wanted:
  Ellesmere Muscat International Private School (060563), Digital Private School (062375).
- Excluded: The American International School of Muscat (TAISM) — American/AP curriculum,
  NOT on the IB register.

## Categories SKIPPED (re-source worklist)

Per the hard rule "SKIP rather than use self-declared firm sites," these were skipped because
no genuine official per-firm register with reachable per-firm pages was found:

- **legal_admin** — SKIPPED. Oman advocates/law firms are licensed via the Ministry of Justice &
  Legal Affairs / Oman Bar, but there is no reachable public per-firm English register page to cite.
  Re-source: check for a MOJLA public advocate/law-firm licence lookup.
- **tax_finance** — SKIPPED. No public statutory register of tax-advisory firms in Oman
  (the Oman Tax Authority regulates taxpayers, not a listed roster of advisory firms).
  Re-source: audit/accountancy firms may be listable via a professional accountancy body register.
- **housing_agencies** — SKIPPED. Real-estate brokerage is licensed by the Ministry of Housing &
  Urban Planning, but no reachable public per-firm broker register page was found.
  Re-source: check MOHUP for a licensed real-estate office lookup.

## Summary
- movers: 2 (FIDI affiliate detail pages)
- banks: 5 (CBO Licensed Banks register)
- schools: 4 (IBO Find an IB World School register)
- skipped: legal_admin, tax_finance, housing_agencies (no reachable official per-firm register)
- Total rows: 11
