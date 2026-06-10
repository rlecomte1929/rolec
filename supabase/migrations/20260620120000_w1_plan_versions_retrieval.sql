-- W1-2 + W1-3 (BureauAI-audit remediation): immutable AI-plan persistence +
-- retrieval telemetry. Resolves the roadmap-representation schism (see
-- docs/adr/roadmap-representation.md): the live roadmap stays a case_forms
-- projection; every AI-generated roadmap is now durably recorded as an immutable
-- plan version, traceable to the retrieval run that produced it.
--
-- All four tables are case-children of public.cases and are tenant-scoped by the
-- canonical via-case RLS pattern (reusing public.my_company_id() / public.my_role()
-- defined in 20260520000000_platform_redesign_schema.sql). Idempotent DDL.

-- ── W1-2: case_plans (one per case) ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.case_plans (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id            uuid NOT NULL UNIQUE REFERENCES public.cases(id) ON DELETE CASCADE,
  -- Points at the latest plan_versions.id. Plain column (no FK) to avoid a
  -- circular dependency with plan_versions.
  current_version_id uuid,
  version_count      int  NOT NULL DEFAULT 0,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now()
);

-- ── W1-3: retrieval_runs (one per retrieval that fed a generation) ──────────
CREATE TABLE IF NOT EXISTS public.retrieval_runs (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id      uuid NOT NULL REFERENCES public.cases(id) ON DELETE CASCADE,
  corridor     text,
  query_text   text,
  top_k        int,
  params       jsonb NOT NULL DEFAULT '{}'::jsonb,
  chunk_count  int  NOT NULL DEFAULT 0,
  created_at   timestamptz NOT NULL DEFAULT now()
);

-- ── W1-2: plan_versions (immutable, append-only) ───────────────────────────
CREATE TABLE IF NOT EXISTS public.plan_versions (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_plan_id       uuid NOT NULL REFERENCES public.case_plans(id) ON DELETE CASCADE,
  case_id            uuid NOT NULL REFERENCES public.cases(id) ON DELETE CASCADE,
  version_no         int  NOT NULL,
  plan_json          jsonb NOT NULL,
  -- sha256 of a stable structural projection of plan_json (corridor + result +
  -- step titles), used to de-duplicate identical regenerations on the GET path.
  plan_hash          text NOT NULL,
  model              text,
  prompt_version_id  text,
  retrieval_run_id   uuid REFERENCES public.retrieval_runs(id) ON DELETE SET NULL,
  corridor           text,
  created_by         uuid,
  created_at         timestamptz NOT NULL DEFAULT now(),
  UNIQUE (case_id, version_no)
);

-- ── W1-3: retrieval_run_chunks (per-chunk telemetry) ───────────────────────
CREATE TABLE IF NOT EXISTS public.retrieval_run_chunks (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  retrieval_run_id  uuid NOT NULL REFERENCES public.retrieval_runs(id) ON DELETE CASCADE,
  case_id           uuid NOT NULL REFERENCES public.cases(id) ON DELETE CASCADE,
  chunk_id          text,
  rank              int,
  raw_score         double precision,
  adjusted_score    double precision,
  trust_tier        int,
  freshness         double precision,
  source_url        text
);

CREATE INDEX IF NOT EXISTS idx_plan_versions_case ON public.plan_versions(case_id);
CREATE INDEX IF NOT EXISTS idx_retrieval_runs_case ON public.retrieval_runs(case_id);
CREATE INDEX IF NOT EXISTS idx_retrieval_run_chunks_run ON public.retrieval_run_chunks(retrieval_run_id);

-- ── RLS: tenant isolation via the case-ownership subquery (canonical pattern) ──
ALTER TABLE public.case_plans          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.plan_versions       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.retrieval_runs      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.retrieval_run_chunks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS case_plans_via_case ON public.case_plans;
CREATE POLICY case_plans_via_case ON public.case_plans FOR ALL
  USING (case_id IN (
    SELECT id FROM public.cases
    WHERE employee_id = (SELECT auth.uid())
       OR (company_id = public.my_company_id() AND public.my_role() IN ('hr','admin'))
  ));

DROP POLICY IF EXISTS plan_versions_via_case ON public.plan_versions;
CREATE POLICY plan_versions_via_case ON public.plan_versions FOR ALL
  USING (case_id IN (
    SELECT id FROM public.cases
    WHERE employee_id = (SELECT auth.uid())
       OR (company_id = public.my_company_id() AND public.my_role() IN ('hr','admin'))
  ));

DROP POLICY IF EXISTS retrieval_runs_via_case ON public.retrieval_runs;
CREATE POLICY retrieval_runs_via_case ON public.retrieval_runs FOR ALL
  USING (case_id IN (
    SELECT id FROM public.cases
    WHERE employee_id = (SELECT auth.uid())
       OR (company_id = public.my_company_id() AND public.my_role() IN ('hr','admin'))
  ));

DROP POLICY IF EXISTS retrieval_run_chunks_via_case ON public.retrieval_run_chunks;
CREATE POLICY retrieval_run_chunks_via_case ON public.retrieval_run_chunks FOR ALL
  USING (case_id IN (
    SELECT id FROM public.cases
    WHERE employee_id = (SELECT auth.uid())
       OR (company_id = public.my_company_id() AND public.my_role() IN ('hr','admin'))
  ));

-- ── Defense-in-depth: never expose via the anon (PostgREST) role ───────────
REVOKE ALL ON public.case_plans           FROM anon;
REVOKE ALL ON public.plan_versions        FROM anon;
REVOKE ALL ON public.retrieval_runs       FROM anon;
REVOKE ALL ON public.retrieval_run_chunks FROM anon;
