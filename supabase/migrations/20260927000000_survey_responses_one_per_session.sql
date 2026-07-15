-- [AIQ-1542] One survey response per test-drive session.
--
-- `survey_responses` had only a NON-unique index on session_id (idx_survey_responses_session),
-- and POST /api/test-drive/survey is unauthenticated + keyed only on session_id. So a
-- double-submit (or a tamper) created duplicate rows and inflated the surveyed count. The
-- endpoint now upserts (latest wins, AIQ-1542); this index enforces it at the DB level as
-- defense-in-depth.
--
-- Partial (session_id IS NOT NULL): anonymous / no-session surveys are allowed and must not
-- collide with one another. `survey_responses` already has RLS enabled + anon revoked
-- (20260830000000_test_drive_schema.sql) — no new security gate needed here.
--
-- Idempotent: the dedupe DELETE is a no-op once clean, and the index uses IF NOT EXISTS.

-- 1) Collapse any pre-existing duplicates, keeping the most recent row per session.
DELETE FROM public.survey_responses a
USING public.survey_responses b
WHERE a.session_id IS NOT NULL
  AND a.session_id = b.session_id
  AND (a.created_at, a.ctid) < (b.created_at, b.ctid);

-- 2) Enforce at most one survey per non-null session going forward.
CREATE UNIQUE INDEX IF NOT EXISTS uq_survey_responses_session
    ON public.survey_responses (session_id)
    WHERE session_id IS NOT NULL;
