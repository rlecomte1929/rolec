# Pending-backlog conversion queue — 2026-09-11

**Goal it serves:** a shippable demo of the first use cases (Andrea ES→IE, Denis NO→FR,
Adrien FR→SG, Abraham US→EC). The bottleneck to demo-completeness is **not** Otto research —
Otto has already delivered these facts, they passed the gate, and they sit as
`review_status='pending'` candidates. The bottleneck is **conversion**: nobody has worked the
review gate. This document triages every pending row so approval is an *informed batch*, not a
blind bulk flip.

> **Why not just run a bulk `UPDATE ... review_status='approved'`?** Because that is the exact
> AIQ-2046 incident (`backend/app/services/lawyer_review_gate.py` header): 9 rows approved "at an
> identical microsecond, so no human read them", 4 of which needed counsel. The lawyer gate exists
> to stop that. Every row below is verified, but *approval itself* must go through the human review
> surface, per corridor.

## Scope

161 `pending` rows in `public.requirement_items` for the seven demo-relevant destination countries
(IRELAND, FRANCE, NORWAY, SPAIN, SINGAPORE, ECUADOR, UNITED STATES), as of 2026-09-11.

## How a pending row becomes served (the two conversion paths)

| Path | When | Action |
|---|---|---|
| **Admin approve** | Row is **not** `needs_lawyer_review` (or is already `attested`) | Admin CMS → **Countries → [Country] → Requirements** → approve. Endpoint: `POST /api/admin/countries/{country_code}/requirements/{id}/review` `{status:"approved"}`. Each row renders with its evidence; approve per informed batch. |
| **Counsel attestation** | Row carries `needs_lawyer_review:true` and `attestation_status != 'attested'` | `admin.py` **blocks** approval (422) until counsel signs. Admin → **Attestations** → create a corridor request → counsel reviews via tokenised link → signs → `attestation_status='attested'` → then approve. |
| **Hold** | Wrong direction / representative-tier scaffold / duplicate | Do **not** approve. Reasons per row below. |

The gate predicate (reproduced from `lawyer_review_gate.blocks_approval`):
`carries_lawyer_review_flag(citations_json, applies_to_nationality_classes_json) AND attestation_status != 'attested'`.

## Summary

| Corridor (country) | Persona / role | Served now | **Approve-ready** | Counsel | Hold | Served after approve |
|---|---|---:|---:|---:|---:|---:|
| ECUADOR | Abraham — destination (arrival) | 6 | **23** | 0 | 0 | **29** |
| SINGAPORE | Adrien — destination (arrival) | 19 | **18** | 0 | 2 | **37** |
| FRANCE | Denis — destination (arrival) | 37 | **25** | 2 | 0 | **62** |
| NORWAY | Denis — **return leg** (FR→NO) | 13 | **30** | 0 | 0 | **43** |
| IRELAND | EU-mover arrival tax/social layer | 219 | **30** | 0 | 0 | **249** |
| SPAIN | Andrea — origin (departure) | 0 | 0 | 2 | 23 | 0 |
| UNITED STATES | Abraham — origin (departure) | 6 | 0 | 0 | 6 | 6 |
| **Total** | | | **126** | **4** | **31** | |

### Persona-benefit precision (read before claiming "this completes Andrea")

- **Biggest direct wins:** Ecuador (Abraham 6→29), Singapore (Adrien 19→37), France (Denis 37→62).
  These are destination-arrival facts correctly nationality-scoped to each persona.
- **Norway (30):** these are *French-national-into-Norway* (FR→NO) facts — Denis's **return leg**,
  not his outbound NO→FR. Approving them completes his round-trip, not his primary journey.
- **Ireland (30):** EU/EEA-worker arrival tax/PRSI facts (e.g. "As a Spanish (EU) citizen…").
  They enrich the ES→IE corridor for an **EU mover**. Andrea is Venezuelan (third-country, CSEP);
  nationality gating means she is served by her **already-approved 219**, so these 30 largely do
  not surface on *her* journey. Approve for corridor completeness, not for Andrea specifically.
