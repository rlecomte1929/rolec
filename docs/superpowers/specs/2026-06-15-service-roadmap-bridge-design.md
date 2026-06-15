# Service → Roadmap bridge — design

**Date:** 2026-06-15
**Branch:** `feat/services-roadmap-bridge`
**Depends on (product sequencing):** the intake wizard no longer collects services
(`feat/intake-remove-services-step`, PR #754) — service selection now happens in
the Service providers tab, which this feature reads from.

## Why

The employee journey is: **intake → preliminary roadmap → Services tab
(recommendations + quotes) → roadmap updates with the latest steps → validate →
execution.** Today the roadmap (`case_milestones`) is generated once on intake
submit and never reflects what the employee does in the Services tab. Choosing a
service or requesting a quote produces no roadmap change. This feature closes that
gap: selected services materialise concrete real-world steps (book embassy
appointment, contact school admissions, open a bank account, …) into the roadmap,
and a quote request advances the relevant step.

## Established facts (recon 2026-06-15)

- **The LIVE employee roadmap is `case_milestones`**, read via
  `GET /api/relocation-plans/{case_id}/view` (phase-grouped). The
  `roadmap_tracks`/`roadmap_steps` tables are orphaned (never written in prod).
- **`case_milestones` columns:** `id, case_id, canonical_case_id, milestone_type,
  title, description, target_date, actual_date, status, sort_order, notes,
  created_at, updated_at`. **No `service_key`, no `source`.**
  (`supabase/migrations/20260325000000_case_milestones.sql`)
- **Written by** `_async_seed_and_generate_roadmap` on submit
  (`backend/main.py:5644`): deterministic seed, then the AI generator
  `persist_generated_milestones` does **DELETE then re-INSERT**
  (`backend/app/services/case_roadmap_profile.py`).
- **Service selection** lives in `services_state.state_json.selectedServices`
  (`POST /api/cases/{id}/services-state`, `backend/app/routers/services_state.py`)
  and `case_services` (`service_key`, `category`, `selected`).
- **Quote requests** → `quote_requests` (`service_categories[]`, `status`),
  `POST /api/employee/quote-requests` (`backend/app/routers/employee_quotes.py`).
  The RFQ submit UI is currently disabled ("not available yet",
  `frontend/src/pages/services/ServicesRfqNew.tsx`).
- **No bridge exists** from any service action to `case_milestones`.

## Architecture

```
selected services (services_state) ──┐
                                     ├─► reconcile_service_milestones(case_id)
quote request (quote_requests) ──────┘            │
                                                  ▼
                              desired service steps (from step library)
                                                  │ upsert/remove ONLY source='service'
                                                  ▼
                                        case_milestones (LIVE roadmap)
                                                  │
                                                  ▼
                          GET /relocation-plans/{id}/view → employee roadmap
```

## Components

### 1. Migration — tag milestones
`supabase/migrations/<ts>_case_milestones_source_service_key.sql`:
- `ALTER TABLE public.case_milestones ADD COLUMN IF NOT EXISTS source text;`
- `ALTER TABLE public.case_milestones ADD COLUMN IF NOT EXISTS service_key text;`
- Backfill: set `source` for existing rows from `milestone_type`
  (`*_ai_*` → `'ai'`, else `'deterministic_seed'`); default new inserts `'manual'`.
- Idempotent (`IF NOT EXISTS`); no new table, so RLS already covers it. Adds an
  index on `(canonical_case_id, source)` for the reconcile/regen scoping queries.

### 2. Step library — `backend/app/services/service_roadmap_steps.py`
A pure deterministic map `service_key → ordered steps`, each step:
`{ key, title, description, phase, sort_offset, default_status }`. **Generic-first**
(corridor-agnostic but accurate). Initial content:

- **immigration:** book consular/embassy appointment · gather visa/permit documents
  · submit application · attend biometrics · collect residence permit
- **schools:** shortlist schools · contact admissions · submit applications ·
  confirm enrolment
- **housing:** define search criteria · request & compare housing quotes · viewings
  · sign lease
- **banking / banks:** book account-opening appointment · open local account
- **movers:** request & compare moving quotes · book mover · pack & ship
- **tax:** book tax-advisor consultation · gather income/residency documents
- **language:** choose a language course · enrol
- **spouse:** partner career consultation · CV / credentials review
- **temp / temp_accommodation:** book temporary accommodation
- **pets:** vet health check & documents · book pet transport

Each step's `phase` maps to the plan-view phases (Pre-Departure / During /
Arrival & Settlement). `request & compare … quotes` steps carry a stable `key` so
the quote-trigger can find and advance them.

