# HU third-country-national relocation facts — 2026-08-31

**Corridor / destination:** Hungary (HU), hub Budapest
**Perspective:** third-country national ("non-EEA") professional relocated by an employer
**Scope:** ONLY third-country facts (not EU free-movement). Every fact is one a third-country
national faces that an EU/EEA citizen relocating to Hungary does **not**.

**Count:** 12 facts (`facts.ndjson`), all `confidence: high`, all `non_obvious: true`,
`needs_lawyer_review: false`.

## Pillar / type distribution
- Pillars: RESIDENCE 6, EMPLOYMENT 3, IDENTITY 1, HOUSING 1, TIMELINE 1
- Types: eligibility 3, obligation 2, process 2, document 2, deadline 2, cost 1

## Sources — all OFFICIAL Hungarian government (verbatim confirmed = YES for every fact)

| Source page | Official body | URL | Facts drawn |
|---|---|---|---|
| Residence permit for guest workers | NDGAP (OIF) | https://oif.gov.hu/factsheets/residence-permit-for-guest-workers | 1 |
| Residence permit for the purpose of employment | NDGAP (OIF) | https://oif.gov.hu/factsheets/residence-permit-for-the-purpose-of-employment | 2 |
| Residence permit for Hungarian Card | NDGAP (OIF) | https://oif.gov.hu/factsheets/residence-permit-for-hungarian-card | 3 |
| EU Blue Card | NDGAP (OIF) | https://oif.gov.hu/factsheets/eu-blue-card | 3 |
| Single application procedure | NDGAP (OIF) | https://oif.gov.hu/factsheets/single-application-procedure | 1 |
| Information for employers and host organisations | NDGAP (OIF) | https://oif.gov.hu/factsheets/information-for-employers-and-host-organizations | 1 |
| General information for foreign citizens (tax) | NAV | https://nav.gov.hu/en/taxation/taxpayer_registration/general-information-for-foreign-citizens-new | 1 |

NDGAP = National Directorate-General for Aliens Policing (Országos Idegenrendészeti
Főigazgatóság). OIF factsheet pages last edited 2026-03 per their own footers.

## Verification method
- Every source page fetched directly via `curl` (HTTP 200; the OIF/NAV sites 403 urllib but
  serve curl with a browser UA). HTML stripped to visible text.
- Each `evidence_quote` confirmed as a verbatim substring of the fetched official text after
  collapsing whitespace/newlines and inline-bold-tag spacing to the page's reading order.
  Curly quotes normalised to straight. All quotes are < 200 chars.
- Validation script result: **12 lines, 0 failures** (valid JSON, quote match, pillar in the
  allowed 7, fact_type valid, nationality `non-EEA`, all `applies_to` keys present).

## Non-obvious highlights
- **Guest Worker permit is a dead end for professionals:** per Govt Decree 450/2024 (23 Dec 2024)
  there are currently *no* third countries whose nationals may be employed under it — must use
  Hungarian Card / EU Blue Card / employment permit.
- **The plain employment permit bars family reunification** and cannot be switched to another
  purpose from inside Hungary — a hard fork versus the Blue Card / Hungarian Card.
- **Three distinct validity terms:** employment permit max 3 yrs total; Hungarian Card 3+3;
  EU Blue Card 4+4.
- **Employer/position-tied:** single permit names the specific employer; any employer/job change
  needs a fresh (extension) application even for long-tenured Blue Card holders.
- **Sequence traps:** apply at a Hungarian consulate abroad first → collect on a single-entry
  type D visa (30-day stay / 3-month validity) → enter within 3 months of approval or the permit
  lapses → register accommodation within 3 days of entry (Enter Hungary) → obtain a tax ID from
  NAV via form T34 before first payroll.

## Unverifiable / dropped
- **SOCIAL_SECURITY (TB / TAJ):** no fact included. The clean third-country-specific angle (a TAJ
  card requires a valid residence permit + Hungarian address) is best documented by NEAK
  (neak.gov.hu), which is outside the requested official-domain allowlist. Generic contribution
  facts (18.5% employee / 13% employer) apply equally to EU citizens and were excluded per the
  "not also applicable to an EU citizen" rule.
- **HEALTHCARE:** the permit pages' "proof of comprehensive health insurance" requirement is
  third-country-specific but was judged less non-obvious than the 12 selected; a verbatim quote
  exists (`residence-permit-for-the-purpose-of-employment`) if a HEALTHCARE fact is wanted later.
- **2026 EU Blue Card threshold** (HUF 1,001,048) is stated on the Blue Card page but not issued
  here as a separate fact; only the current (2025) HUF 883,671 figure is included, tightly quoted.
