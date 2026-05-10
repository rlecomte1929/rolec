-- Append-only audit trail for mobility graph entities (inspectable by admin / SQL)

begin;

create table public.audit_logs (
  id uuid primary key default gen_random_uuid(),
  entity_type text not null,
  entity_id uuid not null,
  action_type text not null,
  old_value_json jsonb,
  new_value_json jsonb,
  actor_type text not null,
  actor_id uuid,
  created_at timestamptz not null default now(),
  constraint audit_logs_action_type_check
    check (action_type in ('insert', 'update', 'delete')),
  constraint audit_logs_actor_type_check
    check (actor_type in ('system', 'human', 'service'))
);

comment on table public.audit_logs is 'MVP audit trail: mobility_cases, case_people, case_documents via triggers; case_requirement_evaluations via app.';
comment on column public.audit_logs.entity_type is 'Logical table name e.g. mobility_cases, case_people.';
comment on column public.audit_logs.actor_type is 'system = default DB trigger; human = set session vars from API; service = automation job.';

create index idx_audit_logs_entity on public.audit_logs (entity_type, entity_id);
create index idx_audit_logs_created_at on public.audit_logs (created_at desc);
create index idx_audit_logs_actor on public.audit_logs (actor_type, created_at desc);

-- Session vars (optional): SET LOCAL relopass.audit_actor_type = 'human'; SET LOCAL relopass.audit_actor_id = '<uuid>';
create or replace function public.relopass_audit_row()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_actor_type text;
  v_actor_id text;
  v_actor_uuid uuid;
begin
  v_actor_type := coalesce(
    nullif(trim(coalesce(current_setting('relopass.audit_actor_type', true), '')), ''),
    'system'
  );
  v_actor_id := nullif(trim(coalesce(current_setting('relopass.audit_actor_id', true), '')), '');
  begin
    v_actor_uuid := v_actor_id::uuid;
  exception
    when invalid_text_representation then
      v_actor_uuid := null;
  end;

  if tg_op = 'INSERT' then
    insert into public.audit_logs (
      entity_type, entity_id, action_type, old_value_json, new_value_json, actor_type, actor_id
    ) values (
      tg_table_name::text,
      new.id,
      'insert',
      null,
      to_jsonb(new),
      v_actor_type,
      v_actor_uuid
    );
    return new;
  elsif tg_op = 'UPDATE' then
    insert into public.audit_logs (
      entity_type, entity_id, action_type, old_value_json, new_value_json, actor_type, actor_id
    ) values (
      tg_table_name::text,
      new.id,
      'update',
      to_jsonb(old),
      to_jsonb(new),
      v_actor_type,
      v_actor_uuid
    );
    return new;
  elsif tg_op = 'DELETE' then
    insert into public.audit_logs (
      entity_type, entity_id, action_type, old_value_json, new_value_json, actor_type, actor_id
    ) values (
      tg_table_name::text,
      old.id,
      'delete',
      to_jsonb(old),
      null,
      v_actor_type,
      v_actor_uuid
    );
    return old;
  end if;
  return null;
end;
$$;

drop trigger if exists trg_audit_mobility_cases on public.mobility_cases;
create trigger trg_audit_mobility_cases
  after insert or update or delete on public.mobility_cases
  for each row execute function public.relopass_audit_row();

drop trigger if exists trg_audit_case_people on public.case_people;
create trigger trg_audit_case_people
  after insert or update or delete on public.case_people
  for each row execute function public.relopass_audit_row();

drop trigger if exists trg_audit_case_documents on public.case_documents;
create trigger trg_audit_case_documents
  after insert or update or delete on public.case_documents
  for each row execute function public.relopass_audit_row();

commit;
