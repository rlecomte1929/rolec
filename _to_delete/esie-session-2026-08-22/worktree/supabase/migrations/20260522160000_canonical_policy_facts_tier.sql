-- [P5-9 C1] Add tier column to canonical_policy_facts so that retrieval
-- can enforce tier isolation between Manager / Senior / Executive etc.
--
-- NULL = applies to all tiers (e.g. universal policy intro facts).
-- A populated value MUST match the caller's resolved tier exactly
-- (case-sensitive) to be returned by the policy assistant.
--
-- Retrieval filter (in services/policy_query_answering.py):
--   WHERE company_id = $1 AND (tier IS NULL OR tier = $caller_tier)
--
-- REPLAY-SAFE GUARD (2026-06-03):
-- public.canonical_policy_facts is created out-of-band (no tracked CREATE
-- migration — see audit/migration-drift-definitive-2026-06-02.md, reverse-drift
-- entry 7). This migration was never applied to prod, so on a fresh
-- `supabase db reset` the table does not exist and the bare ALTER aborts the
-- whole replay (ERROR 42P01). Guarding on to_regclass lets replay walk past on
-- a clean DB while still applying the column idempotently anywhere the table
-- exists. Prod-verified 2026-06-03: table present, tier column absent, this
-- migration name absent from supabase_migrations.schema_migrations.

do $$
begin
  if to_regclass('public.canonical_policy_facts') is not null then
    alter table public.canonical_policy_facts
      add column if not exists tier text;

    create index if not exists idx_canonical_policy_facts_company_tier
      on public.canonical_policy_facts (company_id, tier);

    comment on column public.canonical_policy_facts.tier is
      'Policy tier this fact applies to (Manager/Senior/Executive/etc.). '
      'NULL = universal (all tiers). Retrieval path filters by '
      '(tier IS NULL OR tier = caller_tier) per P5-9 C1.';
  end if;
end $$;
