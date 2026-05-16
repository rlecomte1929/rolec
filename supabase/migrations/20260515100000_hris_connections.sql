-- =============================================================================
-- AIQ-72 (AIQ-33-D): personio_sync_log + trigger for case status → Personio sync
--
-- NOTE: hris_connections, hris_sync_log, and hris_field_mappings were created
-- by AIQ-33-B (supabase/migrations applied prior to this one). This migration
-- only adds the case-status-sync-specific log table, pg_net, and the trigger.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- personio_sync_log
-- Append-only audit trail of every case status → Personio sync attempt.
-- Distinct from hris_sync_log (which tracks Personio → ReloPass hire syncs).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.personio_sync_log (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id               text NOT NULL,
  org_id                text,                      -- hris_connections.org_id = relocation_cases.company_id
  employee_email        text,
  personio_employee_id  bigint,
  direction             text NOT NULL DEFAULT 'relopass_to_personio'
                          CHECK (direction IN ('relopass_to_personio', 'personio_to_relopass')),
  -- success | skip | warn | error
  sync_status           text NOT NULL,
  new_case_status       text,
  fields_updated        jsonb,
  error_message         text,
  personio_response     jsonb,
  synced_at             timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_personio_sync_log_case_id
  ON public.personio_sync_log (case_id, synced_at DESC);

CREATE INDEX IF NOT EXISTS idx_personio_sync_log_status
  ON public.personio_sync_log (sync_status, synced_at DESC);

ALTER TABLE public.personio_sync_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "hr_can_read_own_sync_log"
  ON public.personio_sync_log FOR SELECT TO authenticated
  USING (
    org_id IN (
      SELECT company_id FROM public.hr_users
      WHERE profile_id = (SELECT auth.uid()::text)
    )
  );

GRANT SELECT ON public.personio_sync_log TO authenticated;
GRANT ALL ON public.personio_sync_log TO service_role;

-- ---------------------------------------------------------------------------
-- pg_net: required for async trigger → Edge Function HTTP call
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS pg_net WITH SCHEMA extensions;

-- ---------------------------------------------------------------------------
-- Trigger function: fires on relocation_cases.status change
-- Calls personio-status-sync Edge Function asynchronously via pg_net.
-- Non-blocking: EXCEPTION block ensures a sync failure never rolls back the
-- case status update in the HR UI.
--
-- GUC config required (Supabase → Database → Configuration → Additional config):
--   app.supabase_project_ref = <project-ref>  (e.g. nsvefcvpvwwwhuqyuqmp)
--   app.supabase_anon_key    = <anon-key>
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.fn_notify_personio_status_sync()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, extensions AS $$
DECLARE
  v_url         text;
  v_anon_key    text;
  v_payload     jsonb;
  v_project_ref text;
BEGIN
  -- Skip if status didn't actually change
  IF OLD.status IS NOT DISTINCT FROM NEW.status THEN
    RETURN NEW;
  END IF;

  v_project_ref := current_setting('app.supabase_project_ref', true);
  v_anon_key    := current_setting('app.supabase_anon_key', true);

  IF v_project_ref IS NULL OR v_anon_key IS NULL THEN
    RETURN NEW;
  END IF;

  v_url := format(
    'https://%s.supabase.co/functions/v1/personio-status-sync',
    v_project_ref
  );

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
      'Authorization', 'Bearer ' || v_anon_key
    )
  );

  RETURN NEW;

EXCEPTION WHEN OTHERS THEN
  RAISE WARNING '[personio-sync] trigger error (case_id=%, %->%): %',
    NEW.id, OLD.status, NEW.status, SQLERRM;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_personio_status_sync ON public.relocation_cases;
CREATE TRIGGER trg_personio_status_sync
  AFTER UPDATE OF status
  ON public.relocation_cases
  FOR EACH ROW
  EXECUTE FUNCTION public.fn_notify_personio_status_sync();
