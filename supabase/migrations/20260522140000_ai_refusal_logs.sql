-- Migration: ai_refusal_logs
-- P5-6: Unanswered questions weekly digest
--
-- Creates:
--   ai_refusal_logs  — stores embedding + metadata for every AI refusal event
--                      (TOPIC_REJECTED, LOW_CONFIDENCE, FAITHFULNESS_FAIL, POLICY_EXPIRED)
--
-- Privacy guarantee: raw query text is NEVER stored — only the embedding vector
-- and a truncated SHA-256 hash for deduplication.
--
-- The weekly digest edge function clusters these embeddings, identifies which
-- policy areas are generating the most unanswered questions, and emails HR.
--
-- Idempotent: IF NOT EXISTS guards on all DDL.

-- ---------------------------------------------------------------------------
-- 1. ai_refusal_logs table
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ai_refusal_logs (
    id                 UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id         UUID        NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    -- Hashed session identifier — no raw user identifier stored
    session_id         TEXT,
    -- SHA-256 of the original query, truncated to 8 hex chars — used for dedup
    query_hash         TEXT        NOT NULL,
    -- OpenAI text-embedding-3-small (1536 dims) — the raw query text is NEVER stored
    query_embedding    VECTOR(1536),
    -- Which stage of the assistant pipeline triggered the refusal
    fallback_reason    TEXT        NOT NULL
                           CHECK (fallback_reason IN (
                               'TOPIC_REJECTED',
                               'LOW_CONFIDENCE',
                               'FAITHFULNESS_FAIL',
                               'POLICY_EXPIRED'
                           )),
    -- CAT code suggested by the classification prompt (nullable — not always deterministic)
    suggested_cat_code TEXT        CHECK (
        suggested_cat_code IS NULL
        OR suggested_cat_code ~ '^CAT-\d{2}$'
    ),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE ai_refusal_logs IS
    'Privacy-preserving log of AI assistant refusals. '
    'Stores embeddings only — no raw query text. '
    'Used by the weekly unanswered-questions digest to identify policy gaps.';

-- ---------------------------------------------------------------------------
-- 2. Indexes
-- ---------------------------------------------------------------------------

-- Primary lookup: per-company, time-ordered (used by the weekly digest job)
CREATE INDEX IF NOT EXISTS idx_ai_refusal_logs_company_date
    ON ai_refusal_logs (company_id, created_at DESC);

-- Lookup by refusal type (analytics / observability)
CREATE INDEX IF NOT EXISTS idx_ai_refusal_logs_reason
    ON ai_refusal_logs (fallback_reason, created_at DESC);

-- HNSW index for fast nearest-neighbor search on embeddings
-- (used if we want to find similar past refusals for dedup or analysis)
CREATE INDEX IF NOT EXISTS idx_ai_refusal_logs_embedding
    ON ai_refusal_logs
    USING hnsw (query_embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ---------------------------------------------------------------------------
-- 3. Row-Level Security
-- ---------------------------------------------------------------------------

ALTER TABLE ai_refusal_logs ENABLE ROW LEVEL SECURITY;

-- HR/Admin users can read their company's refusal logs (for transparency)
DROP POLICY IF EXISTS "hr_read_own_company_refusal_logs" ON ai_refusal_logs;
CREATE POLICY "hr_read_own_company_refusal_logs"
    ON ai_refusal_logs FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.id::uuid = auth.uid()
              AND p.company_id = ai_refusal_logs.company_id
              AND p.role IN ('hr', 'admin')
        )
    );

-- No INSERT/UPDATE/DELETE via RLS — only the service role (edge functions) writes here.
-- Service role bypasses RLS by default in Supabase.

-- ---------------------------------------------------------------------------
-- 4. pg_cron weekly job (Monday 09:00 UTC)
-- ---------------------------------------------------------------------------
-- Requires pg_cron + pg_net extensions. Skips silently if not available.
-- The cron job calls the unanswered-questions-digest edge function via HTTP.
-- APP_SUPABASE_EDGE_URL and APP_SUPABASE_SERVICE_KEY must be set as GUC params
-- or substituted at deploy time.
-- ---------------------------------------------------------------------------

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron')
    AND EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_net') THEN
        -- Remove any old schedule first (idempotent)
        PERFORM cron.unschedule('unanswered-questions-digest-weekly')
        FROM cron.job
        WHERE jobname = 'unanswered-questions-digest-weekly';

        PERFORM cron.schedule(
            'unanswered-questions-digest-weekly',
            '0 9 * * 1',  -- Every Monday at 09:00 UTC
            $$
            SELECT net.http_post(
                url := current_setting('app.supabase_edge_url', true)
                       || '/unanswered-questions-digest',
                headers := jsonb_build_object(
                    'Content-Type',  'application/json',
                    'Authorization', 'Bearer ' || current_setting('app.supabase_service_key', true)
                ),
                body := '{"trigger":"cron"}'::jsonb
            );
            $$
        );

        RAISE NOTICE 'pg_cron job "unanswered-questions-digest-weekly" registered.';
    ELSE
        RAISE NOTICE 'pg_cron or pg_net not available — skipping cron schedule.';
    END IF;
END $$;
