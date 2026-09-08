# LU third-country-national relocation facts — 2026-08-31

**Corridor / destination:** Luxembourg (LU), hub Luxembourg City.
**Perspective:** third-country national (non-EEA) professional relocated by an employer.
**Scope rule applied:** only facts that would NOT also apply to an EU/EEA free mover.
EU-free-movement facts and nationality-neutral facts (generic 183-day tax residency, the
impatriate tax regime, generic CCSS affiliation) were deliberately excluded because they
apply to EU citizens too.

**Output:** `facts.ndjson` — 12 facts.

## Sources (official Luxembourg government only)

| # | Source URL | Verbatim confirmed? |
|---|---|---|
| 1 | https://guichet.public.lu/en/citoyens/immigration/plus-3-mois/ressortissant-tiers/salarie/salarie-pays-tiers.html (Conditions of residence for third-country salaried workers) — guichet.public.lu, last update 10.07.2023 | YES — 10 facts |
| 2 | https://guichet.public.lu/en/citoyens/immigration/plus-3-mois/ressortissant-tiers/hautement-qualifie/salarie-hautement-qualifie.html (EU Blue Card, highly qualified third-country workers) — guichet.public.lu, last update 03.03.2026 | YES — 2 facts (declaration-of-arrival + Blue Card threshold; chip-card wording identical on both pages) |

All 12 `evidence_quote` values were confirmed as verbatim substrings of the fetched
official page text (curl fetch, HTML main-content stripped, whitespace normalized to how
the page renders). Verification script re-ran against the final NDJSON: **12/12 confirmed, 0 failed.**

## Verification method

- Pages fetched directly via `curl` (HTTP 200) from guichet.public.lu.
- HTML `<main>` content stripped of tags; `evidence_quote` matched as an exact substring
  after collapsing runs of whitespace to single spaces.
- Every quote is < 200 chars. `quote_verbatim_confirmed: true` on all rows.

## Coverage

- **Pillars:** RESIDENCE ×4, EMPLOYMENT ×3, TIMELINE ×1, HOUSING ×1, HEALTHCARE ×1,
  SOCIAL_SECURITY ×1, IDENTITY ×1 (7 of 7 allowed pillars).
- **fact_type:** document ×3, eligibility ×2, deadline ×2, process ×2, obligation ×2, cost ×1.

Topics: temporary authorisation to stay (apply before entry; 90-day window), type D visa,
residence-permit deadline (3 months), declaration of arrival as interim work permit,
medical check for foreigners, ADEM labour-market test / certificate, first-permit
one-profession/one-sector restriction, EU Blue Card salary threshold (EUR 65,652), CCSS
affiliation certificate for renewal, biometric residence-permit card containing the work
permit, EUR 80 residence-permit fee.

## Unverifiable / excluded sources

None fetched failed. Sources considered but **not used** because their facts are not
third-country-specific (would also apply to an EU citizen), per the scope rule:

- `guichet.public.lu` impatriate tax regime page
  (…/hautement-qualifie/exoneration-hautement-qualifie.html) — fetched OK (HTTP 200), but
  the impatriate scheme (8-year duration, EUR 75,000 threshold, tax-residency requirement)
  applies to EU nationals recruited from abroad as well, so excluded.
- Generic tax residency (183 days / 6 months, impotsdirects.public.lu) and generic CCSS
  affiliation (ccss.lu) — nationality-neutral, excluded. (Social-security is covered only via
  the TCN-specific renewal requirement to produce a CCSS affiliation certificate.)

Note on the salary figure: the current guichet EU Blue Card page (last update 03.03.2026)
states EUR 65,652 as the Grand-Ducal threshold; an older Google-cached search summary
mentioned EUR 58,968 — the live page value (65,652) was used and quoted verbatim.
