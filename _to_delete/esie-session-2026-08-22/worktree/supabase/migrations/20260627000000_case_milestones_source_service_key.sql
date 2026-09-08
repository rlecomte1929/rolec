-- Add provenance tagging to case_milestones so service-derived roadmap steps can
-- be reconciled independently and survive AI roadmap regeneration.
-- Altering an existing table (case_milestones already has RLS enabled, see
-- 20260325000000_case_milestones.sql) — no new RLS block required.

ALTER TABLE public.case_milestones ADD COLUMN IF NOT EXISTS source text;
ALTER TABLE public.case_milestones ADD COLUMN IF NOT EXISTS service_key text;

-- Backfill provenance for existing rows (clarity + queryability). AI-generated
-- milestone_type values look like "{phase}_ai_{order}"; everything else is the
-- deterministic seed. New service rows will be written with source='service'.
UPDATE public.case_milestones
   SET source = CASE WHEN milestone_type LIKE '%\_ai\_%' ESCAPE '\' THEN 'ai'
                     ELSE 'deterministic_seed' END
 WHERE source IS NULL;

CREATE INDEX IF NOT EXISTS idx_case_milestones_canonical_source
  ON public.case_milestones (canonical_case_id, source);
