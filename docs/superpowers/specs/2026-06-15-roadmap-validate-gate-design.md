# Validate-roadmap gate (Phase 3) — design

**Date:** 2026-06-15
**Branch:** `feat/roadmap-validate-gate`
**Depends on (product sequencing):** the roadmap is meaningful after intake
(`feat/intake-remove-services-step`, #754) and is enriched by services
(`feat/services-roadmap-bridge`, #762). This gate sits *after* those: review the
roadmap → validate → execution tasks.

## Why

The employee journey is: **intake → preliminary roadmap → Services tab enriches the
roadmap → validate the roadmap → execution tasks (forms, document uploads).** Today
there is no checkpoint between "roadmap" and "execution": forms and uploads are
**completely ungated** — once a case exists, any form can be opened, filled and
submitted (only tenant isolation is checked). This gate adds the missing
"validate before you dive into the tasks" step the product owner asked for.

## Decisions (approved 2026-06-15)
- **Employee self-validates** (no HR sign-off in v1).
- **Soft gate** — forms/uploads are never hard-blocked (no 403); the UI leads with
  a "validate first" nudge and de-emphasises execution until validated. No risk of
  locking out in-flight cases.
- **One small validation table**, not a revival of the dormant readiness system.
- **No case-status enum change** (the validation table is the source of truth).
- **Sticky** validation (stays validated even if the roadmap later changes).
- **Per canonical case** (whole roadmap), not per-phase.

## Established facts (recon 2026-06-15)
- Forms/uploads are ungated: `list_case_forms` / form field / ad-hoc endpoints call
  only `_assert_case_access` (tenant isolation), never a status/phase gate
  (`backend/app/routers/cases.py:823`, `case_forms_adhoc.py:98`).
- No validate/approve/confirm action or `roadmap_validated`/`locked` state exists.
- The employee roadmap renders from the **relocation plan view**
  (`GET /api/relocation-plans/{id}/view`, served from `backend/main.py`), reading
  `case_milestones` (keyed by `canonical_case_id`).
- A dormant readiness system exists (`readiness_templates`,
  `readiness_checklist_state`, `frontend/src/features/readiness`) but gates nothing.
  Out of scope here.
- `cases.py` is dead/unwired — live `/api/cases` routes are in `cases_read.py` /
  `cases_write.py` (registered in BOTH `backend/main.py` and `backend/app/main.py`).

## Data model

New table `public.case_roadmap_validations`:

| column | type | notes |
|--------|------|-------|
| `canonical_case_id` | text PRIMARY KEY | same key `case_milestones` uses |
| `validated_at` | timestamptz NOT NULL DEFAULT now() | |
| `validated_by_user_id` | text | the employee who validated |
| `created_at` | timestamptz NOT NULL DEFAULT now() | |

Migration must satisfy the **RLS hard-gate** (new public table):
1. `ALTER TABLE … ENABLE ROW LEVEL SECURITY;`
2. A tenant-scoped policy mirroring the `case_milestones` policy (scope by the
   case's owning tenant/assignment — use the existing `case_milestones` RLS policy
   as the canonical reference).
3. `REVOKE ALL ON public.case_roadmap_validations FROM anon;`

Idempotent DDL (`CREATE TABLE IF NOT EXISTS`, `CREATE POLICY IF NOT EXISTS` or
guarded). No backfill.

## Backend

### Validate action
`POST /api/cases/{case_id}/roadmap/validate` — added to **`cases_write.py`** (live,
dual-registered), NOT `cases.py`.
- Auth: employee owns the case (reuse the existing case-access dependency that
  `cases_write` uses; resolve assignment → canonical case id with the existing
  resolver).
- Upsert `(canonical_case_id, validated_at=now, validated_by_user_id=user)` —
  idempotent (re-validating just refreshes `validated_at`).
- Returns `{validated_at, validated_by_user_id}`.
- Best-effort audit log row (mirror existing audit patterns;
  `audit_logs.action_type` only allows insert/update/delete — put the semantic
  event in `new_value.event`).

### State exposure + grandfathering
Extend the **relocation plan view** response (the employee roadmap's read path) with:
- `roadmap_validated_at` / `roadmap_validated_by` — from `case_roadmap_validations`.
- **Derived grandfathering:** if no explicit validation row exists BUT the case is
  already in execution (any `case_forms` row in status
  `in_progress`/`ready`/`submitted`/`approved`), report `roadmap_validated_at` as
  the case's earliest such form activity timestamp (or "true" with a derived flag).
  Pure read-side derivation — no migration/backfill, so active users are never
  nagged by the new gate.

Expose the same fields wherever the dossier page needs them. If the dossier page
reads a different summary endpoint (`cases_read.py`), add the field there too,
reading the same table + derivation (a shared helper
`get_roadmap_validation_state(canonical_case_id)` keeps it DRY).

## Frontend (soft gate)

### Roadmap page (employee plan view)
- Not validated → a "Happy with your plan? **Validate & start tasks**" CTA that
  calls the validate endpoint, then reflects the validated state.
- Validated → a quiet "Validated on {date}" confirmation.

### Dossier / Forms page
- Not validated → lead with a "Validate your roadmap to start" panel and visually
  de-emphasise (dim) the forms section. Forms remain reachable (soft).
- Validated → normal forms UI.
- Reads `roadmap_validated_at` from the case/plan summary it already fetches.

Use the antigravity component library; navy/teal per `DESIGN.md` (no new colors).

## Edge cases
- **Re-validation** is idempotent (refreshes timestamp).
- **Roadmap changes after validation** (employee adds services later): validation
  stays (sticky). A subtle "your roadmap changed since you validated" hint is a
  future nicety, not in v1.
- **Grandfathered case** with no explicit row reads as validated via derivation;
  if such an employee clicks Validate anyway, a real row is written (harmless).
- **No-canonical-case** edge: validate endpoint 404s like sibling case routes.

## Verification
- Backend: `POST …/roadmap/validate` is idempotent, enforces ownership, resolves
  canonical id, writes the row; the plan view exposes `roadmap_validated_at`; the
  grandfather derivation returns validated for a case with an in-progress form and
  unvalidated for a fresh case. Migration round-trip (RLS enforced) via the inline
  rollback-tx pattern.
- Frontend: `tsc --noEmit` clean; a component test asserting the dossier renders the
  nudge when unvalidated and the forms UI when validated; the roadmap CTA calls the
  endpoint and flips state.

## Out of scope (sequenced follow-ups)
- HR/specialist sign-off workflow (the heavier alternative to self-validation).
- Hard-block enforcement (403 on form endpoints) with full grandfathering.
- Wiring a case-status transition on validation (`active`/`in_execution`).
- Reviving the `readiness_checklist_state` system as a richer pre-flight checklist.
- "Roadmap changed since you validated" re-validation prompt.
