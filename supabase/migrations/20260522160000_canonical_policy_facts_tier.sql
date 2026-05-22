-- [P5-9 C1] Add tier column to canonical_policy_facts so that retrieval
-- can enforce tier isolation between Manager / Senior / Executive etc.
--
-- NULL = applies to all tiers (e.g. universal policy intro facts).
-- A populated value MUST match the caller's resolved tier exactly
-- (case-sensitive) to be returned by the policy assistant.
--
-- Retrieval filter (in services/policy_query_answering.py):
--   WHERE company_id = $1 AND (tier IS NULL OR tier = $caller_tier)

ALTER TABLE public.canonical_policy_facts
    ADD COLUMN IF NOT EXISTS tier text;

CREATE INDEX IF NOT EXISTS idx_canonical_policy_facts_company_tier
    ON public.canonical_policy_facts (company_id, tier);

COMMENT ON COLUMN public.canonical_policy_facts.tier IS
    'Policy tier this fact applies to (Manager/Senior/Executive/etc.). '
    'NULL = universal (all tiers). Retrieval path filters by '
    '(tier IS NULL OR tier = caller_tier) per P5-9 C1.';
