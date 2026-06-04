-- P1-08a · rce.roadmap_audit_log — append-only audit trail for roadmap decisions (AIQ-639)
--
-- Parent P1-08 (AIQ-202): "every roadmap decision traceable to source + version".
-- Legal defensibility requires that every piece of AI-generated advice can be
-- reconstructed: which rule_version was used, which source URL was cited, when
-- it was fetched, who (AI or specialist) generated the step, and what the model
-- confidence was at the time. Specialist corrections are captured inline so the
-- full decision history survives.
--
-- This task ships the TABLE ONLY. The writer (the roadmap generator + the
-- specialist-correction path) is a separate subtask (P1-08b) and populates this
-- table transactionally with each roadmap write. Nothing in this migration
-- writes rows.
--
-- Why this table is APPEND-ONLY: it is an audit log. Once a roadmap decision is
-- recorded it must never be mutated or removed — that is what makes the trail
-- legally defensible (P1-08 Technical Constraints: "Append-only table, no UPDATE
-- or DELETE"). We enforce append-only at the RLS layer: there is NO UPDATE and NO
-- DELETE policy, so every UPDATE/DELETE issued by a non-service role is denied by
-- RLS (a missing policy = no rows match = operation refused). The privilege grant
-- is also narrowed to SELECT + INSERT only (defence in depth).
--
-- Adds one table to the rce.* ontology (introduced in C1-01,
-- 20260528020000_relopass_case_engine_v1.sql), mirroring the rce.rule_citations
-- convention (20260605100000):
--
--   rce.roadmap_audit_log  — one immutable row per roadmap-generation /
--                            specialist-correction event.
--
-- FK semantics:
--   case_id         -> rce.cases         ON DELETE CASCADE   (drop a case, drop its log)
--   step_id         -> rce.steps         ON DELETE SET NULL  (a generation event is not
--                       always step-scoped, and a step may be removed while the audit
--                       record of how it was produced is retained)
--   rule_version_id -> rce.rule_versions ON DELETE RESTRICT  (a cited rule_version cannot
--                       be hard-deleted while an audit row references it — provenance
--                       must not silently vanish; this FK also blocks invalid ids)
--
-- SEC-003 HARD GATE compliance (root + backend CLAUDE.md): this new table gets
--   1. ENABLE ROW LEVEL SECURITY
--   2. At least one tenant/role-scoped policy (service_role + case-visibility)
--   3. REVOKE ALL FROM anon
-- Audit rows inherit the visibility of the case they belong to: an authenticated
-- user may read / append a row only if they can read its parent rce.cases row.

-- ─────────────────────────────────────────────────────────────────────────────
-- Table
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE rce.roadmap_audit_log (
  roadmap_audit_log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  -- The case whose roadmap decision this row records. CASCADE: an audit row is
  -- meaningless without its case.
  case_id              UUID NOT NULL REFERENCES rce.cases(case_id) ON DELETE CASCADE,
  -- The roadmap step this decision produced, if the event is step-scoped.
  -- Nullable + SET NULL: not every generation event maps to a single step, and a
  -- step may be removed while we retain the audit record of how it was produced.
  step_id              UUID REFERENCES rce.steps(step_id) ON DELETE SET NULL,
  -- The exact rule_version that produced the decision. RESTRICT: provenance must
  -- survive — a cited rule_version cannot be hard-deleted out from under an audit
  -- row. This FK also rejects any insert with an invalid rule_version_id.
  rule_version_id      UUID NOT NULL REFERENCES rce.rule_versions(rule_version_id) ON DELETE RESTRICT,
  -- Canonical source URL cited for the rule at generation time.
  source_url           TEXT,
  -- When that source was fetched (provenance freshness).
  source_fetch_date    DATE,
  -- Who produced this decision. rce.* convention is TEXT + CHECK (not a native
  -- PG enum), matching link_method / category / reason_code elsewhere in the schema.
  generated_by         TEXT NOT NULL CHECK (generated_by IN ('AI','SPECIALIST')),
  -- When the decision was generated (immutable record timestamp).
  generated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- Model confidence at the moment of generation (NUMERIC(4,3) matches the
  -- confidence scale used by rce.entity_links / rce.canonical_entities).
  confidence_at_time   NUMERIC(4,3),
  -- Inline record of any specialist corrections applied to this decision.
  specialist_corrections JSONB,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Per-case read pattern: "show the full audit trail for this case, newest first".
CREATE INDEX roadmap_audit_log_by_case
  ON rce.roadmap_audit_log (case_id, generated_at DESC);

-- Rule-change-notification read pattern (P1-08d): "which cases were generated
-- against rule_version X" — when X changes, flag those cases.
CREATE INDEX roadmap_audit_log_by_version
  ON rce.roadmap_audit_log (rule_version_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- SEC-003 hard gate: RLS + service-role + case-visibility-scoped INSERT/SELECT
-- policies + REVOKE FROM anon. NO UPDATE and NO DELETE policy — append-only.
-- Drop-then-recreate (no IF NOT EXISTS on policy), mirroring the rce.rule_citations
-- convention (20260605100000).
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE rce.roadmap_audit_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS roadmap_audit_log_service_role_all ON rce.roadmap_audit_log;
DROP POLICY IF EXISTS roadmap_audit_log_case_visibility_read ON rce.roadmap_audit_log;
DROP POLICY IF EXISTS roadmap_audit_log_case_visibility_insert ON rce.roadmap_audit_log;

-- Service role full access: the roadmap generator writes through the service key.
-- (service_role bypasses RLS regardless, but the explicit policy documents intent.)
CREATE POLICY roadmap_audit_log_service_role_all
  ON rce.roadmap_audit_log FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

-- An authenticated user may READ an audit row only if they can read its parent
-- case. Delegates the tenant boundary to rce.cases' own RLS — an audit row is
-- never more visible than the case it belongs to.
CREATE POLICY roadmap_audit_log_case_visibility_read
  ON rce.roadmap_audit_log FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM rce.cases c
      WHERE c.case_id = rce.roadmap_audit_log.case_id
    )
  );

-- An authenticated user may APPEND an audit row only for a case they can read.
-- INSERT only — there is intentionally NO UPDATE and NO DELETE policy, so the log
-- is append-only: any UPDATE/DELETE by a non-service role matches no policy and is
-- denied by RLS.
CREATE POLICY roadmap_audit_log_case_visibility_insert
  ON rce.roadmap_audit_log FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM rce.cases c
      WHERE c.case_id = rce.roadmap_audit_log.case_id
    )
  );

