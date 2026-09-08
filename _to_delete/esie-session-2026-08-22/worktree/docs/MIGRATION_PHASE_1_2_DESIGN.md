# ReloPass Phase 1 & Phase 2 Migration Design

**Principal architect — Option A: case_events as event log, case_actions deferred**

Goal: Prepare the platform for canonical case-centered architecture with minimal breakage.

---

## OPTION A: EVENT MODEL (case_events is immutable event log)

### 1.1 Corrected Schema for `case_events`

`case_events` is the **immutable event log**. It already exists (20260227000000). Phase 1 enhances it; no new table.

**Current schema** (from hr_command_center migration):
```sql
case_events (
  id uuid PRIMARY KEY,
  case_id text NOT NULL,
  assignment_id text REFERENCES case_assignments(id),
  actor_user_id uuid,
  event_type text NOT NULL,
  description text,
  created_at timestamptz DEFAULT now()
)
```

**Phase 1 enhancements**:
```sql
-- Add payload for structured event data; canonical_case_id for case spine
ALTER TABLE public.case_events
  ADD COLUMN IF NOT EXISTS payload jsonb NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS canonical_case_id text NULL;

CREATE INDEX IF NOT EXISTS idx_case_events_canonical_case ON public.case_events(canonical_case_id);
```

**Backfill** `canonical_case_id`: `UPDATE case_events SET canonical_case_id = case_id WHERE case_id IN (SELECT id FROM wizard_cases);`

### 1.2 Event Taxonomy for Phase 1

| event_type | When Emitted | payload keys |
|------------|--------------|--------------|
| `assignment.created` | Assignment created | `assignment_id`, `hr_user_id`, `employee_identifier` |
| `assignment.claimed` | Employee claims invite | `assignment_id`, `employee_user_id` |
| `assignment.submitted` | Employee submits | `assignment_id`, `submitted_at` |
| `assignment.unsubmitted` | Employee unsubmits | `assignment_id` |
| `assignment.approved` | HR approves | `assignment_id`, `decision` |
| `assignment.rejected` | HR rejects | `assignment_id`, `decision` |
| `assignment.reopened` | HR reopens | `assignment_id` |
| `assignment.closed` | Case/assignment closed | `assignment_id` |
| `case.created` | Wizard case created | `case_id` |
| `case.updated` | Draft/profile updated | `case_id` |
| `feedback.added` | HR adds feedback | `assignment_id`, `section` |

---

## OPTION A: FUTURE ACTION MODEL (not Phase 1)

**`case_actions`** will be introduced in a later phase as a **separate operational work-item/task primitive**.

- **Purpose**: Represents actionable work (e.g. "Review eligibility override request", "Verify passport scan")—distinct from immutable events.
- **Proposed later schema** (for reference only; not implemented in Phase 1):
  ```sql
  case_actions (
    id uuid PRIMARY KEY,
    case_id text NOT NULL REFERENCES wizard_cases(id),
    assignment_id text REFERENCES case_assignments(id),
    action_type text NOT NULL,
    status text NOT NULL,  -- pending, in_progress, completed, cancelled
    assigned_to_person_id text,
    due_at timestamptz,
    completed_at timestamptz,
    payload jsonb DEFAULT '{}',
    created_at timestamptz DEFAULT now()
  )
  ```
- **Phase 1**: Do not create `case_actions`. All event/audit logging uses `case_events`.

---

## 1. DATABASE CHANGES

### 1.1 Standardizing case_id

**Current state**: `case_id` is `text` in most tables; `uuid` in `relocation_guidance_packs`, `relocation_trace_events`, `case_resource_preferences`. `wizard_cases.id` and `relocation_cases.id` are `text`/`varchar`. No single canonical case table with formal FKs.

**Strategy**: Use `uuid` as canonical type. `wizard_cases.id` and `relocation_cases.id` store UUID strings—ensure they are valid UUIDs. Add a canonical `cases` table in Phase 2; Phase 1 standardizes types and adds FKs to `wizard_cases`.

