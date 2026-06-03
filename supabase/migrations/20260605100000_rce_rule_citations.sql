-- C1-01c · rce.rule_citations — provenance join between case outputs and rule versions (AIQ-751)
--
-- Architecture Report §4 (Citations / "show your work"). Every deterministic
-- output the engine surfaces to a case — a STEP, a DEADLINE, or an
-- ELIGIBILITY_BRANCH — must be traceable to the exact rule_version that produced
-- it. This table is that audit trail: one row per (output, rule_version) pair.
--
-- This task ships the TABLE ONLY. The writer (the corridor evaluator) is a
-- separate task and populates rule_citations as it materialises case outputs.
-- Nothing in this migration writes rows.
--
-- Why a join table and not a column on each output: a single output can be
-- justified by more than one rule version (e.g. a deadline derived from both a
-- federal and a state rule), and the C2-05 "rule impact" view needs to fan out
-- the other way — "which cases cite rule_version X" — so the relationship is
-- many-to-many and must live in its own table.
--
-- Adds one table to the rce.* ontology (introduced in C1-01,
-- 20260528020000_relopass_case_engine_v1.sql):
--
--   rce.rule_citations  — one row per (case output, rule_version) provenance link.
--
-- FK semantics:
--   case_id         -> rce.cases         ON DELETE CASCADE   (drop a case, drop its citations)
--   rule_version_id -> rce.rule_versions ON DELETE RESTRICT  (a cited rule_version
--                       cannot be hard-deleted while citations reference it —
--                       provenance must not silently vanish)
--
-- Idempotency at the data layer: UNIQUE (case_id, output_kind, output_id,
-- rule_version_id) — re-running the evaluator on an unchanged case re-derives the
-- same citation set without duplicating rows (writer uses ON CONFLICT DO NOTHING).
--
-- SEC-003 HARD GATE compliance (root + backend CLAUDE.md): this new table gets
--   1. ENABLE ROW LEVEL SECURITY
--   2. At least one tenant/role-scoped policy (service_role + case-visibility read)
--   3. REVOKE ALL FROM anon
-- Citations inherit the visibility of the case they belong to: an authenticated
-- user may read a citation only if they can read its parent rce.cases row. Writes
-- are service_role only (the evaluator runs under the service key).

-- ─────────────────────────────────────────────────────────────────────────────
-- Table
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE rce.rule_citations (
  rule_citation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  -- The case whose output this citation justifies. CASCADE: citations are
  -- meaningless without their case.
  case_id          UUID NOT NULL REFERENCES rce.cases(case_id) ON DELETE CASCADE,
  -- Which kind of output is being justified.
  output_kind      TEXT NOT NULL CHECK (output_kind IN ('STEP','DEADLINE','ELIGIBILITY_BRANCH')),
  -- The id of that output (a STEP id, DEADLINE id, or ELIGIBILITY_BRANCH id).
  -- Not a DB-level FK because it points into three different output tables
  -- discriminated by output_kind; integrity is enforced by the writer.
  output_id        UUID NOT NULL,
  -- The exact rule_version that produced the output. RESTRICT: provenance must
  -- survive — a cited rule_version cannot be hard-deleted out from under a citation.
  rule_version_id  UUID NOT NULL REFERENCES rce.rule_versions(rule_version_id) ON DELETE RESTRICT,
  -- Human-facing legal reference string (e.g. "Utlendingsforskriften § 10-1").
  legal_reference  TEXT,
  -- Canonical source URL for the cited rule, if available.
  source_url       TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- Re-deriving an unchanged output yields the same citation, not a duplicate.
  UNIQUE (case_id, output_kind, output_id, rule_version_id)
);

-- C2-05 "rule impact" read pattern: "which cases cite rule_version X".
CREATE INDEX rule_citations_by_version
  ON rce.rule_citations (rule_version_id);

-- Per-case read pattern: "show all citations for this case, newest first".
CREATE INDEX rule_citations_by_case
  ON rce.rule_citations (case_id, created_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- SEC-003 hard gate: RLS + service-role + case-visibility-scoped read policy +
-- REVOKE FROM anon. Drop-then-recreate (no IF NOT EXISTS on policy), mirroring
-- the rce.rule_change_proposals convention (20260604000000).
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE rce.rule_citations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rule_citations_service_role_all ON rce.rule_citations;
DROP POLICY IF EXISTS rule_citations_case_visibility_read ON rce.rule_citations;

-- Service role full access: the corridor evaluator writes through the service key.
-- (service_role bypasses RLS regardless, but the explicit policy documents intent.)
CREATE POLICY rule_citations_service_role_all
  ON rce.rule_citations FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

-- An authenticated user may READ a citation only if they can read its parent
-- case. This delegates the tenant boundary to rce.cases' own RLS — a citation is
-- never more visible than the case it belongs to. No write paths for ordinary
-- authenticated users; the evaluator is the sole writer.
CREATE POLICY rule_citations_case_visibility_read
  ON rce.rule_citations FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM rce.cases c
      WHERE c.case_id = rce.rule_citations.case_id
    )
  );

REVOKE ALL ON rce.rule_citations FROM anon;
-- Defence-in-depth: drop the blanket grant, then re-grant only read to
-- authenticated (gated by the case-visibility policy above). Writes stay
-- service_role only.
REVOKE ALL ON rce.rule_citations FROM authenticated;
GRANT SELECT ON rce.rule_citations TO authenticated;
GRANT ALL ON rce.rule_citations TO service_role;

COMMENT ON TABLE rce.rule_citations IS
  'C1-01c (AIQ-751): provenance join between case outputs (STEP/DEADLINE/'
  'ELIGIBILITY_BRANCH) and the rule_version that produced them. Table only; the '
  'corridor evaluator (separate task) is the sole writer.';

COMMENT ON COLUMN rce.rule_citations.output_id IS
  'Id of the justified output, discriminated by output_kind. Not a DB FK because '
  'it points into three different output tables; integrity is enforced by the writer.';

COMMENT ON COLUMN rce.rule_citations.rule_version_id IS
  'The exact rule_version that produced the output. ON DELETE RESTRICT so '
  'provenance cannot silently vanish while a citation references it.';
