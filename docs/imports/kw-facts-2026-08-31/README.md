# Kuwait (KW) — non-obvious relocation facts

**Corridor:** third-country national (non-EEA) professional relocated by an employer to Kuwait (hub: Kuwait City)
**Generated:** 2026-08-31
**Output:** `facts.ndjson` — 12 facts, all with a verbatim official-source quote.

## Method

Every fact was **direct-fetched from a live official gov.kw page** (curl, browser User-Agent) and its
`evidence_quote` was programmatically confirmed to be an exact substring of the fetched page text
(whitespace-normalised). Quote length is capped at <200 chars (max used: 122). No fact was written
from a source that could not be reached; gaps were left rather than guessed.

All 12 facts come from the **Ministry of Interior (moi.gov.kw)** — the General Department of Residency
service/procedure pages (English) and the General Directorate of Traffic driving-licence page. These
pages are the authoritative MOI statements of the documents and conditions for each residence/visa
transaction.

## Sources used (all reachable, HTTP 200, verbatim confirmed = YES)

| # facts | Source URL | Verbatim confirmed |
|---|---|---|
| 1 | https://www.moi.gov.kw/main/eservices/residence/procedures/34?culture=en — Private Residence Article 18 (First Time) | YES |
| 2 | https://www.moi.gov.kw/main/eservices/residence/procedures/33?culture=en — Private Work Visa | YES |
| 3 | https://www.moi.gov.kw/main/eservices/residence/procedures/40?culture=en — Transfer of Sponsorship (Private Art. 18 → Family) | YES |
| 1 | https://www.moi.gov.kw/main/eservices/residence/procedures/115?culture=en — Absence abroad more than six months | YES |
| 1 | https://www.moi.gov.kw/main/eservices/residence/health-check-status?culture=en — Health Check Status | YES |
| 2 | https://www.moi.gov.kw/main/eServices/gdt/procedures/79?culture=en — Conditions to Obtain Driving License (Non-Kuwaitis) | YES |

(Counts sum to 10 distinct source pages carrying 12 facts; procedures/34 and procedures/40 each carry
multiple facts, procedures/33 carries two.)

## Pillar coverage

RESIDENCE 4 · EMPLOYMENT 2 · HEALTHCARE 2 · HOUSING 2 (driving) · IDENTITY 1 · TIMELINE 1.
No SOCIAL_SECURITY fact — see unreachable sources below.

## Sources that could NOT be reached (facts NOT written from them)

- **e.gov.kw** (Kuwait Government Online national portal — incl. the MOI Article 18 service page and the
  PACI Civil ID service pages): **HTTP 403 Forbidden** from an Azure Application Gateway on every attempt,
  including via a real headless browser. The portal is **IP/geo-gated to Kuwait**. Not used.
- **paci.gov.kw** (Public Authority for Civil Information — the canonical "Civil ID is mandatory for all
  residents" statement): `www.paci.gov.kw` **connection timed out**; `services.paci.gov.kw` returned a
  **302 → /error/405**. Geo/method-gated. Not used. The Civil ID fact in the dataset is therefore
  sourced from the MOI residency procedure that *requires* the original Civil ID card, not from PACI's
  own page.
- **manpower.gov.kw** (Public Authority of Manpower — incl. the English Private-Sector Labour Law No. 6
  of 2010 PDF at `/docs/LaborLaw/Labor_Law_Eng.pdf`): **connection timed out (HTTP 000)** on all hosts
  (`www`, `labour`, `mp`). Fully unreachable — likely geo-blocked. This is why there is **no
  SOCIAL_SECURITY / end-of-service-indemnity fact**; that content lives only in this unreachable PDF.
  Note: the Manpower/PAM work permit is still cited via the MOI page that requires it (procedures/33).
- **washington.mofa.gov.kw / canberra.mofa.gov.kw** (Kuwait embassy work-visa requirement pages):
  behind a **Cloudflare JavaScript challenge** ("Just a moment…"); could not be cleared reliably. Not used.
- **moi.gov.kw residency-rules PDF** (`/main/content/docs/residence/residency-rules-957.pdf` — Ministerial
  Decree No. 957/2019, the Executive Regulation of the Foreigners' Residence Law): downloaded OK (HTTP
  200), but it is **Arabic and the available PDF text extractor mangles the Arabic glyphs** (e.g. الصحي →
  اليحل), so no reliable verbatim substring could be taken from it. **Deliberately not quoted** to avoid a
  quote that would not match the real document. Its content (Article 18 etc.) is instead covered via the
  MOI English service pages.

## Notes for reviewer

- Wording quirks in quotes (e.g. "cleareance", "the General Authority for Manpower" vs "General Authority
  for Labor" vs "Ministry of Social Affairs and Labor" across pages) are **verbatim from the official MOI
  pages** — these are the same labour authority under names used inconsistently on the site. Not typos in
  this dataset.
- `needs_lawyer_review` is `false` on all facts (they are document/procedure/eligibility statements taken
  verbatim from the MOI). The 450 KD family-sponsorship salary threshold and the 2-year driving-licence
  rule (resolution 1729/2005 exemptions) are the two most change-prone items and worth periodic re-check.