```sql
-- Migration: 20260320000000_standardize_case_id_phase1.sql

begin;

-- 1. Ensure wizard_cases.id is uuid-compatible (optional validation)
--    Skip strict check if existing data has non-UUID ids; add later after cleanup.
--    For Phase 1, no constraint. Rely on application to use UUIDs for new cases.

-- 2. Standardize case_id columns that use uuid to use text (for FK to wizard_cases)
--    OR keep uuid and add wizard_cases.id as uuid type.
--    Decision: Keep wizard_cases.id as text (varchar) for backward compat.
--    Tables with uuid case_id must cast: use text for case_id everywhere for Phase 1.

-- 2a. Fix relocation_guidance_packs.case_id: change uuid -> text to match wizard_cases
alter table public.relocation_guidance_packs 
  alter column case_id type text using case_id::text;

-- 2b. Fix relocation_trace_events.case_id
alter table public.relocation_trace_events 
  alter column case_id type text using case_id::text;

-- 2c. Fix case_resource_preferences.case_id (from rkg_resources migration)
alter table public.case_resource_preferences 
  alter column case_id type text using case_id::text;

-- 3. Add canonical_case_id to case_assignments for future use (nullable, backfilled)
alter table public.case_assignments 
  add column if not exists canonical_case_id text null;

-- Backfill: case_assignments.case_id already points to wizard_cases or relocation_cases
-- Set canonical_case_id = case_id where case_id exists in wizard_cases
update public.case_assignments ca
set canonical_case_id = ca.case_id
where ca.canonical_case_id is null
  and exists (select 1 from public.wizard_cases wc where wc.id = ca.case_id);

-- Where case_id points to relocation_cases, we need wizard_cases mapping (Phase 2)
-- For now leave canonical_case_id null for relocation_cases-only refs

commit;
```

### 1.2 Canonical Case Spine (add canonical_case_id to all case-linked tables)

```sql
-- Migration: 20260320000050_canonical_case_spine.sql

begin;

-- Add canonical_case_id and backfill for tables that have case_id
do $$
declare
  tbl text;
begin
  for tbl in select unnest(ARRAY[
    'case_requirements_snapshots', 'case_feedback', 'assignment_invites',
    'dossier_answers', 'dossier_case_questions', 'dossier_case_answers',
    'dossier_source_suggestions', 'case_services', 'case_service_answers',
    'relocation_guidance_packs', 'relocation_trace_events', 'rule_evaluation_logs',
    'rfqs', 'case_resource_preferences', 'service_recommendations', 'case_vendor_shortlist'
  ])
  loop
    if exists (select 1 from information_schema.tables where table_schema='public' and table_name=tbl)
       and exists (select 1 from information_schema.columns where table_schema='public' and table_name=tbl and column_name='case_id')
       and not exists (select 1 from information_schema.columns where table_schema='public' and table_name=tbl and column_name='canonical_case_id')
    then
      execute format('alter table public.%I add column canonical_case_id text null', tbl);
      execute format('update public.%I t set canonical_case_id = t.case_id where exists (select 1 from public.wizard_cases wc where wc.id = t.case_id)', tbl);
    end if;
  end loop;
end $$;

commit;
```

### 1.3 Adding Formal Foreign Keys

```sql
-- Migration: 20260320000100_add_case_foreign_keys_phase1.sql

begin;

-- 1. case_assignments -> wizard_cases (soft FK: add constraint only where case exists in wizard_cases)
--    Cannot add FK if case_id can reference relocation_cases. Use trigger or defer to Phase 2.
--    Phase 1: Add FK from tables that ONLY reference wizard_cases.

-- case_feedback already has: case_id -> wizard_cases(id), assignment_id -> case_assignments(id)
-- No change needed.

-- 2. case_requirements_snapshots: add FK to wizard_cases if missing
--    Pre-check: ensure all case_id values exist in wizard_cases
do $$
begin
  if not exists (
    select 1 from information_schema.table_constraints 
    where table_schema = 'public' and constraint_name = 'fk_case_requirements_snapshots_case'
      and table_name = 'case_requirements_snapshots'
  ) and not exists (
    select 1 from public.case_requirements_snapshots crs
    where not exists (select 1 from public.wizard_cases wc where wc.id = crs.case_id)
  ) then
    alter table public.case_requirements_snapshots
      add constraint fk_case_requirements_snapshots_case 
      foreign key (case_id) references public.wizard_cases(id) on delete cascade;
  end if;
exception when others then
  raise notice 'FK case_requirements_snapshots: %', sqlerrm;
end $$;

-- 3. assignment_invites: add FK only if all case_ids exist in wizard_cases
--    (assignment_invites may reference relocation_cases in legacy setups)
do $$
begin
  if not exists (
    select 1 from information_schema.table_constraints 
    where table_schema = 'public' and constraint_name = 'fk_assignment_invites_case' and table_name = 'assignment_invites'
  ) and not exists (
    select 1 from public.assignment_invites ai
    where not exists (select 1 from public.wizard_cases wc where wc.id = ai.case_id)
  ) then
    alter table public.assignment_invites
      add constraint fk_assignment_invites_case 
      foreign key (case_id) references public.wizard_cases(id) on delete cascade;
  end if;
exception when others then
  raise notice 'FK assignment_invites: %', sqlerrm;
end $$;

-- 4. case_assignments: add FK to wizard_cases (DEFERRABLE, only enforce for new/updated rows where case_id in wizard_cases)
--    Problem: case_assignments.case_id may point to relocation_cases. Create a view or use conditional FK.
--    Simpler: Add FK that allows NULL for legacy; new cases must use wizard_cases.
--    Best: Add check constraint that case_id must exist in wizard_cases OR relocation_cases (complex).
--    Phase 1: Add FK only after we migrate all case_assignments to reference wizard_cases (Phase 2).
--    Skip case_assignments FK for Phase 1.

-- 5. dossier_answers: add FK only if all case_ids in wizard_cases (defer if mixed)
-- 6. case_services, case_service_answers, rfqs: defer to Phase 2 (may reference legacy cases)

commit;
```

