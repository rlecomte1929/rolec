CREATE TABLE public.outreach_messages (
  id                       UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  prospect_id              UUID        NOT NULL REFERENCES public.linkedin_prospects(id) ON DELETE CASCADE,
  message_type             TEXT        NOT NULL DEFAULT 'initial'
    CHECK (message_type IN ('initial','follow_up','reply_response')),
  subject_line             TEXT,
  body                     TEXT        NOT NULL,
  personalisation_notes    TEXT,
  status                   TEXT        NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','approved','sent','archived')),
  approved_at              TIMESTAMPTZ,
  sent_at                  TIMESTAMPTZ,
  copied_to_clipboard_at   TIMESTAMPTZ
);

CREATE TRIGGER set_updated_at_messages
BEFORE UPDATE ON public.outreach_messages
FOR EACH ROW EXECUTE PROCEDURE public.update_updated_at_column();

ALTER TABLE public.outreach_messages ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admin full access" ON public.outreach_messages;
CREATE POLICY "Admin full access" ON public.outreach_messages
  FOR ALL TO authenticated
  USING (public.is_admin()) WITH CHECK (public.is_admin());

REVOKE ALL ON public.outreach_messages FROM anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.outreach_messages TO authenticated;
