# Oman (OM) — non-obvious relocation facts (2026-08-31)

Corridor: third-country-national (non-EEA) **professional** relocated by employer to **Oman** (hub: Muscat).
Perspective nationality: `non-EEA`. Pillars restricted to the 7 allowed (no IMMIGRATION/TAX/FAMILY).

Output: `facts.ndjson` — **10 facts**, all `confidence:high`, `non_obvious:true`, `needs_lawyer_review:false`,
`quote_verbatim_confirmed:true`.

## Pillar / topic coverage
| # | pillar | topic | fact_key |
|---|--------|-------|----------|
| 1 | RESIDENCE  | employer-sponsored work visa (tied to employer) | OM:work_visa:employer_sponsored |
| 2 | EMPLOYMENT | prior Ministry of Manpower labour permit / clearance | OM:labour_clearance:permit_required_before_visa |
| 3 | RESIDENCE  | sponsor must be a local entity | OM:work_visa:local_sponsor_required |
| 4 | EMPLOYMENT | visa occupation must match labour permit (role-tied) | OM:work_visa:occupation_matches_permit |
| 5 | RESIDENCE  | minimum age 21 | OM:work_visa:min_age_21 |
| 6 | HEALTHCARE | medical certificate for listed nationalities (MoH attested) | OM:medical:certificate_listed_countries |
| 7 | RESIDENCE  | release letter to re-enter within 2 years of last departure | OM:work_visa:reentry_release_within_two_years |
| 8 | EMPLOYMENT | transfer of sponsorship = release letter (the historical "NOC") | OM:labour_clearance:transfer_release_letter |
| 9 | RESIDENCE  | work visa valid 2 years, multi-entry | OM:work_visa:validity_two_years |
| 10| IDENTITY   | residence (resident) card mandatory | OM:identity:residence_card_mandatory |

## Sources — all official gov.om, verbatim confirmed
| source_url | facts | verbatim confirmed? | how grounded |
|---|---|---|---|
| https://www.rop.gov.om/english/Visas.aspx (Royal Oman Police — Work Visa) | 1–9 | YES | Live browser DOM extraction of the accordion panels (Description / Requirements / Documents / Exceptional Documents). Each `evidence_quote` is a verbatim contiguous substring of the panel `innerText`. |
| https://gov.om/en/w/get-residence-cards (Gov.om e-services — Get Residence Cards; issued by Royal Oman Police, page "Updated: August 05, 2025") | 10 | YES | Live browser `innerText` search returned the exact sentence; also independently returned identically by WebFetch and by the search snippet. |

Notes on the ROP page: it is an ASP.NET page (`Visas.aspx`) that redirects to `rop.gov.om` and renders visa-type content in collapsible panels; the citable canonical URL is retained as `https://www.rop.gov.om/english/Visas.aspx`. The page's own wording says **"Ministry of Manpower"**; that ministry's functions now sit under the **Ministry of Labour** (2020 merger) — quoted verbatim, clarified in `fact_text`/`non_obvious_note`.

## Sources checked but NOT used (could not verify verbatim, or out of scope)
- **Personal income tax** (`taxoman.gov.om` / `tms.taxoman.gov.om` / `gov.om/en/tax-authority`): **SKIPPED.**
  Two reasons: (a) the requested "no personal income tax" wording is **not stated verbatim** on the official
  gov.om Tax Authority page (it lists Corporate Income Tax, VAT, Excise, TRC, exemptions — no personal-income
  statement), and `taxoman.gov.om/portal/personal-income-tax-faqs` returned HTTP 404 via WebFetch (JS/portal
  gated); (b) a tax fact does not map to any of the 7 allowed pillars. Note also that Oman has now **enacted a
  Personal Income Tax Law effective 1 Jan 2028** (5% above OMR 42,000), so a flat "no income tax" claim is
  becoming time-limited regardless. No tax fact was fabricated.
- **Family Joining Visa** (dependent/family sponsorship, e.g. salary threshold): **SKIPPED.** Content is behind
  the ROP page's visa-type dropdown (ASP.NET postback) and could not be reliably captured — the shared browser
  tab was repeatedly hijacked/navigated to unrelated sites (hasil.gov.my, lmra.gov.bh, bnm.gov.my, esd.imi.gov.my)
  by parallel processes mid-interaction. Not guessed.
- **30-day deadline to obtain the residence card after entry:** appears in third-party guides but was **not**
  found verbatim on the grounded gov.om residence-card page, so it was **not** included.
- **Renewal delay fine / visa fee** ("A fine of 50 per month…", "Twenty (20)"): present verbatim on the ROP page
  but **omitted** — the currency unit is not stated on the page, and asserting OMR would add an unverified detail.

## Method
Direct browser grounding (Claude Browser: `navigate` + DOM `innerText` / `querySelectorAll('.collapse')`) plus
WebFetch cross-check. Every `evidence_quote` confirmed as a verbatim substring of the fetched official text.
No numbers, fees, or citations were invented; any field the source did not carry was left out rather than filled.
