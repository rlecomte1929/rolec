-- AIQ-756-FU2 — public.relocation_cases.id  text -> uuid (fresh-replay parity)
--
-- The Feb-21 baseline (20260221105601_remote_schema.sql) creates
-- public.relocation_cases.id as TEXT. On prod it was converted to uuid
-- out-of-band, so a fresh `supabase db reset` / Supabase Preview diverges: the
-- column stays text, and every later migration that adds a uuid case_id FK to
-- relocation_cases(id) fails with 42804 ("incompatible types: uuid and text").
-- The first to hit it is the BL-Compliance epic's compliance_alerts
-- (20260607000000); #304's immigration_cases / rfq_requests dodged it only via
-- replay-safe guards (so their FKs never materialised on a fresh DB).
--
-- This migration aligns a fresh DB to prod: convert relocation_cases.id to uuid
-- EARLY (immediately after 20260221124204 creates the relocation_runs/sources/
-- artifacts children), so from here on relocation_cases.id is uuid and all uuid
-- FK children — including the previously-guarded immigration_cases/rfq_requests
-- — link cleanly.
--
-- Prod-as-oracle reconciliation of the children (verified 2026-06-04):
--   * relocation_runs / relocation_sources / relocation_artifacts: on prod these
--     have case_id TEXT and NO FK to relocation_cases (the text FK that 124204
--     creates was dropped out-of-band). So drop those three FKs here (which also
--     unblocks the PK type change) and leave their case_id as text — matching
--     prod exactly.
--   * employee_tasks.case_id is text in-repo with no FK at this point; prod has
--     it uuid+FK. That is a separate, non-blocking parity gap (no FK = no replay
--     break) and is intentionally NOT addressed here.
--
-- GUARD: the whole block runs only when relocation_cases.id is still text, so on
-- prod (already uuid) and on any re-run it is a clean no-op. On a fresh replay
-- relocation_cases is empty at this point and its ids are uuid-format text, so
-- the cast is total.

begin;

do $$
begin
  if (select data_type
        from information_schema.columns
       where table_schema = 'public'
         and table_name   = 'relocation_cases'
         and column_name  = 'id') = 'text' then

    -- 1) Drop the text FKs created by 20260221124204 (prod has none).
    alter table public.relocation_runs      drop constraint if exists relocation_runs_case_id_fkey;
    alter table public.relocation_sources   drop constraint if exists relocation_sources_case_id_fkey;
    alter table public.relocation_artifacts drop constraint if exists relocation_artifacts_case_id_fkey;

    -- 2) Convert the primary-key column type text -> uuid.
    alter table public.relocation_cases alter column id drop default;
    alter table public.relocation_cases alter column id type uuid using id::uuid;
    alter table public.relocation_cases alter column id set default gen_random_uuid();

  end if;
end $$;

commit;
