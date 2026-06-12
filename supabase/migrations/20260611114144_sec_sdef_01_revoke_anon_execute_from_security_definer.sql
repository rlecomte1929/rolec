-- Ledger reconciliation (prod-as-oracle): applied to prod 2026-06-11 via MCP
-- apply_migration, never committed. Exact recovered SQL below. Idempotent
-- (REVOKE/GRANT).

-- SEC-SDEF-01: Remove anon EXECUTE from SECURITY DEFINER functions
-- Deployed: 2026-06-11
-- Strategy:
--   Group A: REVOKE FROM PUBLIC entirely (backend/system-only functions)
--   Group B: REVOKE FROM PUBLIC + RE-GRANT TO authenticated (legitimate frontend functions)
--   Leave:   RLS helpers (my_company_id, my_role, rls_can_access_*, etc.) — anon needs
--            EXECUTE to evaluate RLS policy expressions

-- ═══════════════════════════════════════════════════════════════════════
-- GROUP A — backend-only: revoke from PUBLIC, do NOT re-grant to authenticated
-- ═══════════════════════════════════════════════════════════════════════

-- Destructive / PII operations (critical)
REVOKE EXECUTE ON FUNCTION public.fn_anonymise_imm_profile(text) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.fn_immigration_retention_cleanup() FROM PUBLIC;

-- HRIS sync triggers (service_role only)
REVOKE EXECUTE ON FUNCTION public.fn_notify_bamboohr_status_sync() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.fn_notify_personio_status_sync() FROM PUBLIC;

-- Analytics refresh (admin/cron only)
REVOKE EXECUTE ON FUNCTION public.refresh_ai_unit_economics() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.refresh_supplier_stats() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.refresh_ocr_shadow_comparison() FROM PUBLIC;

-- Audit / coordination triggers (internal)
REVOKE EXECUTE ON FUNCTION public.fn_aggregate_case_coordination_status() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.fn_case_close_set_retention() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.fn_imm_employee_profiles_audit() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.relopass_audit_row() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public._relocation_policy_insert_audit() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.trigger_support_triage() FROM PUBLIC;

-- Testing utility
REVOKE EXECUTE ON FUNCTION public.assert_assignment_links(text, uuid, uuid) FROM PUBLIC;

-- ═══════════════════════════════════════════════════════════════════════
-- GROUP B — app functions: revoke from PUBLIC, re-grant to authenticated only
-- ═══════════════════════════════════════════════════════════════════════

REVOKE EXECUTE ON FUNCTION public.activate_policy_version(uuid, text, text) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION public.activate_policy_version(uuid, text, text) TO authenticated;

REVOKE EXECUTE ON FUNCTION public.create_rfq_with_items(text, uuid, text, jsonb, uuid[]) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION public.create_rfq_with_items(text, uuid, text, jsonb, uuid[]) TO authenticated;

REVOKE EXECUTE ON FUNCTION public.create_notification(uuid, text, text, text, text, text, jsonb) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION public.create_notification(uuid, text, text, text, text, text, jsonb) TO authenticated;

REVOKE EXECUTE ON FUNCTION public.log_immigration_data_access(text, text, text, text[], text, text, text, text) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION public.log_immigration_data_access(text, text, text, text[], text, text, text, text) TO authenticated;

REVOKE EXECUTE ON FUNCTION public.notify_hr_risk_change(text, text) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION public.notify_hr_risk_change(text, text) TO authenticated;

REVOKE EXECUTE ON FUNCTION public.post_hr_feedback(text, text) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION public.post_hr_feedback(text, text) TO authenticated;

REVOKE EXECUTE ON FUNCTION public.recalculate_case_risk(text) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION public.recalculate_case_risk(text) TO authenticated;

REVOKE EXECUTE ON FUNCTION public.transition_assignment(text, text, text) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION public.transition_assignment(text, text, text) TO authenticated;
