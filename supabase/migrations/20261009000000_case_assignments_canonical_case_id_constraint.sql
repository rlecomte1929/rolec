-- [AIQ-1720 S3 / AIQ-1732] Enforce the canonical_case_id 1:1 invariant on
-- public.case_assignments: NOT NULL + UNIQUE.
--
-- The resolver bridge (resolve_case_ids, AIQ-1704) has stood in for this; this migration
-- makes the invariant real so a single canonical id can be trusted everywhere. It is
-- applied ONLY AFTER the pre-launch data repair (AIQ-1737·3) brought the live stock to
-- 0 NULL / 0 dangling / 0 duplicate — a violating row would abort the ALTER otherwise.
-- AIQ-1737·4's rollback-tx already proved this exact ALTER applies cleanly against the
-- repaired data AND rejects both a NULL and a duplicate insert.
--
-- S1 verdict (docs/architecture/CASE_ID_UNIFICATION_AUDIT.md): plain UNIQUE + NOT NULL is
-- correct — every duplicate group was a data artifact (demo collision / seed batch / retry
-- dup), none a legitimate 1:N reassignment.
--   FUTURE CAVEAT: if assignment REASSIGNMENT is ever added (a case legitimately getting a
--   new active assignment), plain UNIQUE will block it — switch then to a partial UNIQUE on
--   active rows, or mint a fresh canonical per assignment.
--
-- Idempotent: SET NOT NULL is a no-op when already enforced; the UNIQUE add is guarded on
-- pg_constraint so re-apply is a no-op. Migration discipline (CLAUDE.md): applied
-- out-of-band (operator-run), then the ledger is reconciled by committing this file at the
-- applied version. Timestamp > prod ledger max 20261008000000.

begin;

-- 1. NOT NULL — canonical_case_id must always carry the resolved case id.
--    (No-op if already enforced; the AIQ-1737·2 fixtures use isolated schemas, unaffected.)
alter table public.case_assignments
  alter column canonical_case_id set not null;

-- 2. UNIQUE — one assignment per canonical case (the 1:1 invariant). Guarded so a
--    re-apply is a clean no-op.
do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'case_assignments_canonical_case_id_key'
      and conrelid = 'public.case_assignments'::regclass
  ) then
    alter table public.case_assignments
      add constraint case_assignments_canonical_case_id_key unique (canonical_case_id);
  end if;
end $$;

commit;
