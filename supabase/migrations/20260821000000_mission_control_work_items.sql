-- Mission Control P1 — canonical demand store.
-- Unifies the scattered intakes (public.feedback bug/idea, support_tickets,
-- ai_human_feedback, rce.contradictions, manual) into one ranked work queue that
-- the admin console reads. Admin/service-role only: the backend reads these with
-- the service role; the frontend never touches them directly. Hard security gates
-- per backend/CLAUDE.md: RLS enabled, service-role policy, anon revoked.

-- ── work_items ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.work_items (
  id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),

  -- Provenance (idempotency key = source + source_id).
  source        TEXT        NOT NULL CHECK (source IN ('feedback', 'support', 'ai_feedback', 'contradiction', 'manual')),
  source_id     TEXT,
  source_url    TEXT,

  -- Demand content.
  kind          TEXT        NOT NULL DEFAULT 'task' CHECK (kind IN ('bug', 'idea', 'quality', 'task')),
  title         TEXT        NOT NULL,
  body          TEXT,                                  -- PII-masked before write
  reporter_role TEXT,
  company_id    TEXT,

  -- Triage + lifecycle.
  status        TEXT        NOT NULL DEFAULT 'new'
                            CHECK (status IN ('new', 'triaged', 'planned', 'dispatched', 'in_review', 'done', 'wont_do', 'blocked')),
  priority      TEXT        NOT NULL DEFAULT 'P3' CHECK (priority IN ('P0', 'P1', 'P2', 'P3')),
  complexity    TEXT        CHECK (complexity IN ('trivial', 'low', 'medium', 'high')),
  auto_fixable  BOOLEAN     NOT NULL DEFAULT FALSE,
  triage_json   JSONB,
  plan_json     JSONB,

  dedupe_key    TEXT,
  assignee      TEXT,
  pr_url        TEXT,
  last_run_id   UUID,
  notes         TEXT
);

-- One work_item per origin row (idempotent ingestion). NULL source_id (manual) is
-- exempt from the uniqueness constraint by design (partial index).
CREATE UNIQUE INDEX IF NOT EXISTS work_items_source_unique
  ON public.work_items (source, source_id) WHERE source_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS work_items_status_idx   ON public.work_items (status);
CREATE INDEX IF NOT EXISTS work_items_priority_idx ON public.work_items (priority);
CREATE INDEX IF NOT EXISTS work_items_created_idx  ON public.work_items (created_at DESC);

-- ── work_item_runs ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.work_item_runs (
  id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  work_item_id    UUID        NOT NULL REFERENCES public.work_items(id) ON DELETE CASCADE,
  dispatched_by   TEXT,
  dispatched_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  github_run_id   TEXT,
  github_run_url  TEXT,
  pr_url          TEXT,
  status          TEXT        NOT NULL DEFAULT 'queued'
                              CHECK (status IN ('queued', 'running', 'pr_opened', 'e2e_pass', 'merged', 'deployed', 'failed', 'reverted')),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS work_item_runs_item_idx ON public.work_item_runs (work_item_id);

-- ── Security (hard gates) ───────────────────────────────────────────────────
ALTER TABLE public.work_items     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.work_item_runs ENABLE ROW LEVEL SECURITY;

-- Service-role only: the backend mediates all access; no direct frontend reads.
DROP POLICY IF EXISTS "service role manages work_items" ON public.work_items;
CREATE POLICY "service role manages work_items" ON public.work_items
  FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "service role manages work_item_runs" ON public.work_item_runs;
CREATE POLICY "service role manages work_item_runs" ON public.work_item_runs
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Defense-in-depth: the anon key (shipped in the frontend bundle) gets nothing.
REVOKE ALL ON public.work_items     FROM anon;
REVOKE ALL ON public.work_item_runs FROM anon;
