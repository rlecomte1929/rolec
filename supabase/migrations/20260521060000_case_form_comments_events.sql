-- ============================================================
-- [P4-2] Case-level dossier panel — comments, events, flags
-- ============================================================
-- 1. New table: case_form_comments
-- 2. New table: case_form_events
-- 3. New columns on case_forms: flag_note, flagged_at, flagged_by
-- 4. RLS policies for both new tables
-- 5. Trigger: write a case_form_events row on every status change
-- ============================================================

-- ── 1. case_form_comments ────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.case_form_comments (
  id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  case_form_id uuid       NOT NULL REFERENCES public.case_forms(id) ON DELETE CASCADE,
  author_id   uuid        NOT NULL REFERENCES public.profiles(id)   ON DELETE CASCADE,
  content     text        NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_case_form_comments_form_id
  ON public.case_form_comments(case_form_id);

ALTER TABLE public.case_form_comments ENABLE ROW LEVEL SECURITY;

-- HR/Admin in the same company as the case, and the employee who owns the case,
-- can read and write comments.  We join through case_forms → cases → company.
CREATE POLICY "case_form_comments_access"
  ON public.case_form_comments
  FOR ALL
  USING (
    EXISTS (
      SELECT 1
      FROM public.case_forms cf
      JOIN public.cases c ON c.id = cf.case_id
      JOIN public.profiles p ON p.id::uuid = auth.uid()
      WHERE cf.id = case_form_comments.case_form_id
        AND (
          p.role = 'ADMIN'
          OR c.employee_id = auth.uid()::text
          OR (p.role = 'HR' AND p.company_id = c.company_id)
        )
    )
  );

-- ── 2. case_form_events ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.case_form_events (
  id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  case_form_id uuid        NOT NULL REFERENCES public.case_forms(id) ON DELETE CASCADE,
  event_type   text        NOT NULL,   -- e.g. 'status_change', 'flagged', 'unflagged', 'comment'
  actor_id     uuid        REFERENCES public.profiles(id) ON DELETE SET NULL,
  from_status  document_status,
  to_status    document_status,
  note         text,
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_case_form_events_form_id
  ON public.case_form_events(case_form_id);

ALTER TABLE public.case_form_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "case_form_events_access"
  ON public.case_form_events
  FOR ALL
  USING (
    EXISTS (
      SELECT 1
      FROM public.case_forms cf
      JOIN public.cases c ON c.id = cf.case_id
      JOIN public.profiles p ON p.id::uuid = auth.uid()
      WHERE cf.id = case_form_events.case_form_id
        AND (
          p.role = 'ADMIN'
          OR c.employee_id = auth.uid()::text
          OR (p.role = 'HR' AND p.company_id = c.company_id)
        )
    )
  );

-- ── 3. Flag columns on case_forms ────────────────────────────
ALTER TABLE public.case_forms
  ADD COLUMN IF NOT EXISTS flag_note   text,
  ADD COLUMN IF NOT EXISTS flagged_at  timestamptz,
  ADD COLUMN IF NOT EXISTS flagged_by  uuid REFERENCES public.profiles(id) ON DELETE SET NULL;

-- ── 4. Auto-event trigger on status change ───────────────────
-- Writes a case_form_events row whenever the status column changes.
-- actor_id is left NULL by the trigger (no session context in PL/pgSQL
-- without app-level injection); the API layer writes actor_id explicitly
-- when it calls the status-patch endpoint.
-- The trigger is intentionally lightweight — it only fires on real changes.

CREATE OR REPLACE FUNCTION public.handle_case_form_status_event()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.status IS DISTINCT FROM OLD.status THEN
    INSERT INTO public.case_form_events (
      case_form_id, event_type, from_status, to_status, created_at
    ) VALUES (
      NEW.id, 'status_change', OLD.status, NEW.status, now()
    );
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_case_form_status_change ON public.case_forms;

CREATE TRIGGER on_case_form_status_change
  AFTER UPDATE OF status ON public.case_forms
  FOR EACH ROW
  EXECUTE FUNCTION public.handle_case_form_status_event();

-- ── 5. Add both new tables to supabase_realtime publication ──
-- (mirrors migration 20260521030000 pattern)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime'
      AND tablename = 'case_form_comments'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.case_form_comments;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime'
      AND tablename = 'case_form_events'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.case_form_events;
  END IF;
END $$;

-- ============================================================
-- END
-- ============================================================
