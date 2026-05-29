-- C2-06-FOLLOWUP — rce.case_artefacts
-- Canonical store the policy-gap detector reads from (Architecture Report §6.4).
-- Hybrid model (see AIQ-568 DECISION block): native artefact kinds
-- (language_training_booking, permit_application_submitted, legal_counsel_engaged)
-- are written here directly; document-backed kinds (housing_lease_document,
-- housing_invoice) are mirrored from rce.documents / rce.costs by the adapter's
-- sync helpers, deduped via the source_* UNIQUE constraints.
--
-- RLS note: the DECISION-block sketch scoped RLS via public.hr_users
-- (auth_user_id, employer_id). Those columns do not exist on this database
-- (public.hr_users is {id, company_id, profile_id, permissions_json,
-- created_at}), so that policy cannot be applied. This migration instead
-- follows the rce.* permissive convention established in
-- 20260528020000_relopass_case_engine_v1.sql — tenant hardening deferred to
-- C1-01a, HR scoping enforced at the FastAPI app layer (require_admin_or_hr +
-- org_id vs relocation_cases.company_id, mirroring hr_case_detail.py). SEC-003
-- hard gate is still satisfied (ENABLE RLS + policy + REVOKE FROM anon).

CREATE TABLE rce.case_artefacts (
  artefact_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id              UUID NOT NULL REFERENCES rce.cases(case_id) ON DELETE CASCADE,
  kind                 TEXT NOT NULL,
  subject_kind         TEXT NOT NULL CHECK (subject_kind IN (
                         'EMPLOYEE','SPOUSE','CHILD','DEPENDENT_PARENT','CASE')),
  family_member_id     UUID REFERENCES rce.family_members(family_member_id) ON DELETE CASCADE,
  payload              JSONB,
  magnitude            NUMERIC,
  unit                 TEXT,
  delivered_at         TIMESTAMPTZ,
  source_document_id   UUID REFERENCES rce.documents(document_id) ON DELETE CASCADE,
  source_cost_id       UUID REFERENCES rce.costs(cost_id) ON DELETE CASCADE,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT case_artefacts_one_per_source_doc UNIQUE (source_document_id),
  CONSTRAINT case_artefacts_one_per_source_cost UNIQUE (source_cost_id),
  CONSTRAINT case_artefacts_subject_consistency CHECK (
    (subject_kind = 'CASE' AND family_member_id IS NULL)
    OR (subject_kind IN ('SPOUSE','CHILD','DEPENDENT_PARENT') AND family_member_id IS NOT NULL)
    OR (subject_kind = 'EMPLOYEE' AND family_member_id IS NULL)
  )
);

CREATE INDEX case_artefacts_by_case_kind ON rce.case_artefacts (case_id, kind);
CREATE INDEX case_artefacts_by_subject ON rce.case_artefacts (case_id, subject_kind, family_member_id);

ALTER TABLE rce.case_artefacts ENABLE ROW LEVEL SECURITY;

CREATE POLICY case_artefacts_permissive ON rce.case_artefacts
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

REVOKE ALL ON rce.case_artefacts FROM anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON rce.case_artefacts TO authenticated;
GRANT ALL ON rce.case_artefacts TO service_role;

COMMENT ON TABLE rce.case_artefacts IS
  'Canonical artefact store for the policy-gap detector (Architecture Report §6.4). '
  'Native kinds written directly; document/cost-backed kinds mirrored via adapter '
  'sync helpers. Permissive RLS — C1-01a hardens with tenant scoping.';
