# ZA facts — third-country-national professional relocated to South Africa (hub: Johannesburg)

**Batch:** `za-facts-2026-08-31`
**Perspective:** nationality = `non-EEA`, status = `professional`, corridor = `ZA`
**Facts:** 13, all `confidence: high`, all `quote_verbatim_confirmed: true`, all `needs_lawyer_review: false`
**Sourcing rule:** official South African government (gov.za) only — DHA + SARS. No blogs/relocation-firm/news.

## Verification method

Each `evidence_quote` was confirmed to be a verbatim substring (<200 chars) of the fetched
official text. DHA PDFs were downloaded with `curl` and their text extracted with `pypdf`;
the SARS page was downloaded and stripped to text. Matching was whitespace-insensitive and
punctuation-normalised (straight vs. curly quotes, en-dash vs. hyphen) to absorb PDF/HTML
extraction artefacts only — wording is unchanged. All 13 passed both the substring check and
the <200-char length check (`gen.py`).

## Sources (all confirmed verbatim, all HTTP 200)

| # facts | Source | URL | Confirmed |
|---|---|---|---|
| 3 | DHA — Points-Based System government notice (Minister, dated 18 Oct 2024) | https://www.dha.gov.za/images/notices/october24/Notice_Points-Based_Criteria.pdf | yes |
| 1 | DHA — Critical Skills Work Visa requirements checklist (s.19(4), eff. 9 Oct 2024) | https://www.dha.gov.za/images/notices/8october24/Critical_Skills_work_Visa_requirements_-_8_Oct_2024.pdf | yes |
| 3 | DHA — General Work Visa requirements checklist (s.19(2), eff. 9 Oct 2024) | https://www.dha.gov.za/images/notices/8october24/General_Work_Visa_requirements_-_8_Oct_2028.pdf | yes |
| 3 | DHA — Immigration Regulations, 2014 (updated 2018), reg. 18 (work visa) | https://www.dha.gov.za/images/PDFs/ImmigrationRegulations2014-Updated2018-compressed.pdf | yes |
| 3 | SARS — Tax and Non-Residents (residency tests) | https://www.sars.gov.za/individuals/tax-during-all-life-stages-and-events/tax-and-non-residents/ | yes |

> Note on the General Work Visa filename: the official file is literally named
> `..._8_Oct_2028.pdf` (a typo on the DHA site); the document header reads "Effective 9 October 2024".

## Topics covered (all `non_obvious: true`)

- **Points-based work visa (since 18 Oct 2024)** — must earn **100 points**; the route (critical
  skills vs. general work visa) is decided by *how* the points are earned; an offer of employment
  is **mandatory** and salary is scored (top band above **R976,194** gross p.a. = 50 points).
- **Critical Skills Work Visa** — occupation must be on the *latest* Critical Skills List; SAQA
  foreign-qualification evaluation required.
- **General Work Visa** — SAQA evaluation; visa is **employer/role-tied** (employer must notify the
  Director-General on exit or role change); extension must be lodged **in person, ≥60 days** before
  expiry.
- **Intra-Company Transfer visa** — capped at **4 years, not renewable**; holder confined to the
  **specific position**; requires **≥6 months' prior employment** with the company abroad.
- **SARS tax residency** — two tests (ordinarily-resident **or** physical-presence); the physical
  presence **day-count thresholds** (91 / 91-each / 915 days); the ordinarily-resident meaning
  ("naturally and as a matter of course return").

## Pillars used

`EMPLOYMENT` (7), `RESIDENCE` (5), `TIMELINE` (1). None used `IMMIGRATION`, `TAX`, or `FAMILY`
(disallowed). No `HEALTHCARE / HOUSING / IDENTITY / SOCIAL_SECURITY` facts in this batch — the
requested non-obvious topics were work-visa- and tax-centric.

## Important regime note (not fabricated into a fact)

The Immigration Regulations, 2014 PDF (updated 2018) still shows reg. 18(3)(a) requiring a
**Department of Labour certificate** (labour-market test) for the *general* work visa. That older
requirement has been **superseded** by the Points-Based System government notice (18 Oct 2024) and
the Oct 2024 requirements checklists, which do **not** list a labour certificate. Facts here
reflect the **current (Oct 2024) points-based regime**; the labour-market-test premise is retained
only as historical context, not asserted as a current fact.

## Unverifiable / dropped

- **ICT "does not lead to permanent residence" and "no labour-market test"** — true in practice but
  expressed in the regulations by *absence* (the ICT requirement list simply omits a labour
  certificate; the 4-year non-renewable cap is what is quotable). No verbatim sentence states these
  negatives, so they were folded into the ICT facts' `non_obvious_note` rather than asserted with a
  quote.
- **UIF / social-security (labour.gov.za)** — no `SOCIAL_SECURITY` fact was added; no clean,
  unambiguous verbatim quote for a foreign-national UIF rule was located within scope. Left out
  rather than sourced weakly.
- **SARS tax number registration** — omitted to avoid over-reach; the residency facts are the
  higher-value, cleanly-quotable tax items.
