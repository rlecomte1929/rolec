-- Expand RLS on catalog_destination_requests and catalog_destination_allowlist
-- to support the employee→HR destination-request workflow introduced in
-- backend/app/routers/employee_quotes.py and hr_catalog.py.
--
-- Changes:
--   1. Allow employees to INSERT destination requests for their own company.
--   2. Allow HR to UPDATE (resolve) destination requests for their own company.
--   3. Allow HR to INSERT into catalog_destination_allowlist when approving
--      a request (previously admin-only; HR approval adds the entry).

begin;

-- ── 1. Employee-initiated destination requests ──────────────────────────────
-- Drop the HR-only insert policy and replace with one that also covers employees.
drop policy if exists cdr_insert_hr on public.catalog_destination_requests;

create policy cdr_insert_hr_or_employee
  on public.catalog_destination_requests
  for insert
  to authenticated
  with check (
    company_id in (
      select company_id::uuid from public.profiles
      where id::uuid = auth.uid() and role in ('HR', 'ADMIN', 'EMPLOYEE')
    )
  );

-- ── 2. HR can resolve (approve/reject) tickets for their company ────────────
-- Previously only admin could update. Now HR can update requests scoped to
-- their company_id.
drop policy if exists cdr_update_admin on public.catalog_destination_requests;

create policy cdr_update_hr_or_admin
  on public.catalog_destination_requests
  for update
  to authenticated
  using (
    exists (select 1 from public.profiles where id::uuid = auth.uid() and role = 'ADMIN')
    or company_id in (
      select company_id::uuid from public.profiles
      where id::uuid = auth.uid() and role = 'HR'
    )
  )
  with check (
    exists (select 1 from public.profiles where id::uuid = auth.uid() and role = 'ADMIN')
    or company_id in (
      select company_id::uuid from public.profiles
      where id::uuid = auth.uid() and role = 'HR'
    )
  );

-- ── 3. HR can add entries to the allowlist when approving a request ─────────
-- The existing admin-only policy is kept; this new policy adds HR inserts
-- so the HR PATCH endpoint can write to catalog_destination_allowlist directly
-- when called via the Supabase client (backend service role already bypasses RLS).
create policy cda_insert_hr
  on public.catalog_destination_allowlist
  for insert
  to authenticated
  with check (
    exists (
      select 1 from public.profiles
      where id::uuid = auth.uid() and role in ('HR', 'ADMIN')
    )
  );

commit;
