-- HR Command Center: Risk Scoring RPC and triggers

begin;

-- =============================================================================
-- recalculate_case_risk(assignment_id uuid)
-- MVP rules:
--   - Any task status = 'overdue' → yellow
--   - Visa milestone overdue > 7 days → red (simplified: any overdue > 7 days → red)
--   - budget_estimated > budget_limit (and both set) → red
--   - Else → green
-- =============================================================================
create or replace function public.recalculate_case_risk(p_assignment_id text)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_risk text := 'green';
  v_any_overdue boolean := false;
  v_overdue_days int := 0;
  v_budget_limit numeric;
  v_budget_estimated numeric;
  v_prev_risk text;
begin
  select risk_status, budget_limit, budget_estimated
  into v_prev_risk, v_budget_limit, v_budget_estimated
  from public.case_assignments
  where id = p_assignment_id;

  if not found then
    return;
  end if;

  -- Check for overdue tasks
  select exists (
    select 1 from public.relocation_tasks
    where assignment_id = p_assignment_id and status = 'overdue'
  ) into v_any_overdue;

  if v_any_overdue then
    select coalesce(
      max(extract(day from (current_date - due_date))::int),
      0
    ) into v_overdue_days
    from public.relocation_tasks
    where assignment_id = p_assignment_id and status = 'overdue' and due_date is not null;
  end if;

  -- Budget overrun
  if v_budget_limit is not null and v_budget_estimated is not null and v_budget_estimated > v_budget_limit then
    v_risk := 'red';
  elsif v_overdue_days > 7 then
    v_risk := 'red';
  elsif v_any_overdue then
    v_risk := 'yellow';
  end if;

  update public.case_assignments
  set risk_status = v_risk
  where id = p_assignment_id;

  -- Notify HR if risk changed to yellow or red
  if v_prev_risk is distinct from v_risk and v_risk in ('yellow','red') then
    perform public.notify_hr_risk_change(p_assignment_id, v_risk);
  end if;
end;
$$;

-- Helper to create notification when risk changes (uses existing notification system if available)
create or replace function public.notify_hr_risk_change(p_assignment_id text, p_risk text)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_hr_user_id text;
  v_title text;
  v_body text;
begin
  select hr_user_id into v_hr_user_id
  from public.case_assignments where id = p_assignment_id;
  if v_hr_user_id is null then return; end if;

  v_title := case p_risk
    when 'red' then 'Case at high risk'
    else 'Case needs attention'
  end;
  v_body := case p_risk
    when 'red' then 'Assignment ' || p_assignment_id || ' has been marked high risk. Immediate attention recommended.'
    else 'Assignment ' || p_assignment_id || ' needs attention (yellow risk).'
  end;

  -- Insert into notifications if table exists (SECURITY DEFINER bypasses RLS for insert)
  if exists (select 1 from information_schema.tables where table_schema='public' and table_name='notifications') then
    begin
      insert into public.notifications (user_id, type, title, body, assignment_id, metadata)
      values (
        v_hr_user_id::uuid,
        'CASE_RISK',
        v_title,
        v_body,
        p_assignment_id,
        jsonb_build_object('risk', p_risk, 'assignment_id', p_assignment_id)
      );
    exception when others then
      null; -- Do not fail risk update if notification insert fails
    end;
  end if;
end;
$$;

-- Trigger function: recalculate risk on task update
create or replace function public.trigger_recalculate_risk_on_task()
returns trigger
language plpgsql
as $$
begin
  if coalesce(new.assignment_id, old.assignment_id) is not null then
    perform public.recalculate_case_risk(coalesce(new.assignment_id, old.assignment_id)::text);
  end if;
  return coalesce(new, old);
end;
$$;

drop trigger if exists trg_relocation_tasks_recalc_risk on public.relocation_tasks;
create trigger trg_relocation_tasks_recalc_risk
  after insert or update or delete on public.relocation_tasks
  for each row execute function public.trigger_recalculate_risk_on_task();

-- Trigger function: recalculate risk on budget update (case_assignments)
create or replace function public.trigger_recalculate_risk_on_budget()
returns trigger
language plpgsql
as $$
begin
  if new.budget_limit is distinct from old.budget_limit or new.budget_estimated is distinct from old.budget_estimated then
    perform public.recalculate_case_risk(new.id::text);
  end if;
  return new;
end;
$$;

drop trigger if exists trg_case_assignments_recalc_risk on public.case_assignments;
create trigger trg_case_assignments_recalc_risk
  after update of budget_limit, budget_estimated on public.case_assignments
  for each row execute function public.trigger_recalculate_risk_on_budget();

-- Grant execute to authenticated
grant execute on function public.recalculate_case_risk(text) to authenticated;
grant execute on function public.recalculate_case_risk(text) to service_role;

commit;
