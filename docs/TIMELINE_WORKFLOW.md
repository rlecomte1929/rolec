# Timeline Workflow

Time-based milestones for relocation cases, linking services, evidence, and events.

## 1. Schema

### case_milestones

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT/UUID | Primary key |
| case_id | TEXT | Case reference |
| canonical_case_id | TEXT | Canonical case for lookup |
| milestone_type | TEXT | e.g. case_created, visa_preparation, housing_search |
| title | TEXT | Display title |
| description | TEXT | Optional description |
| target_date | TEXT/DATE | Target completion date |
| actual_date | TEXT/DATE | Actual completion date |
| status | TEXT | pending, in_progress, done, skipped, overdue |
| sort_order | INTEGER | Display order |
| created_at | TEXT | Creation timestamp |
| updated_at | TEXT | Last update timestamp |

### milestone_links

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT/UUID | Primary key |
| milestone_id | TEXT | FK to case_milestones |
| linked_entity_type | TEXT | evidence, event, rfq, service |
| linked_entity_id | TEXT | ID of linked entity |
| created_at | TEXT | Creation timestamp |

---

## 2. Files Changed

| Path | Change |
|------|--------|
| `backend/database.py` | Added case_milestones, milestone_links tables (SQLite); list_case_milestones, upsert_case_milestone, link_milestone_entity, list_milestone_links |
| `backend/app/services/timeline_service.py` | **New** – compute_default_milestones() |
| `backend/main.py` | GET /api/cases/{case_id}/timeline, GET /api/assignments/{assignment_id}/timeline, PATCH milestone, POST link |
| `frontend/src/api/client.ts` | timelineAPI, TimelineMilestone type |
| `frontend/src/features/timeline/CaseTimeline.tsx` | **New** – timeline view component |
| `frontend/src/pages/HrCaseSummary.tsx` | Integrated CaseTimeline |
| `supabase/migrations/20260325000000_case_milestones.sql` | **New** – Postgres schema + RLS |
| `docs/TIMELINE_WORKFLOW.md` | **New** – this doc |

---

## 3. Backend Changes

- **Database**: case_milestones and milestone_links (SQLite in init_db; Postgres via migration)
- **API**:
  - `GET /api/cases/{case_id}/timeline?ensure_defaults=1` – list milestones, optionally create defaults
  - `GET /api/assignments/{assignment_id}/timeline?ensure_defaults=1` – same via assignment
  - `PATCH /api/cases/{case_id}/timeline/milestones/{milestone_id}` – update milestone
  - `POST /api/cases/{case_id}/timeline/milestones/{milestone_id}/links` – add link
- **Auth**: require_hr_or_employee + case/assignment visibility

---

## 4. Frontend Changes

- **CaseTimeline** (`features/timeline/CaseTimeline.tsx`):
  - Milestone list (left) with target dates
  - Detail panel (right) with title, description, target/actual dates
  - Status buttons: Pending, In progress, Done, Skipped
  - Linked entities display when present
- **HrCaseSummary**: Renders CaseTimeline above action buttons

---

## 5. Default Milestone Logic

`compute_default_milestones()` uses:

- **case_draft** (relocationBasics) – target move date
- **selected_services** – from case_services (housing, schools, movers, etc.)
- **target_move_date** – from case

Default set:

| milestone_type | title | sort_order | target_date logic |
|----------------|-------|------------|-------------------|
| case_created | Case created | 0 | — |
| visa_preparation | Visa preparation | 10 | base_date − 70 days |
| housing_search | Housing search | 20 | base_date − 56 days |
| school_search | School search | 30 | base_date − 90 days |
| move_logistics | Move logistics | 40 | base_date − 21 days |
| arrival | Arrival | 50 | target_move_date |
| settling_in | Settling in | 60 | base_date + 14 days |

All milestones are created when `ensure_defaults=1` and none exist.

---

## 6. Verification Steps

1. **Backend**
   - Run app with SQLite (local dev)
   - `GET /api/assignments/{assignment_id}/timeline?ensure_defaults=1` with valid assignment_id
   - Verify 7 milestones returned
   - `PATCH /api/cases/{case_id}/timeline/milestones/{id}` with `{"status":"done"}`
   - Confirm status updated

2. **Frontend**
   - Log in as HR
   - Open a case summary (`/hr/cases/{assignmentId}`)
   - Confirm “Relocation timeline” section with milestones
   - Select a milestone, change status, confirm update

3. **Postgres**
   - Run migration `20260325000000_case_milestones.sql`
   - Confirm tables and RLS policies exist

---

## 7. Deferred Items

- **Milestone linking UI**: Add-link flow from detail panel (evidence, events, RFQs)
- **Employee timeline view**: Same component on employee assignment review
- **Overdue detection**: Auto-set status to overdue when target_date passed and status pending
- **Drag-and-drop** reordering of milestones
- **Notifications**: Reminders for upcoming target dates
