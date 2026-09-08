# Bahrain (BH) — non-obvious relocation facts

**Corridor:** third-country national (non-EEA) professional relocated by their employer to **Bahrain (hub: Manama)**
**Perspective nationality:** non-EEA · **Status:** professional
**Produced:** 2026-08-31 · **Output:** `facts.ndjson` (12 facts, all `confidence: high`, all `non_obvious: true`)

## Method

- Official Bahrain government sources only (LMRA, bahrain.bh national e-gov portal, SIO). No blogs / relocation-firm / news.
- Each `evidence_quote` was extracted **programmatically** as an exact substring of the fetched official text, so `quote_verbatim_confirmed: true` for every fact.
- **Whitespace normalisation only:** line-wraps/multiple spaces in the source (PDF line breaks, HTML markup) were collapsed to single spaces before matching; wording and punctuation are verbatim (original curly apostrophes preserved). No wording was altered.
- LMRA `page/show/*` pages render their body via client-side JS; the substantive text was captured from the rendered page (browser) or from the official PDF linked as that page's "Display" document. HTML pages (SIO, bahrain.bh service catalogue) are server-rendered and were fetched directly.

## Pillar spread (7 allowed; TAX/IMMIGRATION/FAMILY excluded by design)

| Pillar | Count |
|---|---|
| EMPLOYMENT | 5 |
| HEALTHCARE | 2 |
| RESIDENCE | 2 |
| HOUSING | 1 |
| IDENTITY | 1 |
| SOCIAL_SECURITY | 1 |

(No TIMELINE fact; deadline content is carried inside HOUSING/IDENTITY facts.)

## Sources — all confirmed verbatim

| # | Source URL | Authority | Verbatim confirmed? | Facts drawn |
|---|---|---|---|---|
| 1 | https://lmra.gov.bh/en/page/show/106 | LMRA — New Work Permit (rendered page) | YES | employer_applies; medical_wafid; failed_medical_deportation |
| 2 | https://lmra.gov.bh/files/cms/shared/contractual-obligations-employee.pdf | LMRA — Contractual Obligations of Expatriate Employee and Employer (PDF, v.01; linked from page/show/152) | YES | employer_bears_cost; employer_tied; absence_15_days; address_30_days; biometrics_one_month |
| 3 | https://www.lmra.gov.bh/files/cms/shared/file/Flexi%20Permit/Version%200_4/Flexi%20Booklet%200_4%20Ar-En.pdf | LMRA — Flexi Permit "Get the Blue Card" booklet (PDF, v0.4) | YES | flexi_permit:without_sponsor |
| 4 | https://www.bahrain.bh/wps/portal/en/BNP/ServicesCatalogue/GSX-UI-PServiceDetails?psID=2671 | bahrain.bh national e-gov portal — Dependants Residency Permit (Children) | YES | dependant_children_24; dependant_income_400 |
| 5 | https://www.sio.gov.bh/en/end-of-service-gratuity-for-non-bahrainis | Social Insurance Organisation (SIO) — End Of Service Gratuity for non-Bahrainis (FAQ) | YES | eosg_sio_monthly |

## Sources I could NOT reach / verify (skipped rather than guessed)

- **NPRA / CPR ID card as a standalone fact (npra.gov.bh, moi.gov.bh):** the residence-permit and CPR service pages are behind the WebSphere e-gov portal (`services.bahrain.bh`) which requires eKey login and renders via JS; I could not obtain a verbatim official statement dedicated to "the CPR card is mandatory". The IDENTITY pillar is instead carried by the LMRA biometric-registration obligation (fingerprints/photo/signature within one month of first entry), which is the statutory step underlying the CPR/ID. **Skipped the standalone CPR fact.**
- **No personal income tax (nbr.gov.bh / MoF):** no official Bahrain government page states "no personal income tax" verbatim; NBR covers VAT only, and the 7 allowed pillars have no TAX slot. **Skipped** (never invented).
- **LMRA `page/show/194` (Expatriate Employee Transfer):** transfer-without-consent detail — the LMRA page body is JS-rendered and the shared browser session was being driven by parallel processes at fetch time; the transfer obligation is nonetheless covered verbatim from source #2 (employee obligation: notify Authority + employer before transfer). No separate transfer fact was fabricated.
- **Work-permit fees (BHD 195/390 etc.):** appear in LMRA search summaries but were not captured as a verbatim on-page substring in this run, so **no cost fact was emitted** (fees change; not worth an unverified number).

## Notes for the reviewer

- Every fact is employer/role-tied, which is the core non-obvious story for Bahrain: the standard route is an **employer-sponsored** LMRA permit issued on the employer's CR; the **Flexi Permit** (sponsor-free) is an exception, not the default. See `non_obvious_note` on each record.
- `needs_lawyer_review: false` on all — these are direct restatements of published government rules, not interpretive legal advice.
