# ie-es-return-2026-09-10 — IE->ES/VE return requirement facts (A-P10)

**Corridor:** IE->ES (reverse / repatriation, optional VE leg) · **Persona:** Venezuelan third-country national.
**Target table:** public.requirement_items · **Nationality class:** THIRD_COUNTRY

## What this is
9 highest-value return/repatriation facts:
- **HOST-EXIT (Ireland):** Revenue leaving-Ireland admin + employment cessation, split-year treatment, 183/280-day residence + 3-year ordinary residence, PPSN retention — revenue.ie, citizensinformation.ie
- **HOME RE-ENTRY (Spain):** empadronamiento (obligation + TCN docs), NUSS / Social Security re-affiliation, re-establishing tax residence — madrid.es, seg-social.gob.es, agenciatributaria.gob.es
- **VENEZUELA:** consular registry as census/duty + precondition for consular procedures — gob.ve

## Files
- `ie-es-return-2026-09-10.ndjson` — one JSON requirement_item per line
- `manifest.json` — batch metadata incl. sha256 of the ndjson and counts

## Provenance & status
- `fact_key` prefix `ie_es_ret_` (stable, distinct from outbound ES->IE keys).
- `destination_country` is per-record: **IE** host-exit, **ES** home-re-entry, **VE** Venezuela.
- Official hosts only; every `evidence_quote` verbatim (>=25 chars) from its `source_url`.
- Candidate-only: `review_status=pending`, `verification_status=representative`, `quote_verbatim_confirmed=false`.
- `needs_lawyer_review=true` on treaty tie-breaker / dual-residence determinations.

## Honest gaps
- **Irish immigration-permission wind-down on departure** (surrender/hand-back of the IRP card, or fate of an employment-permit Stamp on leaving) could NOT be sourced: no official irishimmigration.ie page states a de-registration/surrender obligation on exit. Omitted rather than cite a non-matching page — this is the one host-exit immigration topic left open.
- The VE consular record is **medium confidence**: the verbatim jurisdiction clause names the Barcelona consulate (Cataluna/Aragon/Baleares/Valencia), NOT Madrid. The census/duty rule and "required for any consular procedure" rule are the same official framework; a Madrid mover registers at the consulate competent for Madrid. Fee = gratuito is stated on the fetched page.
