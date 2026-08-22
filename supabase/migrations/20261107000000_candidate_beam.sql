-- ============================================================================
-- Corridor Candidate Beam — authoring-layer storage.
--
-- One run = N independent LLM passes over one corridor, deduped into a ranked review
-- queue. NOTHING here is served to a customer. Approved items are imported into the
-- existing otto_staging flow in `pending` state and reach customers only through the
-- /admin/countries approval gate that already exists.
--
-- Both tables are admin-only: the content is unreviewed model output, and an unreviewed
-- draft that leaks reads exactly like a published requirement. RLS + service_role policy
-- + REVOKE from anon AND authenticated, per the repo's hard gate for new public tables.
--
-- Timestamp 20261106000000 clears BOTH the repo max and the prod ledger max, which were
-- each 20261105000000 on 2026-08-19. Above-the-ledger alone is not enough here — the repo
-- routinely runs ahead of prod, and three PRs once collided by following that rule.
-- ============================================================================

-- ── Runs ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.candidate_beam_runs (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    set_uid           TEXT UNIQUE,
    corridor          TEXT NOT NULL,
    origin_country    TEXT,
    dest_country      TEXT,
    employee_type     TEXT NOT NULL,
    context           TEXT,
    passes_requested  INTEGER NOT NULL,
    passes_completed  INTEGER NOT NULL DEFAULT 0,
    llm_provider      TEXT,
    llm_model         TEXT,
    status            TEXT NOT NULL DEFAULT 'generating',
    error             TEXT,
    -- Raw parsed items per pass, in arrival order. Load-bearing rather than diagnostic:
    -- the clustering is greedy in arrival order, so a finalize that cannot replay the
    -- exact input cannot reproduce its own output. Re-finalizing from a re-ordered
    -- reconstruction measurably changes cluster membership.
    pass_outputs      JSONB NOT NULL DEFAULT '[]'::jsonb,
    -- Per-attempt framing, timing and ok/error. Failed slots are kept, not overwritten:
    -- the resume mechanism reads them, and a run that quietly dropped a failed pass would
    -- report inflated cross-pass agreement.
    pass_meta         JSONB NOT NULL DEFAULT '[]'::jsonb,
    candidate_count   INTEGER NOT NULL DEFAULT 0,
    created_by        TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT candidate_beam_runs_status_chk
        CHECK (status IN ('generating', 'pending_review', 'failed')),
    -- 2..7 is a cost clamp, not a style choice: every pass is a paid model call, and the
    -- dedupe needs at least two passes for cross-pass agreement to mean anything.
    CONSTRAINT candidate_beam_runs_passes_chk
        CHECK (passes_requested BETWEEN 2 AND 7),
    CONSTRAINT candidate_beam_runs_completed_chk
        CHECK (passes_completed >= 0 AND passes_completed <= passes_requested)
);

