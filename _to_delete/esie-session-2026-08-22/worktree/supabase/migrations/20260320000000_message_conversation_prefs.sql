-- Per-user (HR) thread list preferences: archive = soft-hide from active list (non-destructive).
CREATE TABLE IF NOT EXISTS public.message_conversation_prefs (
  user_id text NOT NULL,
  assignment_id text NOT NULL,
  archived_at timestamptz,
  PRIMARY KEY (user_id, assignment_id)
);

CREATE INDEX IF NOT EXISTS idx_message_conversation_prefs_user_archived
  ON public.message_conversation_prefs (user_id, archived_at);

COMMENT ON TABLE public.message_conversation_prefs IS
  'HR user preferences per assignment thread; archived_at NULL means show in active list.';

ALTER TABLE public.message_conversation_prefs ENABLE ROW LEVEL SECURITY;

-- Direct API uses DB role that bypasses RLS; this protects any future Supabase client access.
CREATE POLICY "message_conversation_prefs_own"
  ON public.message_conversation_prefs
  FOR ALL
  TO authenticated
  USING (user_id = (auth.uid())::text)
  WITH CHECK (user_id = (auth.uid())::text);
