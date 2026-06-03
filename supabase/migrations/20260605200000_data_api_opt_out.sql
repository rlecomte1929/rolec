-- FRIDAY-003b: lock down Supabase Data API (PostgREST/GraphQL) exposure.
-- Consumes the FRIDAY-003a audit (backend/docs/data-api-audit.md §6).
--
-- Context: the anon key ships in the frontend bundle, so any public table that
-- holds an anon/authenticated grant is reachable through the auto-generated
-- Data API regardless of whether the app ever calls it. This caused SEC-002
-- (8 tables of PII exposed). This migration revokes Data API grants on the 24
-- high-confidence tables identified by the audit.
--
-- VERIFY rows (case_readiness, case_readiness_checklist_state,
-- case_readiness_milestone_state, employee_tasks, quote_requests) are
-- intentionally EXCLUDED here pending Romain's Q2/Q4/Q5 answers — they are
-- deferred to a follow-up migration.
--
-- KEEP (deliberately NOT revoked): feedback, error_tickets, error_logs
-- (frontend reads these via supabase-js), and the three published_* read
-- views (published_country_events, published_country_resources,
-- published_resource_sources_safe) which are intended public read surfaces.
--
-- REVOKE is idempotent: revoking a privilege that was never granted is a no-op,
-- so this migration is safe to replay.

-- 6a. anon never needs these (admin/debug surfaces use authenticated sessions)
REVOKE ALL    ON public.ai_spend_requests           FROM anon;
REVOKE ALL    ON public.rp_debug_kv                  FROM anon;

-- 6b. country/requirement reference data is served via the FastAPI backend;
--     no logged-out supabase-js path exists today.
REVOKE SELECT ON public.country_events              FROM anon;
REVOKE SELECT ON public.country_profiles            FROM anon;
REVOKE SELECT ON public.country_resource_items      FROM anon;
REVOKE SELECT ON public.country_resource_sections   FROM anon;
REVOKE SELECT ON public.requirement_items           FROM anon;
REVOKE SELECT ON public.requirements_catalog        FROM anon;

-- 6c. authenticated-only tables the frontend never calls via supabase-js
--     (the backend uses the service-role key, which bypasses grants).
REVOKE ALL    ON public.agent_runs                          FROM authenticated;
REVOKE ALL    ON public.ai_human_feedback                   FROM authenticated;
REVOKE ALL    ON public.ai_model_energy_profiles            FROM authenticated;
REVOKE ALL    ON public.bamboohr_sync_log                   FROM authenticated;
REVOKE ALL    ON public.personio_sync_log                   FROM authenticated;
REVOKE ALL    ON public.conjoint_responses                  FROM authenticated;
REVOKE ALL    ON public.conjoint_results                    FROM authenticated;
REVOKE ALL    ON public.conjoint_studies                    FROM authenticated;
REVOKE ALL    ON public.default_policy_templates            FROM authenticated;
REVOKE ALL    ON public.ocr_shadow_comparisons              FROM authenticated;
REVOKE ALL    ON public.prompt_routing                      FROM authenticated;
REVOKE ALL    ON public.prompt_versions                     FROM authenticated;
REVOKE ALL    ON public.translation_cache                   FROM authenticated;
REVOKE ALL    ON public.readiness_templates                 FROM authenticated;
REVOKE ALL    ON public.readiness_template_milestones       FROM authenticated;
REVOKE ALL    ON public.readiness_template_checklist_items  FROM authenticated;

-- ---------------------------------------------------------------------------
-- ROLLBACK (manual; do not uncomment in this append-only migration):
--   The grants below restore the pre-migration state. The backend uses the
--   service-role key and is unaffected either way; these only matter if a
--   future frontend path needs direct supabase-js access to one of these
--   tables (in which case add explicit RLS first).
--
--   GRANT SELECT ON public.ai_spend_requests          TO anon;
--   GRANT SELECT ON public.rp_debug_kv                 TO anon;
--   GRANT SELECT ON public.country_events              TO anon;
--   GRANT SELECT ON public.country_profiles            TO anon;
--   GRANT SELECT ON public.country_resource_items      TO anon;
--   GRANT SELECT ON public.country_resource_sections   TO anon;
--   GRANT SELECT ON public.requirement_items           TO anon;
--   GRANT SELECT ON public.requirements_catalog        TO anon;
--   GRANT SELECT ON public.agent_runs                          TO authenticated;
--   GRANT SELECT ON public.ai_human_feedback                   TO authenticated;
--   GRANT SELECT ON public.ai_model_energy_profiles            TO authenticated;
--   GRANT SELECT ON public.bamboohr_sync_log                   TO authenticated;
--   GRANT SELECT ON public.personio_sync_log                   TO authenticated;
--   GRANT SELECT ON public.conjoint_responses                  TO authenticated;
--   GRANT SELECT ON public.conjoint_results                    TO authenticated;
--   GRANT SELECT ON public.conjoint_studies                    TO authenticated;
--   GRANT SELECT ON public.default_policy_templates            TO authenticated;
--   GRANT SELECT ON public.ocr_shadow_comparisons              TO authenticated;
--   GRANT SELECT ON public.prompt_routing                      TO authenticated;
--   GRANT SELECT ON public.prompt_versions                     TO authenticated;
--   GRANT SELECT ON public.translation_cache                   TO authenticated;
--   GRANT SELECT ON public.readiness_templates                 TO authenticated;
--   GRANT SELECT ON public.readiness_template_milestones       TO authenticated;
--   GRANT SELECT ON public.readiness_template_checklist_items  TO authenticated;
-- ---------------------------------------------------------------------------
