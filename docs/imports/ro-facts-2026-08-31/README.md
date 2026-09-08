# RO facts — third-country professional relocated to Romania (Bucharest hub)

Generated 2026-08-31. Perspective: **non-EEA** professional, employer-sponsored. Corridor `RO`.
Only facts NOT also applicable to an EU/EEA citizen; all non-obvious; all with a verbatim
official-government quote (< 200 chars).

- Output: `facts.ndjson` — **12 facts**, all `confidence: high`, `needs_lawyer_review: false`,
  `quote_verbatim_confirmed: true`.
- Pillar spread: EMPLOYMENT 9, RESIDENCE 1, TIMELINE 1, HOUSING 1.

## Sources (official government only) — all fetched & verbatim-confirmed

Each `evidence_quote` was confirmed as a whitespace-normalised **verbatim substring** of the
live fetched text (curl direct-fetch; ANAF PDF text-extracted with pypdf). Re-verification script
passed 12/12.

| # | Pillar | Topic | Source URL | Verbatim? |
|---|--------|-------|-----------|-----------|
| 1 | EMPLOYMENT | Work permit tied to a single employer | https://igi.mai.gov.ro/en/employment-and-posting/ | YES |
| 2 | EMPLOYMENT | Only the employer can obtain the permit | https://www.euraxess.gov.ro/romania/information-assistance/work-permit | YES |
| 3 | EMPLOYMENT | Annual quota (Government Decision) | https://igi.mai.gov.ro/en/employment-and-posting/ | YES |
| 4 | EMPLOYMENT | Labour-market test | https://igi.mai.gov.ro/en/employment-and-posting/ | YES |
| 5 | EMPLOYMENT | Work permit fee EUR 100 (employer) | https://igi.mai.gov.ro/en/employment-and-posting/ | YES |
| 6 | EMPLOYMENT | Permit cancelled on contract termination | https://igi.mai.gov.ro/en/employment-and-posting/ | YES |
| 7 | EMPLOYMENT | Blue Card: free mobility only after 12 months | https://igi.mai.gov.ro/en/employment-and-posting/ | YES |
| 8 | RESIDENCE | Long-stay employment visa fee EUR 120 (abroad) | https://igi.mai.gov.ro/en/long-stay-visa-for-employment-purposes/ | YES |
| 9 | TIMELINE | Long-stay visa covers only 90 days | https://igi.mai.gov.ro/en/long-stay-visa-for-employment-purposes/ | YES |
| 10 | HOUSING | Proof of legal living space for the permit | https://igi.mai.gov.ro/en/single-permit/ | YES |
| 11 | EMPLOYMENT | Tax-residency questionnaire within 30 days | https://static.anaf.ro/static/10/Anaf/AsistentaContribuabili_r/Ghid_rezidenta_2023_EN.pdf | YES |
| 12 | EMPLOYMENT | Worldwide taxation once tax-resident | https://static.anaf.ro/static/10/Anaf/AsistentaContribuabili_r/Ghid_rezidenta_2023_EN.pdf | YES |

Domains used: `igi.mai.gov.ro` (IGI — General Inspectorate for Immigration), `euraxess.gov.ro`
(official Romanian government / Ministry portal, `.gov.ro`), `static.anaf.ro` (ANAF — National
Agency for Fiscal Administration, 2025 English "Guidelines for Fiscal Residence of Individuals").

## Caveats / notes for review

- **2026 legislative change (monitor).** Secondary/press reporting indicates OUG 32/2026 (in force
  ~27 Apr 2026) moves employer applications onto an electronic "single application" via
  `WorkinRomania.gov.ro`, and IGI's own homepage news ticker references WorkinRomania. However, the
  IGI English guidance pages fetched here (`/employment-and-posting/`, `/single-permit/`,
  `/long-stay-visa-for-employment-purposes/`) **still describe the work-permit / long-stay-visa /
  single-permit route in full and are the currently-published official guidance** (copyright 2026).
  All facts are grounded in that live official text. The *mechanisms* quoted (employer-obtained
  authorisation, annual quota by Government Decision, labour-market test, single-employer tie,
  90-day visa → in-country residence permit, EUR 120 visa fee) are stable across the reform; the
  exact procedural channel and any fee figures should be re-checked against IGI/WorkinRomania before
  serving. No unofficial (blog/law-firm/news) source was used for any fact.
- **Quota number deliberately omitted.** The only quota figure found verbatim on IGI (100,000) is in
  a 2022 press release (`HG 132/2022`), so it is stale. Fact #3 quotes only the *mechanism*
  ("annual quota approved by Government Decision"), which is confirmed on two live pages.
- **CNP (IDENTITY) dropped on purpose.** A verbatim CNP quote was found on `euraxess.gov.ro`
  ("granted only once … only be changed when obtaining Romanian citizenship"), but a CNP is assigned
  to EU/EEA citizens too, so it fails the "not also applicable to an EU citizen" rule. Excluded.
- **Unverifiable sources:** none. Every shipped fact's quote is a confirmed verbatim substring of
  its cited official page/PDF.

## Reproduce verification

Fetched HTML/PDF and the extraction/verification scripts are in the session scratchpad
(`ro_work/`). Verification normalises whitespace and asserts each `evidence_quote` is a substring of
the fetched official text; the run reported 12/12 OK.
