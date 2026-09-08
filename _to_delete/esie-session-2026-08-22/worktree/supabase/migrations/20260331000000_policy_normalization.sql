-- Canonical policy normalization layer
-- Links to company_policies and policy_documents for traceability
begin;

-- A. policy_versions
create table if not exists public.policy_versions (
  id uuid primary key default gen_random_uuid(),
  policy_id uuid not null references public.company_policies(id) on delete cascade,
  source_policy_document_id uuid references public.policy_documents(id) on delete set null,
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
create index if not exists idx_policy_versions_policy on public.policy_versions(policy_id);
create index if not exists idx_policy_versions_doc on public.policy_versions(source_policy_document_id);

-- B. policy_benefit_rules
create table if not exists public.policy_benefit_rules (
  id uuid primary key default gen_random_uuid(),
  policy_version_id uuid not null references public.policy_versions(id) on delete cascade,
  benefit_key text not null,
  benefit_category text not null,
  calc_type text check (
    calc_type in ('percent_salary', 'flat_amount', 'unit_cap', 'reimbursement', 'difference_only', 'per_diem', 'other')
  ),
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

-- C. policy_rule_conditions
create table if not exists public.policy_rule_conditions (
  id uuid primary key default gen_random_uuid(),
  policy_version_id uuid not null references public.policy_versions(id) on delete cascade,
  object_type text not null check (
    object_type in ('benefit_rule', 'exclusion', 'evidence_requirement')
  ),
  object_id uuid not null,
  condition_type text not null check (
    condition_type in (
      'assignment_type', 'family_status', 'duration_threshold',
      'accompanied_family', 'localization_exclusion', 'remote_location',
      'school_age_threshold', 'other'
    )
  ),
  condition_value_json jsonb not null default '{}',
  auto_generated boolean not null default true,
  review_status text default 'pending',
  confidence numeric,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_policy_rule_conditions_version on public.policy_rule_conditions(policy_version_id);
create index if not exists idx_policy_rule_conditions_object on public.policy_rule_conditions(object_type, object_id);

-- D. policy_exclusions
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

-- E. policy_evidence_requirements
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

-- F. policy_assignment_type_applicability
create table if not exists public.policy_assignment_type_applicability (
  id uuid primary key default gen_random_uuid(),
  policy_version_id uuid not null references public.policy_versions(id) on delete cascade,
  benefit_rule_id uuid not null references public.policy_benefit_rules(id) on delete cascade,
  assignment_type text not null
);
create index if not exists idx_policy_assignment_applicability on public.policy_assignment_type_applicability(policy_version_id);

-- G. policy_family_status_applicability
create table if not exists public.policy_family_status_applicability (
  id uuid primary key default gen_random_uuid(),
  policy_version_id uuid not null references public.policy_versions(id) on delete cascade,
  benefit_rule_id uuid not null references public.policy_benefit_rules(id) on delete cascade,
  family_status text not null
);
create index if not exists idx_policy_family_applicability on public.policy_family_status_applicability(policy_version_id);

-- H. policy_tier_overrides
create table if not exists public.policy_tier_overrides (
  id uuid primary key default gen_random_uuid(),
  policy_version_id uuid not null references public.policy_versions(id) on delete cascade,
  benefit_rule_id uuid not null references public.policy_benefit_rules(id) on delete cascade,
  tier_key text not null,
  override_limits_json jsonb not null default '{}'
);
create index if not exists idx_policy_tier_overrides on public.policy_tier_overrides(policy_version_id);

-- I. policy_source_links
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

-- RLS
alter table public.policy_versions enable row level security;
alter table public.policy_benefit_rules enable row level security;
alter table public.policy_rule_conditions enable row level security;
alter table public.policy_exclusions enable row level security;
alter table public.policy_evidence_requirements enable row level security;
alter table public.policy_assignment_type_applicability enable row level security;
alter table public.policy_family_status_applicability enable row level security;
alter table public.policy_tier_overrides enable row level security;
alter table public.policy_source_links enable row level security;

-- policy_versions: company-scoped via company_policies
create policy policy_versions_company on public.policy_versions for all to authenticated
  using (
    exists (
      select 1 from public.company_policies cp
      join public.profiles p on p.company_id = cp.company_id
      where cp.id = policy_versions.policy_id and (p.id = auth.uid()::text or p.role = 'ADMIN')
    )
  )
  with check (
    exists (
      select 1 from public.company_policies cp
      join public.profiles p on p.company_id = cp.company_id
      where cp.id = policy_versions.policy_id and (p.id = auth.uid()::text or p.role = 'ADMIN')
    )
  );

-- other tables: inherit from policy_version
create policy policy_benefit_rules_company on public.policy_benefit_rules for all to authenticated
  using (
    exists (
      select 1 from public.policy_versions pv
      join public.company_policies cp on cp.id = pv.policy_id
      join public.profiles p on p.company_id = cp.company_id
      where pv.id = policy_benefit_rules.policy_version_id and (p.id = auth.uid()::text or p.role = 'ADMIN')
    )
  )
  with check (
    exists (
      select 1 from public.policy_versions pv
      join public.company_policies cp on cp.id = pv.policy_id
      join public.profiles p on p.company_id = cp.company_id
      where pv.id = policy_benefit_rules.policy_version_id and (p.id = auth.uid()::text or p.role = 'ADMIN')
    )
  );

create policy policy_rule_conditions_company on public.policy_rule_conditions for all to authenticated
  using (
    exists (
      select 1 from public.policy_versions pv
      join public.company_policies cp on cp.id = pv.policy_id
      join public.profiles p on p.company_id = cp.company_id
      where pv.id = policy_rule_conditions.policy_version_id and (p.id = auth.uid()::text or p.role = 'ADMIN')
    )
  )
  with check (
    exists (
      select 1 from public.policy_versions pv
      join public.company_policies cp on cp.id = pv.policy_id
      join public.profiles p on p.company_id = cp.company_id
      where pv.id = policy_rule_conditions.policy_version_id and (p.id = auth.uid()::text or p.role = 'ADMIN')
    )
  );

create policy policy_exclusions_company on public.policy_exclusions for all to authenticated
  using (
    exists (
      select 1 from public.policy_versions pv
      join public.company_policies cp on cp.id = pv.policy_id
      join public.profiles p on p.company_id = cp.company_id
      where pv.id = policy_exclusions.policy_version_id and (p.id = auth.uid()::text or p.role = 'ADMIN')
    )
  )
  with check (
    exists (
      select 1 from public.policy_versions pv
      join public.company_policies cp on cp.id = pv.policy_id
      join public.profiles p on p.company_id = cp.company_id
      where pv.id = policy_exclusions.policy_version_id and (p.id = auth.uid()::text or p.role = 'ADMIN')
    )
  );

create policy policy_evidence_company on public.policy_evidence_requirements for all to authenticated
  using (
    exists (
      select 1 from public.policy_versions pv
      join public.company_policies cp on cp.id = pv.policy_id
      join public.profiles p on p.company_id = cp.company_id
      where pv.id = policy_evidence_requirements.policy_version_id and (p.id = auth.uid()::text or p.role = 'ADMIN')
    )
  )
  with check (
    exists (
      select 1 from public.policy_versions pv
      join public.company_policies cp on cp.id = pv.policy_id
      join public.profiles p on p.company_id = cp.company_id
      where pv.id = policy_evidence_requirements.policy_version_id and (p.id = auth.uid()::text or p.role = 'ADMIN')
    )
  );

create policy policy_assignment_app_company on public.policy_assignment_type_applicability for all to authenticated
  using (
    exists (
      select 1 from public.policy_versions pv
      join public.company_policies cp on cp.id = pv.policy_id
      join public.profiles p on p.company_id = cp.company_id
      where pv.id = policy_assignment_type_applicability.policy_version_id and (p.id = auth.uid()::text or p.role = 'ADMIN')
    )
  )
  with check (
    exists (
      select 1 from public.policy_versions pv
      join public.company_policies cp on cp.id = pv.policy_id
      join public.profiles p on p.company_id = cp.company_id
      where pv.id = policy_assignment_type_applicability.policy_version_id and (p.id = auth.uid()::text or p.role = 'ADMIN')
    )
  );

create policy policy_family_app_company on public.policy_family_status_applicability for all to authenticated
  using (
    exists (
      select 1 from public.policy_versions pv
      join public.company_policies cp on cp.id = pv.policy_id
      join public.profiles p on p.company_id = cp.company_id
      where pv.id = policy_family_status_applicability.policy_version_id and (p.id = auth.uid()::text or p.role = 'ADMIN')
    )
  )
  with check (
    exists (
      select 1 from public.policy_versions pv
      join public.company_policies cp on cp.id = pv.policy_id
      join public.profiles p on p.company_id = cp.company_id
      where pv.id = policy_family_status_applicability.policy_version_id and (p.id = auth.uid()::text or p.role = 'ADMIN')
    )
  );

create policy policy_tier_overrides_company on public.policy_tier_overrides for all to authenticated
  using (
    exists (
      select 1 from public.policy_versions pv
      join public.company_policies cp on cp.id = pv.policy_id
      join public.profiles p on p.company_id = cp.company_id
      where pv.id = policy_tier_overrides.policy_version_id and (p.id = auth.uid()::text or p.role = 'ADMIN')
    )
  )
  with check (
    exists (
      select 1 from public.policy_versions pv
      join public.company_policies cp on cp.id = pv.policy_id
      join public.profiles p on p.company_id = cp.company_id
      where pv.id = policy_tier_overrides.policy_version_id and (p.id = auth.uid()::text or p.role = 'ADMIN')
    )
  );

create policy policy_source_links_company on public.policy_source_links for all to authenticated
  using (
    exists (
      select 1 from public.policy_versions pv
      join public.company_policies cp on cp.id = pv.policy_id
      join public.profiles p on p.company_id = cp.company_id
      where pv.id = policy_source_links.policy_version_id and (p.id = auth.uid()::text or p.role = 'ADMIN')
    )
  )
  with check (
    exists (
      select 1 from public.policy_versions pv
      join public.company_policies cp on cp.id = pv.policy_id
      join public.profiles p on p.company_id = cp.company_id
      where pv.id = policy_source_links.policy_version_id and (p.id = auth.uid()::text or p.role = 'ADMIN')
    )
  );

commit;
