-- AIQ-1417 — enable the HR provider-coordination realtime path on provider_tasks (Oct-30 follow-up).
--
-- Live consumer: frontend/src/components/ProviderCoordinationPanel.tsx (HR command-center case detail),
-- an inline Supabase Realtime channel filtered `case_id=eq.<caseId>`. The table currently has NO grant
-- and is NOT in the supabase_realtime publication, so those HR live-updates silently never fire. This
-- grants SELECT + adds it to the publication, mirroring case_forms (already in the publication + granted,
-- same default(pk) replica identity).
--
-- Safe: provider_tasks RLS is ENABLED and row-scoped — `provider_tasks_hr_all` (org_id IN the user's
-- hr_users companies) covers the HR subscriber; `provider_tasks_provider_*` / `_jwt_*` cover the provider
-- portal. GRANT SELECT is additive and RLS-gated; each subscriber still only receives permitted rows.
-- Idempotent.

grant select on public.provider_tasks to authenticated;

do $$
begin
  if not exists (
    select 1 from pg_publication_tables
    where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'provider_tasks'
  ) then
    alter publication supabase_realtime add table public.provider_tasks;
  end if;
end $$;

-- notifications & supplier_stats (the other 2 of AIQ-1410's 9 edge tables): NO grant — both are
-- backend-routed / dead-code. See docs/security/AIQ-1410_data_api_grants_audit.md for the rationale
-- (notifications realtime module has no importer + user_id != auth.uid(); supplier_stats is an unwired
-- materialized view, so RLS is impossible and a grant would expose all rows for a path nothing calls).
