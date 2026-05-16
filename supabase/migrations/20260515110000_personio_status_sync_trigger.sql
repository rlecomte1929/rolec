-- =============================================================================
-- AIQ-72 (AIQ-33-D): Postgres trigger → personio-status-sync Edge Function
--
-- Fires AFTER UPDATE OF status ON relocation_cases.
-- Uses pg_net to POST to the Supabase Edge Function asynchronously.
-- The call is non-blocking: HR UI is never slowed by Personio latency.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Trigger function
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
  -- Only fire when status actually changed and new status is one we care about.
  -- Covered statuses: in_progress | completed | on_hold | draft | active | closed
  IF OLD.status IS NOT DISTINCT FROM NEW.status THEN
    RETURN NEW;
  END IF;

  -- Build the Edge Function URL from environment-level settings.
  -- These are injected by Supabase as Postgres GUC variables.
  v_project_ref := current_setting('app.supabase_project_ref', true);
  v_anon_key    := current_setting('app.supabase_anon_key', true);

  IF v_project_ref IS NULL OR v_anon_key IS NULL THEN
    -- Settings not configured (local dev without project ref) — skip silently.
    RETURN NEW;
  END IF;

  v_url := format(
    'https://%s.supabase.co/functions/v1/personio-status-sync',
    v_project_ref
  );

  v_payload := jsonb_build_object(
    'case_id',        NEW.id,
    'new_status',     NEW.status,
    'old_status',     OLD.status,
    'employee_id',    NEW.employee_id,
    'company_id',     NEW.company_id,
    'host_country',   NEW.host_country,
    'updated_at',     NEW.updated_at
  );

  -- pg_net.http_post is async — returns immediately without waiting for HTTP response.
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
  -- Never let a sync failure roll back the case status update.
  RAISE WARNING '[personio-sync] trigger error (case_id=%, status=% → %): %',
    NEW.id, OLD.status, NEW.status, SQLERRM;
  RETURN NEW;
END;
$$;

-- ---------------------------------------------------------------------------
-- Drop + recreate trigger (idempotent)
-- ---------------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_personio_status_sync ON public.relocation_cases;

CREATE TRIGGER trg_personio_status_sync
  AFTER UPDATE OF status
  ON public.relocation_cases
  FOR EACH ROW
  EXECUTE FUNCTION public.fn_notify_personio_status_sync();

-- ---------------------------------------------------------------------------
-- GUC settings placeholder comment
-- After deploying this migration, set these two Postgres config parameters
-- in the Supabase dashboard → Database → Configuration → Additional config:
--
--   app.supabase_project_ref = <your-project-ref>   (e.g. abcdefghijklmnop)
--   app.supabase_anon_key    = <your-anon-key>
--
-- Both values are available in Supabase → Project Settings → API.
-- ---------------------------------------------------------------------------
