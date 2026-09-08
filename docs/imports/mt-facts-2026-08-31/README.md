# MT facts — third-country national professional relocated to Malta (Valletta hub)

Batch date: 2026-08-31 · Perspective nationality: `non-EEA` · Corridor: `MT`
Output: `facts.ndjson` (12 facts). All quotes copied verbatim from the cited live page.

## Verification

Every `evidence_quote` was confirmed by re-fetching the exact `source_url` fresh
(independent `urllib` fetch, whitespace-normalised substring match) — simulating the
`confirm_quotes.py` referee. **12 / 12 reproduced verbatim.** `quote_verbatim_confirmed: true`
is set on all facts. All sources are rendered HTML (no PDFs).

## Sources used (all official gov.mt, all confirmed verbatim)

| # | fact_key | source_url | verbatim |
|---|----------|------------|----------|
| 1 | single_permit:combined_work_residence | identita.gov.mt …/single-permit/ | yes |
| 2 | permit_conditions:null_on_employer_or_role_change | identita.gov.mt …/change-of-designation-or-employer/ | yes |
| 3 | eresidence_card:prints_designation_employer | identita.gov.mt …/employment-related-permits/ | yes |
| 4 | permit_scope:no_eu_movement_for_employment | identita.gov.mt …/employment-related-permits/ | yes |
| 5 | processing_time:four_months_statutory | identita.gov.mt …/single-permit/application-processing-period/ | yes |
| 6 | employment_licence:jobsplus_stakeholder_review | jobsplus.gov.mt/find-candidates/non-eu-nationals-tcns | yes |
| 7 | labour_market_test:advertise_no_eu_candidate | jobsplus.gov.mt/find-candidates/non-eu-nationals-tcns | yes |
| 8 | start_of_employment:illegal_before_permit_issued | jobsplus.gov.mt/find-candidates/non-eu-nationals-tcns | yes |
| 9 | key_employee_initiative:min_salary_45000 | identita.gov.mt …/key-employee-initiative/who-is-eligible/ | yes |
| 10 | key_employee_initiative:five_working_days | identita.gov.mt …/key-employee-initiative/ | yes |
| 11 | key_employee_initiative:fees_600_150 | identita.gov.mt …/key-employee-initiative/who-is-eligible/ | yes |
| 12 | specialist_employee_initiative:min_salary_25000_mqf6 | jobsplus.gov.mt/find-candidates/non-eu-nationals-tcns | yes |

Full URLs are in `facts.ndjson`. Two domains only: `identita.gov.mt` (Identità Expatriates
Unit) and `jobsplus.gov.mt` (Employment Licences).

Pillar spread: RESIDENCE ×5, EMPLOYMENT ×5, IDENTITY ×1, TIMELINE ×1.

## Unverifiable / dropped sources (excluded from batch)

These official gov.mt domains were requested but are **hard-blocked to server-side fetchers**
(Cloudflare "Sorry, you have been blocked" / HTTP 403 from datacenter IPs), including the
browser-render path. Any fact cited to them would be **HELD** by the referee, so **no facts
were sourced from them**:

- **cfr.gov.mt** (Commissioner for Revenue / MTCA) — Cloudflare hard block. This drops the
  intended **Highly Qualified Persons 15% flat-tax**, **tax residency**, and **non-dom /
  remittance basis** facts. The HQP 15% page exists and is rendered HTML
  (`…/Tax-Guidelines-on-Highly-Qualified-Persons-Rules.aspx`) but cannot be fetched/reproduced
  by curl, WebFetch, or the browser tool here. Re-source only from a reproducibly-fetchable
  official page.
- **homeaffairs.gov.mt** — HTTP 403 to server-side fetch.
- **socialsecurity.gov.mt** — HTTP 403 to server-side fetch. This drops the intended
  **social security registration** (SOCIAL_SECURITY) fact.

## Data note — KEI minimum salary discrepancy (resolved in favour of Identità)

Two official gov.mt figures exist for the Key Employee Initiative minimum salary:

- **identita.gov.mt** KEI "Who is Eligible" page: **€45,000** per annum
  ("*an annual gross salary of at least €45,000 per annum*").
- **jobsplus.gov.mt** TCN page: **€35,000** per annum
  ("*earning at least €35,000 per annum*").

Fact #9 cites the **Identità €45,000** figure — Identità is the issuing authority for the KEI
residence permit and its dedicated eligibility page is the primary source; the Jobsplus €35,000
appears to be stale. Only the €45,000 figure was written to the batch. Flag for a reviewer if
the corridor needs the definitive current threshold.

## Non-obvious angle

All 12 facts are third-country-only (not applicable to an EU citizen exercising free movement)
and each carries a `non_obvious_note` in "Commonly believed … Actually … Action:" form. Themes:
the single combined permit (not two visas), the permit being void the moment employer/role
changes, the embedded Jobsplus EU-preference labour-market test, illegality of starting work
before issuance, and the KEI/SEI fast-track thresholds, timelines and fees.
