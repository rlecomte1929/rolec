-- Somewhere for the research worklist to land.
--
-- 28% of a beam run is unusable: 10 of 35 candidates in the validated FR→NO run carry no
-- source, `FactRow` requires a `source_url`, so `plan_import` skips every one of them with
-- "no source: research worklist, not importable". They are not junk — they are real
-- obligations the model surfaced but could not cite, and sourcing them is exactly the work a
-- human reviewer should be doing. Until now there was no field to put that work in.
--
-- WHY NOT JUST BACKFILL `source`
-- ------------------------------
-- `candidate_beam_items.source` is defined by its own schema comment as the model's verbatim
-- CLAIM, and its NULL as "the research worklist, not a defect to backfill". Writing a human's
-- finding into that column would destroy the distinction between what a model asserted and
-- what a person verified — permanently, and precisely for the rows where the difference
-- matters most. These are separate columns so the two provenances stay separately readable
-- forever, including after the row has been staged.
--
-- These columns do NOT make a candidate verified. They make it IMPORTABLE, on the same terms
-- as any other beam row: staged at `needs_review`, reaching a customer only through the
-- existing /admin/countries gate.

BEGIN;

ALTER TABLE public.candidate_beam_items
    -- The human's finding. Never written by the pipeline, never derived from `source`.
    ADD COLUMN IF NOT EXISTS researched_source_url     TEXT,
    -- The quotable line. FactRow.evidence_quote exists and beam rows set it to NULL because
    -- the beam has no quote; a human can supply what the model could not, so a researched row
    -- can end up BETTER evidenced than a model-claimed one.
    ADD COLUMN IF NOT EXISTS researched_evidence_quote TEXT,
    -- Cached classify_source() verdict, so the worklist can be sorted by publisher quality
    -- without re-deriving it per read. 'unofficial' is stored, never refused: it is a true
    -- fact about the URL, and hiding it would let a blog citation pass as a government one.
    ADD COLUMN IF NOT EXISTS researched_source_class   TEXT,
    ADD COLUMN IF NOT EXISTS researched_by             TEXT,
    ADD COLUMN IF NOT EXISTS researched_at             TIMESTAMPTZ;

-- Provenance is not optional. Mirrors candidate_beam_items_import_audit_chk: a researched
-- source with no researcher and no timestamp is an assertion nobody owns, which is the one
-- thing this table exists to prevent.
ALTER TABLE public.candidate_beam_items
    DROP CONSTRAINT IF EXISTS candidate_beam_items_research_audit_chk;
ALTER TABLE public.candidate_beam_items
    ADD CONSTRAINT candidate_beam_items_research_audit_chk
        CHECK (
            researched_source_url IS NULL
            OR (researched_by IS NOT NULL AND researched_at IS NOT NULL)
        );

-- The worklist read: rows the beam could not source and nobody has sourced since. Partial, so
-- it stays small and shrinks as research lands.
CREATE INDEX IF NOT EXISTS idx_candidate_beam_items_needs_research
    ON public.candidate_beam_items (run_id)
    WHERE source_missing AND researched_source_url IS NULL;

COMMENT ON COLUMN public.candidate_beam_items.researched_source_url IS
    'A HUMAN''S researched source. Deliberately separate from `source`, which is the model''s unverified claim — the two provenances must stay distinguishable after staging. Does not confer verification; the row still stages at needs_review.';
COMMENT ON COLUMN public.candidate_beam_items.researched_source_class IS
    'Cached classify_source() verdict (official/semi_official/unofficial). Stored even when unofficial, so a weak citation is visible rather than silently equivalent to a government one.';

COMMIT;
