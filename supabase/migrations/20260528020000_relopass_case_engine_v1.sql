-- C1-01 · ReloPass Case Engine (RCE) v1 — ontology tables + pgvector
--
-- Architecture Report §2.1 + §2.2. Parsewise pattern.
--
-- Coexistence note: Tables `cases`, `documents`, `employees`, `hr_policies` already exist
-- in `public` from the legacy schema. The Architecture-Report ontology uses the same
-- table names, so all 20 RCE entities are namespaced under a dedicated `rce` schema.
-- Downstream C1-XX tasks reference `rce.*` consistently.
--
-- PF-1 stress-test additions:
--   * cases.petitioning_party_type + cases.beneficiary_employee_id
--   * steps.time_window_relative_to + min_days + max_days
--   * costs.category controlled enum
--
-- Security (SEC-003 hard gate): every table gets ENABLE RLS + a policy + REVOKE FROM anon.
-- Policies are permissive in this migration; C1-01a replaces them with tenant-scoped policies.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS rce;
GRANT USAGE ON SCHEMA rce TO authenticated, service_role;

-- ─────────────────────────────────────────────────────────────────────────────
-- Foundation entities (no FK dependencies)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS rce.canonical_entities (
  canonical_entity_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_type TEXT NOT NULL CHECK (entity_type IN ('PERSON','EMPLOYER','ADDRESS','AUTHORITY')),
  canonical_form JSONB NOT NULL,
  embedding vector(768),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rce.employers (
  employer_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  legal_name TEXT NOT NULL,
  registry_id TEXT,
  country_iso3 TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rce.authorities (
  authority_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  country_iso3 TEXT,
  jurisdiction TEXT,
  official_url TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rce.addresses (
  address_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  country_iso3 TEXT,
  postal_code TEXT,
  locality TEXT,
  region TEXT,
  street_line_1 TEXT,
  street_line_2 TEXT,
  normalized_hash TEXT UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rce.document_types (
  document_type_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code TEXT NOT NULL UNIQUE,
  expected_fields_json JSONB,
  validator_pack TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rce.rules (
  rule_id TEXT PRIMARY KEY,
  corridor_scope TEXT[],
  legal_reference TEXT NOT NULL,
  description TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Employees (FK → canonical_entities)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS rce.employees (
  employee_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  canonical_entity_id UUID REFERENCES rce.canonical_entities(canonical_entity_id) ON DELETE SET NULL,
  current_residence_country TEXT,
  target_residence_country TEXT,
  role_title TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Cases (FK → employers, employees) + PF-1 columns
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS rce.cases (
  case_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  corridor_id TEXT,
  employer_id UUID REFERENCES rce.employers(employer_id) ON DELETE SET NULL,
  primary_employee_id UUID REFERENCES rce.employees(employee_id) ON DELETE SET NULL,
  status TEXT CHECK (status IN ('DRAFT','ACTIVE','BLOCKED','COMPLETED','CANCELLED')),
  target_arrival_date DATE,
  -- PF-1 additions:
  petitioning_party_type TEXT NOT NULL DEFAULT 'EMPLOYEE'
    CHECK (petitioning_party_type IN ('EMPLOYEE','EMPLOYER')),
  beneficiary_employee_id UUID REFERENCES rce.employees(employee_id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Case-scoped entities
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS rce.family_members (
  family_member_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id UUID NOT NULL REFERENCES rce.cases(case_id) ON DELETE CASCADE,
  relationship_type TEXT NOT NULL
    CHECK (relationship_type IN ('SPOUSE','CHILD','DEPENDENT_PARENT')),
  canonical_entity_id UUID REFERENCES rce.canonical_entities(canonical_entity_id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rce.documents (
  document_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id UUID NOT NULL REFERENCES rce.cases(case_id) ON DELETE CASCADE,
  mime_type TEXT,
  sha256 TEXT NOT NULL UNIQUE,
  uploaded_by UUID,
  document_type_id UUID REFERENCES rce.document_types(document_type_id) ON DELETE SET NULL,
  language TEXT,
  original_filename TEXT,
  storage_uri TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rce.agent_runs (
  agent_run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id TEXT,
  agent_version TEXT,
  case_id UUID REFERENCES rce.cases(case_id) ON DELETE SET NULL,
  inputs_digest TEXT,
  output_digest TEXT,
  status TEXT,
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  llm_model_used TEXT,
  cost_tokens INT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rce.extracted_fields (
  extracted_field_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id UUID NOT NULL REFERENCES rce.documents(document_id) ON DELETE CASCADE,
  field_key TEXT NOT NULL,
  value_raw TEXT,
  value_canonical JSONB,
  confidence NUMERIC(4,3) NOT NULL,
  bbox_page INT,
  bbox_x0 INT,
  bbox_y0 INT,
  bbox_x1 INT,
  bbox_y1 INT,
  agent_run_id UUID REFERENCES rce.agent_runs(agent_run_id) ON DELETE SET NULL,
  resolution_status TEXT
    CHECK (resolution_status IN ('Resolved','Requires attention','Not resolved','No result','Ignored')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT extracted_fields_bbox_range CHECK (
    (bbox_x0 IS NULL OR bbox_x0 BETWEEN 0 AND 1000)
    AND (bbox_x1 IS NULL OR bbox_x1 BETWEEN 0 AND 1000)
    AND (bbox_y0 IS NULL OR bbox_y0 BETWEEN 0 AND 1000)
    AND (bbox_y1 IS NULL OR bbox_y1 BETWEEN 0 AND 1000)
  )
);

CREATE TABLE IF NOT EXISTS rce.entity_links (
  entity_link_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  extracted_field_id UUID NOT NULL REFERENCES rce.extracted_fields(extracted_field_id) ON DELETE CASCADE,
  canonical_entity_id UUID NOT NULL REFERENCES rce.canonical_entities(canonical_entity_id) ON DELETE CASCADE,
  link_method TEXT NOT NULL CHECK (link_method IN ('DETERMINISTIC','LLM','HUMAN')),
  confidence NUMERIC(4,3),
  resolved_by_user_id UUID,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Rule versions, steps, deadlines, costs
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS rce.rule_versions (
  rule_version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rule_id TEXT NOT NULL REFERENCES rce.rules(rule_id) ON DELETE CASCADE,
  version_label TEXT,
  effective_from DATE NOT NULL,
  effective_to DATE,
  predicate_dsl TEXT NOT NULL,
  body JSONB,
  source_url TEXT NOT NULL,
  captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  superseded_by UUID REFERENCES rce.rule_versions(rule_version_id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rce.steps (
  step_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  corridor_id TEXT,
  name TEXT NOT NULL,
  responsible_party TEXT,
  prerequisite_step_ids UUID[],
  expected_duration_days INT,
  -- PF-1 additions:
  time_window_relative_to UUID REFERENCES rce.steps(step_id) ON DELETE SET NULL,
  time_window_min_days INT,
  time_window_max_days INT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rce.deadlines (
  deadline_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id UUID NOT NULL REFERENCES rce.cases(case_id) ON DELETE CASCADE,
  step_id UUID REFERENCES rce.steps(step_id) ON DELETE SET NULL,
  due_date DATE NOT NULL,
  derivation TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- HR policies & clauses
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS rce.hr_policies (
  hr_policy_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  employer_id UUID NOT NULL REFERENCES rce.employers(employer_id) ON DELETE CASCADE,
  version_label TEXT,
  source TEXT NOT NULL CHECK (source IN ('LEGACY_INGESTED','GUIDED_EDITOR')),
  effective_from DATE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rce.policy_clauses (
  policy_clause_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  hr_policy_id UUID NOT NULL REFERENCES rce.hr_policies(hr_policy_id) ON DELETE CASCADE,
  clause_type TEXT NOT NULL,  -- FK to policy_clause_types catalog (Notion-seeded; C1-01b)
  parameters_json JSONB,
  bbox_citation JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Costs (FK → cases, policy_clauses) + PF-1 category
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS rce.costs (
  cost_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id UUID NOT NULL REFERENCES rce.cases(case_id) ON DELETE CASCADE,
  amount NUMERIC,
  currency TEXT,
  -- PF-1 addition: controlled category enum
  category TEXT NOT NULL CHECK (category IN (
    'GOVERNMENT_FEE','LEGAL_FEE','TRANSLATION','NOTARIZATION',
    'RELOCATION_VENDOR','HOUSING_VENDOR','TAX_VENDOR','SCHOOLING','TRANSPORTATION',
    'LANGUAGE_TRAINING','CULTURAL_TRAINING','INSURANCE','OTHER'
  )),
  payer TEXT,
  policy_clause_id UUID REFERENCES rce.policy_clauses(policy_clause_id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Corrections (auditable change-log feeding training set)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS rce.corrections (
  correction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id UUID REFERENCES rce.cases(case_id) ON DELETE SET NULL,
  target_table TEXT NOT NULL,
  target_id UUID NOT NULL,
  field TEXT NOT NULL,
  value_before JSONB,
  value_after JSONB NOT NULL,
  reason_code TEXT NOT NULL CHECK (reason_code IN (
    'OCR_ERROR','TYPO_IN_SOURCE','AMBIGUOUS_PARTICLE',
    'LEGITIMATE_VARIATION','FRAUD_SUSPECTED','OTHER'
  )),
  reason_freetext TEXT,
  context_snapshot JSONB NOT NULL,
  corrected_by UUID,
  corrected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  promoted_to_training_set_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Indexes
-- ─────────────────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS canonical_entities_embedding_hnsw
  ON rce.canonical_entities USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS canonical_entities_person_dob
  ON rce.canonical_entities ((canonical_form->>'normalized_surname'), (canonical_form->>'dob'))
  WHERE entity_type = 'PERSON';

CREATE INDEX IF NOT EXISTS cases_by_arrival ON rce.cases(target_arrival_date);
CREATE INDEX IF NOT EXISTS extracted_fields_by_doc ON rce.extracted_fields(document_id);
CREATE INDEX IF NOT EXISTS corrections_by_target ON rce.corrections(target_table, target_id);
CREATE INDEX IF NOT EXISTS agent_runs_by_case ON rce.agent_runs(case_id, started_at);

-- ─────────────────────────────────────────────────────────────────────────────
-- RLS skeleton — permissive defaults; C1-01a hardens with tenant scoping.
-- Per SEC-003 hard gate: every new table gets ENABLE RLS + policy + REVOKE FROM anon.
-- ─────────────────────────────────────────────────────────────────────────────

DO $$
DECLARE
  t TEXT;
  rce_tables TEXT[] := ARRAY[
    'canonical_entities','employers','authorities','addresses','document_types','rules',
    'employees','cases','family_members','documents','agent_runs','extracted_fields',
    'entity_links','rule_versions','steps','deadlines','hr_policies','policy_clauses',
    'costs','corrections'
  ];
BEGIN
  FOREACH t IN ARRAY rce_tables LOOP
    EXECUTE format('ALTER TABLE rce.%I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format(
      'CREATE POLICY %I ON rce.%I FOR ALL TO authenticated USING (true) WITH CHECK (true)',
      t || '_permissive', t
    );
    EXECUTE format('REVOKE ALL ON rce.%I FROM anon', t);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON rce.%I TO authenticated', t);
    EXECUTE format('GRANT ALL ON rce.%I TO service_role', t);
  END LOOP;
END $$;

COMMENT ON SCHEMA rce IS
  'ReloPass Case Engine (RCE) ontology — Architecture Report §2.1 + §2.2. '
  'Coexists with legacy public.* schema. C1-01a hardens permissive RLS.';
