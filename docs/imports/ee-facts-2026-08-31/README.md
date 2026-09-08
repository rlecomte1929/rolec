# Estonia (EE) — non-obvious third-country-national relocation facts

Hub: Tallinn. Perspective nationality: `non-EEA` (Estonia is EEA — only third-country facts written).
Generated 2026-08-31. 13 facts in `facts.ndjson`.

Scope: temporary residence permit for employment (employer/role-tied), the immigration quota
(0.1% of permanent population) and its ICT/start-up exemptions, short-term-employment registration
(≤365 days), salary threshold (Estonian average gross wage), e-Residency ≠ residence permit,
isikukood, address registration in the Population Register, and tax residency (183 days).

## Sources and verbatim-confirmation status

All quotes copied verbatim (<200 chars) from the cited live page.

### Curl-reachable, server-rendered (referee `confirm_quotes.py` can re-fetch) — 10 facts
Each quote below was re-extracted from the raw HTML and confirmed to appear as a **contiguous
string** in the page's visible text.

| # | Pillar | Source URL | Quote confirmed |
|---|--------|-----------|-----------------|
| unemployment_fund_permit | EMPLOYMENT | https://www.politsei.ee/en/instructions/residence-permit-for-employment | YES |
| average_gross_salary_threshold | EMPLOYMENT | https://www.politsei.ee/en/instructions/residence-permit-for-employment | YES |
| a2_language_for_extension | RESIDENCE | https://www.politsei.ee/en/instructions/residence-permit-for-employment | YES |
| register_place_of_residence | HOUSING | https://www.politsei.ee/en/instructions/residence-permit-for-employment | YES |
| short_term_365_in_455 | EMPLOYMENT | https://www.politsei.ee/en/instructions/working-in-estonia/for-employers | YES |
| short_term_registration_not_a_stay_right | RESIDENCE | https://www.politsei.ee/en/instructions/working-in-estonia/for-employers | YES |
| employer_registers_short_term | EMPLOYMENT | https://www.politsei.ee/en/instructions/working-in-estonia | YES |
| eresidency_not_a_residence_permit | IDENTITY | https://www.politsei.ee/en/instructions/e-resident-s-digital-id | YES |
| tax_residency_183_days | EMPLOYMENT | https://www.emta.ee/en/private-client/foreigner-non-resident/tax-residency/determining-residency | YES |
| resident_taxed_on_worldwide_income | EMPLOYMENT | https://www.emta.ee/en/private-client/foreigner-non-resident/tax-residency/determining-residency | YES |

### Browser-grounded only (JS / Cloudflare gated — referee may HOLD) — 3 facts
These pages return a JS shell / Cloudflare challenge to `curl`, so the automated referee cannot
re-fetch them. Quotes were confirmed verbatim **in a rendered browser** against the live page and
`quote_verbatim_confirmed:true` reflects that manual confirmation. Flagged here so the applier can
re-ground them in a browser if the automated re-fetch fails.

| # | Pillar | Source URL | Gate | Quote confirmed |
|---|--------|-----------|------|-----------------|
| immigration_quota_point_one_percent | RESIDENCE | https://www.riigiteataja.ee/en/eli/517082021004/consolide/current | riigiteataja needs JS ("Ilma Javascript…") | YES (current in-force version, valid from 12.06.2026; Aliens Act §113(2)) |
| ict_startup_exempt_from_quota | RESIDENCE | https://www.riigiteataja.ee/en/eli/517082021004/consolide/current | riigiteataja needs JS | YES (Aliens Act §115(1) cl. 14 ICT + cl. 15 start-up) |
| personal_id_code_isikukood | IDENTITY | https://www.eesti.ee/en/doing-business/occupational-environment-and-personnel/recruitment-from-abroad/ | eesti.ee behind Cloudflare (window.__CF; identical 195 KB shells to curl) | YES (rendered browser) |

## Pillar distribution
EMPLOYMENT 6 · RESIDENCE 4 · IDENTITY 2 · HOUSING 1. (No HEALTHCARE/SOCIAL_SECURITY/TIMELINE —
no curl-verifiable official quote found within the named source set.)

## Sources that could NOT be used verbatim (dropped)
- **eesti.ee / work.eesti.ee state-portal article pages** — Cloudflare-gated to `curl` (JS SPA
  shell). Rich content (labour-market-test wording, residence-permit-card = obligatory domestic ID
  but not a travel document, family-doctor choice, driving-licence 12-month rule) was readable in a
  browser but is **not** referee-reproducible, so only `isikukood` was kept (browser-grounded) and
  the rest were dropped rather than shipped unverifiable.
- **riigiteataja.ee Aliens Act** — JS-gated; used only browser-grounded for the two quota facts,
  which are stated authoritatively nowhere curl-reachable.
- **Salary coefficient table (politsei)** — current euro figures exist (coefficient 1.0 ≈ €2,092
  from 05.03.2026) but sit in a multi-column HTML table; specific cell numbers are fragile for
  word-matching, so no euro amount was quoted. Only the "at least the average gross salary" wording
  was used.
- **sotsiaalkindlustusamet.ee** — homepage curls fine but no page in scope carried a non-obvious,
  third-country-specific, verbatim social-security fact; none written rather than invent one.

## Notes
- `needs_lawyer_review:false` on all — these are plain official statements of rule/process.
- Salary table shows the double-rate ("top specialist") coefficient was abolished for new
  applications as of 24.05.2022; not shipped as a standalone fact (historical/negative).