- **Spain (Andrea's departure):** the 25 pending rows are all `ES:IE-ES:*` — Spain-**as-destination**
  (arrival) content, `representative` tier. They do **not** serve Andrea's Spain-**exit**. Her
  departure phase needs the Otto `es-ie-departure` batch (genuine `ES:ES-IE:*` exit rows), still
  outstanding. **Hold.**
- **USA (Abraham's departure):** 6 rows, all `representative`, with duplicates of already-approved
  rows. Hold pending a real US-exit batch.

## Counsel-required (4) — route to attestation, do NOT admin-approve

Verified genuine cross-border legal/tax determinations; the flag is correct.

| id | country | pillar | why |
|---|---|---|---|
| `5ee81624-a21e-5cf7-900e-3d3a70447420` | FRANCE | EMPLOYMENT | FR-NO treaty Art. 15 allocation of Norwegian employment income during transition |
| `a3a69a5a-a09e-5f4b-9043-06e195e76d40` | FRANCE | EMPLOYMENT | Whether Norway source-taxes Denis's employment income for work done in France |
| `ES:IE-ES:tax_residency_183_days` | SPAIN | EMPLOYMENT | Spanish tax residency (183-day / centre-of-economic-interests) determination |
| `ES:IE-ES:tax_ie_es_double_taxation` | SPAIN | EMPLOYMENT | IE-ES double-taxation convention tie-breaker |

> The 2 Spain counsel rows are also wrong-direction (`IE-ES`); they only matter if IE→ES becomes a
> served corridor. For the current four demos they can stay pending.

## Hold (31) — do NOT approve

**Spain (23)** — all `ES:IE-ES:*`, arrival-framed, `representative` tier. Wrong direction for
Andrea's departure. IDs: `tax_beckham_regime`, `tax_modelo_030_alta`, `healthcare_ehic_transition`,
`healthcare_sns_tsi`, `healthcare_tsi_requirements`, `housing_fianza_deposit`,
`housing_fianza_regional_deposit`, `housing_nie_needed_to_rent`, `driving_dgt_registration`,
`driving_eu_licence_valid`, `registration_nie_number`, `empadronamiento_dependency_chain`,
`empadronamiento_documents`, `empadronamiento_padron_municipal`, `registration_certificado_registro_ue`,
`registration_cita_previa_bottleneck`, `registration_economic_means_proof`, `registration_ex18_form_fee`,
`registration_tie_only_for_non_eu`, `social_security_a1_posted_worker`, `social_security_employer_alta`,
`social_security_nuss_afiliacion`, `social_security_single_state_rule` (all prefixed `ES:IE-ES:`).

**United States (6)** — `representative`, US-origin, with duplicates:
- `05f267da-f763-468f-be37-40f8b60aecb2` (Employment letter) — dupe of an approved row
- `bdfa3247-3570-4681-972d-a0a8b0df675a` (Minimum lead time) — dupe of an approved row
- `48682196-4ee6-5349-ac1a-5cfaeb689c58` (Long-term lease agreement) — internal dupe
- `9455ae2c-7e68-59b7-9bdf-08f6b3b22b8e` (State residency registration) — internal dupe
- `14f8bfd7-b7fc-512a-a906-57ed92a9f832` (Long-term lease agreement) — representative scaffold
- `1582245b-0f52-5554-8e60-426c01c63aeb` (State residency registration) — representative scaffold

**Singapore (2)** — duplicates:
- `f179d500-fd03-493b-ba4b-d5e4d35377da` (Minimum lead time) — dupe of an approved row
- `e01ea767-1656-5c04-b3fe-ecaf993e2a29` (Tenancy agreement (12-month+)) — internal dupe (the
  other copy `2bd170a3-e7c3-516b-ba55-caa56056cc01` is in the approve-ready set)

## Approve-ready (126)

Defined as: every `pending` row in ECUADOR, SINGAPORE, FRANCE, NORWAY, IRELAND that is **not** in
the Counsel or Hold lists above. All are unflagged, cited, and (on sample) correctly
nationality-scoped. Regenerate the exact list — with verdicts — by running
[`manifest.sql`](./manifest.sql) against the DB (read-only).

**Eyeball before approving (low-tier scaffolds inside approve-ready):** a handful of Norway
`representative` rows (`NO immigration registration`, `NO immigration work authorization`,
`NO social security offshore`, `Long-term housing contract`) and one Singapore `Tenancy agreement
(12-month+)` are thin placeholder-style rows rather than corpus-grounded facts. They are correct
but generic; approve if you want them served, or leave pending.

## Recommended order (fastest demo lift first)

1. **Ecuador 23** → Abraham arrival goes 6→29. Biggest single jump; clean corpus-grounded set.
2. **Singapore 18** → Adrien 19→37. Skip the 2 dupes.
3. **France 25** → Denis 37→62. Then open **one** attestation request for the 2 FR counsel rows.
4. **Norway 30** → completes Denis's return leg.
5. **Ireland 30** → corridor completeness for EU movers (optional for the Andrea demo itself).
6. **Spain / USA** → leave held; unblock via the outstanding Otto departure batches.

Nothing here is approved by automation. Each corridor is approved by a human through the Admin CMS
review surface, using this document as the pre-verified basis.