**Simplified Phase 1 FK approach**: Add FKs only to tables that exclusively reference wizard_cases today (case_feedback, case_requirements_snapshots, assignment_invites). Defer case_assignments, dossier_*, case_services, rfqs to Phase 2 after case unification.

### 1.4 Introducing case_participants

```sql
-- Migration: 20260320000200_case_participants.sql

begin;

create table if not exists public.case_participants (
  id uuid primary key default gen_random_uuid(),
  case_id text not null references public.wizard_cases(id) on delete cascade,
  person_id text not null,  -- auth.users.id or profiles.id; no FK to avoid auth schema coupling
  role text not null check (role in ('relocatee', 'hr_owner', 'hr_reviewer', 'observer')),
  invited_at timestamptz null,
  joined_at timestamptz null,
  created_at timestamptz not null default now(),
  unique (case_id, person_id, role)
);

create index idx_case_participants_case on public.case_participants(case_id);
create index idx_case_participants_person on public.case_participants(person_id);

alter table public.case_participants enable row level security;

create policy case_participants_select
  on public.case_participants for select to authenticated
  using (
    exists (
      select 1 from public.case_assignments ca
      where ca.case_id = case_participants.case_id
        and (ca.hr_user_id::text = auth.uid()::text or ca.employee_user_id::text = auth.uid()::text)
    )
  );

create policy case_participants_insert
  on public.case_participants for insert to authenticated
  with check (
    exists (
      select 1 from public.case_assignments ca
      where ca.case_id = case_participants.case_id and ca.hr_user_id::text = auth.uid()::text
    )
  );

grant select, insert on public.case_participants to authenticated;

-- Backfill: Create participants from case_assignments
insert into public.case_participants (case_id, person_id, role, joined_at)
select ca.case_id, ca.hr_user_id::text, 'hr_owner', ca.created_at
from public.case_assignments ca
where ca.case_id in (select id from public.wizard_cases)
  and not exists (
    select 1 from public.case_participants cp 
    where cp.case_id = ca.case_id and cp.person_id = ca.hr_user_id::text and cp.role = 'hr_owner'
  );

insert into public.case_participants (case_id, person_id, role, joined_at)
select ca.case_id, ca.employee_user_id::text, 'relocatee', ca.updated_at
from public.case_assignments ca
where ca.employee_user_id is not null
  and ca.case_id in (select id from public.wizard_cases)
  and not exists (
    select 1 from public.case_participants cp 
    where cp.case_id = ca.case_id and cp.person_id = ca.employee_user_id::text and cp.role = 'relocatee'
  );

commit;
```

### 1.5 Enhancing case_events (Option A: no case_actions)

