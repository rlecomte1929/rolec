-- Normalization persistence marker (transactional pipeline sets final state on commit).
-- Stub CREATE ensures this migration is safe to run before 20260331000000_policy_normalization.sql.
-- The full CREATE TABLE IF NOT EXISTS in that migration is a no-op when the table already exists.
-- FK on source_policy_document_id is omitted here because policy_documents is created later
-- (20260329000000_policy_documents.sql); the column is retained so the ADD COLUMN below and
-- subsequent migrations keep working.
begin;

create table if not exists public.policy_versions (
  id uuid primary key default gen_random_uuid(),
  policy_id uuid not null references public.company_policies(id) on delete cascade,
  source_policy_document_id uuid,
  version_number int not null default 1,
  status text not null default 'draft' check (
    status in ('draft', 'auto_generated', 'in_review', 'approved', 'archived')
  ),
  auto_generated boolean not null default false,
  review_status text default 'pending' check (
    review_status in ('pending', 'accepted', 'rejected', 'edited')
  ),
  confidence numeric,
  created_by text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.policy_versions
  add column if not exists normalization_state text;

comment on column public.policy_versions.normalization_state is
  'normalization_in_progress | normalization_failed | normalized_draft | normalized_complete';

commit;
