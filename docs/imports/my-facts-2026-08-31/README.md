# Malaysia (MY) — non-obvious relocation facts — 2026-08-31

Corridor: **MY** (hub: Kuala Lumpur). Persona: third-country national ("non-EEA")
professional relocated by their employer. Output: `facts.ndjson` (12 candidate facts).

All facts are candidates only (`needs_lawyer_review:false`, `quote_verbatim_confirmed:true`).
Every `evidence_quote` was confirmed as a **verbatim substring** of the fetched official
text (see verification note). Numbers/fees are quoted only where they appear verbatim on an
official gov.my page (RM20,000, RM250,000/RM350,000/RM500,000, 30%, 182 days, 14 working days).

## Count
- **12 facts.**
- Pillars: EMPLOYMENT 7, RESIDENCE 4, TIMELINE 1.
- fact_types: eligibility 5, obligation 3, process 2, deadline 1, document 1.

## Topics
1. Employer must register with ESD first (individual cannot self-apply) — RESIDENCE
2. Employer paid-up-capital gate (SSM + RM250k/RM350k/RM500k) — RESIDENCE
3. ESD company registration takes 14 working days — TIMELINE
4. Director must sign Letter of Undertaking in person to activate — RESIDENCE
5. EP Categories I/II/III revised salary thresholds + duration framework (eff 1 Jun 2026) — EMPLOYMENT
6. Category I EP minimum salary RM20,000 and above — EMPLOYMENT
7. EP tied to a local-talent replacement plan (failure → apps rejected) — EMPLOYMENT
8. Dependants not automatic; separate Dependant Pass, salary + insurance conditions — RESIDENCE
9. Tax residency = 182 days physical presence, not nationality — EMPLOYMENT
10. Non-residents taxed at flat 30% — EMPLOYMENT
11. Non-residents cannot claim personal relief/rebate — EMPLOYMENT
12. Keep certified passport copy + entry/exit records to prove residency — EMPLOYMENT

## Source URLs — official gov.my only (all verbatim-confirmed)
| # facts | Source | URL | Fetched via |
|---|---|---|---|
| 1-4 | ESD (Immigration Dept) — Company Registration FAQ | https://esd.imi.gov.my/portal/faq/esd-company-registration/ | curl HTML + browser get_page_text |
| 5 | ESD — Announcement 273: Revised EP Salary Policy briefing | https://esd.imi.gov.my/portal/latest-news/announcement/announcement-273/ | curl HTML + browser get_page_text |
| 6-8 | MOHA/ESD — FAQ: Revised Employment Pass Salary Policy (effective 1 June 2026) | https://esd.imi.gov.my/portal/pdf/EN%20FAQ%20-%20NEW%20EXPATRIATE%20EMPLOYMENT%20POLICY%20(EFFECTIVE%201%20JUNE%202026).pdf | curl PDF → pypdf text extract |
| 9-12 | LHDN (Inland Revenue Board) — Tax Treatment Residents & Non-Residents | https://www.hasil.gov.my/wp-content/uploads/T2025_tax-treatment-residents-non-residents.pdf | curl PDF → pypdf text extract |

## Verbatim confirmed?
**Yes — all 12.** Each `evidence_quote` was grep/substring-checked against the raw fetched
source (stripped HTML for the two ESD web pages; pypdf-extracted text for the two PDFs).
PDF quotes were chosen as single-line substrings to avoid extraction line-break artifacts.

## Unverifiable / dropped sources
- **hasil.gov.my HTML pages** (`/en/individual/individual-life-cycle/.../non-resident/`): the
  HASiL portal was recently upgraded; the older non-resident/residence HTML URLs now return
  **404** ("The HASiL Official Portal has recently been upgraded"). Tax facts were instead
  sourced from the still-live LHDN PDF `T2025_tax-treatment-residents-non-residents.pdf`.
- **phl.hasil.gov.my** (`/pdf/pdfam/006a.pdf`, `individual.pdf`): connection timed out /
  refused from this environment — not used.
- **hasil `/media/<hash>/` PDFs** (e.g. PR 2/2026 foreign nationals): 404 after the portal
  upgrade (hashed paths changed) — not used.
- **esd.imi.gov.my/portal/expatriates/**: returned **403 Forbidden** — not used.
- **RM5,000 (Category III) figure**: NOT asserted as current. The old threshold could not be
  confirmed verbatim on a current official page after the 1 June 2026 policy revision, so only
  the verbatim RM20,000 Category I figure is included.
- **EPF/SOCSO (SOCIAL_SECURITY)** and **MDEC tech-specific** facts: no verbatim quote obtained
  from the enumerated official sources within scope — none included.

## Notes for the reviewer
- Facts 5-8 come from the MOHA official Q&A for the **New Expatriate Employment Policy
  effective 1 June 2026** — current as of the 2026-08-31 fetch.
- Fact 9 (182-day quote) is drawn from an official LHDN worked example that states the
  residency test; the fact is phrased as the general rule.