```sql
-- Migration: 20260320000300_case_events_enhance.sql

begin;

-- Add payload and canonical_case_id to existing case_events
alter table public.case_events
  add column if not exists payload jsonb not null default '{}',
  add column if not exists canonical_case_id text null;

create index if not exists idx_case_events_canonical_case on public.case_events(canonical_case_id);

-- Backfill canonical_case_id where case_id exists in wizard_cases
update public.case_events ce
set canonical_case_id = ce.case_id
where ce.canonical_case_id is null
  and exists (select 1 from public.wizard_cases wc where wc.id = ce.case_id);

-- Migrate description into payload for new events (optional; existing events keep description)
-- No schema change to description column; new writes use payload.

comment on table public.case_events is 'Immutable event log for case/assignment state changes. Option A: case_actions deferred.';

commit;
```

### 1.6 Introducing case_evidence (revised: multi-level linkage)

```sql
-- Migration: 20260320000400_case_evidence.sql

begin;

create table if not exists public.case_evidence (
  id uuid primary key default gen_random_uuid(),
  -- Multi-level linkage: at least one of case_id, case_participant_id, assignment_id required
  case_id text null references public.wizard_cases(id) on delete cascade,
  case_participant_id uuid null references public.case_participants(id) on delete cascade,
  assignment_id text null references public.case_assignments(id) on delete cascade,
  requirement_id text null,
  evidence_type text not null,
  file_url text null,
  metadata jsonb not null default '{}',
  status text not null default 'submitted' check (status in ('submitted', 'verified', 'rejected')),
  submitted_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  constraint chk_case_evidence_linkage check (
    case_id is not null or case_participant_id is not null or assignment_id is not null
  )
);

create index idx_case_evidence_case on public.case_evidence(case_id);
create index idx_case_evidence_participant on public.case_evidence(case_participant_id);
create index idx_case_evidence_assignment on public.case_evidence(assignment_id);
create index idx_case_evidence_requirement on public.case_evidence(requirement_id);

alter table public.case_evidence enable row level security;

create policy case_evidence_select
  on public.case_evidence for select to authenticated
  using (
    (case_id is not null and exists (
      select 1 from public.case_assignments ca
      where ca.case_id = case_evidence.case_id
        and (ca.hr_user_id::text = auth.uid()::text or ca.employee_user_id::text = auth.uid()::text)
    ))
    or (case_participant_id is not null and exists (
      select 1 from public.case_participants cp
      join public.case_assignments ca on ca.case_id = cp.case_id
      where cp.id = case_evidence.case_participant_id
        and (ca.hr_user_id::text = auth.uid()::text or ca.employee_user_id::text = auth.uid()::text)
    ))
    or (assignment_id is not null and exists (
      select 1 from public.case_assignments ca
      where ca.id = case_evidence.assignment_id
        and (ca.hr_user_id::text = auth.uid()::text or ca.employee_user_id::text = auth.uid()::text)
    ))
  );

create policy case_evidence_insert
  on public.case_evidence for insert to authenticated
  with check (
    (assignment_id is not null and exists (
      select 1 from public.case_assignments ca
      where ca.id = case_evidence.assignment_id and ca.employee_user_id::text = auth.uid()::text
    ))
    or (case_id is not null and exists (
      select 1 from public.case_assignments ca
      where ca.case_id = case_evidence.case_id and ca.hr_user_id::text = auth.uid()::text
    ))
    or (case_participant_id is not null and exists (
      select 1 from public.case_participants cp
      join public.case_assignments ca on ca.case_id = cp.case_id
      where cp.id = case_evidence.case_participant_id and ca.hr_user_id::text = auth.uid()::text
    ))
  );

grant select, insert on public.case_evidence to authenticated;

-- No backfill. New evidence flows use this table.

commit;
```

### 1.7 Marking relocation_cases as Legacy-Compatible

```sql
-- Migration: 20260320000500_relocation_cases_legacy_flag.sql

begin;

-- 1. Add legacy flag
alter table public.relocation_cases 
  add column if not exists is_legacy boolean not null default true;

alter table public.relocation_cases 
  add column if not exists canonical_case_id text null;

-- 2. Add comment for documentation
comment on table public.relocation_cases is 'Legacy relocation cases. Prefer wizard_cases for new flows. canonical_case_id links to wizard_cases.id when migrated.';

-- 3. Create view for "all cases" that unions wizard + legacy (for compatibility reads)
create or replace view public.cases_unified as
select 
  id,
  'wizard' as source,
  id as canonical_id,
  null as hr_user_id,
  draft_json::jsonb as profile_snapshot,
  origin_country,
  dest_country,
  purpose,
  target_move_date,
  status,
  created_at,
  updated_at
from public.wizard_cases
union all
select 
  rc.id,
  'legacy' as source,
  rc.canonical_case_id as canonical_id,
  rc.hr_user_id,
  rc.profile_json::jsonb as profile_snapshot,
  rc.home_country as origin_country,
  rc.host_country as dest_country,
  null as purpose,
  null as target_move_date,
  rc.status,
  rc.created_at::timestamptz,
  rc.updated_at::timestamptz
from public.relocation_cases rc
where rc.is_legacy = true;

commit;
```

