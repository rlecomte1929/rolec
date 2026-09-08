-- Section C of HR Policy: per-jurisdiction × employee_level × assignment_type
-- override rows that hang off a base policy_config_benefits row.
--
-- Why a separate table: the existing benefit row already carries broadcast
-- targeting (assignment_types[], employee_levels[], family_statuses[]).
-- Section C is different: it answers "for THIS benefit, override the cap
-- when the employee is in country X and at level Y." That's a stacking
-- model, not a broadcast model — adding more columns to the benefit row
-- would not let HR author multiple overrides per benefit.
--
-- jurisdiction_countries is a text[] (ISO-3166 alpha-2) so HR can group
-- countries that share the same override (e.g. {'SG','MY','TH'} = SEA
-- bucket). Empty array is rejected at validation time.
--
-- Resolution order (implemented in services/policy_section_c_resolver.py):
--   1. Filter override rows whose jurisdiction_countries contain the
--      employee's destination country.
--   2. Score each by specificity: employee_level match (+2),
--      assignment_type match (+1). NULL on either dimension is a wildcard
--      that matches but scores zero on that axis.
--   3. Highest score wins; tie -> highest display_order; tie -> most
--      recent updated_at.
--   4. If no override matches, the base policy_config_benefits row applies.

begin;

create table if not exists public.policy_benefit_jurisdiction_overrides (
  id uuid primary key default gen_random_uuid(),
  benefit_row_id uuid not null
    references public.policy_config_benefits (id) on delete cascade,
  jurisdiction_countries text[] not null,
  -- Nullable axes: NULL means "wildcard" — applies regardless of the
  -- employee's value on that axis but scores zero in the specificity tie-
  -- break, so a more-specific row wins.
  employee_level text
    check (employee_level in ('entry', 'manager', 'director', 'vp', 'c_suite')),
  assignment_type text,
  -- Optional override values. NULL means "inherit from base row" — useful
  -- when HR only wants to override the markdown clauses for a region but
  -- keep the cap unchanged.
  amount_value numeric,
  currency_code text,
  cap_rule_json jsonb not null default '{}',
  reimbursement_md text,
  repayment_md text,
  display_order int not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  -- Same (level, assignment_type) tuple cannot be authored twice for the
  -- same benefit. Different country lists are fine - HR can split
  -- {'SG','MY'} into two rows later if they diverge. NULLs in unique
  -- constraints don't collide in Postgres, so wildcard rows can coexist.
  unique (benefit_row_id, employee_level, assignment_type)
);

-- Hot path: resolver queries by benefit_row_id, then array-contains for
-- the employee's country.
create index if not exists idx_pbjo_benefit
  on public.policy_benefit_jurisdiction_overrides (benefit_row_id);
create index if not exists idx_pbjo_countries
  on public.policy_benefit_jurisdiction_overrides
  using gin (jurisdiction_countries);

comment on table public.policy_benefit_jurisdiction_overrides is
  'Section C of HR Policy: per-jurisdiction overrides that stack on top of a base policy_config_benefits row. See services/policy_section_c_resolver.py for resolution semantics.';

-- updated_at trigger (clone of the standard pattern used by other
-- policy_config_* tables).
create or replace function public.policy_benefit_jurisdiction_overrides_set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

drop trigger if exists trg_pbjo_set_updated_at
  on public.policy_benefit_jurisdiction_overrides;
create trigger trg_pbjo_set_updated_at
  before update on public.policy_benefit_jurisdiction_overrides
  for each row execute function public.policy_benefit_jurisdiction_overrides_set_updated_at();

alter table public.policy_benefit_jurisdiction_overrides enable row level security;

-- RLS clones policy_config_benefits' pattern: traverse override -> benefit
-- -> version -> config -> company, gated by HR/ADMIN role on profiles.
-- Both USING and WITH CHECK enforce the same predicate so HR can't insert
-- overrides into another company's policy.
create policy pbjo_rw on public.policy_benefit_jurisdiction_overrides
  for all to authenticated
  using (
    exists (
      select 1
      from public.policy_config_benefits b
      join public.policy_config_versions v on v.id = b.policy_config_version_id
      join public.policy_configs c on c.id = v.policy_config_id
      join public.profiles p on p.id = auth.uid()::text
      where b.id = policy_benefit_jurisdiction_overrides.benefit_row_id
        and (
          p.role = 'ADMIN'
          or (p.role = 'HR' and p.company_id = c.company_id)
        )
    )
  )
  with check (
    exists (
      select 1
      from public.policy_config_benefits b
      join public.policy_config_versions v on v.id = b.policy_config_version_id
      join public.policy_configs c on c.id = v.policy_config_id
      join public.profiles p on p.id = auth.uid()::text
      where b.id = policy_benefit_jurisdiction_overrides.benefit_row_id
        and (
          p.role = 'ADMIN'
          or (p.role = 'HR' and p.company_id = c.company_id)
        )
    )
  );

-- Audit trigger (mirrors the pattern used by other policy_config_* tables).
drop trigger if exists trg_audit_pbjo
  on public.policy_benefit_jurisdiction_overrides;
create trigger trg_audit_pbjo
  after insert or update or delete on public.policy_benefit_jurisdiction_overrides
  for each row execute function public.relopass_audit_row();

commit;
