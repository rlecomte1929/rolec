-- Repair schema drift: company_policies.is_default_template must be boolean (Postgres strict).
-- If the column was added manually or via a bad script as integer/smallint, inserts that bind
-- integers can still fail or behave oddly. This migration is idempotent: no-op when type is already boolean.
begin;

do $repair$
begin
  if exists (
    select 1
    from information_schema.columns c
    where c.table_schema = 'public'
      and c.table_name = 'company_policies'
      and c.column_name = 'is_default_template'
      and c.data_type in ('smallint', 'integer', 'bigint')
  ) then
    alter table public.company_policies
      alter column is_default_template type boolean
      using (coalesce(is_default_template, 0) <> 0);
  end if;
end
$repair$;

commit;
