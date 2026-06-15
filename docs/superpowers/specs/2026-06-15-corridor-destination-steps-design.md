# Destination-specific roadmap step overrides — design

**Date:** 2026-06-15
**Branch:** `feat/corridor-destination-steps`
**Builds on:** the service→roadmap bridge (#762, merged) and its generic per-service
step library. Independent of the RFQ-button PR (#768) — both touch
`service_roadmap_steps.py` in different regions, so whichever merges second rebases.

## Why

The bridge materialises generic per-service roadmap steps (housing, schools, banking,
…) that are identical for every case regardless of where the employee is moving. The
steps that genuinely differ are **destination-driven** — e.g. opening a German bank
account needs an *Anmeldung* (address registration) first; pet import rules are set by
the destination country. This adds **destination-specific step overrides** so those
services reflect the destination.

## Established facts (recon 2026-06-15)
- **Immigration is already corridor-tailored** by the AI roadmap generator (retrieves
  `immigration_corpus_chunks` by corridor → `case_milestones` `source='ai'`). So this
  feature **excludes immigration** to avoid duplication.
- The generic library `service_roadmap_steps.py` is a flat `service_key → [ServiceStep]`
  with no corridor/destination dimension; `reconcile_service_milestones`
  (`service_roadmap_bridge.py`) has no access to the case's destination today.
- A corridor registry + pathway step-graphs exist (`corridor_registry.py`,
  `corridors/<ID>/`), but hold retrieval/SLA config / immigration pathways — not
  per-service roadmap steps. Not used here.

## Decisions (approved 2026-06-15)
- **Destination dimension** (ISO2 of the destination country), not full origin→dest
  corridor — that's what drives non-immigration steps.
- **Augment-only** — destination steps *add* to the generic steps; they don't replace
  generic ones. (Replace-semantics is a future option.)
- **Non-immigration services only.** Immigration is left to the AI generator.
- **Destinations DE + NO first** (the two built corridors' destinations). Adding more
  is just more map entries.
- **No schema change** — reuses `source='service'` / `service_key` / `milestone_type`.

## Components

### 1. Destination step map — `service_roadmap_steps.py`
Add alongside the generic `SERVICE_STEPS`:

```python
# service_key -> destination ISO2 -> extra ServiceSteps (augment the generic list).
SERVICE_STEPS_BY_DESTINATION: Dict[str, Dict[str, List[ServiceStep]]] = { ... }
```

Plus helpers:
- `destination_steps(service_key, dest_iso) -> List[ServiceStep]` (alias-aware on
  service_key; `None`/unknown dest → `[]`).
- `steps_for_service_in_destination(service_key, dest_iso) -> List[ServiceStep]` —
  returns the generic steps **+** destination extras, sorted by `sort_offset`
  (destination steps use offsets that slot them into the right place).

**Content v1** (indicative-but-accurate; only steps that genuinely differ):

| Service | DE | NO |
|--------|----|----|
| banking | `Register your address (Anmeldung)` before opening (sort before open_account) | — |
| housing | `Register your address (Anmeldung) at the Bürgeramt` | — |
| schools | note on school year / Schulpflicht | school-year note |
| pets | EU pet passport + rabies titer for DE entry | NO import rules (tapeworm treatment, etc.) |
| movers | customs/import note for DE (EU) | customs note for NO (non-EU) |

Immigration: **no** destination entries (AI owns it).

### 2. Bridge resolves destination — `service_roadmap_bridge.py`
- Add `_destination_iso_for_case(db, case_id) -> Optional[str]`: resolve the case's
  destination country to ISO2 (read the canonical case / `relocation_cases` host
  country or the wizard draft `relocationBasics.destCountry`; normalise name→ISO2 with
  a small map, reusing `corridor_registry`/existing helpers where possible). Best-effort
  → `None` when unresolved (falls back to generic steps).
- In `reconcile_service_milestones`, resolve the destination once and build desired
  steps via `steps_for_service_in_destination(service_key, dest_iso)` instead of
  `steps_for_service`. Caller signatures unchanged.

### 3. Reconcile prune (correctness)
Today `reconcile_service_milestones` only removes whole deselected services
(`delete_service_milestones_not_in`). Add a prune so any `source='service'` row whose
`milestone_type` is **not** in the freshly-desired set is removed — so a destination
change (or any future step-set change) cleans up stale steps. Implement by collecting
the desired `milestone_type`s and deleting service rows not in that set
(new DB helper `delete_service_milestones_not_in_types(case_id, milestone_types)` or
reuse a scoped delete). Keeps employee progress on surviving steps (upsert preserves
status).

## Edge cases
- **Unknown / unresolved destination** → generic steps only (no extras). No crash.
- **Destination change after steps exist** → prune removes the old destination's extras;
  new ones added. (Rare; destination is set at intake.)
- **Service deselected** → existing `delete_service_milestones_not_in` removes all its
  rows (generic + dest extras share the service_key).
- **Dest-step key collisions** → destination step `key`s are distinct from generic keys,
  so `milestone_type = service_{service_key}_{key}` never collides.

## Verification
- Unit tests: `steps_for_service_in_destination("banking","DE")` includes the Anmeldung
  step and the generic steps, sorted; unknown dest → generic only; immigration has no
  dest entries.
- Reconcile tests (extend `test_service_roadmap_bridge.py` with a FakeDB destination):
  selecting banking for a DE case materialises generic + Anmeldung; changing destination
  prunes the old extra; non-service rows untouched.
- `_destination_iso_for_case` resolves a case draft's destCountry to ISO2.
- Backend suite green. No migration, no frontend change.

## Out of scope (follow-ups)
- Replace-semantics (a destination step replacing a generic step's copy).
- More destinations / full per-corridor content.
- Surfacing the `rce.steps` pathway step-graph (IN_DE BlueCard) in the employee roadmap.
