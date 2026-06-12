-- Ledger reconciliation (prod-as-oracle): applied to prod 2026-06-11 via MCP
-- apply_migration, never committed. Exact recovered SQL below. Idempotent
-- (CREATE OR REPLACE).

-- SEC-SRCHPATH-01: Add SET search_path to all SECURITY DEFINER functions missing it
-- Deployed: 2026-06-11
-- Functions fixed: _relocation_policy_insert_audit, activate_policy_version,
--                  my_company_id, my_role, trigger_support_triage

-- 1. _relocation_policy_insert_audit (trigger)
CREATE OR REPLACE FUNCTION public._relocation_policy_insert_audit()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
begin
  insert into public.policy_audit_log (policy_id, event_type, changed_by, diff)
  values (new.id, 'created', new.created_by,
          jsonb_build_object('after', row_to_json(new)::jsonb));
  return new;
end;
$function$;

-- 2. activate_policy_version (search_path only — auth guard added in SEC-SDEF-02)
CREATE OR REPLACE FUNCTION public.activate_policy_version(p_new_version_id uuid, p_org_id text, p_changed_by text DEFAULT NULL::text)
 RETURNS uuid
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_old_id uuid;
begin
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

-- 3. my_company_id (RLS helper)
CREATE OR REPLACE FUNCTION public.my_company_id()
 RETURNS uuid
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  SELECT company_id FROM public.profiles WHERE id = (SELECT auth.uid())
$function$;

-- 4. my_role (RLS helper)
CREATE OR REPLACE FUNCTION public.my_role()
 RETURNS text
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  SELECT role FROM public.profiles WHERE id = (SELECT auth.uid())
$function$;

-- 5. trigger_support_triage (trigger using pg_net — explicit net. prefix preserved)
CREATE OR REPLACE FUNCTION public.trigger_support_triage()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
BEGIN
  PERFORM net.http_post(
    url     := current_setting('app.supabase_url') || '/functions/v1/support-triage',
    headers := jsonb_build_object(
      'Content-Type',  'application/json',
      'Authorization', 'Bearer ' || current_setting('app.service_role_key')
    ),
    body    := jsonb_build_object('ticket_id', NEW.id::text)
  );
  RETURN NEW;
EXCEPTION WHEN OTHERS THEN
  RAISE WARNING 'support_triage trigger: pg_net call failed: %', SQLERRM;
  RETURN NEW;
END;
$function$;
