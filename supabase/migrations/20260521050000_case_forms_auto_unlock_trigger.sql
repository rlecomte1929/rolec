-- ============================================================
-- [P2-6] Blocking dependency logic — auto-unlock trigger
-- ============================================================
-- When a CaseForm transitions to 'approved', this trigger:
--   1. Resets any CaseForms that were gated on it back to
--      'not_started' so the Pre-Fill Engine can populate them.
--      (The Python API layer calls run_prefill_for_dependents
--       synchronously after writing approved; this trigger is
--       the DB-side atomicity guarantee + pg_notify signal.)
--   2. Emits pg_notify('form_unblocked', approved_form_id)
--      for future Realtime subscribers.
--
-- Notes:
--   - The UPDATE is a no-op if the blocked form is already
--     past not_started (idempotent).
--   - The trigger only fires on status column changes (AFTER
--     UPDATE OF status) to avoid firing on unrelated updates.
-- ============================================================

CREATE OR REPLACE FUNCTION public.handle_case_form_approval()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  -- Only act when transitioning INTO 'approved'
  IF NEW.status = 'approved' AND (OLD.status IS DISTINCT FROM 'approved') THEN

    -- Unlock any CaseForms gated on this one.
    -- Blocked forms sit at 'not_started'; we touch only those so we
    -- don't downgrade a form that the employee already started.
    UPDATE public.case_forms
    SET
      status     = 'not_started',
      updated_at = now()
    WHERE
      blocker_form_id = NEW.id
      AND status = 'not_started';

    -- Signal Realtime / Edge Function subscribers that a form was approved
    -- and its dependents may now be accessible.
    PERFORM pg_notify(
      'form_unblocked',
      json_build_object(
        'approved_form_id', NEW.id,
        'case_id',          NEW.case_id
      )::text
    );

  END IF;
  RETURN NEW;
END;
$$;

-- Drop and recreate so the migration is idempotent on re-apply
DROP TRIGGER IF EXISTS on_case_form_approved ON public.case_forms;

CREATE TRIGGER on_case_form_approved
  AFTER UPDATE OF status ON public.case_forms
  FOR EACH ROW
  EXECUTE FUNCTION public.handle_case_form_approval();

-- ============================================================
-- END
-- ============================================================
