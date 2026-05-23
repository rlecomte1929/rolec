-- Migration: case_messages
-- Enables Step 5 (WZ5) of the employee wizard: threaded messaging on a case.
-- Each message records the sender, their role at time of sending, and the text.

CREATE TABLE IF NOT EXISTS public.case_messages (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id     TEXT        NOT NULL,
    sender_id   TEXT        NOT NULL,
    sender_role TEXT        NOT NULL,           -- 'employee' | 'hr' | 'admin'
    content     TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_case_messages_case_id
    ON public.case_messages (case_id, created_at DESC);

-- RLS: employees can only read/write messages on their own cases;
--      HR can read/write all messages for cases in their company.
ALTER TABLE public.case_messages ENABLE ROW LEVEL SECURITY;

-- All authenticated users can insert their own messages
CREATE POLICY "case_messages_insert_own"
    ON public.case_messages
    FOR INSERT
    TO authenticated
    WITH CHECK (sender_id = auth.uid()::text);

-- Employees can select messages on cases they are linked to
CREATE POLICY "case_messages_select_employee"
    ON public.case_messages
    FOR SELECT
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.case_assignments ca
            WHERE ca.case_id = case_messages.case_id
              AND ca.employee_id = auth.uid()::text
        )
        OR
        EXISTS (
            SELECT 1 FROM public.relocation_cases rc
            WHERE rc.id = case_messages.case_id
              AND rc.created_by = auth.uid()::text
        )
        OR
        EXISTS (
            SELECT 1 FROM public.profiles p
            WHERE p.id = auth.uid()::text
              AND p.role IN ('HR', 'ADMIN')
        )
    );
