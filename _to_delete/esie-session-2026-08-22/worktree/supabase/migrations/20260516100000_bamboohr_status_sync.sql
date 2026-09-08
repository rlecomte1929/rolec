-- =============================================================================
-- AIQ-38-C: bamboohr_sync_log + trigger for case status → BambooHR sync
--
-- Mirrors the Personio pattern from 20260515100000_hris_connections.sql.
-- Key differences:
--   - provider-specific log table: bamboohr_sync_log (vs personio_sync_log)
--   - bamboohr_employee_id text (extracted from employee_id = "bamboohr:<id>")
--   - Direction: relopass_to_bamboohr
--
-- The trigger only fires when employee_id starts with "bamboohr:" — the
-- Edge Function also guards on this, but the trigger skips the HTTP call
-- entirely for non-BambooHR cases via the WHEN clause.
--
-- GUC config required (Supabase → Database → Configuration → Additional config):
--   app.supabase_project_ref = <project-ref>  (e.g. nsvefcvpvwwwhuqyuqmp)
--   app.supabase_anon_key    = <anon-key>
-- =============================================================================

-- ---------------------------------------------------------------------------
-- bamboohr_sync_log
-- Append-only audit trail of every case status → BambooHR sync attempt.
-- Distinct from hris_sync_log (BambooHR → ReloPass hire syncs) and
-- personio_sync_log (Personio status syncs).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.bamboohr_sync_log (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id               text NOT NULL,
  org_id                text,
  bamboohr_employee_id  text,
  direction             text NOT NULL DEFAULT 'relopass_to_bamboohr'
                          CHECK (direction IN ('relopass_to_bamboohr', 'bamboohr_to_relopass')),
  -- success | skip | warn | error
  sync_status           text NOT NULL,
  new_case_status       text,
  fields_updated        jsonb,
  error_message         text,
  bamboohr_response     jsonb,
  synced_at             timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bamboohr_sync_log_case_id
  ON public.bamboohr_sync_log (case_id, synced_at DESC);

CREATE INDEX IF NOT EXISTS idx_bamboohr_sync_log_status
  ON public.bamboohr_sync_log (sync_status, synced_at DESC);

ALTER TABLE public.bamboohr_sync_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "hr_can_read_own_bamboohr_sync_log"
  ON public.bamboohr_sync_log FOR SELECT TO authenticated
  USING (
    org_id IN (
      SELECT company_id FROM public.hr_users
      WHERE profile_id = (SELECT auth.uid()::text)
    )
  );

GRANT SELECT ON public.bamboohr_sync_log TO authenticated;
GRANT ALL ON public.bamboohr_sync_log TO service_role;

-- ---------------------------------------------------------------------------
-- pg_net: already enabled in 20260515100000; CREATE EXTENSION IF NOT EXISTS
-- is idempotent so safe to repeat.
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS pg_net WITH SCHEMA extensions;

-- ---------------------------------------------------------------------------
-- Trigger function: fires on relocation_cases.status change
-- Only calls the Edge Function when employee_id starts with "bamboohr:"
-- (WHEN clause avoids a network call for non-BambooHR cases entirely).
-- Calls bamboohr-status-sync Edge Function asynchronously via pg_net.
-- Non-blocking: EXCEPTION block ensures a sync failure never rolls back the
-- case status update in the HR UI.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.fn_notify_bamboohr_status_sync()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, extensions AS $$
DECLARE
  v_url     text := 'https://nsvefcvpvwwwhuqyuqmp.supabase.co/functions/v1/bamboohr-status-sync';
  v_key     text := 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5zdmVmY3Zwdnd3d2h1cXl1cW1wIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzEyMjgwNzIsImV4cCI6MjA4NjgwNDA3Mn0.TFDDThoEm9Q8zLEkmgVKiseolUbzN2GyFo0BMnv8qMQ';
  v_payload jsonb;
BEGIN
  -- Skip if status didn't actually change
  IF OLD.status IS NOT DISTINCT FROM NEW.status THEN
    RETURN NEW;
  END IF;

  v_payload := jsonb_build_object(
    'case_id',      NEW.id,
    'new_status',   NEW.status,
    'old_status',   OLD.status,
    'employee_id',  NEW.employee_id,
    'company_id',   NEW.company_id,
    'host_country', NEW.host_country,
    'updated_at',   NEW.updated_at
  );

  PERFORM extensions.http_post(
    url     := v_url,
    body    := v_payload::text,
    headers := jsonb_build_object(
      'Content-Type',  'application/json',
      'Authorization', 'Bearer ' || v_key
    )
  );

  RETURN NEW;

EXCEPTION WHEN OTHERS THEN
  RAISE WARNING '[bamboohr-sync] trigger error (case_id=%, %->%): %',
    NEW.id, OLD.status, NEW.status, SQLERRM;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_bamboohr_status_sync ON public.relocation_cases;
CREATE TRIGGER trg_bamboohr_status_sync
  AFTER UPDATE OF status
  ON public.relocation_cases
  FOR EACH ROW
  -- Only fire for BambooHR-sourced employees; skip all other cases at the DB level
  WHEN (NEW.employee_id IS NOT NULL AND NEW.employee_id LIKE 'bamboohr:%')
  EXECUTE FUNCTION public.fn_notify_bamboohr_status_sync();
