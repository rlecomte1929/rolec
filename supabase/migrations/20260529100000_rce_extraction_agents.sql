-- C1-05a · Extraction Agent registry — Parsewise versioning + persistence
--
-- Adds two tables to the rce.* ontology (introduced in C1-01):
--
--   rce.extraction_agents   — logical agent identity (name + current_version)
--   rce.agent_versions      — each version's frozen Parsewise field set
--
-- Versioning rule (Parsewise, non-negotiable): changing any of
--   { extraction_instructions, value_type, unit, examples,
--     resolution_instructions, inconsistency_instructions,
--     enable_complex_calculations_in_resolution, enable_web_search }
-- creates a new agent_versions row AND clears the old version's extractions.
-- The "clear extractions" side-effect is implemented in Python (relopass.agents.registry)
-- because it crosses the agent_versions → extracted_fields boundary and benefits
-- from auditable application-layer logic. The SQL constraint here only ensures
-- the new version row exists and is referenced as `current_version`.
--
-- Foreign keys:
--   * rce.agent_versions.agent_id   → rce.extraction_agents.agent_id
--   * rce.extraction_agents.current_version_id → rce.agent_versions.agent_version_id  (deferred)
--   * rce.agent_runs.agent_id is TEXT (per C1-01), not a FK. We add an optional
--     reference column rce.agent_runs.agent_version_ref → rce.agent_versions.agent_version_id
--     so cost lookups by version remain efficient. The existing TEXT columns
--     (agent_id, agent_version) stay populated for human-readable audit.
--
-- SEC-003 hard gate compliance: every new table gets ENABLE RLS + a permissive
-- policy + REVOKE FROM anon + GRANT to authenticated / service_role. C1-01a
-- will tighten the policies to tenant-scoped ones.

CREATE TABLE rce.extraction_agents (
  agent_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  -- Stable human-readable identifier (e.g. "passport_td3.surname", "payslip.gross_salary").
  -- Names are scoped per document_type via the dot-prefix convention.
  name TEXT NOT NULL UNIQUE,
  description TEXT,
  -- Pointer to the current version. NULL while the first version is being inserted;
  -- the registry sets it after the first agent_versions row lands.
  current_version_id UUID,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE rce.agent_versions (
  agent_version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id UUID NOT NULL REFERENCES rce.extraction_agents(agent_id) ON DELETE CASCADE,
  -- Monotonically increasing per agent_id. The registry computes the next value
  -- inside a serialisable transaction so concurrent saves don't collide.
  version_number INT NOT NULL,
  -- SHA-256 over the canonical JSON form of the versioned-field tuple (see below).
  -- Indexed for O(log n) lookup: "is this exact field set already stored?"
  version_hash TEXT NOT NULL,

  -- The 9 Parsewise agent fields (the spec from Architecture Report §4.1).
  -- All fields are stored verbatim on every version row so a version is a
  -- complete, self-contained snapshot.
  extraction_instructions TEXT NOT NULL,
  value_type TEXT NOT NULL CHECK (value_type IN ('string','number','date','boolean','enum')),
  unit TEXT,
  dimensions TEXT,
  resolution_instructions TEXT,
  inconsistency_instructions TEXT,
  enable_web_search BOOLEAN NOT NULL DEFAULT false,
  enable_complex_calculations_in_resolution BOOLEAN NOT NULL DEFAULT false,
  -- Few-shot exemplars; structure validated at the application layer (Pydantic).
  examples JSONB NOT NULL DEFAULT '[]'::jsonb,
  -- Per-field-key schema the runtime validates against post-extraction
  -- (Pydantic JSON-Schema export).
  output_schema JSONB,

  -- Bookkeeping
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID,

  UNIQUE (agent_id, version_number),
  UNIQUE (agent_id, version_hash)
);

-- After agent_versions exists, the current_version_id FK can point at it.
ALTER TABLE rce.extraction_agents
  ADD CONSTRAINT extraction_agents_current_version_fk
  FOREIGN KEY (current_version_id) REFERENCES rce.agent_versions(agent_version_id)
  ON DELETE SET NULL
  DEFERRABLE INITIALLY DEFERRED;

CREATE INDEX agent_versions_by_agent
  ON rce.agent_versions(agent_id, version_number DESC);

CREATE INDEX agent_versions_by_hash
  ON rce.agent_versions(agent_id, version_hash);

-- Connect agent_runs (C1-01) to agent_versions so cost analysis by version is
-- a single join instead of two text-column lookups.
ALTER TABLE rce.agent_runs
  ADD COLUMN agent_version_ref UUID REFERENCES rce.agent_versions(agent_version_id) ON DELETE SET NULL;

CREATE INDEX agent_runs_by_version_ref
  ON rce.agent_runs(agent_version_ref, started_at);

-- ─────────────────────────────────────────────────────────────────────────────
-- SEC-003 hard gate: RLS + policy + revoke + grant
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE rce.extraction_agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE rce.agent_versions   ENABLE ROW LEVEL SECURITY;

-- Permissive policies (C1-01a hardens to tenant-scoped policies). Mirroring
-- the C1-01 convention so the audit dashboard sees consistent shape.
CREATE POLICY extraction_agents_permissive_all
  ON rce.extraction_agents FOR ALL TO authenticated USING (true) WITH CHECK (true);

CREATE POLICY agent_versions_permissive_all
  ON rce.agent_versions FOR ALL TO authenticated USING (true) WITH CHECK (true);

REVOKE ALL ON rce.extraction_agents FROM anon;
REVOKE ALL ON rce.agent_versions    FROM anon;

GRANT SELECT, INSERT, UPDATE, DELETE ON rce.extraction_agents TO authenticated, service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON rce.agent_versions    TO authenticated, service_role;
