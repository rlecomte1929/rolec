-- Teardown for verify_fresh_onboarding.py.
-- Deletes every throwaway tenant the probe creates: companies named 'Probe %'
-- and accounts under @probe.test, plus all dependent case/policy/identity rows.
-- Scoped by name/email only (no hardcoded ids), so it cleans ALL probe runs.
-- Run via the Supabase MCP (`execute_sql`) — db push is drift-blocked.
-- Idempotent and safe to run repeatedly.
BEGIN;

-- Resolve the probe tenant set once.
CREATE TEMP TABLE _probe_companies ON COMMIT DROP AS
  SELECT id::text AS id FROM companies WHERE name LIKE 'Probe %';
CREATE TEMP TABLE _probe_cases ON COMMIT DROP AS
  SELECT id::text AS cid FROM relocation_cases WHERE company_id::text IN (SELECT id FROM _probe_companies)
  UNION
  SELECT case_id FROM case_assignments WHERE employee_identifier LIKE '%@probe.test';

-- Case-scoped children first.
DELETE FROM case_forms WHERE case_id::text IN (SELECT cid FROM _probe_cases);
DELETE FROM assignment_claim_invites WHERE assignment_id IN (
  SELECT id FROM case_assignments WHERE case_id IN (SELECT cid FROM _probe_cases));
DELETE FROM case_assignments WHERE case_id IN (SELECT cid FROM _probe_cases)
  OR employee_identifier LIKE '%@probe.test';
DELETE FROM public.cases WHERE id::text IN (SELECT cid FROM _probe_cases);
DELETE FROM wizard_cases WHERE id IN (SELECT cid FROM _probe_cases);
DELETE FROM relocation_cases WHERE id::text IN (SELECT cid FROM _probe_cases)
  OR company_id::text IN (SELECT id FROM _probe_companies);

-- Policy: policy_configs(company_id) -> versions(policy_config_id) -> benefits(version_id).
DELETE FROM policy_config_benefits WHERE policy_config_version_id IN (
  SELECT v.id FROM policy_config_versions v JOIN policy_configs c ON c.id = v.policy_config_id
  WHERE c.company_id::text IN (SELECT id FROM _probe_companies));
DELETE FROM policy_config_versions WHERE policy_config_id IN (
  SELECT id FROM policy_configs WHERE company_id::text IN (SELECT id FROM _probe_companies));
DELETE FROM policy_configs WHERE company_id::text IN (SELECT id FROM _probe_companies);

-- Tenant identities.
DELETE FROM hr_users WHERE company_id::text IN (SELECT id FROM _probe_companies)
  OR profile_id IN (SELECT id::text FROM profiles WHERE email LIKE '%@probe.test');
DELETE FROM employee_contacts WHERE company_id::text IN (SELECT id FROM _probe_companies);
DELETE FROM profiles WHERE email LIKE '%@probe.test';
DELETE FROM users WHERE email LIKE '%@probe.test';
DELETE FROM companies WHERE name LIKE 'Probe %';

COMMIT;

-- Verify clean.
SELECT (SELECT count(*) FROM companies WHERE name LIKE 'Probe %') AS companies_left,
       (SELECT count(*) FROM users WHERE email LIKE '%@probe.test') AS users_left,
       (SELECT count(*) FROM case_assignments WHERE employee_identifier LIKE '%@probe.test') AS assignments_left;
