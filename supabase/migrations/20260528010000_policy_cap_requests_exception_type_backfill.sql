-- Backfill `exception_type` on legacy / in-transit policy_cap_requests rows
-- ─────────────────────────────────────────────────────────────────────────────
-- The 20260528000000 migration added the column NULLABLE so the field could be
-- rolled out without breaking existing flows. This follow-up applies a
-- deterministic inference rule to populate `exception_type` on rows that
-- predate the field-required tightening, plus any rows posted in the brief
-- window between the column rollout and this backfill.
--
-- Inference rule (high-confidence only — anything ambiguous stays NULL and
-- continues to fall through to the frontend's CATEGORY_TO_TYPE mapping):
--
--   1. cap_amount = 0  AND requested_amount > 0  → 'new_category'
--      (Asking for a benefit that isn't in the package — implicit cap=0.)
--
--   2. cap_amount > 0  AND requested_amount > cap_amount → 'cap_override'
--      (Asking to exceed an existing cap. The most common shape.)
--
--   3. Otherwise → leave NULL.
--      timeline_extension / additional_coverage need duration / benefit
--      context that isn't captured in the amount columns alone; we don't
--      guess. The inbox UI keeps falling back to its client-side mapping.
-- ─────────────────────────────────────────────────────────────────────────────

UPDATE public.policy_cap_requests
SET exception_type = 'new_category'
WHERE exception_type IS NULL
  AND cap_amount = 0
  AND requested_amount > 0;

UPDATE public.policy_cap_requests
SET exception_type = 'cap_override'
WHERE exception_type IS NULL
  AND cap_amount > 0
  AND requested_amount > cap_amount;
