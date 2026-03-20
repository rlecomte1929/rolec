-- HR Messages / conversation summaries: columns expected by list_hr_conversation_summaries
-- when runtime DDL is disabled (production). Safe IF NOT EXISTS.

-- messages: read/delivery (unread counts, mark read)
ALTER TABLE public.messages ADD COLUMN IF NOT EXISTS delivered_at timestamptz;
ALTER TABLE public.messages ADD COLUMN IF NOT EXISTS read_at timestamptz;
ALTER TABLE public.messages ADD COLUMN IF NOT EXISTS dismissed_at timestamptz;
ALTER TABLE public.messages ADD COLUMN IF NOT EXISTS recipient_user_id text;
ALTER TABLE public.messages ADD COLUMN IF NOT EXISTS sender_user_id text;

CREATE INDEX IF NOT EXISTS idx_messages_recipient_unread_pg
  ON public.messages (recipient_user_id, read_at, dismissed_at, created_at DESC);

-- case_assignments: used in HR conversation list + case joins
ALTER TABLE public.case_assignments ADD COLUMN IF NOT EXISTS canonical_case_id text;
ALTER TABLE public.case_assignments ADD COLUMN IF NOT EXISTS employee_first_name text;
ALTER TABLE public.case_assignments ADD COLUMN IF NOT EXISTS employee_last_name text;

-- conversation archive prefs (if an older migration was skipped)
CREATE TABLE IF NOT EXISTS public.message_conversation_prefs (
  user_id text NOT NULL,
  assignment_id text NOT NULL,
  archived_at timestamptz,
  PRIMARY KEY (user_id, assignment_id)
);

CREATE INDEX IF NOT EXISTS idx_message_conversation_prefs_user_archived_pg
  ON public.message_conversation_prefs (user_id, archived_at);