### 3. Reconcile — `reconcile_service_milestones(case_id, selected_services)`
Lives in a new service module (`service_roadmap_bridge.py`). Idempotent:
1. Resolve `canonical_case_id` (reuse existing resolver).
2. Build desired `source='service'` milestones from `selected_services` via the
   step library (deterministic `milestone_type` = `service_{service_key}_{step.key}`
   so upserts are stable).
3. `UPSERT` desired rows (insert missing, update title/desc/phase/sort on change).
4. `DELETE` `source='service'` rows whose `service_key` is **not** in
   `selected_services` (lifecycle = remove on deselect).
5. **Never** touches rows with `source IN ('ai','deterministic_seed','manual')`.
Returns a summary `{added, removed, kept}` for logging/tests.

### 4. Triggers
- **Selection:** in `PUT/POST /api/cases/{id}/services-state`, after persisting the
  blob, call `reconcile_service_milestones(case_id, state.selectedServices)`.
  Best-effort + idempotent — a reconcile failure must not fail the save.
- **Quote request:** in `create_quote_request` (`employee_quotes.py`), after the
  insert, flip the matching `service_{key}_quote` step to `in_progress` and record
  the `quote_request_id` in `notes`/metadata, for each requested
  `service_category`. (Maps category → service_key via the step library.)
  Dormant in practice until the RFQ submit UI is enabled — see follow-ups.

### 5. AI-regen coexistence
Scope `persist_generated_milestones`' DELETE to `source='ai'` (or
`source IS DISTINCT FROM 'service'`) so service-sourced milestones survive a
roadmap regeneration. The deterministic seed already runs before generation; this
change only narrows the destructive delete.

## Decisions (approved 2026-06-15)
- **Generic-first content** (not corridor-specific). Corridor tailoring is a later
  content effort / AI augmentation — out of scope.
- **Lifecycle = remove on deselect.** Deselecting a service removes its `pending`
  steps; in-progress/done state is the employee's signal that work started.
- **Trigger = selection materialises + quote advances.**
- **RFQ submit button:** backend quote-trigger is built now; wiring the disabled
  `ServicesRfqNew` submit UI is a separate follow-up. The trigger is dormant until
  then.

## Edge cases
- **Reconcile vs. AI-regen ordering:** AI-regen runs once on submit (before any
  service selection in the normal flow); the scoped delete makes later re-runs safe
  regardless.
- **Unknown service_key** (in `selectedServices` but not in the library): skipped,
  logged — no crash.
- **Case with no canonical id:** reconcile no-ops with a warning (mirrors existing
  best-effort milestone code).
- **Duplicate categories across services:** stable `milestone_type` keys make
  upserts idempotent; no duplicates.

## Verification
- Unit tests for `service_roadmap_steps` (every service_key yields ≥1 well-formed
  step) and `reconcile_service_milestones` (select → steps appear; deselect →
  removed; AI/manual rows untouched; idempotent on repeat).
- Test that the scoped AI-regen delete preserves `source='service'` rows.
- Migration round-trip test (columns added, backfill correct, RLS intact) via the
  inline rollback-tx pattern.
- Backend test suite green; the migration file passes the ledger/RLS guards.

## Out of scope (sequenced follow-ups)
- Corridor-specific step content (FR→DE vs IN→DE) / AI augmentation of steps.
- Wiring the `ServicesRfqNew` submit button (enables the quote-trigger end-to-end).
- The "validate roadmap before execution" gate (separate vision phase).
- Frontend: surfacing `service_key`/`source` as roadmap UI affordances (the plan
  view already renders the new milestones with no UI change required).
