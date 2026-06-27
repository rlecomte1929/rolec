-- AIQ-1320: make the shared audit trigger tolerant of tables without an `id` PK.
--
-- public.relopass_audit_row() referenced new.id / old.id for audit_logs.entity_id.
-- Every table using it had an `id` PK except public.services_state, which is keyed
-- on case_id. So an INSERT/UPDATE on services_state raised
--   psycopg2.errors.UndefinedColumn: record "new" has no field "id"
-- → every employee services-state save 500'd (the feature had never persisted
-- server-side; the GET path was fixed in AIQ-1320 #1075 but the POST/save was not).
--
-- Fix: resolve the entity id via a jsonb lookup that (a) never errors when the
-- column is absent and (b) falls back to case_id. Behaviour is IDENTICAL for the
-- ~10 id-keyed tables: `(to_jsonb(new)->>'id')::uuid` round-trips to the same uuid
-- as `new.id`. services_state now audits with its case_id. Idempotent
-- (CREATE OR REPLACE); the triggers themselves are unchanged.

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
      (coalesce(to_jsonb(new) ->> 'id', to_jsonb(new) ->> 'case_id'))::uuid,
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
      (coalesce(to_jsonb(new) ->> 'id', to_jsonb(new) ->> 'case_id'))::uuid,
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
      (coalesce(to_jsonb(old) ->> 'id', to_jsonb(old) ->> 'case_id'))::uuid,
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
