# es-departure-2026-09-10 — ES departure requirement facts (A-P1)

**Corridor:** ES->IE (Madrid -> Dublin) · **Persona:** Andrea, Venezuelan third-country national, professional move.
**Target table:** public.requirement_items · **Nationality class:** THIRD_COUNTRY

## What this is
9 official-source departure requirement facts for someone leaving Spain for Ireland, across three topics:
- **baja del padron** (Madrid municipal de-registration) — madrid.es
- **Seguridad Social / A1 posted worker** (if kept on a Spanish contract) — seg-social.es
- **AEAT tax-exit / non-resident transition** (Modelo 030, Modelo 247, 183-day residence rule, Modelo 210 IRNR) — agenciatributaria.gob.es

## Files
- `es-departure-2026-09-10.ndjson` — one JSON requirement_item per line
- `manifest.json` — batch metadata incl. sha256 of the ndjson, record/non_obvious/needs_lawyer counts

## Provenance & status
- **Official hosts only** (madrid.es, seg-social.es, agenciatributaria.gob.es, *.gob.es). No blogs/law firms/vendors.
- Every `evidence_quote` is copied verbatim (>=25 chars) from the exact `source_url`.
- All records are **candidate-only**: `review_status=pending`, `verification_status=representative`, `quote_verbatim_confirmed=false`. Nothing is lawyer-confirmed.
- `needs_lawyer_review=true` only on legal/tax determinations (the 183-day / no-split residence conclusion). Procedural rules are not flagged.

## Honest gaps
- No EEA/non-EEA duplicate pairs were emitted; the subject is specifically the Venezuelan TCN mover. Three genuinely nationality-agnostic facts (Spanish 183-day residence, empadronamiento obligation, day-counts) could be duplicated with nationality "EEA" if strict universal pairing is required later.
