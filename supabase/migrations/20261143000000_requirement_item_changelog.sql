-- Append-only history for public.requirement_items (RP-K-004).
-- Serving still reads requirement_items; this table is the rollback source.
-- Hard gates: RLS + policy + REVOKE anon.

CREATE TABLE IF NOT EXISTS public.requirement_item_changelog (
    change_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    requirement_id text NOT NULL,
    country_code text,
    change_type text NOT NULL
        CHECK (change_type IN (
            'requirement_added',
            'requirement_revised',
            'requirement_deprecated',
            'source_updated',
            'severity_changed'
        )),
    previous_value jsonb,
    new_value jsonb,
    changed_by text,
    changed_at timestamptz NOT NULL DEFAULT now(),
    change_justification text,
    new_source_document text,
    new_source_url text,
    reviewer_sign_off text,
    reviewed_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_requirement_item_changelog_requirement
    ON public.requirement_item_changelog (requirement_id, changed_at DESC);

COMMENT ON TABLE public.requirement_item_changelog IS
    'Append-only requirement_items history. Do not UPDATE or DELETE rows; rollback is a new compensating write.';

ALTER TABLE public.requirement_item_changelog ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS requirement_item_changelog_service_role_only
    ON public.requirement_item_changelog;
CREATE POLICY requirement_item_changelog_service_role_only
    ON public.requirement_item_changelog
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_proc
        WHERE proname = 'is_admin' AND pronamespace = 'public'::regnamespace
    ) THEN
        DROP POLICY IF EXISTS requirement_item_changelog_admin_read
            ON public.requirement_item_changelog;
        CREATE POLICY requirement_item_changelog_admin_read
            ON public.requirement_item_changelog
            FOR SELECT
            USING (public.is_admin());
    ELSE
        RAISE NOTICE 'public.is_admin() absent — changelog is service_role-only here.';
    END IF;
END $$;

REVOKE ALL ON public.requirement_item_changelog FROM anon, authenticated, public;
GRANT ALL ON public.requirement_item_changelog TO service_role;
