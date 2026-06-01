-- C1-08 (the long-undisclosed dependency surfaced by #189/#183 during the
-- 2026-06-01 PR queue triage — see audit/daytime-run-stuck.md).
-- Creates rce.contradictions to unblock the C1-12 resolve+escalate flow.
-- Schema synthesized from #189's resolve handler (backend/app/routers/hr_case_resolve.py)
-- + #181's defensively-degraded read paths (backend/app/routers/hr_case_detail.py).
-- IDEMPOTENT: uses IF NOT EXISTS / DROP POLICY IF EXISTS so it applies cleanly to
-- fresh DBs AND no-ops on prod if the table is later created out-of-band (lesson
-- from #176's stale-vs-hardened migration reconciliation).
--
-- ─────────────────────────────────────────────────────────────────────────────
-- RLS DESIGN NOTE — service-role-only (matches live rce.* convention)
-- ====================================================================
-- Architecture Report §12.2 specifies a 3-principal policy model
-- (HR Operator / Employee / Family Member) for rce.* tables. We DELIBERATELY
-- deviate from that spec here and match the actual live convention used by
-- every other rce.* table on prod (rce.cases, rce.corrections,
-- rce.extracted_fields, rce.rule_change_proposals — all *_service_role_only).
--
-- Reasoning:
--   1. The rce schema is NOT PostgREST-exposed (anon/authenticated requests
--      return 406 "Invalid schema: rce"). Direct client access is impossible.
--   2. All read/write paths go through the backend pooler with service-role
--      credentials, which bypasses RLS regardless of policy content.
--   3. A 3-principal policy would be never-exercised code that creates a
--      file-vs-prod divergence — exactly the #176 pattern that bit us when
--      stale permissive policies (USING(true) for authenticated) almost shipped
--      over prod's restrictive *_service_role_only.
--
-- If/when the rce schema is exposed via PostgREST or accessed via the Supabase-JS
-- client (neither currently planned), replace this with a 3-principal hardening
-- migration aligned with the live convention at that time — NOT with §12.2
-- verbatim, which predates the service-role-only convention.
-- See: audit/dual-layer-mount-check-2026-06-01.md, audit/daytime-run-stuck.md.
-- ─────────────────────────────────────────────────────────────────────────────

-- ─────────────────────────────────────────────────────────────────────────────
-- Table
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS rce.contradictions (
  contradiction_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id              UUID NOT NULL REFERENCES rce.cases(case_id) ON DELETE CASCADE,
  -- Nullable: #189 guards `if canonical_entity_id and field_key` — a contradiction
  -- can predate canonical-entity resolution (C1-07). SET NULL mirrors the sibling
  -- FK pattern in 20260528020000 (extracted_fields → canonical_entities).
  canonical_entity_id  UUID REFERENCES rce.canonical_entities(canonical_entity_id) ON DELETE SET NULL,
  -- Nullable for the same reason (paired with canonical_entity_id in #189's guard).
  field_key            TEXT,
  contradiction_type   TEXT NOT NULL,
  -- JSONB array of candidate objects. #181/#189 parse this as a list of dicts
  -- (candidate_id, document_id, value_raw, value_canonical, confidence, bbox_page,
  --  bbox, source_agent_run_id, source_label, …). Kept as JSONB, not a child table,
  -- to match how both handlers already read/write it.
  candidates           JSONB NOT NULL DEFAULT '[]'::jsonb,
  /* resolution_status values match #181's existing buckets:
     'Requires attention' + 'Not resolved' + 'No result' aggregate to "pending" in
     the summary endpoint (hr_case_detail.py); 'Resolved' is the only terminal state.
     #189's escalate handler transitions to 'Not resolved' (kept in the pending
     bucket, ownership transferred to compliance); resolve transitions to 'Resolved'. */
  resolution_status    TEXT NOT NULL DEFAULT 'Requires attention'
                         CHECK (resolution_status IN
                                ('Requires attention','Not resolved','No result','Resolved')),
  -- JSONB winning candidate, set by #189's resolve: `SET suggested_winner = CAST(:winner AS JSONB)`.
  suggested_winner     JSONB,
  -- Idempotency/dedup hash of the contradiction's content (#181 SELECTs it).
  content_hash         TEXT,
  detected_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- detected_by TEXT (conservative call): accepts both system identifiers
  -- ('extraction_agent_v3', 'rule_engine') and user names. If it should be a FK to
  -- an agent table later, it can be migrated. Nullable — some detection paths may
  -- not record a source.
  detected_by          TEXT,
  resolved_at          TIMESTAMPTZ,
  -- resolved_by UUID FK to auth.users(id): #189 binds `:hr_user_id = hr_user.id`,
  -- which the resolve handler derives from JWT auth (= auth.uid()). Nullable until
  -- resolution. ⚠️ Reviewer: confirm hr_user.id is the auth.users uuid (not the
  -- legacy public.users.id) before prod apply — if it's the legacy id, drop the FK.
  resolved_by          UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Indexes
-- ─────────────────────────────────────────────────────────────────────────────
-- #189 resolve: SELECT … FROM rce.contradictions WHERE contradiction_id = … (PK)
--   and WHERE case_id = … ; #181 list: WHERE case_id = … ORDER BY detected_at DESC.
CREATE INDEX IF NOT EXISTS ix_rce_contradictions_case_id
  ON rce.contradictions (case_id);
-- #181 summary: COUNT(*) FILTER (WHERE resolution_status …) GROUP BY case_id.
CREATE INDEX IF NOT EXISTS ix_rce_contradictions_case_status
  ON rce.contradictions (case_id, resolution_status);

-- ─────────────────────────────────────────────────────────────────────────────
-- RLS — service-role-only (see design note above). SEC-003 hard gate satisfied:
-- ENABLE RLS + a policy + REVOKE FROM anon.
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE rce.contradictions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "contradictions_service_role_only" ON rce.contradictions;
CREATE POLICY "contradictions_service_role_only"
  ON rce.contradictions FOR ALL TO service_role
  USING (true) WITH CHECK (true);

REVOKE ALL ON rce.contradictions FROM anon, authenticated;
GRANT ALL ON rce.contradictions TO service_role;  -- matches rce.extracted_fields grant set
