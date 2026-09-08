# Israel (IL) — non-obvious relocation facts, official gov sources

**Corridor:** third-country-national (non-EEA) professional relocated by employer to Israel (hub: Tel Aviv)
**Date:** 2026-08-31
**Output:** `facts.ndjson` — 12 facts, all with a verbatim official-government quote (`quote_verbatim_confirmed: true`)

Pillar spread: EMPLOYMENT 5 · SOCIAL_SECURITY 3 · RESIDENCE 2 · HEALTHCARE 1 · HOUSING 1

## Sources used (all official, under gov.il)

| # facts | Source | URL | Fetch method | Verbatim confirmed? |
|---|---|---|---|---|
| 2 | PIBA — Apply for a permit to employ an expert foreign worker (service page) | https://www.gov.il/en/service/working_permit_for_foreign_workers | Browser (Cloudflare-gated; curl/WebFetch return 403) | Yes — quote is exact substring of the rendered page |
| 6 | PIBA — Application for a Permit to Employ a Foreign National Expert (form 5.3.0041, EN), under s.1m Foreign Workers Law 1991 | https://www.gov.il/BlobFolder/service/working_permit_for_foreign_workers/en/5.3.0041%D6%B9_eng_forms_0.pdf | Browser same-origin fetch of PDF bytes → base64 → pdfminer text extraction | Yes — each quote grep-verified as exact substring of extracted PDF text |
| 2 | National Insurance Institute (Bituach Leumi) — Employment of a foreign resident (Employers) | https://www.btl.gov.il/English%20Homepage/Insurance/Employers/foreignresident/Pages/default.aspx | curl (not Cloudflare-gated) | Yes — exact substring of page HTML text |
| 1 | National Insurance Institute — Information to foreign worker, Work Injury | https://www.btl.gov.il/English%20Homepage/Benefits/Work%20Injury%20Insurance/Pages/Foreign-worker.aspx | curl | Yes — exact substring of page HTML text |

Every `evidence_quote` was programmatically checked as an exact substring (whitespace-collapsed) of the fetched official text and is < 200 chars.

## Non-obvious topics covered
- B/1 expert permit is **employer-obtained**, not worker-applied; employer pays the permit fee.
- Foreign-expert ("mumche") track needs expertise **unavailable in Israel**.
- **Double-the-average-wage** minimum-salary rule for expert wages (published by the NII).
- First expert permit **capped at 2 years** (academic) / **1 year** (non-academic), then renewed.
- Work is **tied to the sponsoring employer/field**; changing needs prior written PIBA authorization.
- **Limited period** — must leave Israel immediately when employment ends.
- Employer must provide **private medical insurance** (foreign workers are outside the resident public-health system) — HEALTHCARE.
- Employer must provide **adequate accommodation** — HOUSING.
- **"Center of life"** residency test (National Insurance; mirrors income-tax residency) — not day-count/citizenship.
- Employer must **pay National Insurance** for a non-resident foreign worker; foreign worker is **insured for work injury**.

## Sources I could NOT reach / dropped

- **www.gov.il via direct curl and WebFetch → Cloudflare 403** ("Attention Required"). Worked around by driving the browser pane (which passes the JS challenge) for the two gov.il sources above.
- **Israel Tax Authority income-tax "center of life" definition and the foreign-expert flat-tax rule** — NOT confirmed.
  - `financeisrael.mof.gov.il` Income Tax Ordinance PDF was **unreachable** (curl HTTP 000, connection failed).
  - The gov.il Tax Authority glossary (https://www.gov.il/en/pages/taxes-glossary) was reachable but did **not** contain a "resident of Israel"/"center of life" definition.
  - The English expert-procedure policy landing page (`.../policies/request_for_working_permit_expert_foreign_workers_procedure/`) returned **404**.
  - Consequence: the **foreign-expert flat-tax** topic was **dropped** (no verbatim official quote obtained — no invention). The "center of life" fact instead cites the National Insurance (btl.gov.il) definition, which is the same statutory concept, and the fact_text notes it mirrors income-tax residency without overclaiming a tax quote.
