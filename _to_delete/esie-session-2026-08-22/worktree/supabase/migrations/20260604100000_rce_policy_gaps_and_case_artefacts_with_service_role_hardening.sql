-- ===========================================================================
-- Backfill for #176 — rce.policy_gaps + rce.case_artefacts + service-role-only
-- hardening, all in one file so a fresh `supabase db reset` reaches the same
-- end-state as prod (see audit/migration-drift-definitive-2026-06-02.md).
--
-- These three logical migrations were applied to prod out-of-band:
--   20260529125415  rce_policy_gaps              (table + permissive RLS)
--   20260529125813  rce_case_artefacts           (table + permissive RLS)
--   20260530111216  rce_service_role_only        (DO loop, flips rce.* policies)
-- None of them had repo source files. This migration is idempotent so it
-- applies cleanly to fresh DBs AND no-ops on prod (where the tables and
-- policies already exist in their final state).
-- ===========================================================================

-- Step 1 — tables (idempotent)

CREATE TABLE IF NOT EXISTS rce.policy_gaps (
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

CREATE UNIQUE INDEX IF NOT EXISTS policy_gaps_open_unique
  ON rce.policy_gaps (
    case_id,
    policy_clause_id,
    gap_type,
    COALESCE(family_member_id, '00000000-0000-0000-0000-000000000000'::uuid)
  )
  WHERE cleared_at IS NULL;

CREATE INDEX IF NOT EXISTS policy_gaps_by_case_open
  ON rce.policy_gaps (case_id) WHERE cleared_at IS NULL;

CREATE TABLE IF NOT EXISTS rce.case_artefacts (
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

CREATE INDEX IF NOT EXISTS case_artefacts_by_case_kind ON rce.case_artefacts (case_id, kind);
CREATE INDEX IF NOT EXISTS case_artefacts_by_subject  ON rce.case_artefacts (case_id, subject_kind, family_member_id);

-- Step 2 — enable RLS (idempotent — Postgres no-ops if already enabled)

ALTER TABLE rce.policy_gaps    ENABLE ROW LEVEL SECURITY;
ALTER TABLE rce.case_artefacts ENABLE ROW LEVEL SECURITY;

-- Step 3 — service-role-only policies (the rce.* canonical convention)
-- Mirrors the DO-block at prod version 20260530111216 but targets only the
-- two tables this migration introduces, so it's safe to drop in.

DROP POLICY IF EXISTS policy_gaps_permissive          ON rce.policy_gaps;
DROP POLICY IF EXISTS policy_gaps_permissive_all      ON rce.policy_gaps;
DROP POLICY IF EXISTS policy_gaps_service_role_only   ON rce.policy_gaps;
CREATE POLICY policy_gaps_service_role_only
  ON rce.policy_gaps FOR ALL TO service_role
  USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS case_artefacts_permissive        ON rce.case_artefacts;
DROP POLICY IF EXISTS case_artefacts_permissive_all    ON rce.case_artefacts;
DROP POLICY IF EXISTS case_artefacts_service_role_only ON rce.case_artefacts;
CREATE POLICY case_artefacts_service_role_only
  ON rce.case_artefacts FOR ALL TO service_role
  USING (true) WITH CHECK (true);

-- Step 4 — revoke from non-service-role, grant to service-role
-- Idempotent (REVOKE / GRANT are repeatable).

REVOKE ALL ON rce.policy_gaps    FROM anon, authenticated, public;
REVOKE ALL ON rce.case_artefacts FROM anon, authenticated, public;

GRANT ALL ON rce.policy_gaps    TO service_role;
GRANT ALL ON rce.case_artefacts TO service_role;