### 1.8 Preparing wizard_cases as Canonical RelocationCase

```sql
-- Migration: 20260320000600_wizard_cases_canonical_prep.sql

begin;

-- 1. Add company_id if missing
alter table public.wizard_cases 
  add column if not exists company_id text null;

-- 2. Add profile_snapshot as materialized key fields (optional denormalization)
alter table public.wizard_cases 
  add column if not exists profile_snapshot_json jsonb null;

-- 3. Ensure status has sensible default and check
alter table public.wizard_cases 
  alter column status set default 'created';

-- 4. Add index for common lookups
create index if not exists idx_wizard_cases_company on public.wizard_cases(company_id);
create index if not exists idx_wizard_cases_dest_country on public.wizard_cases(dest_country);
create index if not exists idx_wizard_cases_status on public.wizard_cases(status);

-- 5. Comment
comment on table public.wizard_cases is 'Canonical relocation case (RelocationCase). Primary case entity for new flows.';

commit;
```

---

## 2. CANONICAL CASE MIGRATION SPINE

Phase 1 adds `canonical_case_id` to all case-linked tables. Populate from `wizard_cases.id` where `case_id` exists in wizard_cases; leave null for legacy-only refs.

| Table | Phase 1 Migration | Backfill Rule |
|-------|-------------------|---------------|
| case_assignments | 20260320000000 | `canonical_case_id = case_id` where case_id in wizard_cases |
| case_events | 20260320000300 | `canonical_case_id = case_id` where case_id in wizard_cases |
| case_requirements_snapshots | 20260320000100 (new col) | `canonical_case_id = case_id` (all ref wizard) |
| case_feedback | 20260320000100 (new col) | `canonical_case_id = case_id` (FK to wizard) |
| assignment_invites | 20260320000100 (new col) | `canonical_case_id = case_id` where case_id in wizard_cases |
| dossier_answers | 20260320000000 (in 00000) | `canonical_case_id = case_id` where case_id in wizard_cases |
| dossier_case_questions | same | same |
| dossier_case_answers | same | same |
| dossier_source_suggestions | same | same |
| case_services | same | same |
| case_service_answers | same | same |
| relocation_guidance_packs | same | same |
| relocation_trace_events | same | same |
| rule_evaluation_logs | same | same |
| rfqs | same | same |
| case_resource_preferences | same | same |
| service_recommendations | same | same |
| case_vendor_shortlist | same | same |
| relocation_cases | 20260320000500 | `canonical_case_id` links to wizard after migration |

**Migration 20260320000050_canonical_case_spine.sql**: Add `canonical_case_id` to all above tables; backfill where `case_id IN (SELECT id FROM wizard_cases)`.

---

## 3. NEW WRITES POLICY

**Rule**: All new-flow writes MUST use `wizard_cases.id` as the case identifier. Legacy `relocation_cases.id` is read-only.

| Write Operation | Rule |
|-----------------|------|
| Create case | INSERT into `wizard_cases` only. Never create in `relocation_cases`. |
| Create assignment | `case_id` MUST exist in `wizard_cases`. Reject if case_id not in wizard_cases and `REQUIRE_WIZARD_CASE_FOR_NEW=true`. |
| Create assignment_invite | `case_id` MUST be wizard case. |
| Create case_* (feedback, requirements snapshot, services, etc.) | `case_id` MUST be wizard case for new flows. |
| Insert case_events | Use `case_id` from assignment/case (which must be wizard). Set `canonical_case_id = case_id`. |
| Insert case_participants | `case_id` MUST reference wizard_cases. |
| Insert case_evidence | At least one of case_id, case_participant_id, assignment_id. If case_id, must be wizard. |
| PATCH case | Only if case in wizard_cases. Return 405 for legacy. |
| Dossier, guidance, RFQ | `case_id` from request MUST resolve to wizard case for new flows. |

