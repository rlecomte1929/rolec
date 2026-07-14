CREATE TABLE public.prospect_replies (
  id                   UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  prospect_id          UUID        NOT NULL REFERENCES public.linkedin_prospects(id) ON DELETE CASCADE,
  reply_text           TEXT,
  replied_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  sentiment            TEXT        DEFAULT 'not_set'
    CHECK (sentiment IN ('positive','neutral','negative','not_set')),
  next_action          TEXT,
  next_action_due      TIMESTAMPTZ,
  outreach_message_id  UUID        REFERENCES public.outreach_messages(id)
);

ALTER TABLE public.prospect_replies ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admin full access" ON public.prospect_replies;
CREATE POLICY "Admin full access" ON public.prospect_replies
  FOR ALL TO authenticated
  USING  (EXISTS (SELECT 1 FROM public.admin_allowlist WHERE user_id = auth.uid() AND enabled = 1))
  WITH CHECK (EXISTS (SELECT 1 FROM public.admin_allowlist WHERE user_id = auth.uid() AND enabled = 1));

REVOKE ALL ON public.prospect_replies FROM anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.prospect_replies TO authenticated;
