-- AIQ-1349 — per-requirement provenance level for the immigration catalog.
--
-- representative  = curated + cited, not yet lawyer-verified
-- corpus_grounded = grounded in the immigration corpus with source citations (FR/NL)
-- expert_verified = signed off by a licensed immigration professional (human-only)
--
-- Surfaced per requirement in the API/UI so the provenance is visible alongside the
-- disclaimer. requirement_items already exists with RLS; a new column needs no policy.
-- Idempotent.

ALTER TABLE public.requirement_items
  ADD COLUMN IF NOT EXISTS verification_status text;
