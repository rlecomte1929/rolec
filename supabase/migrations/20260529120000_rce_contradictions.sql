-- C1-08 · Cross-document contradiction detection storage
--
-- Per Architecture Report §3.6 — the contradictions table is the
-- ReloPass equivalent of Parsewise's `inconsistency` rows. Every entry
-- captures a (case, canonical_entity, field_key) tuple where two or
-- more documents disagree on the field's value beyond the field's
-- allowed-variation tolerance.
--
-- Idempotency key: (case_id, canonical_entity_id, field_key, content_hash)
-- — content_hash is a SHA-256 over the sorted Candidate list, so
-- re-running detect_contradictions() on unchanged data is a no-op.
--
-- suggested_winner is intentionally always NULL at write time. The
-- Resolution UI (C1-12) or a human reviewer decides the canonical
-- value; the choice gets recorded into rce.corrections (which already
-- exists from C1-01).
--
-- SEC-003 hard gate: ENABLE RLS + permissive policy + REVOKE FROM anon
-- + GRANT to authenticated / service_role. C1-01a will tighten the
-- permissive policy to tenant-scoped once it ships.

CREATE TABLE rce.contradictions (
  contradiction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id UUID NOT NULL REFERENCES rce.cases(case_id) ON DELETE CASCADE,
  canonical_entity_id UUID
    REFERENCES rce.canonical_entities(canonical_entity_id) ON DELETE SET NULL,
  field_key TEXT NOT NULL,
  contradiction_type TEXT NOT NULL CHECK (contradiction_type IN (
    'DIRECT_CONTRADICTION',     -- e.g. payslip says 50 000 €, contract says 60 000 €
    'MISSING_VALUE',            -- one source has a value, another should but doesn't
    'TEMPORAL_INCONSISTENCY',   -- e.g. employment start before passport issued
    'FORMAT_MISMATCH',          -- same numeric value, different units (covered by FORMAT)
    'UNIT_MISMATCH'             -- e.g. salary stated monthly on one doc, annual on another
  )),

  -- Idempotency fingerprint over the sorted Candidate list.
  content_hash TEXT NOT NULL,

  -- Candidate values from each source. Each entry: value (JSONB), document_id,
  -- page, bbox, source_agent_run_id, confidence. Parsewise §3.6 shape.
  candidates JSONB NOT NULL,

  resolution_status TEXT NOT NULL DEFAULT 'Requires attention'
    CHECK (resolution_status IN (
      'Resolved','Requires attention','Not resolved','No result','Ignored'
    )),
  -- suggested_winner stays null on detect (spec) — the Resolution UI fills it
  -- if it surfaces a winner to the human reviewer.
  suggested_winner JSONB,

  -- Bookkeeping
  detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  detected_by TEXT NOT NULL DEFAULT 'agent_contradiction_v1',
  resolved_at TIMESTAMPTZ,
  resolved_by UUID,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  UNIQUE (case_id, canonical_entity_id, field_key, content_hash)
);

CREATE INDEX contradictions_by_case
  ON rce.contradictions(case_id, resolution_status);

CREATE INDEX contradictions_by_entity_field
  ON rce.contradictions(canonical_entity_id, field_key, detected_at);

-- ─────────────────────────────────────────────────────────────────────────────
-- SEC-003 hard gate
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE rce.contradictions ENABLE ROW LEVEL SECURITY;

CREATE POLICY contradictions_permissive_all
  ON rce.contradictions FOR ALL TO authenticated USING (true) WITH CHECK (true);

REVOKE ALL ON rce.contradictions FROM anon;

GRANT SELECT, INSERT, UPDATE, DELETE
  ON rce.contradictions
  TO authenticated, service_role;
