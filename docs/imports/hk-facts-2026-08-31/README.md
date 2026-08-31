# Hong Kong (HK) — non-obvious relocation facts

**Corridor:** third-country-national ("non-EEA") professional relocated by their employer to Hong Kong.
**Date:** 2026-08-31 · **Facts:** 12 · **All quotes browser/source confirmed verbatim.**

## Sourcing method (honesty note)

The shared browser MCP pool was being hijacked by parallel agents (tabs cycled through
unrelated foreign-government sites mid-call), so it could not reliably hold a Hong Kong page
open for verbatim extraction. Every fact was instead grounded by fetching the **raw HTML
directly from the official HK government servers** (curl, HTTP 200) and asserting each
`evidence_quote` is an **exact substring** of that page's rendered text. Verification passed
for all 12 quotes (`quote_verbatim_confirmed=true`). Sources are official government domains
only (immd.gov.hk, gov.hk, mpfa.org.hk, td.gov.hk); no blogs/law-firm/relocation-firm/news.

## Facts, sources and verification

| # | Pillar | Topic | Source URL | HTTP | Quote verbatim-confirmed |
|---|--------|-------|-----------|------|--------------------------|
| 1 | RESIDENCE | GEP visa is employer-sponsored / tied | https://www.immd.gov.hk/eng/services/visas/GEP.html | 200 | Yes (exact substring) |
| 2 | EMPLOYMENT | Visa/entry permit required before working | https://www.immd.gov.hk/eng/services/visas/GEP.html | 200 | Yes |
| 3 | RESIDENCE | Dependants may work and study | https://www.immd.gov.hk/eng/services/visas/GEP.html | 200 | Yes |
| 4 | TIMELINE | GEP processing ~4 weeks after complete file | https://www.immd.gov.hk/eng/services/visas/GEP.html | 200 | Yes |
| 5 | RESIDENCE | TTPS needs no job offer to apply | https://www.immd.gov.hk/eng/services/visas/TTPS.html | 200 | Yes |
| 6 | IDENTITY | HK Identity Card registration mandatory | https://www.immd.gov.hk/eng/faq/faq_hkic.html | 200 | Yes |
| 7 | EMPLOYMENT | Salaries tax is territorial | https://www.gov.hk/en/residents/taxes/salaries/salariestax/chargeable/index.htm | 200 | Yes |
| 8 | EMPLOYMENT | No PAYE withholding — you file and pay | https://www.gov.hk/en/residents/taxes/salaries/salariestax/employeeobligations.htm | 200 | Yes |
| 9 | SOCIAL_SECURITY | MPF enrolment within first 60 days | https://www.mpfa.org.hk/en/mpf-system/enrolment-and-termination | 200 | Yes |
| 10 | SOCIAL_SECURITY | MPF exemption: first 13 months / overseas scheme | https://www.mpfa.org.hk/en/mpf-system/mpf-coverage | 200 | Yes |
| 11 | SOCIAL_SECURITY | MPF is 5% employee + 5% employer | https://www.mpfa.org.hk/en/mpf-system/mandatory-contributions | 200 | Yes |
| 12 | HOUSING | Direct issue of HK driving licence without test | https://www.td.gov.hk/en/public_services/licences_and_permits/driving_licences/how_to_apply_for_a_driving_licence/driving_in_hong_kong_for_overseas_driving_licence_/index.html | 200 | Yes |

Pillar spread: RESIDENCE ×3, EMPLOYMENT ×3, SOCIAL_SECURITY ×3, TIMELINE ×1, IDENTITY ×1, HOUSING ×1.

## Topics dropped (no verbatim official quote found in budget)

- **HKID "within 30 days of arrival" for adult new arrivals.** IMMD/GovHK pages state the
  mandatory-registration obligation and the ≤180-day exemption (both captured in fact #6) and a
  30-day figure for the 11th-birthday first registration and for card *replacement after
  absence* — but no page fetched stated an explicit "within 30 days of arrival" for an adult
  new arrival (that limit lives in the Registration of Persons Regulations, Cap. 177A). The
  30-day-of-arrival number was therefore **not** asserted, to avoid fabricating a figure not on
  the cited page. Fact #6 is scoped to what the official page verbatim supports.
- **No-capital-gains / no-VAT nuance.** Not included — no single official page was opened that
  states it verbatim within budget; not fabricated.
