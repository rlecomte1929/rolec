begin;

insert into storage.buckets (id, name, public)
values ('hr-policies', 'hr-policies', false)
on conflict (id) do nothing;

drop policy if exists hr_policies_read on storage.objects;
create policy hr_policies_read on storage.objects
  for select to authenticated
  using (
    bucket_id = 'hr-policies'
    and exists (
      select 1 from public.profiles p
      where p.id = auth.uid()::text
        and p.company_id = split_part(name, '/', 2)
    )
  );

drop policy if exists hr_policies_write on storage.objects;
create policy hr_policies_write on storage.objects
  for all to authenticated
  using (
    bucket_id = 'hr-policies'
    and exists (
      select 1 from public.profiles p
      where p.id = auth.uid()::text
        and p.company_id = split_part(name, '/', 2)
        and p.role in ('HR','ADMIN')
    )
  )
  with check (
    bucket_id = 'hr-policies'
    and exists (
      select 1 from public.profiles p
      where p.id = auth.uid()::text
        and p.company_id = split_part(name, '/', 2)
        and p.role in ('HR','ADMIN')
    )
  );

commit;
