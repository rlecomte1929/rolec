# Phase 1 Step 2: case_participants Implementation

## Exact Files Changed

| File | Changes |
|------|---------|
| `supabase/migrations/20260322000000_case_participants.sql` | New migration: table + backfill |
| `backend/database.py` | SQLite table creation, `ensure_case_participant`, `list_case_participants` |
| `backend/main.py` | Wire `ensure_case_participant` in assignment creation and both claim paths |

---

## Migration SQL

```sql
-- supabase/migrations/20260322000000_case_participants.sql

begin;

create table if not exists public.case_participants (
  id uuid primary key default gen_random_uuid(),
  case_id text not null references public.wizard_cases(id) on delete cascade,
  person_id text not null,
  role text not null check (role in ('relocatee','hr_owner','hr_reviewer','observer')),
  invited_at timestamptz null,
  joined_at timestamptz null,
  created_at timestamptz not null default now(),
  unique(case_id, person_id, role)
);

create index if not exists idx_case_participants_case_id on public.case_participants (case_id);
create index if not exists idx_case_participants_person_id on public.case_participants (person_id);

-- Backfill from case_assignments
insert into public.case_participants (case_id, person_id, role, joined_at, created_at)
select ca.case_id, ca.hr_user_id, 'hr_owner', now(), now()
from public.case_assignments ca
where ca.hr_user_id is not null and ca.case_id is not null
  and exists (select 1 from public.wizard_cases wc where wc.id = ca.case_id)
on conflict (case_id, person_id, role) do nothing;

insert into public.case_participants (case_id, person_id, role, joined_at, created_at)
select ca.case_id, ca.employee_user_id::text, 'relocatee', now(), now()
from public.case_assignments ca
where ca.employee_user_id is not null and ca.case_id is not null
  and exists (select 1 from public.wizard_cases wc where wc.id = ca.case_id)
on conflict (case_id, person_id, role) do nothing;

commit;
```

---

## Exact Methods Added to Database

### ensure_case_participant

```python
def ensure_case_participant(
    self,
    case_id: str,
    person_id: str,
    role: str,
    invited_at: Optional[str] = None,
    joined_at: Optional[str] = None,
    request_id: Optional[str] = None,
) -> None:
```

- Upserts (insert or update on conflict) a row in `case_participants`
- Uses `op_name="ensure_case_participant"` for `db_op` timing logs
- Postgres: `ON CONFLICT (case_id, person_id, role) DO UPDATE SET ...`
- SQLite: same via `ON CONFLICT` (3.24+)

### list_case_participants

```python
def list_case_participants(
    self, case_id: str, request_id: Optional[str] = None
) -> List[Dict[str, Any]]:
```

- Returns participants for a case ordered by `created_at`
- Uses `op_name="list_case_participants"` for `db_op` timing logs

---

## Exact Call Sites Wired in main.py

| Location | Call |
|----------|------|
| **Assignment creation** (after `db.create_assignment`) | `db.ensure_case_participant(case_id, effective["id"], "hr_owner", joined_at=now_iso)` |
| **Claim (GET /assignments/current)** (after `attach_employee_to_assignment`) | `db.ensure_case_participant(case_id, effective["id"], "relocatee", joined_at=now_iso)` |
| **Claim (POST /assignments/{id}/claim)** (after `attach_employee_to_assignment`) | `db.ensure_case_participant(case_id, effective["id"], "relocatee", joined_at=now_iso)` |

---

## Manual SQL Verification Steps

### After migration (Postgres/Supabase)

```sql
-- 1. Table exists
SELECT COUNT(*) FROM public.case_participants;

-- 2. Backfill: hr_owner rows from case_assignments
SELECT cp.*, ca.id as assignment_id
FROM public.case_participants cp
JOIN public.case_assignments ca ON ca.case_id = cp.case_id AND ca.hr_user_id = cp.person_id
WHERE cp.role = 'hr_owner'
LIMIT 5;

-- 3. Backfill: relocatee rows
SELECT cp.*, ca.id as assignment_id
FROM public.case_participants cp
JOIN public.case_assignments ca ON ca.case_id = cp.case_id AND ca.employee_user_id::text = cp.person_id
WHERE cp.role = 'relocatee'
LIMIT 5;

-- 4. New assignment: after HR assigns, expect hr_owner
-- (trigger via UI, then)
SELECT * FROM public.case_participants WHERE case_id = '<case_id>' ORDER BY created_at DESC;

-- 5. New claim: after employee claims, expect relocatee
SELECT * FROM public.case_participants WHERE case_id = '<case_id>' AND role = 'relocatee';
```

### Local SQLite

```bash
sqlite3 relopass.db "SELECT * FROM case_participants LIMIT 5;"
```

---

## Rollback Notes

### Revert code

- Remove `ensure_case_participant` calls from `main.py` (3 call sites)
- Optionally remove `ensure_case_participant` and `list_case_participants` from `database.py`
- Optionally remove SQLite `case_participants` creation from `database.py` init_db

### Revert database (Postgres)

```sql
-- Drop table (cascade removes dependent objects if any)
DROP TABLE IF EXISTS public.case_participants;
```

### Rollback migration

If using Supabase migration history, add a down migration:

```sql
-- 20260322000001_case_participants_rollback.sql
DROP TABLE IF EXISTS public.case_participants;
```
