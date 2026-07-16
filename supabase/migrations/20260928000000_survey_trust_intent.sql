-- TD-M4 (AIQ-1559): trust / intent-to-use — the predictive signal beyond problem-fit.
-- Additive columns only. survey_responses already has admin-read RLS (from TD-1); the new
-- columns inherit it. The enum (yes|maybe|no) is validated in the API layer, so no DB CHECK
-- is added here — keeping this a pure additive column migration.
ALTER TABLE public.survey_responses ADD COLUMN IF NOT EXISTS trust_intent     text;
ALTER TABLE public.survey_responses ADD COLUMN IF NOT EXISTS trust_intent_why text;
