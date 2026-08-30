# Andrea family-reunification facts — ES→IE, 2026-08-30

Requirement facts for how a Critical Skills Employment Permit (CSEP) holder's **family** joins her
in Ireland — Andrea's corridor (Spain→Ireland, third-country, spouse + two minor children).
Otto-sourced, browser-grounded, delivered as NDJSON to GCS.

## Audience
Every fact: `applies_to.nationality="non-EEA"`, `applies_to.status="professional"`, `corridor="ES->IE"`.

## Files
- `facts.ndjson` — 20 facts across **6 distinct requirement topics** (a first delivery put all 20
  under one topic; re-briefed to split so they land as granular requirements, matching the rest of
  the corridor).
- `manifest.json` — batch id + Otto's per-topic summary.

## What lands (20 facts → 6 requirements)
| entity_topic_key | facts | gist |
|---|---|---|
| `family_join_eligibility` | 2 | CSEP holder brings immediate family immediately (no 12-month hold); Category B sponsor |
| `spouse_work_permission` | 4 | spouse gets **Stamp 1G** — works with no employment permit |
| `dependant_children_permission` | 4 | children under 16 need no ISD registration; 16–18 must register |
| `join_family_d_visa` | 3 | Join Family "D" long-stay visa for visa-required family |
| `family_registration_irp` | 3 | IRP registration of family after arrival |
| `family_financial_requirements` | 4 | financial thresholds / policy conditions |

Hosts: enterprise.gov.ie, irishimmigration.ie (official), citizensinformation.ie (semi-official → 4
facts land `needs_review`). Verifier: 20 importable / 0 rejected.

## Landing
Staged in `otto_staging` then promoted to `public.requirement_items` at `review_status='pending'` —
never served until a human approves at `/admin/countries`. Import:
`scripts/import_otto_facts.py <batch> --apply --promote --expected 20`.