**Enforcement**: Backend validates `case_id IN (SELECT id FROM wizard_cases)` before INSERT for tables in the spine. Feature flag `REQUIRE_WIZARD_CASE_FOR_NEW` gates strict rejection (Phase 1: warn only; Phase 2: reject).

---

## 4. DUAL-READ EXIT CRITERIA

Switch off dual-read (stop falling back to `relocation_cases`) when ALL of the following hold:

| Criterion | Threshold | Measurement |
|-----------|-----------|-------------|
| Legacy case reads | < 1% of case lookups in 7 days | Log `get_case_*` source; count legacy hits |
| case_assignments.case_id | 100% point to wizard_cases | `SELECT COUNT(*) FROM case_assignments WHERE case_id NOT IN (SELECT id FROM wizard_cases)` = 0 |
| relocation_cases with canonical_case_id | 100% of active legacy have mapping | All relocation_cases with recent activity have canonical_case_id set |
| No PATCH to legacy cases | 0 writes to relocation_cases for case data | Audit log |
| Frontend caseId | All HR/employee flows pass wizard id | Code review; no assignment-id-as-caseId in case APIs |

**Exit action**: Set `ALLOW_LEGACY_CASE_READ=false`. Remove fallback in `get_case_from_wizard_or_legacy`. Return 404 for legacy case_id.

---

## 5. BACKEND CHANGES

### Phase 1 — Minimal Safe Sequence

| Order | Module/File | Change |
|-------|-------------|--------|
| 1 | `backend/database.py` | Add `get_case_from_wizard_or_legacy(case_id)`. Use for all case lookups. |
| 2 | `backend/database.py` | Add `insert_case_event(case_id, assignment_id, actor_id, event_type, payload)`. Writes to `case_events`. |
| 3 | `backend/main.py` | In `set_assignment_submitted`, `update_assignment_status`, HR decision handler: call `insert_case_event` after successful update. |
| 4 | `backend/app/crud.py` | No change to get_case (already wizard). Ensure create_case always writes to wizard_cases. |
| 5 | `backend/database.py` | Add `ensure_case_participant(case_id, person_id, role)`. Call when assignment created/claimed. |
| 6 | `backend/main.py` | In assignment create/claim flow: call `ensure_case_participant` for hr_owner and employee. |
| 7 | `backend/routes/resources.py` | Ensure `_get_draft_for_case` uses `get_case_from_wizard_or_legacy` when app_crud.get_case returns None. |
| 8 | `backend/database.py` | Add `save_evidence(case_id?, case_participant_id?, assignment_id?, ...)`. Enforce linkage rule. |
| 9 | `backend/main.py` | Add `POST /api/assignments/{id}/evidence` endpoint; keep existing compliance/answer flows. |
| 10 | `backend/app/routers/cases.py` | Ensure case creation goes to wizard_cases; add company_id from request context. |

### Phase 2 — Deeper Integration

| Order | Module/File | Change |
|-------|-------------|--------|
| 11 | `backend/database.py` | Implement `get_case_unified(case_id)` using cases_unified view or wizard-first + legacy fallback. |
| 12 | `backend/main.py` | Replace all `db.get_case_by_id` with `db.get_case_unified`. Deprecate direct relocation_cases reads. |
| 13 | `backend/database.py` | Enforce `REQUIRE_WIZARD_CASE_FOR_NEW`: reject assignment create if case_id not in wizard_cases. |
| 14 | — | case_actions (future): implement when operational task primitive is designed. |

### Exact Files to Touch (Phase 1)

```
backend/database.py          # get_case_from_wizard_or_legacy, insert_case_event, ensure_case_participant, save_evidence
backend/main.py              # assignment transitions + insert_case_event; ensure_case_participant; POST /evidence
backend/routes/resources.py  # _get_draft_for_case fallback
backend/app/crud.py          # (optional) create_case company_id
backend/app/routers/cases.py # create case company_id
```

---

## 6. IMPLEMENTATION SEQUENCE

Exact order of execution:

