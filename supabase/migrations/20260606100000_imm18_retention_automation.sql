-- IMM-18 (AIQ-124) — GDPR Art.17 erasure + Art.5(1)(e) storage-limitation automation
--
-- Targets imm_employee_profiles (the live immigration PII table; employee_profiles is
-- the superseded no-op table). Adds:
--   1. anonymised_at marker column (idempotency)
--   2. system_log table (nightly job audit)
--   3. fn_anonymise_imm_profile()        — NULL all PII, keep skeleton + write ANONYMISED log
--   4. fn_immigration_retention_cleanup() — nightly: anonymise expired, hard-delete >30d past
--   5. cases-status trigger              — on close/complete, set retention_expires_at +36mo
--   6. pg_cron schedule                  — invokes the immigration-retention-cleanup Edge Function
--
-- NEVER hard-deletes consent_records or data_access_log — those are compliance evidence.

-- 1) Idempotency marker --------------------------------------------------------
ALTER TABLE public.imm_employee_profiles
  ADD COLUMN IF NOT EXISTS anonymised_at TIMESTAMPTZ;

-- 2) system_log ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.system_log (
  id        BIGSERIAL PRIMARY KEY,
  job_name  TEXT NOT NULL,
  status    TEXT NOT NULL,           -- success | error
  details   JSONB,
  run_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_system_log_job_run ON public.system_log(job_name, run_at DESC);

ALTER TABLE public.system_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS system_log_admin_select ON public.system_log;
CREATE POLICY system_log_admin_select
  ON public.system_log FOR SELECT TO authenticated
  USING (public.is_admin());

DROP POLICY IF EXISTS system_log_service_role ON public.system_log;
CREATE POLICY system_log_service_role
  ON public.system_log FOR ALL TO service_role
  USING (true) WITH CHECK (true);

REVOKE ALL ON public.system_log FROM anon;

-- 3) Single-profile anonymiser -------------------------------------------------
-- Dynamically NULLs every column except the audit skeleton, so it survives schema
-- drift. NOT NULL columns (id, case_id, employee_id, org_id, created_at, updated_at)
-- are all in the keep-set, so the UPDATE never violates a constraint.
CREATE OR REPLACE FUNCTION public.fn_anonymise_imm_profile(p_profile_id TEXT)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_keep    TEXT[] := ARRAY['id','case_id','employee_id','org_id',
                            'created_at','updated_at','retention_expires_at','anonymised_at'];
  v_col     TEXT;
  v_sets    TEXT := '';
  v_case_id TEXT;
BEGIN
  SELECT case_id INTO v_case_id FROM public.imm_employee_profiles WHERE id = p_profile_id;
  IF NOT FOUND THEN
    RETURN;
  END IF;

  FOR v_col IN
    SELECT column_name FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'imm_employee_profiles'
      AND column_name <> ALL (v_keep)
  LOOP
    v_sets := v_sets || format('%I = NULL, ', v_col);
  END LOOP;

  EXECUTE format(
    'UPDATE public.imm_employee_profiles SET %s anonymised_at = NOW(), updated_at = NOW() WHERE id = %L',
    v_sets, p_profile_id
  );

  -- Final compliance entry (field NAMES only, no values).
  INSERT INTO public.data_access_log
    (case_id, profile_id, accessed_by_user_id, accessed_by_role,
     action, fields_accessed, purpose, accessed_at)
  VALUES
    (v_case_id, p_profile_id, 'system', 'system',
     'ANONYMISED', ARRAY['all_pii'], 'retention_erasure', NOW());
END;
$$;

-- 4) Nightly cleanup -----------------------------------------------------------
-- Runs as one transaction: either the whole sweep commits or none of it does.
CREATE OR REPLACE FUNCTION public.fn_immigration_retention_cleanup()
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_anon INT := 0;
  v_del  INT := 0;
  v_id   TEXT;
BEGIN
  -- Anonymise rows past retention that aren't anonymised yet.
  FOR v_id IN
    SELECT id FROM public.imm_employee_profiles
    WHERE retention_expires_at IS NOT NULL
      AND retention_expires_at < NOW()
      AND anonymised_at IS NULL
  LOOP
    PERFORM public.fn_anonymise_imm_profile(v_id);
    v_anon := v_anon + 1;
  END LOOP;

  -- Hard-delete rows more than 30 days past retention (consent_records and
  -- data_access_log are intentionally left untouched).
  WITH del AS (
    DELETE FROM public.imm_employee_profiles
    WHERE retention_expires_at IS NOT NULL
      AND retention_expires_at < NOW() - INTERVAL '30 days'
    RETURNING id
  )
  SELECT count(*) INTO v_del FROM del;

  INSERT INTO public.system_log (job_name, status, details)
  VALUES ('immigration-retention-cleanup', 'success',
          jsonb_build_object('anonymised', v_anon, 'deleted', v_del));

  RETURN jsonb_build_object('anonymised', v_anon, 'deleted', v_del);
END;
$$;

-- 5) Retention-on-close trigger ------------------------------------------------
CREATE OR REPLACE FUNCTION public.fn_case_close_set_retention()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF NEW.status IN ('closed', 'completed')
     AND (OLD.status IS DISTINCT FROM NEW.status) THEN
    UPDATE public.imm_employee_profiles
    SET retention_expires_at = NOW() + INTERVAL '36 months',
        updated_at = NOW()
    WHERE case_id IN (NEW.id, NEW.case_id)
      AND retention_expires_at IS NULL;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_case_close_set_retention ON public.case_assignments;
CREATE TRIGGER trg_case_close_set_retention
  AFTER UPDATE ON public.case_assignments
  FOR EACH ROW
  EXECUTE FUNCTION public.fn_case_close_set_retention();

-- 6) Nightly schedule (03:30 UTC) ---------------------------------------------
DO $outer$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron')
     AND EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_net') THEN

    PERFORM cron.unschedule('immigration-retention-cleanup-nightly')
    FROM cron.job
    WHERE jobname = 'immigration-retention-cleanup-nightly';

    PERFORM cron.schedule(
      'immigration-retention-cleanup-nightly',
      '30 3 * * *',
      $cron$
      SELECT net.http_post(
        url     := current_setting('app.supabase_edge_url', true)
                   || '/immigration-retention-cleanup',
        headers := jsonb_build_object(
          'Content-Type',  'application/json',
          'Authorization', 'Bearer '
              || current_setting('app.supabase_service_key', true)
        ),
        body    := '{"trigger":"cron"}'::jsonb
      );
      $cron$
    );
    RAISE NOTICE 'pg_cron job "immigration-retention-cleanup-nightly" registered (03:30 UTC).';
  ELSE
    RAISE NOTICE 'pg_cron/pg_net unavailable — skipping retention cron schedule.';
  END IF;
END $outer$;
