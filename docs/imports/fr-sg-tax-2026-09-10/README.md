# AD-TAX · Singapore income-tax requirement facts (FR->SG corridor)

**batch_id:** `fr-sg-tax-2026-09-10`
**corridor:** FR-SG (Paris -> Singapore) · **destination side (Singapore tax)**
**persona:** Adrien, French national, working in Singapore on an Employment Pass
**artifact:** `fr-sg-tax-2026-09-10.ndjson` · **records:** 6 · **sha256:** `dcd70297c8630bcd7617b51076b600bb50c2817a2f29d846f574f62bd1b1c7e9`

## Status (all records)
- review_status: `pending`
- verification_status: `representative`
- status: `draft` (candidate-only)
- platform_vetting_status: `pending`
- quote_verbatim_confirmed: `false` (every record — awaiting human/lawyer verification)

## Scope
Singapore-side (destination) individual income-tax obligations for an Employment Pass holder. Tax facts are mapped to the `EMPLOYMENT` pillar per loader convention. A French national is `non-EEA` (third-country) from Singapore's perspective — never null.

## Coverage (fact_key -> pillar -> flags)
| fact_key | type | non_obvious | lawyer |
|---|---|---|---|
| fr_sg_tax_residency_183_day_rule | eligibility | no | no |
| fr_sg_tax_non_resident_employment_rate | other | yes | no |
| fr_sg_tax_filing_deadline_18_april | deadline | no | no |
| fr_sg_tax_no_cpf_for_ep_holders | eligibility | yes | no |
| fr_sg_tax_clearance_ir21 | deadline | yes | no |
| fr_sg_tax_france_singapore_dta | eligibility | yes | **yes** |

non_obvious_count = 4 · needs_lawyer_review_count = 1

## Sources (official only)
- **iras.gov.sg** — Working out my tax residency; Individual Income Tax rates; Tax Season 2026 filing; Tax clearance for non-Singapore Citizen employees (IR21); List of DTAs
- **mom.gov.sg** — Who is entitled to CPF contributions

## Key judgement calls
- **Non-resident rate** stated as the higher of flat 15% or progressive resident rates (IRAS), not a simple "15% for foreigners" — flagged non_obvious.
- **No CPF for EP holders:** sourced positively to the MOM CPF-eligibility page ("payable for Singapore citizens (SCs) and Singapore permanent residents (SPRs)"), which is the explicit official statement; EP holders are foreigners and therefore excluded. (CPFB corroborates that CPF is exempted for foreign employees, but cpf.gov.sg is outside the AD-TAX whitelist so it is cited only in the note.)
- **France-Singapore DTA:** a DTA exists (revised DTA in force 2016; modified by the MLI, ratified 19 Jul 2021). Because whether Adrien can claim relief is residency- and article-specific, the fact is sourced to the IRAS List of DTAs and flagged `needs_lawyer_review: true`. **No specific relief position was invented.**

## Source access issues (honest log)
- **IRAS is JavaScript-rendered.** Both the platform scraper (`web_fetch`) and the AI fetch tool (`WebFetch`) returned only navigation chrome for the individual-income-tax-rates, working-out-my-tax-residency, non-residents and IR21 pages. Verbatim quotes were captured from official-domain (iras.gov.sg) search excerpts of those same pages and **must be re-confirmed against the live IRAS pages** before operational use. Every record carries `quote_verbatim_confirmed: false`.
- **MOM CPF page scraped cleanly** — the CPF-eligibility quote is verbatim from the live mom.gov.sg page.
- **No fee, rate, deadline or treaty position was invented.**

## Loader notes
- destination_country = `SG` for every record.
- nationality = `non-EEA` (French national is third-country from Singapore's perspective), never null.
- Tax obligations mapped to the `EMPLOYMENT` pillar per loader convention.
