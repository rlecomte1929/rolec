# Switzerland + Italy + Sweden destination facts (2026-08-31)

Three EEA destinations (coverage-master ranks 10/11/14, hubs Zurich/Milan/Stockholm), all greenfield.
Dual-audience (EEA free-mover + non-EEA), official-sourced. **10 requirement_items landed (pending):**
Switzerland 3, Italy 2, Sweden 5.

## Sources
CH: admin.ch (sem/bag) + fedlex.admin.ch (AIG/DBG/AHVG consolidated law). IT: normattiva.it (D.Lgs
30/2007, TU 286/1998, TUIR 917/1986) + agenziaentrate.gov.it + interno.gov.it. SE: migrationsverket.se,
skatteverket.se, forsakringskassan.se.

## Referee + honesty
verify_ledger confirmed **22/36 quotes verbatim**; 14 dropped to worklist (the JS-rendered German/Italian
consolidated-law pages parse differently than the browser capture — re-confirm before approval). 6 topics
were unmapped (pillar conflicts, e.g. multi-pillar tax/social-security topics) and stay staged as a
worklist. Honesty calls the research made: **Switzerland has NO 183-day tax rule** — recorded the real
30-day (with work) / 90-day trigger instead of a fabricated 183; the **Italy EEA-side SSN enrolment** had
no allowlisted verbatim and is a documented reject, not invented.

## Code
- `requirements_country_key.py`: `"IT":"ITALY"`, `"SE":"SWEDEN"` (+ test). CH already mapped.
- `backend/imports/otto/parsers.py`: allowlisted `normattiva.it` (IT law portal) + `migrationsverket.se`
  / `skatteverket.se` / `forsakringskassan.se` (Swedish agencies) — 8th too-narrow-allowlist instance.
- **EEA permit-gating fix:** these are the first EEA destinations promoted; one SE "right of residence"
  permission row mapped to `["OWN_NATIONAL","EU_EEA"]` and was re-scoped to `["EU_EEA"]` so a Swedish
  national never receives free-mover permission content. Scope guard exit 0.

Gate remaining (human): approve at `/admin/countries`; serving needs the IT/SE catalog + allowlist merged.
