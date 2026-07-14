CREATE TABLE public.message_templates (
  id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  name          TEXT        NOT NULL,
  message_type  TEXT        NOT NULL DEFAULT 'initial'
    CHECK (message_type IN ('initial','follow_up','reply_response')),
  body_template TEXT        NOT NULL,
  is_active     BOOLEAN     DEFAULT TRUE
);

CREATE TRIGGER set_updated_at_templates
BEFORE UPDATE ON public.message_templates
FOR EACH ROW EXECUTE PROCEDURE public.update_updated_at_column();

ALTER TABLE public.message_templates ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admin full access" ON public.message_templates;
CREATE POLICY "Admin full access" ON public.message_templates
  FOR ALL TO authenticated
  USING  (EXISTS (SELECT 1 FROM public.admin_allowlist WHERE user_id = auth.uid() AND enabled = 1))
  WITH CHECK (EXISTS (SELECT 1 FROM public.admin_allowlist WHERE user_id = auth.uid() AND enabled = 1));

REVOKE ALL ON public.message_templates FROM anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.message_templates TO authenticated;

INSERT INTO public.message_templates (name, message_type, body_template) VALUES
(
  'FR→NO HR Generalist — Initial outreach',
  'initial',
  'Hi {{full_name}},

I noticed your role at {{company_name}} — it looks like you''re the person responsible for international mobility when it comes up.

I''m building a tool called ReloPass specifically for HR generalists managing France→Norway relocations (and the reverse). It surfaces the non-obvious compliance requirements — D-numbers, tax card timing, EEA registration — before they become missed deadlines.

Would you be open to a 15-minute conversation? I''m looking to work closely with a handful of early users and this corridor felt relevant to what your team does.

Best,
[Your name]'
),
(
  'Follow-up (10-day no-reply)',
  'follow_up',
  'Hi {{full_name}},

Just following up on my note from last week — happy to keep it brief.

If the France→Norway compliance side isn''t currently a pain point, completely understood. If it is (or might be), I''d love 15 minutes.

Best,
[Your name]'
);
