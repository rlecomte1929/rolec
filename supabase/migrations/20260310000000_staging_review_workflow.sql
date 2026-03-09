-- Staging review workflow: audit log, review reason, promoted references
begin;

-- staging_review_audit_log
create table if not exists public.staging_review_audit_log (
  id uuid primary key default gen_random_uuid(),
  entity_type text not null, -- staged_resource, staged_event
  entity_id uuid not null,
  action_type text not null, -- approve_new, merge, reject, mark_duplicate, ignore, restore_review
  performed_by_user_id text not null,
  target_live_id uuid,
  merge_mode text,
  review_reason text,
  change_summary text,
  created_at timestamptz not null default now()
);

create index if not exists idx_staging_audit_entity on public.staging_review_audit_log(entity_type, entity_id);
create index if not exists idx_staging_audit_performed on public.staging_review_audit_log(performed_by_user_id);
create index if not exists idx_staging_audit_created on public.staging_review_audit_log(created_at desc);

alter table public.staging_review_audit_log enable row level security;
create policy "staging_audit_admin" on public.staging_review_audit_log for all using (true) with check (true);

-- Add review_reason and promoted_live_resource_id to staged_resource_candidates
alter table public.staged_resource_candidates
  add column if not exists review_reason text,
  add column if not exists promoted_live_resource_id uuid;

-- Add review_reason and promoted_live_event_id to staged_event_candidates
alter table public.staged_event_candidates
  add column if not exists review_reason text,
  add column if not exists promoted_live_event_id uuid;

-- Extend status constraint: allow approved_new, approved_merged, duplicate, ignored, error
-- (Postgres check: we use text, so no constraint change needed; ensure app accepts these)
commit;
