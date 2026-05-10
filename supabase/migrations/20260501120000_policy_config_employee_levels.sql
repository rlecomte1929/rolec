-- Compensation & Allowance matrix: add `employee_levels` targeting axis.
--
-- Third targeting dimension alongside assignment_types / family_statuses.
-- Canonical values: entry | manager | director | vp | c_suite.
-- Empty array = "applies to all levels" (back-compat: every existing
-- matrix row implicitly matches every level until HR edits it).
--
-- No data migration needed — the NOT NULL DEFAULT '[]' fills existing
-- rows with the same effective semantics they had before.
--
-- The UNIQUE (policy_config_version_id, benefit_key, targeting_signature)
-- constraint keeps working because the service recomputes
-- targeting_signature including this new axis. Rows that never get
-- employee_levels set retain their prior 2-axis or "global" signature,
-- so no existing uniqueness collisions are introduced.

begin;

alter table public.policy_config_benefits
  add column if not exists employee_levels jsonb not null default '[]'::jsonb;

-- Optional lightweight index for HR UIs that filter by level; safe to
-- drop later if query planner prefers a partial or GIN index.
create index if not exists idx_pc_benefits_employee_levels
  on public.policy_config_benefits
  using gin (employee_levels);

commit;
