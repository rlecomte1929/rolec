-- CATALOG-3 / AIQ-1067 — Employee provider ratings -> live recommendation signal.
--
-- Today `supplier_scoring_metadata.average_rating`/`review_count` (the value the
-- recommender actually scores, via search_by_service_destination) is static seed
-- data. This table captures real employee ratings so the aggregate can be
-- recomputed from usage. The write endpoint recomputes the aggregate app-side.
--
-- Security hard gates (CLAUDE.md): RLS enabled + scoped policies + REVOKE anon.

CREATE TABLE IF NOT EXISTS public.provider_ratings (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  -- Rater (auth uid == profiles.id). Denormalised company_id below lets HR read
  -- ratings for their own company's cases without a join in the RLS policy.
  employee_id   uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  company_id    uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
  supplier_id   text NOT NULL REFERENCES public.suppliers(id) ON DELETE CASCADE,
  case_id       uuid NOT NULL REFERENCES public.cases(id) ON DELETE CASCADE,
  score         smallint NOT NULL CHECK (score BETWEEN 1 AND 5),
  comment       text,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  -- Idempotency: one rating per provider per case per employee. The write
  -- endpoint upserts on this key so a re-rate updates rather than duplicates.
  CONSTRAINT uq_provider_ratings_emp_supplier_case UNIQUE (employee_id, supplier_id, case_id)
);

COMMENT ON TABLE public.provider_ratings IS
  '[CATALOG-3] Per-employee 1-5 provider ratings. Aggregated into supplier_scoring_metadata.average_rating/review_count, which the recommendation engine scores.';

CREATE INDEX IF NOT EXISTS idx_provider_ratings_supplier ON public.provider_ratings (supplier_id);
CREATE INDEX IF NOT EXISTS idx_provider_ratings_company  ON public.provider_ratings (company_id);
CREATE INDEX IF NOT EXISTS idx_provider_ratings_case     ON public.provider_ratings (case_id);

ALTER TABLE public.provider_ratings ENABLE ROW LEVEL SECURITY;

-- Employee: full access to their OWN ratings only.
DROP POLICY IF EXISTS "provider_ratings_emp_rw_own" ON public.provider_ratings;
CREATE POLICY "provider_ratings_emp_rw_own" ON public.provider_ratings
  FOR ALL
  USING (employee_id = auth.uid())
  WITH CHECK (employee_id = auth.uid());

-- Admin: read-only across all ratings (aggregate visibility / moderation).
DROP POLICY IF EXISTS "provider_ratings_admin_read" ON public.provider_ratings;
CREATE POLICY "provider_ratings_admin_read" ON public.provider_ratings
  FOR SELECT
  USING (public.is_admin());

-- HR: read-only for ratings scoped to companies they manage.
-- hr_company_ids() RETURNS SETOF text, so it must be used as `IN (SELECT ...)`
-- (a set-returning function is not allowed in `= ANY(...)` inside a policy), and
-- company_id (uuid) is cast to text to match the function's text company ids.
DROP POLICY IF EXISTS "provider_ratings_hr_read" ON public.provider_ratings;
CREATE POLICY "provider_ratings_hr_read" ON public.provider_ratings
  FOR SELECT
  USING (company_id::text IN (SELECT public.hr_company_ids()));

-- Defense-in-depth: the anon key (shipped in the frontend bundle) must never
-- reach this table directly via PostgREST.
REVOKE ALL ON public.provider_ratings FROM anon;
