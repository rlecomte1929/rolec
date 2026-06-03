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

-- Replay-safe guard. The header's "safe to replay" claim relies on every table
-- existing, but a few of these (e.g. ai_spend_requests, rp_debug_kv, agent_runs)
-- were created out-of-band on prod by the backend ORM and have no repo CREATE, so
-- a fresh replay / Supabase Preview aborts on the first REVOKE against a missing
-- relation (42P01). Guard each REVOKE with to_regclass() so a missing table is a
-- true no-op. On prod all tables exist, so every REVOKE runs exactly as the flat
-- statements did — identical effect, zero prod mutation. (priv/role come from the
-- fixed list below, not user input, so the format() interpolation is safe.)
do $$
declare
  r record;
begin
  for r in
    select tbl, role_name, priv from (values
      -- 6a. anon never needs these (admin/debug surfaces use authenticated sessions)
      ('ai_spend_requests',                  'anon',          'ALL'),
      ('rp_debug_kv',                        'anon',          'ALL'),
      -- 6b. country/requirement reference data is served via the FastAPI backend;
      --     no logged-out supabase-js path exists today.
      ('country_events',                     'anon',          'SELECT'),
      ('country_profiles',                   'anon',          'SELECT'),
      ('country_resource_items',             'anon',          'SELECT'),
      ('country_resource_sections',          'anon',          'SELECT'),
      ('requirement_items',                  'anon',          'SELECT'),
      ('requirements_catalog',               'anon',          'SELECT'),
      -- 6c. authenticated-only tables the frontend never calls via supabase-js
      --     (the backend uses the service-role key, which bypasses grants).
      ('agent_runs',                         'authenticated', 'ALL'),
      ('ai_human_feedback',                  'authenticated', 'ALL'),
      ('ai_model_energy_profiles',           'authenticated', 'ALL'),
      ('bamboohr_sync_log',                  'authenticated', 'ALL'),
      ('personio_sync_log',                  'authenticated', 'ALL'),
      ('conjoint_responses',                 'authenticated', 'ALL'),
      ('conjoint_results',                   'authenticated', 'ALL'),
      ('conjoint_studies',                   'authenticated', 'ALL'),
      ('default_policy_templates',           'authenticated', 'ALL'),
      ('ocr_shadow_comparisons',             'authenticated', 'ALL'),
      ('prompt_routing',                     'authenticated', 'ALL'),
      ('prompt_versions',                    'authenticated', 'ALL'),
      ('translation_cache',                  'authenticated', 'ALL'),
      ('readiness_templates',                'authenticated', 'ALL'),
      ('readiness_template_milestones',      'authenticated', 'ALL'),
      ('readiness_template_checklist_items', 'authenticated', 'ALL')
    ) as t(tbl, role_name, priv)
  loop
    if to_regclass('public.' || r.tbl) is not null then
      execute format('revoke %s on public.%I from %I', r.priv, r.tbl, r.role_name);
    end if;
  end loop;
end $$;

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