| Step | Action | Verification |
|------|--------|--------------|
| 1 | Apply migration 20260320000000 (standardize case_id, add canonical_case_id to case_assignments) | `SELECT canonical_case_id FROM case_assignments LIMIT 1` non-null where wizard |
| 2 | Apply migration 20260320000050 (canonical_case_id to all spine tables) | All spine tables have canonical_case_id; backfill done |
| 3 | Apply migration 20260320000100 (FKs) | FKs valid; no constraint violations |
| 4 | Apply migration 20260320000200 (case_participants) | Row count from backfill |
| 5 | Apply migration 20260320000300 (case_events enhance) | `payload`, `canonical_case_id` columns exist |
| 6 | Apply migration 20260320000400 (case_evidence) | Table created; constraint check passes |
| 7 | Apply migration 20260320000500 (relocation_cases legacy) | `cases_unified` view returns rows |
| 8 | Apply migration 20260320000600 (wizard_cases prep) | `company_id` column exists |
| 9 | Backend: implement `get_case_from_wizard_or_legacy` | Unit test; integration test |
| 10 | Backend: implement `insert_case_event` | Unit test; verify events in DB after transition |
| 11 | Backend: wire `insert_case_event` to assignment transitions | Manual: submit assignment, check case_events |
| 12 | Backend: implement `ensure_case_participant` | Manual: create assignment, check case_participants |
| 13 | Backend: implement `save_evidence` | Unit test |
| 14 | Backend: add POST /evidence endpoint | API test |
| 15 | Backend: wire `_get_draft_for_case` fallback | Manual: legacy case id returns draft |
| 16 | Frontend: CaseWizardPage id resolution | Manual: invite link with assignment id works |
| 17 | Frontend: HrCaseSummary, HrReviewCase use wizard case id | Manual: no regressions |
| 18 | Verification: run full flow (create case → assign → submit → approve) | E2E |
| 19 | Verification: dual-read returns correct case for wizard and legacy ids | Log/monitor |

---

## 7. FRONTEND CHANGES

### Screens/Components That Must Stop Depending on Legacy Semantics

| Component | Current Behavior | Required Change |
|-----------|------------------|-----------------|
| `CaseWizardPage.tsx` | Uses `caseId` from route (may be assignment id); `getRelocationCase`; `patchCase` | Treat route param as case id when it's UUID; when it's assignment id, resolve case_id from assignment. Use canonical case API. |
| `EmployeeCaseSummary.tsx` | `caseId` from params, may be assignment id | Same: resolve case from assignment when needed. |
| `HrCaseSummary.tsx` | Fetches case by caseId | Ensure caseId is always wizard_cases.id for wizard-created cases. |
| `HrReviewCase.tsx` | caseId in route | Same. |
| `Resources.tsx` | `caseIdParam ?? assignmentId`; can use either | Standardize: when coming from employee journey, use assignment to get case_id. When from HR, use case_id directly. |
| `review.ts` (api) | `getWizardCaseForReview(caseId)` | No change if caseId is wizard id. Ensure callers pass wizard case id. |
| `getAssignmentIdForCase` | Resolves assignment from case_id | No change. |
| `ServicesRfqNew.tsx` | `caseId` from API | Ensure API returns wizard case id when available. |
| `HrComplianceCheck.tsx` | `caseId` from search/selected | Ensure caseId is canonical. |
| `HrDashboard.tsx` | Lists assignments with case_id | Display case_id; ensure it's wizard id for new cases. |
| `CaseContextBar.tsx` | Receives stage from case/assignment | No semantic change. |
| Routes (`routes.ts`) | `/hr/cases/:caseId`, `/cases/:caseId/resources` | Document: caseId must be wizard_cases.id for new flows. |

### Assignment/Workflow Surfaces — Priority

1. **CaseWizardPage.tsx** — High. Handles employee intake; route can be assignment id or case id. Add `useEffect` to resolve: if param looks like assignment id (from invite link), fetch assignment → get case_id → use that for all case operations.
2. **Resources.tsx** — Medium. Already handles both; ensure backend returns consistent case_id.
3. **HrCaseSummary.tsx, HrReviewCase.tsx** — Medium. HR flows use case_id from assignment list; ensure list returns wizard case id.
4. **api/review.ts** — Low. `getWizardCaseForReview` expects wizard id; callers (HrReviewCase) must pass it.

---

## 8. COMPATIBILITY STRATEGY

### Dual-Read Period

- **Case lookup**: `get_case_from_wizard_or_legacy(case_id)` tries wizard_cases first, then relocation_cases. All reads use this.
- **Write path**: New cases always go to wizard_cases. Legacy relocation_cases are read-only for case data.
- **assignment.case_id**: Can point to either. Backend resolves via unified lookup. No frontend change to which id is stored.

