-- Shared updated_at trigger function (new — no prior definition in repo)
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE public.linkedin_prospects (
  id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  full_name           TEXT        NOT NULL,
  linkedin_url        TEXT        UNIQUE NOT NULL,
  profile_headline    TEXT,
  company_name        TEXT        NOT NULL,
  company_size        TEXT,
  job_title           TEXT        NOT NULL,
  corridor_relevance  TEXT,
  notes               TEXT,
  source              TEXT        DEFAULT 'linkedin',
  status              TEXT        NOT NULL DEFAULT 'flagged'
    CHECK (status IN ('flagged','message_drafted','message_sent','replied','follow_up_sent','converted','not_interested','archived')),
  message_sent_at     TIMESTAMPTZ,
  last_reply_at       TIMESTAMPTZ,
  follow_up_sent_at   TIMESTAMPTZ,
  converted_at        TIMESTAMPTZ
);

CREATE TRIGGER set_updated_at
BEFORE UPDATE ON public.linkedin_prospects
FOR EACH ROW EXECUTE PROCEDURE public.update_updated_at_column();

ALTER TABLE public.linkedin_prospects ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admin full access" ON public.linkedin_prospects;
CREATE POLICY "Admin full access" ON public.linkedin_prospects
  FOR ALL TO authenticated
  USING (public.is_admin()) WITH CHECK (public.is_admin());

REVOKE ALL ON public.linkedin_prospects FROM anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.linkedin_prospects TO authenticated;