CREATE INDEX IF NOT EXISTS idx_candidate_beam_runs_status_created
    ON public.candidate_beam_runs (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_candidate_beam_runs_corridor
    ON public.candidate_beam_runs (corridor, employee_type);

-- ── Items ────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.candidate_beam_items (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id                   UUID NOT NULL
                                 REFERENCES public.candidate_beam_runs (id) ON DELETE CASCADE,
    -- Stable across re-finalize, and the idempotency key for import: re-importing must
    -- update the row it created before, never silently write a second staging row.
    candidate_uid            TEXT NOT NULL,

    rank                     INTEGER NOT NULL,
    pass_frequency           INTEGER NOT NULL,
    passes_total             INTEGER NOT NULL,
    confidence_band          TEXT NOT NULL,
    flagged                  BOOLEAN NOT NULL DEFAULT FALSE,
    source_missing           BOOLEAN NOT NULL DEFAULT FALSE,

    title                    TEXT NOT NULL,
    official_guidance        TEXT,
    actual_reality           TEXT,
    action_required          TEXT,
    -- The model's CLAIM, stored verbatim and unverified. Never invented, never
    -- URL-ified, never "cleaned" — a source that looks checked but is not survives review
    -- by looking already-done. NULL means no pass cited one; that is the research
    -- worklist, not a defect to backfill.
    source                   TEXT,
    category                 TEXT,
    -- Every contributing per-pass variant, so a reviewer can audit where the passes
    -- diverged rather than trusting the merged representative text.
    variants                 JSONB NOT NULL DEFAULT '[]'::jsonb,

    status                   TEXT NOT NULL DEFAULT 'pending_review',
    review_note              TEXT,
    reviewed_by              TEXT,
    reviewed_at              TIMESTAMPTZ,

    -- Import audit. Set only by the import step.
    import_country           TEXT,
    import_requirement_type  TEXT,
    imported_ref             TEXT,
    imported_at              TIMESTAMPTZ,
    imported_by              TEXT,

    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Four states, enforced in the database rather than only in the router. The whole
    -- safety argument for this feature is that beam output cannot become customer-facing
    -- without a human, and a CHECK is what makes "no code path may set verified" true of
    -- the schema instead of true of the code as currently written.
    CONSTRAINT candidate_beam_items_status_chk
        CHECK (status IN ('pending_review', 'approved', 'rejected', 'imported')),
    CONSTRAINT candidate_beam_items_band_chk
        CHECK (confidence_band IN ('near-certain', 'strong', 'moderate', 'low')),
    CONSTRAINT candidate_beam_items_frequency_chk
        CHECK (pass_frequency >= 1 AND pass_frequency <= passes_total),
    -- An imported item must carry its audit trail. Without this, "imported" could be set
    -- with no record of what it became, and import_verify would have nothing to check.
    CONSTRAINT candidate_beam_items_import_audit_chk
        CHECK (
            status <> 'imported'
            OR (import_country IS NOT NULL
                AND import_requirement_type IS NOT NULL
                AND imported_ref IS NOT NULL
                AND imported_at IS NOT NULL)
        ),
    CONSTRAINT candidate_beam_items_uid_unique UNIQUE (run_id, candidate_uid)
);

CREATE INDEX IF NOT EXISTS idx_candidate_beam_items_run_rank
    ON public.candidate_beam_items (run_id, rank);
CREATE INDEX IF NOT EXISTS idx_candidate_beam_items_status
    ON public.candidate_beam_items (status);

-- ── RLS ──────────────────────────────────────────────────────────────────────
-- Unreviewed model output. It reads exactly like a published requirement to anyone who
-- sees it, so it is admin-only: no anon, no authenticated, service_role for the backend.

ALTER TABLE public.candidate_beam_runs  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.candidate_beam_items ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS candidate_beam_runs_service_role_only ON public.candidate_beam_runs;
CREATE POLICY candidate_beam_runs_service_role_only
    ON public.candidate_beam_runs
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

DROP POLICY IF EXISTS candidate_beam_items_service_role_only ON public.candidate_beam_items;
CREATE POLICY candidate_beam_items_service_role_only
    ON public.candidate_beam_items
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- Admin read/write, when public.is_admin() exists. Guarded because is_admin() is defined
-- out-of-band and a hard dependency would make this migration unapplyable on an
-- environment that has not got it yet — the same guard the ai_unit_economics migration
-- uses for the same reason.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_proc
        WHERE proname = 'is_admin' AND pronamespace = 'public'::regnamespace
    ) THEN
        DROP POLICY IF EXISTS candidate_beam_runs_admin_all ON public.candidate_beam_runs;
        CREATE POLICY candidate_beam_runs_admin_all
            ON public.candidate_beam_runs
            FOR ALL
            USING (public.is_admin())
            WITH CHECK (public.is_admin());

        DROP POLICY IF EXISTS candidate_beam_items_admin_all ON public.candidate_beam_items;
        CREATE POLICY candidate_beam_items_admin_all
            ON public.candidate_beam_items
            FOR ALL
            USING (public.is_admin())
            WITH CHECK (public.is_admin());
    ELSE
        RAISE NOTICE 'public.is_admin() absent — candidate beam tables are service_role-only here.';
    END IF;
END $$;

REVOKE ALL ON public.candidate_beam_runs  FROM anon, authenticated, public;
REVOKE ALL ON public.candidate_beam_items FROM anon, authenticated, public;
GRANT ALL ON public.candidate_beam_runs  TO service_role;
GRANT ALL ON public.candidate_beam_items TO service_role;

COMMENT ON TABLE public.candidate_beam_runs IS
    'Corridor Candidate Beam runs. Authoring layer — never served to customers.';
COMMENT ON TABLE public.candidate_beam_items IS
    'Deduped, ranked beam candidates awaiting human review. Approved items import into '
    'otto_staging in pending state; nothing here reaches a customer without /admin/countries.';
