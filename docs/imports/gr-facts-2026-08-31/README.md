# GR facts — third-country professional relocated to Greece (Athens hub)

Batch date: 2026-08-31
Corridor: **GR** · Nationality perspective: **non-EEA** · Status: **professional** (employer relocation)
Output: `facts.ndjson` — **10 facts**, all `confidence: high`, all `quote_verbatim_confirmed: true`.

Scope: third-country-national requirements only. No EU free-movement facts were written.

## Verification method

Each `evidence_quote` was confirmed as a **verbatim substring** of the fetched official page:
- migration.gov.gr pages: fetched by direct `curl`, quotes checked against the rendered text of the saved HTML.
- mfa.gr / aade.gr / gov.gr / e-efka.gov.gr: these hosts return **403 to curl (WAF)**, so they were **browser-grounded** — the live page's `main`/`body` `innerText` was checked with `.includes(<quote>)` returning `true`.

## Sources (all official Greek government) — verbatim confirmed?

| # | Fact | Pillar | Source URL | Verbatim |
|---|------|--------|------------|----------|
| 1 | National (type D) long-stay visa required before entry for work | RESIDENCE | https://www.mfa.gr/en/services/national-visas/ | YES (browser) |
| 2 | Residence permit for dependent employment (Article 15) | RESIDENCE | migration.gov.gr categories page* | YES (curl) |
| 3 | Employer-initiated recruitment (metaklisi) | EMPLOYMENT | migration.gov.gr categories page* | YES (curl, Greek) |
| 4 | EU Blue Card (highly-skilled) is a separate category | RESIDENCE | migration.gov.gr categories page* | YES (curl, Greek) |
| 5 | Residence permit is purpose-bound (change needs new status) | RESIDENCE | migration.gov.gr categories page* | YES (curl) |
| 6 | Tax residency after >183 days → worldwide income taxed | EMPLOYMENT | https://www.aade.gr/en/greeks-abroad-non-residents/income-taxation/tax-residence-natural-persons-itc | YES (browser) |
| 7 | Greek AFM/TIN can be issued from abroad via a tax representative | EMPLOYMENT | https://www.aade.gr/en/greeks-abroad-non-residents/registration-tax-register/issuance-tax-identification-number-and-authentication-key-and-appointment | YES (browser) |
| 8 | Article 5C special taxation for new tax residents | EMPLOYMENT | https://www.aade.gr/en/greeks-abroad-non-residents/income-taxation/tax-incentives-order-attract-new-tax-residents | YES (browser) |
| 9 | AMKA (Social Insurance Number) + e-EFKA registration to be paid | SOCIAL_SECURITY | https://www.gov.gr/en/services/1001371/bebaiose-apographes-eephka | YES (browser) |
| 10 | Bilateral social-security conventions with named third countries | SOCIAL_SECURITY | https://www.e-efka.gov.gr/en/node/25 | YES (browser, Greek) |

\* migration.gov.gr categories page (full URL, requires the trailing encoded zero-width char to resolve):
`https://migration.gov.gr/en/migration-policy/metanasteusi-stin-ellada/katigories-adeion-diamonis-politon-triton-choron-dikaiologitika%e2%80%8b/`

## Topics covered
type-D national visa · Article-15 dependent-employment residence permit · employer metaklisi (work authorisation) · EU Blue Card / highly-skilled · permit purpose-binding · 183-day tax residency · AFM/TIN · Article 5C new-tax-resident incentive · AMKA + e-EFKA · bilateral social-security conventions.

## Notes, caveats and unverifiable items (nothing invented)

- **No exact numbers were quotable, so none were written.** Specifically:
  - The **EU Blue Card salary threshold** and the **Article 5C exemption rate (commonly cited as 50%)** live only inside **WAF-blocked PDFs** on aade.gr (`FAQS_5G_KFE.pdf`) and a migration.gov.gr circular (doc 5910/20). Neither could be fetched (403 to curl; the PDFs do not render as readable text in the browser tools). Per the no-invention rule, facts 4 and 8 describe the regime **without** a specific figure.
- **MFA type-D visa detail is in a WAF-blocked `.docx`** (`General-Supporting-Documents-...-D-type-visas.docx`, 403 to curl). Fact 1 is grounded on the verbatim page text of the National Visas landing page instead.
- **EU-applicability caveat.** Facts 6 (183-day), 7 (AFM), 8 (Article 5C) and 9 (AMKA) are obligations a relocating third-country professional must meet, but they are **not exclusive to third-country nationals** — an EU/EEA worker relocating to Greece meets them too. They are included because they are on the batch's explicit topic list and the `non_obvious_note` frames the third-country journey. Facts 1–5 and 10 are genuinely third-country-specific. If the pipeline requires strictly TCN-exclusive facts, treat 6–9 as review-flagged.
- migration.gov.gr's Blue Card entry still cites the **older** legal basis (Art. 114, L.4251/2014) on the live page even though other categories reference the new Migration Code (L.5038/2023); the quote is reproduced as the official page states it.
- efka.gov.gr / e-efka.gov.gr "English" (`/en/`) nodes still render **Greek** content; fact 10's quote is therefore Greek (permitted — quote may be Greek, `fact_text` is English). AMKA (fact 9) was sourced from gov.gr, which has clean English.