### ID Resolution Rules

| Incoming ID | Resolution |
|-------------|------------|
| UUID string matching wizard_cases.id | Use wizard case |
| UUID string matching relocation_cases.id | Use legacy case (read-only) |
| Assignment id passed as "caseId" | Fetch assignment, use assignment.case_id |
| Invalid / not found | 404 |

### Backfill for Legacy Cases

- For each `relocation_cases` row with no corresponding wizard_cases: Optionally create a wizard_cases row with `draft_json = profile_json`, set `relocation_cases.canonical_case_id = wizard_cases.id`. Then migrate case_assignments.case_id to point to wizard_cases.id. This is Phase 2.
- Phase 1: No data migration. Only dual-read.

### API Contract

- `GET /api/cases/{id}` — Returns case from wizard or legacy. Response includes `source: 'wizard' | 'legacy'`.
- `PATCH /api/cases/{id}` — Only allowed for wizard cases. Legacy returns 405.
- Assignment creation — `case_id` must exist in wizard_cases for new flows. Legacy case_id continues to work for reads.

---

## 9. CUTOVER PLAN

### Migration Step Order

| Step | Action | Rollback |
|------|--------|----------|
| 1 | Apply DB migrations 20260320000000–00600 | Revert migrations in reverse order |
| 2 | Deploy backend Phase 1 (dual-read, case_events, case_participants) | Redeploy previous backend |
| 3 | Deploy frontend: CaseWizardPage id resolution | Revert frontend |
| 4 | Monitor: case_events emission, error rates | Fix or rollback |
| 5 | Phase 2: Backfill relocation_cases → wizard_cases, migrate case_assignments | Restore from backup; revert migrations |
| 6 | Phase 2: Add FKs from case_assignments to wizard_cases | Drop FKs |
| 7 | Deprecate relocation_cases reads (optional) | Re-enable dual-read |

### Backfill Requirements

| Backfill | When | Script |
|----------|------|--------|
| case_participants | During migration 00200 | In-migration INSERT from case_assignments |
| canonical_case_id on case_events | Migration 00300 | In-migration UPDATE where case_id in wizard_cases |
| canonical_case_id on case_assignments + spine tables | Migration 00000 | In-migration UPDATE for wizard refs |
| relocation_cases.canonical_case_id | Phase 2 | Script: create wizard_cases from legacy, update relocation_cases |
| case_assignments.case_id for legacy | Phase 2 | UPDATE to canonical_case_id after legacy migration |

### Feature Flags

| Flag | Purpose | Default |
|------|---------|---------|
| `USE_CASE_EVENTS` | Emit to case_events on assignment transitions | true |
| `USE_CASE_PARTICIPANTS` | Backfill + use case_participants on assign | true |
| `USE_UNIFIED_CASE_LOOKUP` | Use get_case_from_wizard_or_legacy | true |
| `ALLOW_LEGACY_CASE_READ` | Fallback to relocation_cases | true |
| `REQUIRE_WIZARD_CASE_FOR_NEW` | Reject assignment create if case not in wizard | false (Phase 1), true (Phase 2) |

### Rollback Plan

1. **DB**: Migrations are additive (new tables, new columns). Rolling back = drop new tables/columns. `case_participants` and `case_evidence` can be dropped; `case_events` enhancements (payload, canonical_case_id) can be reverted. Type changes (uuid→text) are one-way.
2. **Backend**: Feature flags off + revert deploy. Dual-read is backward compatible.
3. **Frontend**: Revert CaseWizardPage changes. Old behavior: treat route param as case id. If that was assignment id, some flows may break; document that invite links must use case id in Phase 1 if we don't add resolution.
4. **Data**: No destructive migrations in Phase 1. Phase 2 backfill is reversible if we keep relocation_cases and case_assignments.case_id backup.

### Pre-Cutover Checklist

- [ ] All migrations run clean on staging
- [ ] Backfill case_participants row count matches case_assignments
- [ ] assignment status transitions write to case_events
- [ ] get_case_from_wizard_or_legacy returns correct case for wizard and legacy ids
- [ ] CaseWizardPage resolves assignment id → case id when needed
- [ ] No regression in HR dashboard, employee journey, resources page
