-- Harden identity/linking: one pending claim invite per assignment; supporting indexes.
-- Auth email uniqueness remains on public.users only (users_email_key).
-- Employee contact uniqueness: (company_id, email_normalized) partial unique (existing) + (company_id, invite_key).

begin;

-- Remove duplicate pending rows so the partial unique index can be created.
delete from public.assignment_claim_invites a
where a.status = 'pending'
  and exists (
    select 1 from public.assignment_claim_invites b
    where b.assignment_id = a.assignment_id
      and b.status = 'pending'
      and (
        b.created_at < a.created_at
        or (b.created_at = a.created_at and b.id < a.id)
      )
  );

create unique index if not exists idx_assignment_claim_invites_one_pending_per_assignment
  on public.assignment_claim_invites (assignment_id)
  where status = 'pending';

create index if not exists idx_assignment_claim_invites_assignment_status
  on public.assignment_claim_invites (assignment_id, status);

create index if not exists idx_employee_contacts_email_normalized
  on public.employee_contacts (email_normalized)
  where email_normalized is not null and trim(email_normalized) <> '';

commit;
