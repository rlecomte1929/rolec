-- Ledger reconciliation (prod-as-oracle): applied to prod 2026-06-11 via MCP
-- apply_migration, never committed. Exact recovered SQL below. Idempotent
-- (CREATE OR REPLACE).

-- SEC-SDEF-02: Add is_admin()/service_role guards to unguarded SECURITY DEFINER functions
-- Deployed: 2026-06-11
-- Functions: activate_policy_version, fn_anonymise_imm_profile,
--            fn_immigration_retention_cleanup, refresh_ai_unit_economics,
--            refresh_supplier_stats

-- ─────────────────────────────────────────────────────────────────────
-- 1. activate_policy_version — admin-only guard added
-- ─────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.activate_policy_version(
  p_new_version_id uuid,
  p_org_id text,
  p_changed_by text DEFAULT NULL::text
)
 RETURNS uuid
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_old_id uuid;
begin
  -- Security guard: admin only
  if not is_admin() then
    raise exception 'Only admin users can activate policy versions';
  end if;

  update public.relocation_policies
  set    is_active = false
  where  org_id   = p_org_id
    and  is_active = true
    and  id       <> p_new_version_id
  returning id into v_old_id;

  if v_old_id is not null then
    insert into public.policy_audit_log (policy_id, event_type, changed_by, diff)
    values (v_old_id, 'deactivated', p_changed_by,
            jsonb_build_object('before', jsonb_build_object('is_active', true),
                               'after',  jsonb_build_object('is_active', false)));
  end if;

  update public.relocation_policies
  set    is_active = true
  where  id       = p_new_version_id
    and  org_id   = p_org_id;

  if not found then
    raise exception 'Policy version % not found for org %', p_new_version_id, p_org_id;
  end if;

  insert into public.policy_audit_log (policy_id, event_type, changed_by, diff)
  values (p_new_version_id, 'activated', p_changed_by,
          jsonb_build_object('before', jsonb_build_object('is_active', false),
                             'after',  jsonb_build_object('is_active', true)));

  return p_new_version_id;
end;
$function$;

-- ─────────────────────────────────────────────────────────────────────
-- 2. fn_anonymise_imm_profile — service_role or admin guard added
-- ─────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.fn_anonymise_imm_profile(p_profile_id text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_keep    TEXT[] := ARRAY['id','case_id','employee_id','org_id',
                            'created_at','updated_at','retention_expires_at','anonymised_at'];
  v_col     TEXT;
  v_sets    TEXT := '';
  v_case_id TEXT;
BEGIN
  -- Security guard: service_role (cron/backend) or admin user only
  IF NOT (auth.role() = 'service_role' OR is_admin()) THEN
    RAISE EXCEPTION 'fn_anonymise_imm_profile: service_role or admin only';
  END IF;

  SELECT case_id INTO v_case_id FROM public.imm_employee_profiles WHERE id = p_profile_id;
  IF NOT FOUND THEN
    RETURN;
  END IF;

  FOR v_col IN
    SELECT column_name FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'imm_employee_profiles'
      AND column_name <> ALL (v_keep)
  LOOP
    v_sets := v_sets || format('%I = NULL, ', v_col);
  END LOOP;

  EXECUTE format(
    'UPDATE public.imm_employee_profiles SET %s anonymised_at = NOW(), updated_at = NOW() WHERE id = %L',
    v_sets, p_profile_id
  );

  INSERT INTO public.data_access_log
    (case_id, profile_id, accessed_by_user_id, accessed_by_role,
     action, fields_accessed, purpose, accessed_at)
  VALUES
    (v_case_id, p_profile_id, 'system', 'system',
     'ANONYMISED', ARRAY['all_pii'], 'retention_erasure', NOW());
END;
$function$;

-- ─────────────────────────────────────────────────────────────────────
-- 3. fn_immigration_retention_cleanup — service_role or admin guard added
-- ─────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.fn_immigration_retention_cleanup()
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_anon INT := 0;
  v_del  INT := 0;
  v_id   TEXT;
BEGIN
  -- Security guard: service_role (cron/backend) or admin user only
  IF NOT (auth.role() = 'service_role' OR is_admin()) THEN
    RAISE EXCEPTION 'fn_immigration_retention_cleanup: service_role or admin only';
  END IF;

  FOR v_id IN
    SELECT id FROM public.imm_employee_profiles
    WHERE retention_expires_at IS NOT NULL
      AND retention_expires_at < NOW()
      AND anonymised_at IS NULL
  LOOP
    PERFORM public.fn_anonymise_imm_profile(v_id);
    v_anon := v_anon + 1;
  END LOOP;

  WITH del AS (
    DELETE FROM public.imm_employee_profiles
    WHERE retention_expires_at IS NOT NULL
      AND retention_expires_at < NOW() - INTERVAL '30 days'
    RETURNING id
  )
  SELECT count(*) INTO v_del FROM del;

  INSERT INTO public.system_log (job_name, status, details)
  VALUES ('immigration-retention-cleanup', 'success',
          jsonb_build_object('anonymised', v_anon, 'deleted', v_del));

  RETURN jsonb_build_object('anonymised', v_anon, 'deleted', v_del);
END;
$function$;

-- ─────────────────────────────────────────────────────────────────────
-- 4. refresh_ai_unit_economics — service_role or admin guard added
--    (converted from LANGUAGE sql to plpgsql to support IF block)
-- ─────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.refresh_ai_unit_economics()
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
BEGIN
  IF NOT (auth.role() = 'service_role' OR is_admin()) THEN
    RAISE EXCEPTION 'refresh_ai_unit_economics: service_role or admin only';
  END IF;
  REFRESH MATERIALIZED VIEW CONCURRENTLY public.mv_ai_unit_economics;
END;
$function$;

-- ─────────────────────────────────────────────────────────────────────
-- 5. refresh_supplier_stats — service_role or admin guard added
--    (converted from LANGUAGE sql to plpgsql to support IF block)
-- ─────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.refresh_supplier_stats()
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
BEGIN
  IF NOT (auth.role() = 'service_role' OR is_admin()) THEN
    RAISE EXCEPTION 'refresh_supplier_stats: service_role or admin only';
  END IF;
  REFRESH MATERIALIZED VIEW CONCURRENTLY public.supplier_stats;
END;
$function$;
