# FR→SG requirement facts — Adrien (Paris → Singapore), 2026-08-30

First requirement-fact batch for the **FR→SG** corridor (Adrien Hardy, a French professional moving
to Singapore). Singapore has no free-movement scheme, so every foreigner is the **work-pass /
third-country** track: `applies_to.nationality="non-EEA"`, `status="professional"`, `corridor="FR->SG"`.

## Landed (7 requirements at `review_status='pending'`, all `corpus_grounded`)
Otto delivered **30** facts (all self-marked `quote_verbatim_confirmed`); `verify_ledger.py` re-fetched
every page and **confirmed 17**, rejecting 13 whose quote was not on the cited page. The 17 clean facts
promoted to 7 SINGAPORE requirements:

| topic | requirement |
|---|---|
| employment_pass | Employment Pass (EP) |
| compass_framework | COMPASS Framework |
| employment_pass_application | EP Application Process |
| singapore_entry_visa | Entry to Singapore — French Nationals |
| cpf_contributions | CPF — EP Holders Exempt |
| dependants_pass | Dependant's Pass |
| long_term_visit_pass | Long-Term Visit Pass (LTVP) |

All behind the `/admin/countries` gate. Promote was **scoped** (`promote(country='SG')` with the 8
pre-existing `SG-immig-2026-08-12` `ready` rows parked+restored); the 11 already-approved SINGAPORE
rows were untouched (no title collision).

## Code dependency
`backend/imports/otto/parsers.py` — added `gov.sg` to `_OFFICIAL_SUFFIXES` (covers mom/ica/iras/cpf).
The bare `gov` suffix does **not** match `mom.gov.sg` (host ends in `.sg`), so all 30 scored
UNOFFICIAL until this landed — the 4th too-narrow-allowlist instance. Regression test added in
`backend/tests/test_otto_fact_ingest.py`.

## Files
- `facts.ndjson` (30) — Otto delivery as received · `clean.ndjson` (17) — imported · `worklist.ndjson`
  (13) — quote-not-on-page, to re-source · `rejects.ndjson` (10) — Otto's own rejects · `manifest.json`.

## Known gaps (corridor NOT complete — send back to Otto / browser-ground)
- **4 topics at 0 facts:** tax_residence (IRAS is JS-rendered — the scraper sees nav-only HTML),
  fin_number, housing_rental, healthcare_ep (Otto flagged a policy ambiguity — employer "can choose"
  medical cover — needs a counsel check).
- **COMPASS C4–C6** confirmed to exist but not individually extracted (topic partially complete).
- **13 of 30 quotes** failed the ground-truth re-fetch — some are likely JS-rendered gov.sg pages the
  verifier can't read (candidates for browser-grounding, the pattern used for Denis's tax facts).
