-- AIQ-1349 PR1 — capture assignment type / duration on the canonical case.
--
-- The relocation journey was duration-blind: public.cases carried no assignment
-- type, so the policy resolver (already STA/LTA-aware) and roadmap generation had
-- nothing to branch on. Add two nullable columns the intake bridge now populates.
-- public.cases already has RLS enabled with policies; adding columns needs no new
-- policy. Idempotent.

ALTER TABLE public.cases ADD COLUMN IF NOT EXISTS assignment_type text;
ALTER TABLE public.cases ADD COLUMN IF NOT EXISTS expected_duration_months integer;
