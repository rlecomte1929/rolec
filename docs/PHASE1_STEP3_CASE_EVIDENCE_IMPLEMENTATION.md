# Phase 1 Step 3: case_evidence Implementation

## Exact Files Changed

| File | Changes |
|------|---------|
| `supabase/migrations/20260323000000_case_evidence.sql` | New migration: table, indexes, comment |
| `backend/database.py` | SQLite table creation, `insert_case_evidence`, `list_case_evidence`, `list_assignment_evidence` |
| `backend/schemas.py` | `AddEvidenceRequest`, `AddEvidenceResponse` |
| `backend/main.py` | `POST /api/assignments/{assignment_id}/evidence`, `GET /api/cases/{case_id}/evidence` |

---

## Migration SQL

```sql
-- supabase/migrations/20260323000000_case_evidence.sql

begin;

create table if not exists public.case_evidence (
  id uuid primary key default gen_random_uuid(),
  case_id text not null references public.wizard_cases(id) on delete cascade,
  assignment_id text null references public.case_assignments(id) on delete set null,
  participant_id text null,
  requirement_id text null,
  evidence_type text not null,
  file_url text null,
  metadata jsonb not null default '{}',
  status text not null default 'submitted' check (status in ('submitted','verified','rejected')),
  submitted_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create index if not exists idx_case_evidence_case_id on public.case_evidence (case_id);
create index if not exists idx_case_evidence_assignment_id on public.case_evidence (assignment_id);
create index if not exists idx_case_evidence_participant_id on public.case_evidence (participant_id);
create index if not exists idx_case_evidence_requirement_id on public.case_evidence (requirement_id);

comment on table public.case_evidence is 'Phase 1 evidence primitive. Stores submitted evidence items per case/assignment.';

commit;
```

---

## Database Methods Added

| Method | Signature | Description |
|--------|-----------|-------------|
| `insert_case_evidence` | `(case_id, assignment_id, participant_id, requirement_id, evidence_type, file_url=None, metadata=None, status='submitted', request_id=None)` | Inserts a row; returns evidence `id` |
| `list_case_evidence` | `(case_id, request_id=None)` | Returns list of evidence for a case, newest first |
| `list_assignment_evidence` | `(assignment_id, request_id=None)` | Returns list of evidence for an assignment, newest first |

All use `_exec` with `op_name` for db_op timing logs.

---

## Route Handlers Added

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/assignments/{assignment_id}/evidence` | require_hr_or_employee | Insert evidence; derives `case_id` from assignment |
| GET | `/api/cases/{case_id}/evidence` | require_hr_or_employee | List evidence for a case |

---

## Request/Response Shapes

**POST /api/assignments/{assignment_id}/evidence**

Request body:
```json
{
  "evidenceType": "passport_scan",
  "participantId": null,
  "requirementId": null,
  "fileUrl": "https://...",
  "metadata": {}
}
```

Response:
```json
{
  "evidenceId": "uuid"
}
```

**GET /api/cases/{case_id}/evidence**

Response:
```json
{
  "case_id": "case-uuid",
  "evidence": [
    {
      "id": "uuid",
      "case_id": "case-uuid",
      "assignment_id": "assignment-uuid",
      "participant_id": null,
      "requirement_id": null,
      "evidence_type": "passport_scan",
      "file_url": "https://...",
      "metadata": {},
      "status": "submitted",
      "submitted_at": "...",
      "created_at": "..."
    }
  ]
}
```

---

## Manual Verification SQL

```sql
-- 1. Check table exists
SELECT EXISTS (SELECT 1 FROM information_schema.tables 
  WHERE table_schema = 'public' AND table_name = 'case_evidence');

-- 2. Inspect schema
\d public.case_evidence

-- 3. Count rows (after inserts)
SELECT COUNT(*) FROM public.case_evidence;

-- 4. Sample rows
SELECT id, case_id, assignment_id, evidence_type, status, created_at 
FROM public.case_evidence 
ORDER BY created_at DESC LIMIT 5;
```

---

## Rollback Notes

To rollback the migration:

```sql
begin;
drop index if exists public.idx_case_evidence_requirement_id;
drop index if exists public.idx_case_evidence_participant_id;
drop index if exists public.idx_case_evidence_assignment_id;
drop index if exists public.idx_case_evidence_case_id;
drop table if exists public.case_evidence;
commit;
```

Backend changes (Database methods, endpoints, schemas) can be reverted via git. No data migration of legacy `employee_answers` or `compliance_reports` was performed.

---

## Limitation: wizard_cases FK

`case_evidence.case_id` references `wizard_cases(id)`. Assignments created via HR Dashboard use `relocation_cases` for `case_id`. Inserting evidence for such assignments will return 400 with:

> "Evidence requires case_id in wizard_cases. HR-created cases use relocation_cases."

Evidence insertion works for assignments whose `case_id` exists in `wizard_cases` (e.g. employee wizard flow).
