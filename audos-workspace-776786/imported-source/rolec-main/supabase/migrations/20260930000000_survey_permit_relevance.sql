-- TD-EEA (INSEAD cohort): permit-relevance probe on the completion survey — does the
-- tester actually face Employment Permit moves (high-stakes, employer-as-applicant) vs
-- EEA free-movement moves (lighter admin)?
-- Additive column only. survey_responses already has admin-read RLS (from TD-1); the new
-- column inherits it. The enum (yes|not_yet|no) is validated in the API layer, so no DB
-- CHECK is added here — same pattern as 20260928000000_survey_trust_intent.sql.
ALTER TABLE public.survey_responses ADD COLUMN IF NOT EXISTS permit_relevance text;
