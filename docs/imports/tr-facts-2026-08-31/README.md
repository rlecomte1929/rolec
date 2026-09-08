# TR facts — third-country-national professional relocated to Türkiye (Istanbul hub)

- **Corridor / destination:** TR (hub: Istanbul)
- **Perspective:** nationality = `non-EEA`, status = `professional` (employer-sponsored)
- **Date:** 2026-08-31
- **Output:** `facts.ndjson` — 11 facts, all `confidence: high`, all `non_obvious: true`, all `needs_lawyer_review: false`
- **Sourcing rule:** official Turkish government (`gov.tr`) only. No blogs / relocation-firm / news.
- **Grounding:** every fact direct-fetched; each `evidence_quote` re-checked programmatically as a **verbatim substring** of the fetched official text and confirmed **< 200 chars**. All 11 PASS.

## Pillar distribution
RESIDENCE 5 · EMPLOYMENT 3 · IDENTITY 1 · SOCIAL_SECURITY 1 · TIMELINE 1

## Topics covered
1. Work permit doubles as the residence permit (LFIP No. 6458 Art. 27) — RESIDENCE
2. Register at Provincial Directorate of Migration Management within 20 working days of entry — RESIDENCE
3. Work visa applied for at a Turkish mission (consulate) abroad before entry; domestic filing only if ≥6-month residence permit — RESIDENCE
4. T.C. Foreigner Identity Number starts with 99 — IDENTITY
5. Permit tied to one employer; different employer = new first application — EMPLOYMENT
6. First (definite) work permit granted for up to one year — EMPLOYMENT
7. Turquoise Card: 3-year transition period before it becomes indefinite — RESIDENCE
8. SGK (social security) notification within 30 days of permit start date — SOCIAL_SECURITY
9. Income-tax residency: continuous stay > 6 months in one calendar year — EMPLOYMENT
10. Work permit extension window opens 60 days before expiry (late = first application) — TIMELINE
11. 10 legal days' grace after work permit expiry to apply for a residence permit — RESIDENCE

## Source URLs (official, gov.tr) — all verbatim-confirmed
| # facts | Source | URL | Verbatim confirmed? |
|---|---|---|---|
| 1, 2, 11 | Presidency of Migration Management (goc) — Work Permit FAQ | https://en.goc.gov.tr/work-permit | Yes (direct curl) |
| 3 | Ministry of Labour, UIGM — Info & documents in work-permit evaluation | https://www.csgb.gov.tr/uigm/en/general-information/information-and-documents-required-in-the-work-permit-evaluation-process/ | Yes (direct curl) |
| 4, 10 | Ministry of Labour, UIGM — Application Types | https://www.csgb.gov.tr/uigm/en/work-permit/application-types/ | Yes (direct curl) |
| 5, 6 | Ministry of Labour, UIGM — Work Permit Types | https://www.csgb.gov.tr/uigm/en/work-permit/work-permit-types/ | Yes (direct curl) |
| 7 | Ministry of Labour, UIGM — Turquoise Card | https://www.csgb.gov.tr/uigm/en/turkuaz-kart/ | Yes (direct curl) |
| 8 | Ministry of Labour, UIGM — Social Security of Foreign Employees | https://www.csgb.gov.tr/uigm/en/general-information/social-security-of-foreign-employees/ | Yes (direct curl) |
| 9 | Revenue Administration (gib) — 2025 Guidebook for Taxpayers (non-resident) PDF | https://intvrg.gib.gov.tr/hazirbeyan/assets/pdf/2025THEGUIDEBOOKTAXPAYERS.pdf | Yes (direct curl + PDF text extract) |

## Notes / unverifiable sources
- **gib.gov.tr "Turkish Taxation System" HTML page** (e.g. `https://mersin.gib.gov.tr/en/references-and-resources/turkish-taxation-system`) is a **client-rendered Next.js app**: curl / WebFetch / RSC-fetch returned no body text, so it could **not** be self-verified. It carries the extra "resident = worldwide income / full tax liable" statement and the "specific job/business/particular purpose" 6-month exception. Rather than ship an unverifiable quote, the tax-residency fact (9) is sourced from the **directly-fetchable gib 2025 Guidebook PDF**, whose verbatim non-resident definition establishes the same > 6-month continuous-stay threshold.
- **Shared browser pane** was being driven by other agents during this run (observed loading unrelated sites), so browser-grounding was unavailable; all grounding was done via direct curl + local text/PDF extraction instead.
- No facts were dropped for lack of a quote — all 11 candidates passed verbatim verification. Nothing was fabricated: no invented numbers, fees, or citations.

## Pillar compliance
`applies_to.pillar` is one of the 7 allowed values only (EMPLOYMENT, HEALTHCARE, HOUSING, IDENTITY, RESIDENCE, SOCIAL_SECURITY, TIMELINE). IMMIGRATION / TAX / FAMILY were **not** used (income-tax mapped to EMPLOYMENT; work-permit-as-residence/visa/status mapped to RESIDENCE; SGK to SOCIAL_SECURITY; foreigner-ID to IDENTITY; pure deadline to TIMELINE).
