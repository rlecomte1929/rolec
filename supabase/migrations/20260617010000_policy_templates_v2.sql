-- N12 / AIQ-852 — Unify four HR policy template systems into one versioned schema.
--
-- Creates the canonical, versioned template tables that mirror the unified Python
-- registry in backend/app/services/policy_template_service.py (the source of truth).
--
-- ADDITIVE ONLY. The four legacy systems remain in place, marked deprecated, until a
-- follow-up cleanup task retires them after validation:
--   1. POLICY_TEMPLATES dict  — policy_config_templates.py
--   2. _TIER_CAPS dict        — policy_starter_templates.py
--   3. benefits_templates     — out-of-band table read by routers/policy_templates.py
--   4. canonical LTA tuple + default_policy_templates.snapshot_json (W4 gap-fill)
--
-- Versioning is semver ('1.0.0'); version archiving is via superseded_by (soft-delete:
-- on update, insert a new version row and point the old row's superseded_by at it, set
-- status='archived' — old versions are never overwritten).

-- ---------------------------------------------------------------------------
-- Schema
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.policy_templates_v2 (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  template_id text NOT NULL,
  version text NOT NULL,                 -- semver, e.g. '1.0.0'
  policy_type text NOT NULL CHECK (policy_type IN ('LTA', 'STA', 'commuter')),
  generosity_tier text NOT NULL CHECK (generosity_tier IN ('conservative', 'standard', 'premium')),
  geography text,
  industry text,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived', 'draft')),
  superseded_by uuid REFERENCES public.policy_templates_v2(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (template_id, version)
);

CREATE TABLE IF NOT EXISTS public.policy_template_benefits (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  template_pk uuid NOT NULL REFERENCES public.policy_templates_v2(id) ON DELETE CASCADE,
  benefit_key text NOT NULL,
  default_value numeric,                 -- numeric cap where one exists (incl. a cap on a narrative field); NULL when uncapped
  value_type text NOT NULL CHECK (value_type IN ('amount', 'duration', 'quantity', 'percentage', 'narrative', 'external_reference')),
  is_required boolean NOT NULL DEFAULT false,
  field_confidence numeric NOT NULL DEFAULT 0.5 CHECK (field_confidence >= 0 AND field_confidence <= 1),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (template_pk, benefit_key)
);

CREATE INDEX IF NOT EXISTS idx_policy_templates_v2_lookup
  ON public.policy_templates_v2 (policy_type, generosity_tier, status);
CREATE INDEX IF NOT EXISTS idx_policy_template_benefits_pk
  ON public.policy_template_benefits (template_pk);

-- ---------------------------------------------------------------------------
-- RLS (public schema is exposed via PostgREST + the public anon key — hard gate)
-- ---------------------------------------------------------------------------
ALTER TABLE public.policy_templates_v2 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.policy_template_benefits ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS policy_templates_v2_auth_select ON public.policy_templates_v2;
CREATE POLICY policy_templates_v2_auth_select ON public.policy_templates_v2
  FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS policy_templates_v2_admin_write ON public.policy_templates_v2;
CREATE POLICY policy_templates_v2_admin_write ON public.policy_templates_v2
  FOR ALL TO authenticated USING (public.is_admin()) WITH CHECK (public.is_admin());

DROP POLICY IF EXISTS policy_templates_v2_service ON public.policy_templates_v2;
CREATE POLICY policy_templates_v2_service ON public.policy_templates_v2
  FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS policy_template_benefits_auth_select ON public.policy_template_benefits;
CREATE POLICY policy_template_benefits_auth_select ON public.policy_template_benefits
  FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS policy_template_benefits_admin_write ON public.policy_template_benefits;
CREATE POLICY policy_template_benefits_admin_write ON public.policy_template_benefits
  FOR ALL TO authenticated USING (public.is_admin()) WITH CHECK (public.is_admin());

DROP POLICY IF EXISTS policy_template_benefits_service ON public.policy_template_benefits;
CREATE POLICY policy_template_benefits_service ON public.policy_template_benefits
  FOR ALL TO service_role USING (true) WITH CHECK (true);

GRANT SELECT ON public.policy_templates_v2 TO authenticated;
GRANT INSERT, UPDATE, DELETE ON public.policy_templates_v2 TO authenticated;
GRANT SELECT ON public.policy_template_benefits TO authenticated;
GRANT INSERT, UPDATE, DELETE ON public.policy_template_benefits TO authenticated;
REVOKE ALL ON public.policy_templates_v2 FROM anon;
REVOKE ALL ON public.policy_template_benefits FROM anon;

-- ---------------------------------------------------------------------------
-- Seed — mirrors policy_template_service.py registry (3 tiers x LTA + 3 tiers x STA).
-- Data migrated from the legacy systems: LTA caps from _TIER_CAPS / POLICY_TEMPLATES;
-- STA is new placeholder content (field_confidence 0.5). Deterministic UUIDs (uuid5)
-- keep this idempotent. Regenerate with: see N12 PR description.
-- ---------------------------------------------------------------------------
INSERT INTO public.policy_templates_v2 (id, template_id, version, policy_type, generosity_tier, status) VALUES
  ('f41c17a1-d11c-5a67-8fa3-6de0d7f372be', 'LTA_conservative', '1.0.0', 'LTA', 'conservative', 'active'),
  ('98a75ee1-7f72-5e04-86f1-2f26824c6613', 'STA_conservative', '1.0.0', 'STA', 'conservative', 'active'),
  ('845175b3-4ace-500f-8d26-c96ecab1f0fe', 'LTA_standard', '1.0.0', 'LTA', 'standard', 'active'),
  ('8b96e0a3-f784-516b-abe8-9b7c7120c5cf', 'STA_standard', '1.0.0', 'STA', 'standard', 'active'),
  ('5875fc09-cf54-5365-b4db-0f85dcc08b9b', 'LTA_premium', '1.0.0', 'LTA', 'premium', 'active'),
  ('233b6afc-1d30-5f0a-88c3-af8e6be7d39a', 'STA_premium', '1.0.0', 'STA', 'premium', 'active')
ON CONFLICT (template_id, version) DO NOTHING;

INSERT INTO public.policy_template_benefits (id, template_pk, benefit_key, default_value, value_type, is_required, field_confidence) VALUES
  ('a7d64ee2-d898-5dbd-93ce-a9d37293276a', 'f41c17a1-d11c-5a67-8fa3-6de0d7f372be', 'eligibility_and_assignment_scope', NULL, 'narrative', true, 0.9),
  ('a5f392af-7f71-54bb-b174-bc3953d4415e', 'f41c17a1-d11c-5a67-8fa3-6de0d7f372be', 'policy_definitions_and_exceptions', NULL, 'narrative', true, 0.9),
  ('f43ddebf-c909-5274-9ec4-9f7982bab8c4', 'f41c17a1-d11c-5a67-8fa3-6de0d7f372be', 'work_permits_and_visas', 2500.0, 'narrative', true, 0.9),
  ('afb9a402-7ff5-5227-a469-a8f700f7d001', 'f41c17a1-d11c-5a67-8fa3-6de0d7f372be', 'medical_exam_support', NULL, 'amount', true, 0.9),
  ('dfe3889c-e9f8-53f1-a97c-4c02f5374c4c', 'f41c17a1-d11c-5a67-8fa3-6de0d7f372be', 'pre_assignment_visit', NULL, 'duration', true, 0.9),
  ('08f96888-766d-53c9-9ae6-c9d5f3d17fdb', 'f41c17a1-d11c-5a67-8fa3-6de0d7f372be', 'policy_briefing', NULL, 'narrative', false, 0.9),
  ('a9c1f09f-d8e6-5cbe-817d-0d9f92a41d7e', 'f41c17a1-d11c-5a67-8fa3-6de0d7f372be', 'cultural_training', NULL, 'narrative', true, 0.9),
  ('6bb0d100-7e04-5e2f-ac92-e1431054767e', 'f41c17a1-d11c-5a67-8fa3-6de0d7f372be', 'language_training', NULL, 'narrative', true, 0.9),
  ('007a4f12-690a-55b3-afa5-d261445be2b4', 'f41c17a1-d11c-5a67-8fa3-6de0d7f372be', 'travel_to_host', NULL, 'amount', true, 0.9),
  ('9408e9c2-af93-5b44-85cb-161c16cd51a7', 'f41c17a1-d11c-5a67-8fa3-6de0d7f372be', 'relocation_allowance', NULL, 'amount', true, 0.9),
  ('96048181-bc3e-59fc-bde7-064ff22bec10', 'f41c17a1-d11c-5a67-8fa3-6de0d7f372be', 'removal_expenses', 5000.0, 'amount', true, 0.9),
  ('a7487216-f616-5510-bd7c-056bf0bca77f', 'f41c17a1-d11c-5a67-8fa3-6de0d7f372be', 'shipment_outbound', 5000.0, 'amount', true, 0.9),
  ('03cb53ef-71e7-5aff-9eb1-0c23ed7ae16d', 'f41c17a1-d11c-5a67-8fa3-6de0d7f372be', 'storage', NULL, 'duration', true, 0.9),
  ('254cfb24-309a-518d-8ca2-cb22766d9aa4', 'f41c17a1-d11c-5a67-8fa3-6de0d7f372be', 'temporary_living_outbound', 3500.0, 'duration', true, 0.9),
  ('0da42b01-9700-5206-bd26-7ba7fe7707d2', 'f41c17a1-d11c-5a67-8fa3-6de0d7f372be', 'settling_in_support', NULL, 'narrative', true, 0.9),
  ('9a66f34d-0c56-56c3-b438-c3e7b3c5a06a', 'f41c17a1-d11c-5a67-8fa3-6de0d7f372be', 'host_housing', 2500.0, 'narrative', true, 0.9),
  ('d3bf9430-1d2c-537e-a446-a1a048b9f720', 'f41c17a1-d11c-5a67-8fa3-6de0d7f372be', 'host_transportation', NULL, 'narrative', false, 0.9),
  ('43c80625-e68c-51ae-a8e3-c5ea6a36e059', 'f41c17a1-d11c-5a67-8fa3-6de0d7f372be', 'tax_equalization', NULL, 'narrative', true, 0.9),
  ('5d966659-e5c6-52a9-af31-63aa82d5b34a', 'f41c17a1-d11c-5a67-8fa3-6de0d7f372be', 'tax_briefing', NULL, 'narrative', false, 0.9),
  ('06a46b9d-8e31-5838-8207-dc2b6c7b5d7b', 'f41c17a1-d11c-5a67-8fa3-6de0d7f372be', 'tax_return_support', NULL, 'narrative', true, 0.9),
  ('0a150cca-1a64-5785-bbf4-c427c2c94701', 'f41c17a1-d11c-5a67-8fa3-6de0d7f372be', 'mobility_premium', NULL, 'percentage', true, 0.9),
  ('f27c7ab0-4419-5e89-8a07-5f9234e47623', 'f41c17a1-d11c-5a67-8fa3-6de0d7f372be', 'location_premium', NULL, 'amount', true, 0.9),
  ('3e196f35-1d39-5dfe-ac72-67df91be3575', 'f41c17a1-d11c-5a67-8fa3-6de0d7f372be', 'remote_premium', NULL, 'percentage', true, 0.9),
  ('b4f4f91d-6ddd-5fc5-a426-e6ecbc44ebc3', 'f41c17a1-d11c-5a67-8fa3-6de0d7f372be', 'cola', NULL, 'percentage', true, 0.9),
  ('4bae895d-8fd7-5faf-91bb-d6d0bd0a056a', 'f41c17a1-d11c-5a67-8fa3-6de0d7f372be', 'spouse_support', NULL, 'amount', true, 0.9),
  ('b14e20d2-09bb-5195-a7fa-ab79bd392e17', 'f41c17a1-d11c-5a67-8fa3-6de0d7f372be', 'child_education', 8000.0, 'narrative', true, 0.9),
  ('046e05d0-1932-59fd-b239-b4c420748506', 'f41c17a1-d11c-5a67-8fa3-6de0d7f372be', 'school_search', 8000.0, 'narrative', true, 0.9),
  ('0c0d4d48-bc24-5d49-8c57-3a44c5279be3', 'f41c17a1-d11c-5a67-8fa3-6de0d7f372be', 'home_leave', NULL, 'quantity', true, 0.9),
  ('187c9eb5-f8c4-505c-9433-9a4e160fcfc5', 'f41c17a1-d11c-5a67-8fa3-6de0d7f372be', 'return_shipment', 5000.0, 'amount', true, 0.9),
  ('f6cc8c39-83de-55ff-887d-358f6872e183', 'f41c17a1-d11c-5a67-8fa3-6de0d7f372be', 'return_travel', NULL, 'amount', true, 0.9),
  ('8aebc768-addb-5659-bc43-63c1e9410d7e', 'f41c17a1-d11c-5a67-8fa3-6de0d7f372be', 'temporary_living_return', 3500.0, 'duration', true, 0.9),
  ('d853c0f1-6c6e-5872-aaa8-527b5c9bb20f', 'f41c17a1-d11c-5a67-8fa3-6de0d7f372be', 'repatriation_allowance', NULL, 'amount', true, 0.9),
  ('d8c2f2fd-8476-50ed-9563-864e82c1e620', 'f41c17a1-d11c-5a67-8fa3-6de0d7f372be', 'approval_authority_matrix', NULL, 'narrative', true, 0.9),
  ('ca1ae567-4e4e-558c-9c4c-64fdd064aeea', 'f41c17a1-d11c-5a67-8fa3-6de0d7f372be', 'mandatory_notifications_and_compliance', NULL, 'narrative', false, 0.9),
  ('1d4ef0ca-fb32-5166-9ead-151f292c6195', 'f41c17a1-d11c-5a67-8fa3-6de0d7f372be', 'external_providers_and_dependencies', NULL, 'external_reference', false, 0.9),
  ('dfde8d33-f134-58b9-863d-f119b6b046a4', '98a75ee1-7f72-5e04-86f1-2f26824c6613', 'work_permits_and_visas', 2000.0, 'narrative', true, 0.5),
  ('ff3e2e26-b5b0-52fa-93d9-149ab479595f', '98a75ee1-7f72-5e04-86f1-2f26824c6613', 'medical_exam_support', NULL, 'amount', true, 0.5),
  ('4ef33aae-bac0-52b0-9b0d-65ab9c5579c9', '98a75ee1-7f72-5e04-86f1-2f26824c6613', 'travel_to_host', 1200.0, 'amount', true, 0.5),
  ('4cfc5b73-408d-54ac-8852-db746ca0d7f8', '98a75ee1-7f72-5e04-86f1-2f26824c6613', 'temporary_living_outbound', 6000.0, 'duration', true, 0.5),
  ('7dba78e9-6997-5dc5-be99-f0184bfdf59d', '98a75ee1-7f72-5e04-86f1-2f26824c6613', 'settling_in_support', NULL, 'narrative', true, 0.5),
  ('fbdbb60a-5ef5-542d-9cf7-64992187d842', '98a75ee1-7f72-5e04-86f1-2f26824c6613', 'host_transportation', 1200.0, 'narrative', false, 0.5),
  ('374a2eec-abd9-5830-ad4a-a9a4ddea51ac', '98a75ee1-7f72-5e04-86f1-2f26824c6613', 'mobility_premium', NULL, 'percentage', true, 0.5),
  ('d464f881-d80d-5aaf-8c63-c42f30ad3dcb', '98a75ee1-7f72-5e04-86f1-2f26824c6613', 'home_leave', NULL, 'quantity', true, 0.5),
  ('6c3830a3-2f9e-5c2e-a9a1-93d82d017384', '98a75ee1-7f72-5e04-86f1-2f26824c6613', 'tax_briefing', NULL, 'narrative', false, 0.5),
  ('a14328a1-f71b-5492-b7d6-411bff319c58', '98a75ee1-7f72-5e04-86f1-2f26824c6613', 'return_travel', 1200.0, 'amount', true, 0.5),
  ('f7161ac1-5589-5787-bd85-2dbd63018597', '98a75ee1-7f72-5e04-86f1-2f26824c6613', 'approval_authority_matrix', NULL, 'narrative', true, 0.5),
  ('9626ecb0-351c-5158-8cc1-2b7cff97f5ab', '845175b3-4ace-500f-8d26-c96ecab1f0fe', 'eligibility_and_assignment_scope', NULL, 'narrative', true, 0.9),
  ('954a6927-1389-5de7-a21c-e870f9de8d16', '845175b3-4ace-500f-8d26-c96ecab1f0fe', 'policy_definitions_and_exceptions', NULL, 'narrative', true, 0.9),
  ('6b5c6032-32e5-5694-8e00-98ac5a50b18d', '845175b3-4ace-500f-8d26-c96ecab1f0fe', 'work_permits_and_visas', 4000.0, 'narrative', true, 0.9),
  ('bfb472bf-7801-50a7-915b-64d21779ec63', '845175b3-4ace-500f-8d26-c96ecab1f0fe', 'medical_exam_support', NULL, 'amount', true, 0.9),
  ('c96aefa1-a3a0-5706-8630-0ffd49ba9884', '845175b3-4ace-500f-8d26-c96ecab1f0fe', 'pre_assignment_visit', NULL, 'duration', true, 0.9),
  ('78fb0026-3133-55ac-8297-d11fcde3b9da', '845175b3-4ace-500f-8d26-c96ecab1f0fe', 'policy_briefing', NULL, 'narrative', false, 0.9),
  ('758aaa15-d7e3-5d1a-acd8-f25f112d1545', '845175b3-4ace-500f-8d26-c96ecab1f0fe', 'cultural_training', NULL, 'narrative', true, 0.9),
  ('8eaf3856-04e4-5868-b952-d3d958fb7eb5', '845175b3-4ace-500f-8d26-c96ecab1f0fe', 'language_training', NULL, 'narrative', true, 0.9),
  ('b64555ea-a100-5a5e-8d77-7899e4b8d5fe', '845175b3-4ace-500f-8d26-c96ecab1f0fe', 'travel_to_host', NULL, 'amount', true, 0.9),
  ('29f8997c-8cbc-526a-80f3-306424bb26dc', '845175b3-4ace-500f-8d26-c96ecab1f0fe', 'relocation_allowance', NULL, 'amount', true, 0.9),
  ('e0e54a87-b38f-5576-b730-59ad21f3969d', '845175b3-4ace-500f-8d26-c96ecab1f0fe', 'removal_expenses', 10000.0, 'amount', true, 0.9),
  ('d63707c5-923a-5909-b603-b60aab3afea8', '845175b3-4ace-500f-8d26-c96ecab1f0fe', 'shipment_outbound', 10000.0, 'amount', true, 0.9),
  ('b0bd48e2-0d05-5741-afa6-05c6f1e2d579', '845175b3-4ace-500f-8d26-c96ecab1f0fe', 'storage', NULL, 'duration', true, 0.9),
  ('953fc7c7-fc6f-587e-8de4-591bc55213d5', '845175b3-4ace-500f-8d26-c96ecab1f0fe', 'temporary_living_outbound', 5500.0, 'duration', true, 0.9),
  ('b8e9c88d-d941-5d6e-b11c-964cb4937393', '845175b3-4ace-500f-8d26-c96ecab1f0fe', 'settling_in_support', NULL, 'narrative', true, 0.9),
  ('9588ad56-fca0-5499-badd-c51f94b852b1', '845175b3-4ace-500f-8d26-c96ecab1f0fe', 'host_housing', 3500.0, 'narrative', true, 0.9),
  ('fdec4c54-8831-5244-a43f-85d2ce8edf8a', '845175b3-4ace-500f-8d26-c96ecab1f0fe', 'host_transportation', NULL, 'narrative', false, 0.9),
  ('af3d9127-9ff1-5789-9a3f-b55e148db6ba', '845175b3-4ace-500f-8d26-c96ecab1f0fe', 'tax_equalization', NULL, 'narrative', true, 0.9),
  ('9660b4f6-c343-5ca0-8823-3619c9e6386b', '845175b3-4ace-500f-8d26-c96ecab1f0fe', 'tax_briefing', NULL, 'narrative', false, 0.9),
  ('84385302-e03c-51ac-9fd5-0abf1af5bd8e', '845175b3-4ace-500f-8d26-c96ecab1f0fe', 'tax_return_support', NULL, 'narrative', true, 0.9),
  ('245536bc-4d3d-5765-bd1e-f8569a926d12', '845175b3-4ace-500f-8d26-c96ecab1f0fe', 'mobility_premium', NULL, 'percentage', true, 0.9),
  ('9f155f1b-d572-5f16-b87a-c7c54d32e574', '845175b3-4ace-500f-8d26-c96ecab1f0fe', 'location_premium', NULL, 'amount', true, 0.9),
  ('133d66b0-3e44-5aef-8bbb-ee631318f04c', '845175b3-4ace-500f-8d26-c96ecab1f0fe', 'remote_premium', NULL, 'percentage', true, 0.9),
  ('4542507b-d6a1-5999-9cc1-b78d4437015c', '845175b3-4ace-500f-8d26-c96ecab1f0fe', 'cola', NULL, 'percentage', true, 0.9),
  ('4fcd0ae9-60e0-5616-94f0-621cff8e6e71', '845175b3-4ace-500f-8d26-c96ecab1f0fe', 'spouse_support', NULL, 'amount', true, 0.9),
  ('2cbe1165-699e-58f6-b391-79e7859b3dc9', '845175b3-4ace-500f-8d26-c96ecab1f0fe', 'child_education', 15000.0, 'narrative', true, 0.9),
  ('119fe833-bbdb-56f2-822f-e1c758189c59', '845175b3-4ace-500f-8d26-c96ecab1f0fe', 'school_search', 15000.0, 'narrative', true, 0.9),
  ('178c52bb-f006-5dc9-90e0-75ef986abb90', '845175b3-4ace-500f-8d26-c96ecab1f0fe', 'home_leave', NULL, 'quantity', true, 0.9),
  ('ff61fb8e-0010-58d7-bed1-4f4dcf893e79', '845175b3-4ace-500f-8d26-c96ecab1f0fe', 'return_shipment', 10000.0, 'amount', true, 0.9),
  ('96fc4cc0-f708-5a7b-bc5d-16a36ae32cb6', '845175b3-4ace-500f-8d26-c96ecab1f0fe', 'return_travel', NULL, 'amount', true, 0.9),
  ('e0eac07b-c892-557f-b20d-3dda6107d683', '845175b3-4ace-500f-8d26-c96ecab1f0fe', 'temporary_living_return', 5500.0, 'duration', true, 0.9),
  ('10485fd8-8f06-5231-9ac9-d47a9563b2e8', '845175b3-4ace-500f-8d26-c96ecab1f0fe', 'repatriation_allowance', NULL, 'amount', true, 0.9),
  ('2da338d9-1842-5cea-8799-861953b166fc', '845175b3-4ace-500f-8d26-c96ecab1f0fe', 'approval_authority_matrix', NULL, 'narrative', true, 0.9),
  ('6a44ae10-f248-5428-813d-8eb6c03201aa', '845175b3-4ace-500f-8d26-c96ecab1f0fe', 'mandatory_notifications_and_compliance', NULL, 'narrative', false, 0.9),
  ('50480f4f-4e9f-5867-8fd0-a6c6c9c5e9af', '845175b3-4ace-500f-8d26-c96ecab1f0fe', 'external_providers_and_dependencies', NULL, 'external_reference', false, 0.9),
  ('47560b27-9dd3-5aba-a6f0-b8181af9c34a', '8b96e0a3-f784-516b-abe8-9b7c7120c5cf', 'work_permits_and_visas', 3000.0, 'narrative', true, 0.5),
  ('6908ff8f-748f-5c50-986b-a7d7860b5bf5', '8b96e0a3-f784-516b-abe8-9b7c7120c5cf', 'medical_exam_support', NULL, 'amount', true, 0.5),
  ('3e6166e1-d1e8-5d0f-b290-760188f589ad', '8b96e0a3-f784-516b-abe8-9b7c7120c5cf', 'travel_to_host', 2000.0, 'amount', true, 0.5),
  ('c73d46d0-4b1c-544f-bd3b-ff97367bc3a2', '8b96e0a3-f784-516b-abe8-9b7c7120c5cf', 'temporary_living_outbound', 9000.0, 'duration', true, 0.5),
  ('2c8d8398-21ae-5143-b3d9-d737d7770af8', '8b96e0a3-f784-516b-abe8-9b7c7120c5cf', 'settling_in_support', NULL, 'narrative', true, 0.5),
  ('062e5ac9-f7c9-505d-82a6-3b71da50ff46', '8b96e0a3-f784-516b-abe8-9b7c7120c5cf', 'host_transportation', 2000.0, 'narrative', false, 0.5),
  ('80d82bca-c137-5abc-85c2-34bfdd0e6c70', '8b96e0a3-f784-516b-abe8-9b7c7120c5cf', 'mobility_premium', NULL, 'percentage', true, 0.5),
  ('6631a5cd-cb7f-5de6-a4b4-d918cdc76fbf', '8b96e0a3-f784-516b-abe8-9b7c7120c5cf', 'home_leave', NULL, 'quantity', true, 0.5),
  ('3ec33fbf-dc61-58a3-acc1-0e97a828a9a2', '8b96e0a3-f784-516b-abe8-9b7c7120c5cf', 'tax_briefing', NULL, 'narrative', false, 0.5),
  ('fd6d1ce9-5610-5e4a-a20a-bfe3f106d3a6', '8b96e0a3-f784-516b-abe8-9b7c7120c5cf', 'return_travel', 2000.0, 'amount', true, 0.5),
  ('23dd6f7f-f561-555f-a071-2efceadcc7d1', '8b96e0a3-f784-516b-abe8-9b7c7120c5cf', 'approval_authority_matrix', NULL, 'narrative', true, 0.5),
  ('360ede12-3b51-563b-b2e5-0bfa4cb376e1', '5875fc09-cf54-5365-b4db-0f85dcc08b9b', 'eligibility_and_assignment_scope', NULL, 'narrative', true, 0.9),
  ('1ce860d5-48d8-5e3d-92d1-4ab99011e91c', '5875fc09-cf54-5365-b4db-0f85dcc08b9b', 'policy_definitions_and_exceptions', NULL, 'narrative', true, 0.9),
  ('66a11931-69e3-5a9f-9eb1-2df82ab3e64b', '5875fc09-cf54-5365-b4db-0f85dcc08b9b', 'work_permits_and_visas', 6500.0, 'narrative', true, 0.9),
  ('acd34333-3d9a-5773-b3fc-90f4cfcff279', '5875fc09-cf54-5365-b4db-0f85dcc08b9b', 'medical_exam_support', NULL, 'amount', true, 0.9),
  ('2d598b59-74b6-54a1-b72b-02b037d9049b', '5875fc09-cf54-5365-b4db-0f85dcc08b9b', 'pre_assignment_visit', NULL, 'duration', true, 0.9),
  ('fa0a7752-4ac4-5d5a-8d2a-b0aadcf11379', '5875fc09-cf54-5365-b4db-0f85dcc08b9b', 'policy_briefing', NULL, 'narrative', false, 0.9),
  ('fb8c713c-1d83-5c09-90c1-a8f8dd677582', '5875fc09-cf54-5365-b4db-0f85dcc08b9b', 'cultural_training', NULL, 'narrative', true, 0.9),
  ('ac4e8fe1-beb8-5be8-abe7-83778ec8e357', '5875fc09-cf54-5365-b4db-0f85dcc08b9b', 'language_training', NULL, 'narrative', true, 0.9),
  ('3e038284-1d51-5fb8-ab39-a85560acfd65', '5875fc09-cf54-5365-b4db-0f85dcc08b9b', 'travel_to_host', NULL, 'amount', true, 0.9),
  ('aa0a5ba3-144d-5db9-a805-126fe27cb663', '5875fc09-cf54-5365-b4db-0f85dcc08b9b', 'relocation_allowance', NULL, 'amount', true, 0.9),
  ('d9076c11-f2d7-5bda-ba23-53cedf4163fe', '5875fc09-cf54-5365-b4db-0f85dcc08b9b', 'removal_expenses', 18000.0, 'amount', true, 0.9),
  ('8a3bc722-e645-59f3-b2bc-859889aaed4c', '5875fc09-cf54-5365-b4db-0f85dcc08b9b', 'shipment_outbound', 18000.0, 'amount', true, 0.9),
  ('626943cb-40fd-5971-9b19-e7e4f6d1b4de', '5875fc09-cf54-5365-b4db-0f85dcc08b9b', 'storage', NULL, 'duration', true, 0.9),
  ('2589f696-4491-5eaa-a3b9-a6398c1888f0', '5875fc09-cf54-5365-b4db-0f85dcc08b9b', 'temporary_living_outbound', 8500.0, 'duration', true, 0.9),
  ('1573430e-3812-5df1-b012-72b10059fd1d', '5875fc09-cf54-5365-b4db-0f85dcc08b9b', 'settling_in_support', NULL, 'narrative', true, 0.9),
  ('dda577d1-73ef-50bd-86c3-fc5c041f76b9', '5875fc09-cf54-5365-b4db-0f85dcc08b9b', 'host_housing', 5000.0, 'narrative', true, 0.9),
  ('044d410a-180c-5cde-98a6-7259639ea4a6', '5875fc09-cf54-5365-b4db-0f85dcc08b9b', 'host_transportation', NULL, 'narrative', false, 0.9),
  ('985bb408-53b0-5db8-97e4-72caa784970a', '5875fc09-cf54-5365-b4db-0f85dcc08b9b', 'tax_equalization', NULL, 'narrative', true, 0.9),
  ('52fac92e-d8ca-5c43-a388-966c9d9c03eb', '5875fc09-cf54-5365-b4db-0f85dcc08b9b', 'tax_briefing', NULL, 'narrative', false, 0.9),
  ('469dd8a3-7315-584f-b867-c0684c3f22dc', '5875fc09-cf54-5365-b4db-0f85dcc08b9b', 'tax_return_support', NULL, 'narrative', true, 0.9),
  ('d7df6090-e036-5689-b678-07df168fea6f', '5875fc09-cf54-5365-b4db-0f85dcc08b9b', 'mobility_premium', NULL, 'percentage', true, 0.9),
  ('28a56247-a7ea-5244-b6f7-043011a871b4', '5875fc09-cf54-5365-b4db-0f85dcc08b9b', 'location_premium', NULL, 'amount', true, 0.9),
  ('e6925fba-6130-5590-a3fc-0d69d77f91cf', '5875fc09-cf54-5365-b4db-0f85dcc08b9b', 'remote_premium', NULL, 'percentage', true, 0.9),
  ('0047486c-e1d7-5c31-8514-207d56b8ad5c', '5875fc09-cf54-5365-b4db-0f85dcc08b9b', 'cola', NULL, 'percentage', true, 0.9),
  ('113bd1d2-e945-51ec-834c-c75d54dc3581', '5875fc09-cf54-5365-b4db-0f85dcc08b9b', 'spouse_support', NULL, 'amount', true, 0.9),
  ('a1e35d63-7d50-52a7-8135-edc9568584ce', '5875fc09-cf54-5365-b4db-0f85dcc08b9b', 'child_education', 25000.0, 'narrative', true, 0.9),
  ('eb952a82-09dd-5779-9ec8-089d6b2ff4e3', '5875fc09-cf54-5365-b4db-0f85dcc08b9b', 'school_search', 25000.0, 'narrative', true, 0.9),
  ('f8b296f2-c342-57dd-8ee4-fad9f6b720eb', '5875fc09-cf54-5365-b4db-0f85dcc08b9b', 'home_leave', NULL, 'quantity', true, 0.9),
  ('37ac6833-1fce-5d3a-b9fe-6260d6a308e3', '5875fc09-cf54-5365-b4db-0f85dcc08b9b', 'return_shipment', 18000.0, 'amount', true, 0.9),
  ('ff4ef23d-12c6-5b53-bb7c-1a4281543f19', '5875fc09-cf54-5365-b4db-0f85dcc08b9b', 'return_travel', NULL, 'amount', true, 0.9),
  ('e154afb4-8e8c-516b-86ef-3f58051c67a2', '5875fc09-cf54-5365-b4db-0f85dcc08b9b', 'temporary_living_return', 8500.0, 'duration', true, 0.9),
  ('29a66c15-949b-50d7-8f78-a21fd8e2dd80', '5875fc09-cf54-5365-b4db-0f85dcc08b9b', 'repatriation_allowance', NULL, 'amount', true, 0.9),
  ('bb947b2d-7ecf-56e5-beb0-50be2d02a958', '5875fc09-cf54-5365-b4db-0f85dcc08b9b', 'approval_authority_matrix', NULL, 'narrative', true, 0.9),
  ('7430bf8e-f917-5df6-a266-f2f275d9084e', '5875fc09-cf54-5365-b4db-0f85dcc08b9b', 'mandatory_notifications_and_compliance', NULL, 'narrative', false, 0.9),
  ('6493a4a4-18d9-515b-84db-8fe9093367dc', '5875fc09-cf54-5365-b4db-0f85dcc08b9b', 'external_providers_and_dependencies', NULL, 'external_reference', false, 0.9),
  ('a0fc334e-0ad9-5cb9-b5cb-8d54690db770', '233b6afc-1d30-5f0a-88c3-af8e6be7d39a', 'work_permits_and_visas', 4500.0, 'narrative', true, 0.5),
  ('a27bb8b5-da83-5cb6-be8e-d2bdb404e9d4', '233b6afc-1d30-5f0a-88c3-af8e6be7d39a', 'medical_exam_support', NULL, 'amount', true, 0.5),
  ('7e6e6459-9263-5f9e-89df-c2133b751f14', '233b6afc-1d30-5f0a-88c3-af8e6be7d39a', 'travel_to_host', 3500.0, 'amount', true, 0.5),
  ('db5f2539-cd06-5836-8ce2-98b4745788fa', '233b6afc-1d30-5f0a-88c3-af8e6be7d39a', 'temporary_living_outbound', 14000.0, 'duration', true, 0.5),
  ('66344959-c05b-52b6-9174-801929d6c590', '233b6afc-1d30-5f0a-88c3-af8e6be7d39a', 'settling_in_support', NULL, 'narrative', true, 0.5),
  ('bd1740fd-6308-560c-9d37-1d5b8ba996e0', '233b6afc-1d30-5f0a-88c3-af8e6be7d39a', 'host_transportation', 3500.0, 'narrative', false, 0.5),
  ('b8c466c7-6053-5a72-b2d0-132b6a23a2f7', '233b6afc-1d30-5f0a-88c3-af8e6be7d39a', 'mobility_premium', NULL, 'percentage', true, 0.5),
  ('504e120a-d97d-58ed-b848-095274748589', '233b6afc-1d30-5f0a-88c3-af8e6be7d39a', 'home_leave', NULL, 'quantity', true, 0.5),
  ('3c669037-5fab-5511-aaba-5a01d98ef2ca', '233b6afc-1d30-5f0a-88c3-af8e6be7d39a', 'tax_briefing', NULL, 'narrative', false, 0.5),
  ('c35987a8-4184-5ae2-a1b5-f25bfaee38f6', '233b6afc-1d30-5f0a-88c3-af8e6be7d39a', 'return_travel', 3500.0, 'amount', true, 0.5),
  ('7d927600-d662-5790-9761-88a1414b6adc', '233b6afc-1d30-5f0a-88c3-af8e6be7d39a', 'approval_authority_matrix', NULL, 'narrative', true, 0.5)
ON CONFLICT (id) DO NOTHING;
