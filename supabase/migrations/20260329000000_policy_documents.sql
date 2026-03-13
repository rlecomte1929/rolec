-- Policy document intake pipeline: staging before extraction to company_policies
begin;

create table if not exists public.policy_documents (
  id uuid primary key default gen_random_uuid(),
  company_id text not null,
  uploaded_by_user_id text not null,
  filename text not null,
  mime_type text not null,
  storage_path text not null,
  checksum text,
  uploaded_at timestamptz not null default now(),
  processing_status text not null default 'uploaded' check (
    processing_status in (
      'uploaded', 'text_extracted', 'classified', 'normalized',
      'review_required', 'approved', 'failed'
    )
  ),
  detected_document_type text check (
    detected_document_type in (
      'assignment_policy', 'policy_summary', 'tax_policy',
      'country_addendum', 'unknown'
    )
  ),
  detected_policy_scope text check (
    detected_policy_scope in (
      'global', 'long_term_assignment', 'short_term_assignment',
      'tax_equalization', 'mixed', 'unknown'
    )
  ),
  version_label text,
  effective_date date,
  raw_text text,
  extraction_error text,
  extracted_metadata jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_policy_documents_company on public.policy_documents(company_id);
create index if not exists idx_policy_documents_status on public.policy_documents(processing_status);
create index if not exists idx_policy_documents_uploaded_at on public.policy_documents(uploaded_at desc);

alter table public.policy_documents enable row level security;

drop policy if exists policy_documents_hr on public.policy_documents;
create policy policy_documents_hr on public.policy_documents
  for all to authenticated
  using (
    exists (
      select 1 from public.profiles p
      where p.id = auth.uid()::text
        and (p.company_id = policy_documents.company_id or p.role = 'ADMIN')
    )
  )
  with check (
    exists (
      select 1 from public.profiles p
      where p.id = auth.uid()::text
        and (p.company_id = policy_documents.company_id or p.role = 'ADMIN')
    )
  );

commit;
