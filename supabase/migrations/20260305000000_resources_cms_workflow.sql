-- Resources CMS: workflow, audit, visibility
-- Admin-only management; HR/Employee see only published content
begin;

-- Add workflow columns to country_resources
alter table public.country_resources add column if not exists status text not null default 'draft'
  check (status in ('draft', 'in_review', 'approved', 'published', 'archived'));
alter table public.country_resources add column if not exists created_by_user_id text;
alter table public.country_resources add column if not exists updated_by_user_id text;
alter table public.country_resources add column if not exists reviewed_by_user_id text;
alter table public.country_resources add column if not exists published_by_user_id text;
alter table public.country_resources add column if not exists review_notes text;
alter table public.country_resources add column if not exists internal_notes text;
alter table public.country_resources add column if not exists published_at timestamptz;
alter table public.country_resources add column if not exists reviewed_at timestamptz;
alter table public.country_resources add column if not exists archived_at timestamptz;
alter table public.country_resources add column if not exists version_number int not null default 1;
alter table public.country_resources add column if not exists parent_resource_id uuid references public.country_resources(id) on delete set null;
alter table public.country_resources add column if not exists is_visible_to_end_users boolean not null default false;

create index if not exists idx_country_resources_status on public.country_resources(status);
create index if not exists idx_country_resources_visible on public.country_resources(is_visible_to_end_users);

-- Add workflow columns to rkg_country_events
alter table public.rkg_country_events add column if not exists status text not null default 'draft'
  check (status in ('draft', 'in_review', 'approved', 'published', 'archived'));
alter table public.rkg_country_events add column if not exists created_by_user_id text;
alter table public.rkg_country_events add column if not exists updated_by_user_id text;
alter table public.rkg_country_events add column if not exists reviewed_by_user_id text;
alter table public.rkg_country_events add column if not exists published_by_user_id text;
alter table public.rkg_country_events add column if not exists review_notes text;
alter table public.rkg_country_events add column if not exists internal_notes text;
alter table public.rkg_country_events add column if not exists published_at timestamptz;
alter table public.rkg_country_events add column if not exists reviewed_at timestamptz;
alter table public.rkg_country_events add column if not exists archived_at timestamptz;
alter table public.rkg_country_events add column if not exists version_number int not null default 1;
alter table public.rkg_country_events add column if not exists parent_event_id uuid references public.rkg_country_events(id) on delete set null;
alter table public.rkg_country_events add column if not exists is_visible_to_end_users boolean not null default false;

create index if not exists idx_rkg_events_status on public.rkg_country_events(status);
create index if not exists idx_rkg_events_visible on public.rkg_country_events(is_visible_to_end_users);

-- resource_audit_log
create table if not exists public.resource_audit_log (
  id uuid primary key default gen_random_uuid(),
  entity_type text not null, -- resource, event, category, tag, source
  entity_id uuid not null,
  action_type text not null, -- create, update, submit_for_review, approve, publish, archive, delete, restore
  performed_by_user_id text not null,
  previous_status text,
  new_status text,
  change_summary text,
  created_at timestamptz not null default now()
);

create index if not exists idx_resource_audit_entity on public.resource_audit_log(entity_type, entity_id);
create index if not exists idx_resource_audit_created on public.resource_audit_log(created_at desc);

-- Add write columns to resource_categories for admin management
alter table public.resource_categories add column if not exists created_by_user_id text;
alter table public.resource_categories add column if not exists updated_by_user_id text;
alter table public.resource_sources add column if not exists created_by_user_id text;
alter table public.resource_sources add column if not exists updated_by_user_id text;
alter table public.resource_tags add column if not exists created_by_user_id text;
alter table public.resource_tags add column if not exists updated_by_user_id text;

-- RLS: drop broad read policies, add role-aware policies
-- Note: Supabase RLS uses auth.role() or auth.jwt(). For API-backed access we enforce in backend.
-- We keep permissive read for now (API filters) and add admin write policies.
-- Public/HR/Employee access is via API which filters status=published and is_visible_to_end_users.

-- Admin gets full access via service role in backend. For RLS with anon/key:
-- We'll use a simple approach: backend uses service_role for admin, and filters for public API.
-- Drop old policies if we want stricter RLS - for now keep reads open, restrict writes to backend.

-- Allow admin service role full access (backend uses get_supabase_admin_client)
-- For direct client access we'd need auth.uid() and a users/roles table.
-- Since Resources API is backend-mediated, RLS on these tables is secondary.
-- Add policy: allow all for service role (backend), anon reads only published (if using client)
-- Simplest: keep existing read policies; backend enforces write auth.

-- Add updated_at trigger for country_resources
create or replace function public.set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_country_resources_updated on public.country_resources;
create trigger trg_country_resources_updated
  before update on public.country_resources
  for each row execute function public.set_updated_at();

drop trigger if exists trg_rkg_country_events_updated on public.rkg_country_events;
create trigger trg_rkg_country_events_updated
  before update on public.rkg_country_events
  for each row execute function public.set_updated_at();

commit;
