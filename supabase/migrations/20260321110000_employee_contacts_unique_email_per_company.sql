-- One operational contact per company per normalized email (when email is known).
begin;

create unique index if not exists idx_employee_contacts_company_email_unique
  on public.employee_contacts (company_id, email_normalized)
  where email_normalized is not null and trim(email_normalized) <> '';

commit;
