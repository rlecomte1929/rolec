# Case Readiness Core v1 — results

## Final data model

### Template layer (shared)

- **`readiness_templates`** — `destination_key`, `route_key` (default `employment`), route title, **`employee_summary`**, **`hr_summary`**, **`internal_notes_hr`**, **`watchouts_json`**. Unique `(destination_key, route_key)`.
- **`readiness_template_checklist_items`** — ordered items: title, `owner_role`, `required`, optional `depends_on_sort_order`, `notes_employee`, `notes_hr`.
- **`readiness_template_milestones`** — ordered milestones: `phase`, title, `body_employee`, `body_hr`, `owner_role`, `relative_timing`.

### Case layer (minimal)

- **`case_readiness`** — PK `assignment_id`, `template_id`, resolved `destination_key`, `route_key`, optional `case_note_hr`.
- **`case_readiness_checklist_state`** — PK `(assignment_id, template_checklist_id)`, `status` (`pending` | `in_progress` | `done` | `waived` | `blocked`), `notes`.
- **`case_readiness_milestone_state`** — PK `(assignment_id, template_milestone_id)`, `completed_at`, `notes`.

## Reused vs created

- **Reused:** `case_assignments`, `employee_profiles`, `relocation_cases`, HR authorization (`_hr_can_access_assignment`), destination extraction from existing profile JSON.
- **Created:** Tables above, `backend/readiness_service.py` (normalization), `backend/seed_data/readiness_templates.json`, APIs below.

## UI attachment

- **HR Case Summary** (`HrCaseSummary`, route `/cases/:caseId/...`): **`CaseReadinessCore`** renders below the main case header card, bound to **`assignment.id`** from `hrAPI.getAssignment`.

## Summary-first loading

1. **`GET /api/hr/assignments/{id}/readiness/summary`** — small JSON: route title, HR summary, top watchouts, checklist counts, next milestone. No full checklist rows.
2. **`GET /api/hr/assignments/{id}/readiness/detail`** — full checklist + milestones merged with case state; called **only when** the user expands “Show checklist & timeline”.
3. Checklist/milestone **PATCH** refreshes detail + summary (two light calls after mutation).

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/hr/assignments/{assignment_id}/readiness/summary` | Compact summary |
| GET | `/api/hr/assignments/{assignment_id}/readiness/detail` | Checklist + milestones |
| PATCH | `/api/hr/assignments/{assignment_id}/readiness/checklist-items/{item_id}` | Update item status |
| PATCH | `/api/hr/assignments/{assignment_id}/readiness/milestones/{milestone_id}` | Set completion |

Mutations use **`_deny_if_impersonating`** (read-only view-as).

## Template resolution

1. Read destination string from employee profile (`movePlan.destination` or `relocationBasics.destCountry`), else case profile / `host_country`.
2. **Normalize** to a stable key (e.g. `Singapore` → `SG`) via `readiness_service.normalize_destination_key`.
3. **`route_key` v1:** constant `employment` until the platform stores permit route explicitly.
4. Lookup **`readiness_templates`** WHERE `destination_key` + `route_key`; **upsert `case_readiness`** row referencing that template (no template row copy).

## Avoiding duplication

- Templates live **once** per `(destination_key, route_key)`.
- Cases only store **foreign keys + state columns**; text remains in template tables (or seed JSON).

## Seeding

- **`backend/seed_data/readiness_templates.json`** — SG + FR `employment` examples (checklist + milestones).
- **`Database.seed_readiness_templates_if_empty()`** — runs after SQLite DDL and when **`DISABLE_RUNTIME_DDL`** (Postgres) so hosted DB still gets templates if tables exist from Supabase migration.

## Employee vs HR (future)

- **Employee-safe:** `employee_summary`, `notes_employee`, `body_employee`, watchouts can be filtered for a future employee API.
- **Internal:** `hr_summary`, `internal_notes_hr`, `notes_hr`, `body_hr` — expose only on HR (or admin) endpoints.

## Supabase

- Migration: `supabase/migrations/20260321000002_case_readiness_core.sql` (DDL + FKs).

## Manual verification

- [ ] Create/open an HR case whose profile **destination** is **Singapore** or **France** → summary shows route title and watchouts.
- [ ] Expand checklist → items load once; collapse/expand does not refetch (until assignment changes).
- [ ] Change checklist status → counts on summary update; no duplicate template rows in DB.
- [ ] Toggle milestone complete → next milestone in summary updates.
- [ ] Assignment in **another company** (as HR B) → **403** on readiness endpoints.
- [ ] Destination with **no template** → summary `resolved: false`, `reason: no_template`.
- [ ] No destination in profile → `reason: no_destination`.

## Performance notes

- Summary uses **one aggregate query** for checklist counts + **one ordered query** for next milestone (no per-item fan-out).
- No readiness fetch on assignments **list** pages.
