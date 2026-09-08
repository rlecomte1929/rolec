# NZ (Auckland hub) — non-obvious relocation facts, third-country-national professional

Generated 2026-08-31. Perspective nationality: **non-EEA**. Status: **professional** (employer-sponsored).
Corridor target: **NZ**. Output: `facts.ndjson` (12 facts, candidates only — `needs_lawyer_review:false` but unpromoted).

## Method

Every fact was **browser-grounded**: the official page was opened in-browser and the `evidence_quote`
copied as a **verbatim substring (<200 chars)** of the live page text. Sources are **official
NZ government only** (all under `govt.nz`). No blogs, relocation firms, law firms, or news.
No numbers, fees, or citations were invented; where a rule has a future change date, the
verbatim quote carries that date.

## Facts and sources (all browser-confirmed verbatim ✓)

| # | Pillar | Topic | Source URL |
|---|--------|-------|------------|
| 1 | RESIDENCE | AEWV job offer must be from accredited employer with approved job check | https://www.immigration.govt.nz/visas/accredited-employer-work-visa/ |
| 2 | RESIDENCE | Employer must be AEWV-accredited before it can hire migrants | https://www.immigration.govt.nz/work/for-employers/getting-accreditation-or-approval-to-hire/employer-accreditation-for-the-aewv/aewv-employer-accreditation-and-job-check-process/ |
| 3 | RESIDENCE | AEWV tied to employer/role/location; change needs variation or Job Change | https://www.immigration.govt.nz/visas/accredited-employer-work-visa/ |
| 4 | RESIDENCE | Partner work/visitor visa + dependent-children student/visitor visas | https://www.immigration.govt.nz/visas/accredited-employer-work-visa/ |
| 5 | EMPLOYMENT | Pay test is NZ market rate (median-wage threshold removed) | https://www.immigration.govt.nz/work/requirements-for-work-visas/wage-rates-for-work-visas/ |
| 6 | IDENTITY | IRD number required (lifelong tax identifier) to be paid / bank / KiwiSaver | https://www.ird.govt.nz/managing-my-tax/ird-numbers |
| 7 | EMPLOYMENT | No IR330 → PAYE deducted at 45% non-declaration rate | https://www.ird.govt.nz/income-tax/income-tax-for-individuals/tax-codes-and-tax-rates-for-individuals/tax-codes-for-individuals |
| 8 | EMPLOYMENT | Tax residency (183-day OR permanent place of abode) is separate from immigration status | https://www.ird.govt.nz/international-tax/individuals/tax-residency-status-for-individuals |
| 9 | EMPLOYMENT | ~4-year transitional-resident exemption on most foreign income (NOT foreign employment income) | https://www.ird.govt.nz/roles/nz-tax-residents/exemption |
| 10 | HEALTHCARE | Publicly funded health only if work visa is 2 years or more | https://www.healthnz.govt.nz/hospitals-services/eligibility-subsidies/publicly-funded-healthcare |
| 11 | HOUSING | Drive on overseas licence for a limited window (18→12 months from 1 Nov 2026), then convert | https://www.nzta.govt.nz/travelling-on-our-roads/visitors-and-new-residents/driving-on-nz-roads/time-limit-extended-for-driving-on-an-overseas-licence |
| 12 | SOCIAL_SECURITY | KiwiSaver: temporary work-visa holders cannot join (no auto-enrolment) | https://www.ird.govt.nz/kiwisaver/kiwisaver-individuals/joining-kiwisaver |

## Pillar distribution

RESIDENCE 4 · EMPLOYMENT 4 · IDENTITY 1 · HEALTHCARE 1 · HOUSING 1 · SOCIAL_SECURITY 1 (6 of 7 pillars; no TIMELINE).

## Notes / caveats

- **URL structure churn:** `immigration.govt.nz` and `health.govt.nz` have been restructured; several
  legacy paths 404 or redirect. The URLs above are the live, resolving pages as of 2026-08-31. The
  health-eligibility page now lives on `healthnz.govt.nz` (Health NZ | Te Whatu Ora, under `govt.nz`).
- **Driving (fact 11) is date-sensitive:** as of today the limit is still 18 months (the 2024 extension
  ends 31 Oct 2026); from 1 Nov 2026 it reduces to 12 months. The verbatim quote states this explicitly,
  so the fact is accurate for anyone arriving now or later.
- **Market rate (fact 5):** the general median-wage pay threshold for the AEWV was removed; the grounded
  quote is the market-rate definition. The removal date (10 Mar 2025) is context in the note, not asserted
  as a served number.
- **No unverifiable sources used.** Every quote was confirmed against the opened live page.

## Load path

Candidates only. Do not promote to `live`/`verified`/`approved`. If loaded to
`public.requirement_items`, set `review_status='pending'` explicitly and keep `ON CONFLICT` from
overwriting a reviewer's decision.
