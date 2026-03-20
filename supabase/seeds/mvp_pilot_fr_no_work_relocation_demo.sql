-- =============================================================================
-- MVP DEMO SEED ONLY — NOT LEGAL ADVICE — France → Norway work relocation pilot
-- Pilot id: fr_no_work_relocation_v1
-- Requires migration: 20260411110000_mobility_graph_pilot_seed_support.sql
-- Re-run safe: upserts by requirement_code / rule_code / mobility_cases.id
-- Not in config.toml sql_paths by default — run manually: psql … -f …
-- =============================================================================

begin;

-- ---------------------------------------------------------------------------
-- requirements_catalog (4 items; proof_of_address is optional via case flag)
-- ---------------------------------------------------------------------------
insert into public.requirements_catalog (id, requirement_code, metadata)
values
  (
    '11111111-1111-4111-8111-111111111101'::uuid,
    'passport_valid',
    '{"mvp_demo_seed": true, "pilot_id": "fr_no_work_relocation_v1", "title": "Passport is valid (demo checklist item)"}'::jsonb
  ),
  (
    '11111111-1111-4111-8111-111111111102'::uuid,
    'signed_employment_contract',
    '{"mvp_demo_seed": true, "pilot_id": "fr_no_work_relocation_v1", "title": "Signed employment contract on file (demo)"}'::jsonb
  ),
  (
    '11111111-1111-4111-8111-111111111103'::uuid,
    'passport_copy_uploaded',
    '{"mvp_demo_seed": true, "pilot_id": "fr_no_work_relocation_v1", "title": "Passport copy uploaded (demo)"}'::jsonb
  ),
  (
    '11111111-1111-4111-8111-111111111104'::uuid,
    'proof_of_address',
    '{"mvp_demo_seed": true, "pilot_id": "fr_no_work_relocation_v1", "title": "Proof of address (demo; optional for this pilot)", "optional": true}'::jsonb
  )
on conflict (requirement_code) do update
set
  metadata = excluded.metadata;

-- ---------------------------------------------------------------------------
-- policy_rules (pilot-scoped; JSON kept intentionally small)
-- ---------------------------------------------------------------------------
insert into public.policy_rules (id, rule_code, conditions, metadata)
values
  (
    '22222222-2222-4222-8222-222222222201'::uuid,
    'mvp_fr_no_work_relocation_employee_core_v1',
    '{
      "match": {
        "origin_country": "FR",
        "destination_country": "NO",
        "case_type": "work_relocation"
      },
      "applies_to_roles": ["employee"],
      "requires_requirement_codes": [
        "passport_valid",
        "signed_employment_contract",
        "passport_copy_uploaded"
      ]
    }'::jsonb,
    '{"mvp_demo_seed": true, "pilot_id": "fr_no_work_relocation_v1", "description": "Core demo checklist for employee on FR→NO work relocation"}'::jsonb
  ),
  (
    '22222222-2222-4222-8222-222222222202'::uuid,
    'mvp_fr_no_work_relocation_employee_proof_of_address_v1',
    '{
      "match": {
        "origin_country": "FR",
        "destination_country": "NO",
        "case_type": "work_relocation"
      },
      "applies_to_roles": ["employee"],
      "only_if": {
        "case_metadata": {"needs_proof_of_address": true}
      },
      "requires_requirement_codes": ["proof_of_address"]
    }'::jsonb,
    '{"mvp_demo_seed": true, "pilot_id": "fr_no_work_relocation_v1", "description": "Optional demo rule when case.metadata.needs_proof_of_address is true"}'::jsonb
  )
on conflict (rule_code) do update
set
  conditions = excluded.conditions,
  metadata = excluded.metadata;

-- ---------------------------------------------------------------------------
-- Sample mobility case + employee (demo UUIDs; no FK to real companies/users)
-- ---------------------------------------------------------------------------
insert into public.mobility_cases (
  id,
  company_id,
  employee_user_id,
  origin_country,
  destination_country,
  case_type,
  metadata
)
values (
  '33333333-3333-4333-8333-333333333301'::uuid,
  '00000000-0000-4000-8000-000000000001'::uuid,
  '00000000-0000-4000-8000-000000000002'::uuid,
  'FR',
  'NO',
  'work_relocation',
  '{
    "mvp_demo_seed": true,
    "pilot_id": "fr_no_work_relocation_v1",
    "disclaimer": "Illustrative MVP demo data only — not legal advice",
    "needs_proof_of_address": false
  }'::jsonb
)
on conflict (id) do update
set
  company_id = excluded.company_id,
  employee_user_id = excluded.employee_user_id,
  origin_country = excluded.origin_country,
  destination_country = excluded.destination_country,
  case_type = excluded.case_type,
  metadata = excluded.metadata;

insert into public.case_people (id, case_id, role)
values (
  '33333333-3333-4333-8333-333333333302'::uuid,
  '33333333-3333-4333-8333-333333333301'::uuid,
  'employee'
)
on conflict (id) do update
set
  case_id = excluded.case_id,
  role = excluded.role;

commit;
