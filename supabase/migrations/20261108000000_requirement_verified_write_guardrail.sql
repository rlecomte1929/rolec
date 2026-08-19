-- Verified-write guardrail — generator/verifier separation for the provenance ladder.
--
-- requirement_items.verification_status (representative / corpus_grounded / expert_verified,
-- AIQ-1349) tops out at a state defined as "signed off by a licensed immigration professional
-- (human-only)". These two columns record WHO signed and WHEN, so the human signature is a
-- fact and not a bare label:
--
--   verified_by  — the human actor behind verification_status='expert_verified'
--   verified_at  — when they signed it off
--
-- Enforcement lives in the backend at the single write funnel
-- (backend/app/crud.py::create_requirement_item + backend/app/services/verification_guard.py):
-- generator/import/seed paths cannot write expert_verified or these columns at all, and the
-- only path that can (verification_guard.mark_expert_verified, behind the admin router)
-- refuses actors that are missing or look automated. Fail-closed.
--
-- Mirrors reviewed_by/reviewed_at (publication gate) and attested_by/attested_at (counsel
-- attestation axis, 20261104000000).
--
-- requirement_items already exists with RLS; new columns need no policy. Idempotent.
--
-- guard: column-read-ok this migration is applied to production by the operator BEFORE the
-- PR is merged (psql -f + `supabase migration repair --status applied 20261108000000`),
-- same procedure as 20261103000000 / 20261104000000. The DTO readers are additionally
-- getattr-defaulted and degrade to NULL rather than raising. Do NOT merge the PR until
-- the apply is confirmed.

ALTER TABLE public.requirement_items
  ADD COLUMN IF NOT EXISTS verified_by text;

ALTER TABLE public.requirement_items
  ADD COLUMN IF NOT EXISTS verified_at timestamptz;
