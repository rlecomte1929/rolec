# Iceland (IS) — non-obvious relocation facts for a third-country-national professional

**Corridor:** `* → IS` (hub: Reykjavik) · **Nationality perspective:** `non-EEA` · **Status:** `professional`
**Generated:** 2026-08-31 · **Facts:** 13 · **Confidence:** all `high`

Scope: facts that apply to a **third-country (non-EEA/EFTA) national** relocated by an employer.
Facts that also apply to an EU/EEA citizen were excluded (see "Deliberate omissions").

## Verification method (matches the applier's `confirm_quotes.py`)

Each `source_url` was fetched fresh as **rendered HTML** (`curl`, HTTP 200, no WAF block on
`island.is` / `skatturinn.is`) **and** cross-read in-browser. Every `evidence_quote` was then
re-checked against the fetched HTML with the same normalisation the referee uses — HTML entities
decoded, tags stripped, whitespace collapsed — and confirmed as a verbatim substring.
**Result: 13/13 quotes reproduced (0 misses).** No PDFs were cited (all quotes are on rendered
HTML pages). `island.is` serves body copy as server-rendered Contentful rich-text embedded in the
HTML, so quotes must sit inside a single text node — quotes were chosen accordingly.

## Sources (all official `.is`, English pages) — verbatim confirmed?

| # | Pillar | Source URL | Verbatim? |
|---|--------|-----------|-----------|
| 1 | EMPLOYMENT | island.is/en/o/directorate-of-immigration/news/new-residence-and-work-permit-rules-take-effect | yes |
| 2 | EMPLOYMENT | island.is/en/permit-based-on-work/rights | yes |
| 3 | EMPLOYMENT | island.is/en/permit-based-on-work/rights | yes |
| 4 | EMPLOYMENT | island.is/en/apply-for-a-work-permit/expert-knowledge | yes |
| 5 | EMPLOYMENT | island.is/en/permit-based-on-work/requirements | yes |
| 6 | RESIDENCE | island.is/en/permit-based-on-work | yes |
| 7 | RESIDENCE | island.is/en/permit-based-on-work/requirements | yes |
| 8 | RESIDENCE | island.is/en/permit-based-on-work/rights | yes |
| 9 | HEALTHCARE | island.is/en/permit-based-on-work/requirements | yes |
| 10 | HEALTHCARE | island.is/en/apply-for-health-insurance | yes |
| 11 | IDENTITY | island.is/en/permit-based-on-work/permit-granted | yes |
| 12 | HOUSING | island.is/en/legal-domicile-immigrant | yes |
| 13 | TIMELINE | island.is/en/permit-based-on-work/permit-granted | yes |

Issuing bodies behind these pages: **Directorate of Immigration (Útlendingastofnun, utl.is)**,
**Directorate of Labour (Vinnumálastofnun)**, **Iceland Health (Sjúkratryggingar)**,
**Registers Iceland (Þjóðskrá)**. All now publish through the `island.is` state portal.

## Pillar distribution

EMPLOYMENT 5 · RESIDENCE 3 · HEALTHCARE 2 · IDENTITY 1 · HOUSING 1 · TIMELINE 1 (SOCIAL_SECURITY: none)

## Key non-obvious findings

- **Authority moved (8 July 2026):** work-permit applications are now processed by the
  **Directorate of Immigration**, not the Directorate of Labour — a live change that inverts the
  common "apply to Vinnumálastofnun" belief.
- **Two permits, and no work before both:** a work permit *and* a residence permit are required,
  and the person may not start working before both are granted.
- **Employer/role-tied:** the permit is valid only for the specific employer; changing jobs needs
  a new permit from the new employer.
- **Expert-knowledge vs shortage-of-labour** stay rules differ: expert-knowledge applicants may be
  in Iceland during processing; shortage-of-labour visa nationals may not.
- **Kennitala / domicile chicken-and-egg:** a non-EEA national needs a residence permit *and* a
  kennitala before a legal domicile can be registered; the kennitala itself is only allocated after
  the residence permit is issued.
- **Health cover gap:** private insurance (min ISK 2,000,000) is required for the permit, and
  national health insurance only begins ~3 months after domicile registration.

## Notes / caveats

- **Info pages in flux:** the 8 July 2026 amendments consolidated the *Residence permits based on
  work* and *Apply for a work permit* pages; the news source states these "will be consolidated and
  updated over the coming weeks." URLs were re-fetched 2026-08-31 and were live then; re-confirm at
  serve time.
- **`utl.is` and `vinnumalastofnun.is` now redirect** to `island.is`; several legacy English URLs
  (e.g. `/en/general-info-on-work-permits`) 404. Cited URLs are the current live equivalents.

## Deliberate omissions (not third-country-specific)

- **Tax residency (183 days / 6 months → unlimited liability, skatturinn.is):** verified live and
  quotable, but the residence-based threshold applies **identically to EEA citizens**, so it was
  excluded under the "only facts not also applicable to an EU/EEA citizen" rule. Source on file:
  `skatturinn.is/english/individuals/general-information/` — "If you stay in Iceland for less than
  six months in a twelve month period, your tax liability is limited."
- **SOCIAL_SECURITY:** no clean third-country-specific, verbatim-quotable fact found; residence-based
  social-insurance entitlement also applies to EEA nationals. Omitted rather than pad.

## Unverifiable / dead sources encountered

- `island.is/en/general-info-on-work-permits` → 404 (content moved post-8-July-2026).
- `island.is/en/moving-to-iceland-insurance/foreign-employees-in-iceland` → 404 (Iceland Health
  content reached via `apply-for-health-insurance` instead).
- `vinnumalastofnun.is/en/employer/work-permits` → redirects to `island.is` and 404s.
