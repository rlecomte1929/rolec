-- AIQ-1410 — Data-API grants for frontend-referenced tables (Oct-30 2026 deadline)
--
-- ⚠️ DRAFT — REVIEW REQUIRED. DO NOT APPLY BLINDLY. ⚠️
-- The GRANT statements below are intentionally COMMENTED OUT so this file is a
-- no-op if `supabase db push` runs. Granting anon/authenticated OPENS Data-API
-- (PostgREST/Realtime) access to a table — the opposite of the SEC-002 lockdown —
-- so each grant is a deliberate, per-table security decision.
--
-- HOW TO USE (per docs/security/AIQ-1410_data_api_grants_audit.md):
--   1. Confirm the frontend genuinely needs Data-API access for the table (not the
--      FastAPI backend). Realtime subs (notifications/case_forms/provider_tasks)
--      are the priority to verify.
--   2. Verify the table's RLS correctly scopes rows for `authenticated`.
--   3. Uncomment ONLY the confirmed lines, apply to the DEV branch first, test,
--      then prod. Reconcile the ledger per CLAUDE.md.
--
-- Context: ReloPass routes almost all data through the backend (service_role), so
-- the vast majority of tables are unaffected by Oct-30. These 8 are the frontend's
-- direct Data-API surface that currently lacks grants. `supplier_stats` is
-- EXCLUDED — it has RLS OFF; granting it would expose every row to any logged-in
-- user. Add RLS before considering a grant.

-- ── Realtime subscriptions (need SELECT→authenticated for Realtime to deliver) ──
-- grant select on public.notifications   to authenticated;  -- realtime: NotificationsBell
-- grant select on public.case_forms      to authenticated;  -- realtime: dossier forms
-- grant select on public.provider_tasks  to authenticated;  -- realtime: provider portal

-- ── Direct .from() reads (verify each is a live Data-API dependency, not backend) ──
-- grant select on public.notification_preferences to authenticated;
-- grant select on public.policy_documents         to authenticated;
-- grant select on public.daily_summaries          to authenticated;
-- grant select on public.pet_import_rules         to authenticated;

-- ── profiles: frontend does .select AND .insert ──
-- grant select, insert on public.profiles to authenticated;

-- supplier_stats: RLS is OFF — do NOT grant until RLS is enabled + policies added.
