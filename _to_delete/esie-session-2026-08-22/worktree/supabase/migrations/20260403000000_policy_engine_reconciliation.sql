-- Policy engine reconciliation: guarantees all policy tables exist in production.
-- Run when policy_documents, policy_versions, resolved_assignment_policies etc. are missing.
-- Idempotent: uses CREATE TABLE IF NOT EXISTS, DROP POLICY IF EXISTS.
-- Requires: company_policies, profiles (from earlier migrations).
begin;

-- 1. policy_documents
create table if not exists public.policy_documents (
  id uuid primary key default gen_random_uuid(),
  company_id text not null,
  uploaded_by_user_id text not null,
  filename text not null,
  mime_type text not null,
  storage_path text not null,
  checksum text,
  uploaded_at timestamptz not null default now(),
  processing_status text not null default 'uploaded' check (
    processing_status in (
      'uploaded', 'text_extracted', 'classified', 'normalized',
      'review_required', 'approved', 'failed'
    )
  ),
  detected_document_type text check (
    detected_document_type in (
      'assignment_policy', 'policy_summary', 'tax_policy',
      'country_addendum', 'unknown'
    )
  ),
  detected_policy_scope text check (
    detected_policy_scope in (
      'global', 'long_term_assignment', 'short_term_assignment',
      'tax_equalization', 'mixed', 'unknown'
    )
  ),
  version_label text,
  effective_date date,
  raw_text text,
  extraction_error text,
  extracted_metadata jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_policy_documents_company on public.policy_documents(company_id);
create index if not exists idx_policy_documents_status on public.policy_documents(processing_status);
create index if not exists idx_policy_documents_uploaded_at on public.policy_documents(uploaded_at desc);
alter table public.policy_documents enable row level security;
drop policy if exists policy_documents_hr on public.policy_documents;
create policy policy_documents_hr on public.policy_documents for all to authenticated
  using (exists (select 1 from public.profiles p where p.id = auth.uid()::text and (p.company_id = policy_documents.company_id or p.role = 'ADMIN')))
  with check (exists (select 1 from public.profiles p where p.id = auth.uid()::text and (p.company_id = policy_documents.company_id or p.role = 'ADMIN')));

-- 2. policy_document_clauses
create table if not exists public.policy_document_clauses (
  id uuid primary key default gen_random_uuid(),
  policy_document_id uuid not null references public.policy_documents(id) on delete cascade,
  section_label text,
  section_path text,
  clause_type text not null default 'unknown' check (
    clause_type in ('scope', 'eligibility', 'benefit', 'exclusion', 'approval_rule', 'evidence_rule', 'tax_rule', 'definition', 'lifecycle_rule', 'unknown')
  ),
  title text,
  raw_text text not null,
  normalized_hint_json jsonb,
  source_page_start integer,
  source_page_end integer,
  source_anchor text,
  confidence real default 0.5,
  hr_override_notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_policy_document_clauses_doc on public.policy_document_clauses(policy_document_id);
create index if not exists idx_policy_document_clauses_type on public.policy_document_clauses(clause_type);
create index if not exists idx_policy_document_clauses_section on public.policy_document_clauses(section_label);
alter table public.policy_document_clauses enable row level security;
drop policy if exists policy_document_clauses_hr on public.policy_document_clauses;
create policy policy_document_clauses_hr on public.policy_document_clauses for all to authenticated
  using (exists (select 1 from public.policy_documents pd join public.profiles p on p.company_id = pd.company_id where pd.id = policy_document_clauses.policy_document_id and (p.id = auth.uid()::text or p.role = 'ADMIN')))
  with check (exists (select 1 from public.policy_documents pd join public.profiles p on p.company_id = pd.company_id where pd.id = policy_document_clauses.policy_document_id and (p.id = auth.uid()::text or p.role = 'ADMIN')));

-- 3. policy_versions (includes published status)
create table if not exists public.policy_versions (
  id uuid primary key default gen_random_uuid(),
  policy_id uuid not null references public.company_policies(id) on delete cascade,
  source_policy_document_id uuid references public.policy_documents(id) on delete set null,
  version_number int not null default 1,
  status text not null default 'draft' check (
    status in ('draft', 'auto_generated', 'in_review', 'approved', 'archived', 'review_required', 'reviewed', 'published')
  ),
  auto_generated boolean not null default false,
  review_status text default 'pending' check (review_status in ('pending', 'accepted', 'rejected', 'edited')),
  confidence numeric,
  created_by text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_policy_versions_policy on public.policy_versions(policy_id);
create index if not exists idx_policy_versions_doc on public.policy_versions(source_policy_document_id);
alter table public.policy_versions enable row level security;
drop policy if exists policy_versions_company on public.policy_versions;
create policy policy_versions_company on public.policy_versions for all to authenticated
  using (exists (select 1 from public.company_policies cp join public.profiles p on p.company_id = cp.company_id where cp.id = policy_versions.policy_id and (p.id = auth.uid()::text or p.role = 'ADMIN')))
  with check (exists (select 1 from public.company_policies cp join public.profiles p on p.company_id = cp.company_id where cp.id = policy_versions.policy_id and (p.id = auth.uid()::text or p.role = 'ADMIN')));

-- 4. policy_benefit_rules
create table if not exists public.policy_benefit_rules (
  id uuid primary key default gen_random_uuid(),
  policy_version_id uuid not null references public.policy_versions(id) on delete cascade,
  benefit_key text not null,
  benefit_category text not null,
  calc_type text check (calc_type in ('percent_salary', 'flat_amount', 'unit_cap', 'reimbursement', 'difference_only', 'per_diem', 'other')),
  amount_value numeric,
  amount_unit text,
  currency text,
  frequency text,
  description text,
  metadata_json jsonb,
  auto_generated boolean not null default true,
  review_status text default 'pending',
  confidence numeric,
  raw_text text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_policy_benefit_rules_version on public.policy_benefit_rules(policy_version_id);
create index if not exists idx_policy_benefit_rules_key on public.policy_benefit_rules(benefit_key);
alter table public.policy_benefit_rules enable row level security;
drop policy if exists policy_benefit_rules_company on public.policy_benefit_rules;
create policy policy_benefit_rules_company on public.policy_benefit_rules for all to authenticated
  using (exists (select 1 from public.policy_versions pv join public.company_policies cp on cp.id = pv.policy_id join public.profiles p on p.company_id = cp.company_id where pv.id = policy_benefit_rules.policy_version_id and (p.id = auth.uid()::text or p.role = 'ADMIN')))
  with check (exists (select 1 from public.policy_versions pv join public.company_policies cp on cp.id = pv.policy_id join public.profiles p on p.company_id = cp.company_id where pv.id = policy_benefit_rules.policy_version_id and (p.id = auth.uid()::text or p.role = 'ADMIN')));

-- 5. policy_rule_conditions
create table if not exists public.policy_rule_conditions (
  id uuid primary key default gen_random_uuid(),
  policy_version_id uuid not null references public.policy_versions(id) on delete cascade,
  object_type text not null check (object_type in ('benefit_rule', 'exclusion', 'evidence_requirement')),
  object_id uuid not null,
  condition_type text not null check (condition_type in ('assignment_type', 'family_status', 'duration_threshold', 'accompanied_family', 'localization_exclusion', 'remote_location', 'school_age_threshold', 'other')),
  condition_value_json jsonb not null default '{}',
  auto_generated boolean not null default true,
  review_status text default 'pending',
  confidence numeric,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_policy_rule_conditions_version on public.policy_rule_conditions(policy_version_id);
create index if not exists idx_policy_rule_conditions_object on public.policy_rule_conditions(object_type, object_id);
alter table public.policy_rule_conditions enable row level security;
drop policy if exists policy_rule_conditions_company on public.policy_rule_conditions;
create policy policy_rule_conditions_company on public.policy_rule_conditions for all to authenticated
  using (exists (select 1 from public.policy_versions pv join public.company_policies cp on cp.id = pv.policy_id join public.profiles p on p.company_id = cp.company_id where pv.id = policy_rule_conditions.policy_version_id and (p.id = auth.uid()::text or p.role = 'ADMIN')))
  with check (exists (select 1 from public.policy_versions pv join public.company_policies cp on cp.id = pv.policy_id join public.profiles p on p.company_id = cp.company_id where pv.id = policy_rule_conditions.policy_version_id and (p.id = auth.uid()::text or p.role = 'ADMIN')));

-- 6. policy_exclusions
create table if not exists public.policy_exclusions (
  id uuid primary key default gen_random_uuid(),
  policy_version_id uuid not null references public.policy_versions(id) on delete cascade,
  benefit_key text,
  domain text not null,
  description text,
  auto_generated boolean not null default true,
  review_status text default 'pending',
  confidence numeric,
  raw_text text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_policy_exclusions_version on public.policy_exclusions(policy_version_id);
alter table public.policy_exclusions enable row level security;
drop policy if exists policy_exclusions_company on public.policy_exclusions;
create policy policy_exclusions_company on public.policy_exclusions for all to authenticated
  using (exists (select 1 from public.policy_versions pv join public.company_policies cp on cp.id = pv.policy_id join public.profiles p on p.company_id = cp.company_id where pv.id = policy_exclusions.policy_version_id and (p.id = auth.uid()::text or p.role = 'ADMIN')))
  with check (exists (select 1 from public.policy_versions pv join public.company_policies cp on cp.id = pv.policy_id join public.profiles p on p.company_id = cp.company_id where pv.id = policy_exclusions.policy_version_id and (p.id = auth.uid()::text or p.role = 'ADMIN')));

-- 7. policy_evidence_requirements
create table if not exists public.policy_evidence_requirements (
  id uuid primary key default gen_random_uuid(),
  policy_version_id uuid not null references public.policy_versions(id) on delete cascade,
  benefit_rule_id uuid references public.policy_benefit_rules(id) on delete set null,
  evidence_items_json jsonb not null default '[]',
  description text,
  auto_generated boolean not null default true,
  review_status text default 'pending',
  confidence numeric,
  raw_text text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_policy_evidence_version on public.policy_evidence_requirements(policy_version_id);
alter table public.policy_evidence_requirements enable row level security;
drop policy if exists policy_evidence_company on public.policy_evidence_requirements;
create policy policy_evidence_company on public.policy_evidence_requirements for all to authenticated
  using (exists (select 1 from public.policy_versions pv join public.company_policies cp on cp.id = pv.policy_id join public.profiles p on p.company_id = cp.company_id where pv.id = policy_evidence_requirements.policy_version_id and (p.id = auth.uid()::text or p.role = 'ADMIN')))
  with check (exists (select 1 from public.policy_versions pv join public.company_policies cp on cp.id = pv.policy_id join public.profiles p on p.company_id = cp.company_id where pv.id = policy_evidence_requirements.policy_version_id and (p.id = auth.uid()::text or p.role = 'ADMIN')));

-- 8. policy_assignment_type_applicability
create table if not exists public.policy_assignment_type_applicability (
  id uuid primary key default gen_random_uuid(),
  policy_version_id uuid not null references public.policy_versions(id) on delete cascade,
  benefit_rule_id uuid not null references public.policy_benefit_rules(id) on delete cascade,
  assignment_type text not null
);
create index if not exists idx_policy_assignment_applicability on public.policy_assignment_type_applicability(policy_version_id);
alter table public.policy_assignment_type_applicability enable row level security;
drop policy if exists policy_assignment_app_company on public.policy_assignment_type_applicability;
create policy policy_assignment_app_company on public.policy_assignment_type_applicability for all to authenticated
  using (exists (select 1 from public.policy_versions pv join public.company_policies cp on cp.id = pv.policy_id join public.profiles p on p.company_id = cp.company_id where pv.id = policy_assignment_type_applicability.policy_version_id and (p.id = auth.uid()::text or p.role = 'ADMIN')))
  with check (exists (select 1 from public.policy_versions pv join public.company_policies cp on cp.id = pv.policy_id join public.profiles p on p.company_id = cp.company_id where pv.id = policy_assignment_type_applicability.policy_version_id and (p.id = auth.uid()::text or p.role = 'ADMIN')));

-- 9. policy_family_status_applicability
create table if not exists public.policy_family_status_applicability (
  id uuid primary key default gen_random_uuid(),
  policy_version_id uuid not null references public.policy_versions(id) on delete cascade,
  benefit_rule_id uuid not null references public.policy_benefit_rules(id) on delete cascade,
  family_status text not null
);
create index if not exists idx_policy_family_applicability on public.policy_family_status_applicability(policy_version_id);
alter table public.policy_family_status_applicability enable row level security;
drop policy if exists policy_family_app_company on public.policy_family_status_applicability;
create policy policy_family_app_company on public.policy_family_status_applicability for all to authenticated
  using (exists (select 1 from public.policy_versions pv join public.company_policies cp on cp.id = pv.policy_id join public.profiles p on p.company_id = cp.company_id where pv.id = policy_family_status_applicability.policy_version_id and (p.id = auth.uid()::text or p.role = 'ADMIN')))
  with check (exists (select 1 from public.policy_versions pv join public.company_policies cp on cp.id = pv.policy_id join public.profiles p on p.company_id = cp.company_id where pv.id = policy_family_status_applicability.policy_version_id and (p.id = auth.uid()::text or p.role = 'ADMIN')));

-- 10. policy_tier_overrides
create table if not exists public.policy_tier_overrides (
  id uuid primary key default gen_random_uuid(),
  policy_version_id uuid not null references public.policy_versions(id) on delete cascade,
  benefit_rule_id uuid not null references public.policy_benefit_rules(id) on delete cascade,
  tier_key text not null,
  override_limits_json jsonb not null default '{}'
);
create index if not exists idx_policy_tier_overrides on public.policy_tier_overrides(policy_version_id);
alter table public.policy_tier_overrides enable row level security;
drop policy if exists policy_tier_overrides_company on public.policy_tier_overrides;
create policy policy_tier_overrides_company on public.policy_tier_overrides for all to authenticated
  using (exists (select 1 from public.policy_versions pv join public.company_policies cp on cp.id = pv.policy_id join public.profiles p on p.company_id = cp.company_id where pv.id = policy_tier_overrides.policy_version_id and (p.id = auth.uid()::text or p.role = 'ADMIN')))
  with check (exists (select 1 from public.policy_versions pv join public.company_policies cp on cp.id = pv.policy_id join public.profiles p on p.company_id = cp.company_id where pv.id = policy_tier_overrides.policy_version_id and (p.id = auth.uid()::text or p.role = 'ADMIN')));

-- 11. policy_source_links
create table if not exists public.policy_source_links (
  id uuid primary key default gen_random_uuid(),
  policy_version_id uuid not null references public.policy_versions(id) on delete cascade,
  object_type text not null,
  object_id uuid not null,
  clause_id uuid not null references public.policy_document_clauses(id) on delete cascade,
  source_page_start int,
  source_page_end int,
  source_anchor text
);
create index if not exists idx_policy_source_links_version on public.policy_source_links(policy_version_id);
create index if not exists idx_policy_source_links_object on public.policy_source_links(object_type, object_id);
alter table public.policy_source_links enable row level security;
drop policy if exists policy_source_links_company on public.policy_source_links;
create policy policy_source_links_company on public.policy_source_links for all to authenticated
  using (exists (select 1 from public.policy_versions pv join public.company_policies cp on cp.id = pv.policy_id join public.profiles p on p.company_id = cp.company_id where pv.id = policy_source_links.policy_version_id and (p.id = auth.uid()::text or p.role = 'ADMIN')))
  with check (exists (select 1 from public.policy_versions pv join public.company_policies cp on cp.id = pv.policy_id join public.profiles p on p.company_id = cp.company_id where pv.id = policy_source_links.policy_version_id and (p.id = auth.uid()::text or p.role = 'ADMIN')));

-- 12. resolved_assignment_policies
create table if not exists public.resolved_assignment_policies (
  id uuid primary key default gen_random_uuid(),
  assignment_id text not null,
  case_id text,
  company_id text not null,
  policy_id uuid not null references public.company_policies(id) on delete cascade,
  policy_version_id uuid not null references public.policy_versions(id) on delete cascade,
  canonical_case_id text,
  resolution_status text not null default 'ok' check (resolution_status in ('ok', 'partial', 'review_needed', 'no_policy')),
  resolved_at timestamptz not null default now(),
  resolution_context_json jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(assignment_id)
);
create index if not exists idx_resolved_policies_assignment on public.resolved_assignment_policies(assignment_id);
create index if not exists idx_resolved_policies_case on public.resolved_assignment_policies(case_id);
create index if not exists idx_resolved_policies_company on public.resolved_assignment_policies(company_id);

-- 13. resolved_assignment_policy_benefits
create table if not exists public.resolved_assignment_policy_benefits (
  id uuid primary key default gen_random_uuid(),
  resolved_policy_id uuid not null references public.resolved_assignment_policies(id) on delete cascade,
  benefit_key text not null,
  included boolean not null default true,
  min_value numeric,
  standard_value numeric,
  max_value numeric,
  currency text,
  amount_unit text,
  frequency text,
  approval_required boolean not null default false,
  evidence_required_json jsonb not null default '[]',
  exclusions_json jsonb not null default '[]',
  condition_summary text,
  source_rule_ids_json jsonb not null default '[]',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_resolved_benefits_policy on public.resolved_assignment_policy_benefits(resolved_policy_id);
create index if not exists idx_resolved_benefits_key on public.resolved_assignment_policy_benefits(benefit_key);

-- 14. resolved_assignment_policy_exclusions
create table if not exists public.resolved_assignment_policy_exclusions (
  id uuid primary key default gen_random_uuid(),
  resolved_policy_id uuid not null references public.resolved_assignment_policies(id) on delete cascade,
  benefit_key text,
  domain text not null,
  description text,
  source_rule_ids_json jsonb not null default '[]'
);
create index if not exists idx_resolved_exclusions_policy on public.resolved_assignment_policy_exclusions(resolved_policy_id);

-- 15. assignment_policy_service_comparisons
create table if not exists public.assignment_policy_service_comparisons (
  id uuid primary key default gen_random_uuid(),
  assignment_id text not null,
  case_id text,
  canonical_case_id text,
  resolved_policy_id uuid references public.resolved_assignment_policies(id) on delete cascade,
  service_category text not null,
  requested_value_json jsonb not null default '{}',
  policy_status text not null check (policy_status in ('included', 'capped', 'approval_required', 'excluded', 'partial', 'out_of_scope')),
  policy_min_value numeric,
  policy_standard_value numeric,
  policy_max_value numeric,
  currency text,
  amount_unit text,
  variance_json jsonb not null default '{}',
  explanation text,
  evidence_required_json jsonb not null default '[]',
  approval_required boolean not null default false,
  source_rule_ids_json jsonb not null default '[]',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_comparisons_assignment on public.assignment_policy_service_comparisons(assignment_id);
create index if not exists idx_comparisons_resolved_policy on public.assignment_policy_service_comparisons(resolved_policy_id);

commit;
