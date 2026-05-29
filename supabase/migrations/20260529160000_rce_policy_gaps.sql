-- C2-06 — rce.policy_gaps
-- Persistence target for the policy-versus-reality gap detector
-- (backend/relopass/policy_evidence/detector.py + the C2-06-FOLLOWUP adapter).
--
-- One row per (case, clause, gap_type, subject) that is currently un-evidenced.
-- The adapter diffs detected gaps against open rows:
--   detected only → INSERT
--   existing only → UPDATE SET cleared_at = now()
-- Cleared rows are retained for the audit trail (never deleted by the adapter).
--
-- RLS follows the rce.* permissive convention established in
-- 20260528020000_relopass_case_engine_v1.sql (§"RLS skeleton"): permissive
-- USING(true) for authenticated, anon revoked, tenant hardening deferred to
-- C1-01a. HR/case scoping for the read endpoint is enforced at the FastAPI
-- app layer via _assert_case_access. Per SEC-003 hard gate this still gets
-- ENABLE RLS + a policy + REVOKE FROM anon.

CREATE TABLE rce.policy_gaps (
  gap_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id           UUID NOT NULL REFERENCES rce.cases(case_id) ON DELETE CASCADE,
  policy_clause_id  UUID NOT NULL REFERENCES rce.policy_clauses(policy_clause_id) ON DELETE CASCADE,
  clause_type       TEXT NOT NULL,
  family_member_id  UUID REFERENCES rce.family_members(family_member_id) ON DELETE CASCADE,
  subject_kind      TEXT NOT NULL CHECK (subject_kind IN (
                      'EMPLOYEE','SPOUSE','CHILD','DEPENDENT_PARENT','CASE')),
  gap_type          TEXT NOT NULL CHECK (gap_type IN (
                      'MISSING_BENEFIT_DELIVERY','MISSING_DOCUMENT','BELOW_ENTITLEMENT')),
  suggested_action  TEXT,
  evidence_payload  JSONB,
  citation          JSONB,
  detected_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  cleared_at        TIMESTAMPTZ,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One open gap per (case, clause, gap_type, subject). The COALESCE sentinel
-- collapses NULL family_member_id (CASE-level / employee-level subjects) so
-- they participate in uniqueness; partial predicate lets a cleared gap and a
-- freshly re-detected open gap coexist.
CREATE UNIQUE INDEX policy_gaps_open_unique
  ON rce.policy_gaps (
    case_id,
    policy_clause_id,
    gap_type,
    COALESCE(family_member_id, '00000000-0000-0000-0000-000000000000'::uuid)
  )
  WHERE cleared_at IS NULL;

CREATE INDEX policy_gaps_by_case_open
  ON rce.policy_gaps (case_id) WHERE cleared_at IS NULL;

-- RLS (rce.* permissive convention; SEC-003 hard gate)
ALTER TABLE rce.policy_gaps ENABLE ROW LEVEL SECURITY;

CREATE POLICY policy_gaps_permissive ON rce.policy_gaps
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

REVOKE ALL ON rce.policy_gaps FROM anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON rce.policy_gaps TO authenticated;
GRANT ALL ON rce.policy_gaps TO service_role;

COMMENT ON TABLE rce.policy_gaps IS
  'Detected policy-versus-reality gaps (Architecture Report §6.4). '
  'Written by the C2-06 detector adapter; cleared rows retained for audit. '
  'Permissive RLS — C1-01a hardens with tenant scoping.';
