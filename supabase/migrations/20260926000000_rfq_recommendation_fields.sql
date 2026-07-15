-- [AIQ-1516] HR payer view — persist the best-value recommendation + structured override.
--
-- The HR validation decision already lives on rfqs (validated_quote_id / validated_by_user_id /
-- validated_at / validation_reason, from AIQ-1524). We extend that ONE row rather than add a
-- parallel case_vendor_decisions table — a second table would duplicate validated_quote_id/by/at
-- and give "which vendor did HR pick?" two sources of truth, the exact trap this repo keeps
-- hitting (three RFQ systems, two vendor pools). Decision 2026-07-15.
--
-- All three columns are nullable and additive: existing rows and the budget engine already handle
-- their absence (estimated_cost was NULL before AIQ-1524 too). No FK, no RLS change — rfqs is
-- served through the backend (RLS already configured), never PostgREST.

ALTER TABLE public.rfqs
    -- The recommendation narrative, FROZEN at validation time. Must survive later changes to
    -- vendor_metric_snapshots / ratings — the reasoning HR signed off on is a historical fact.
    ADD COLUMN IF NOT EXISTS recommendation_snapshot jsonb,
    -- Did HR validate the engine's own pick? Drives the override-rate metric. NULL until a
    -- validation happens; false when HR chose a different offer than recommended.
    ADD COLUMN IF NOT EXISTS was_recommended boolean,
    -- Why HR overrode the recommendation. Required (app-enforced, 422) when was_recommended = false.
    -- employee_preference | preferred_supplier | negotiated_terms | policy_exception | other
    ADD COLUMN IF NOT EXISTS override_reason_category text;

COMMENT ON COLUMN public.rfqs.recommendation_snapshot IS
  'AIQ-1516: best-value recommendation narrative frozen at HR validation time (jsonb).';
COMMENT ON COLUMN public.rfqs.was_recommended IS
  'AIQ-1516: true if HR validated the engine-recommended quote; false on override.';
COMMENT ON COLUMN public.rfqs.override_reason_category IS
  'AIQ-1516: category HR chose when overriding the recommendation (app-required on override).';
