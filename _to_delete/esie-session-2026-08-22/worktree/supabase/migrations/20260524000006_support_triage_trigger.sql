-- SUPPORT-4B: Supabase trigger → support-triage Edge Function
-- ─────────────────────────────────────────────────────────────────────────────
-- Fires the support-triage Edge Function via pg_net within 60 seconds of any
-- new support_tickets INSERT.  The Edge Function calls Claude Sonnet and writes
-- the triage_result back to the row.
-- ─────────────────────────────────────────────────────────────────────────────

-- Trigger function: fires pg_net HTTP POST to support-triage Edge Function
CREATE OR REPLACE FUNCTION public.trigger_support_triage()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  -- Fire-and-forget: errors in pg_net do not roll back the INSERT
  PERFORM net.http_post(
    url     := current_setting('app.supabase_url') || '/functions/v1/support-triage',
    headers := jsonb_build_object(
      'Content-Type',  'application/json',
      'Authorization', 'Bearer ' || current_setting('app.service_role_key')
    ),
    body    := jsonb_build_object('ticket_id', NEW.id::text)
  );
  RETURN NEW;
EXCEPTION WHEN OTHERS THEN
  -- Never block the INSERT even if pg_net is unavailable
  RAISE WARNING 'support_triage trigger: pg_net call failed: %', SQLERRM;
  RETURN NEW;
END;
$$;

-- Drop and recreate trigger (idempotent)
DROP TRIGGER IF EXISTS trg_support_ticket_triage ON public.support_tickets;
CREATE TRIGGER trg_support_ticket_triage
  AFTER INSERT ON public.support_tickets
  FOR EACH ROW EXECUTE FUNCTION public.trigger_support_triage();

COMMENT ON FUNCTION public.trigger_support_triage() IS
  'SUPPORT-4B: fires support-triage Edge Function on every new support_ticket row';

COMMENT ON TRIGGER trg_support_ticket_triage ON public.support_tickets IS
  'SUPPORT-4B: triggers AI triage within 60 seconds of ticket insert';