REVOKE ALL ON rce.roadmap_audit_log FROM anon;
-- Defence-in-depth: drop the blanket grant, then re-grant only SELECT + INSERT to
-- authenticated (each gated by the case-visibility policies above). UPDATE and
-- DELETE are not granted at all — append-only at both the privilege and policy layers.
REVOKE ALL ON rce.roadmap_audit_log FROM authenticated;
GRANT SELECT, INSERT ON rce.roadmap_audit_log TO authenticated;
GRANT ALL ON rce.roadmap_audit_log TO service_role;

COMMENT ON TABLE rce.roadmap_audit_log IS
  'P1-08a (AIQ-639): append-only audit trail — one immutable row per roadmap '
  'generation / specialist correction, traceable to the rule_version, source URL '
  'and fetch date that produced it. INSERT-only RLS (no UPDATE/DELETE policy). '
  'Table only; the roadmap generator (P1-08b) is the sole writer.';

COMMENT ON COLUMN rce.roadmap_audit_log.generated_by IS
  'Who produced the decision: AI (roadmap generator) or SPECIALIST (human correction).';

COMMENT ON COLUMN rce.roadmap_audit_log.rule_version_id IS
  'The exact rule_version that produced the decision. ON DELETE RESTRICT so '
  'provenance cannot silently vanish while an audit row references it.';

COMMENT ON COLUMN rce.roadmap_audit_log.specialist_corrections IS
  'Inline JSONB record of any specialist corrections applied to this decision.';
