-- Policy document clauses: structured segmentation with source traceability
begin;

create table if not exists public.policy_document_clauses (
  id uuid primary key default gen_random_uuid(),
  policy_document_id uuid not null references public.policy_documents(id) on delete cascade,
  section_label text,
  section_path text,
  clause_type text not null default 'unknown' check (
    clause_type in (
      'scope', 'eligibility', 'benefit', 'exclusion', 'approval_rule',
      'evidence_rule', 'tax_rule', 'definition', 'lifecycle_rule', 'unknown'
    )
  ),
  title text,
  raw_text text not null,
  normalized_hint_json jsonb,
  source_page_start integer,
  source_page_end integer,
  source_anchor text,
  confidence real default 0.5,
  hr_override_notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_policy_document_clauses_doc on public.policy_document_clauses(policy_document_id);
create index if not exists idx_policy_document_clauses_type on public.policy_document_clauses(clause_type);
create index if not exists idx_policy_document_clauses_section on public.policy_document_clauses(section_label);

alter table public.policy_document_clauses enable row level security;

drop policy if exists policy_document_clauses_hr on public.policy_document_clauses;
create policy policy_document_clauses_hr on public.policy_document_clauses
  for all to authenticated
  using (
    exists (
      select 1 from public.policy_documents pd
      join public.profiles p on p.company_id = pd.company_id
      where pd.id = policy_document_clauses.policy_document_id
        and (p.id = auth.uid()::text or p.role = 'ADMIN')
    )
  )
  with check (
    exists (
      select 1 from public.policy_documents pd
      join public.profiles p on p.company_id = pd.company_id
      where pd.id = policy_document_clauses.policy_document_id
        and (p.id = auth.uid()::text or p.role = 'ADMIN')
    )
  );

commit;
