-- Policy Assistant: document-grounded knowledge pipeline (upload → chunks → facts → snapshot).
-- Does not modify company_policies / published baseline tables.

begin;

-- Extend policy_documents (existing intake table) with assistant pipeline fields.
alter table public.policy_documents
  add column if not exists file_size_bytes bigint,
  add column if not exists archived_at timestamptz,
  add column if not exists assistant_import_status text,
  add column if not exists processed_at timestamptz;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'policy_documents_assistant_import_status_check'
  ) then
    alter table public.policy_documents
      add constraint policy_documents_assistant_import_status_check
      check (
        assistant_import_status is null
        or assistant_import_status in (
          'uploaded',
          'extracting_text',
          'text_ready',
          'extracting_facts',
          'ready_for_assistant',
          'failed'
        )
      );
  end if;
end $$;

comment on column public.policy_documents.assistant_import_status is
  'Parallel to processing_status (legacy ingest). Tracks assistant knowledge pipeline only.';

create table if not exists public.policy_document_chunks (
  id uuid primary key default gen_random_uuid(),
  policy_document_id uuid not null references public.policy_documents (id) on delete cascade,
  chunk_index integer not null,
  page_number integer,
  section_title text,
  text_content text not null,
  token_count integer,
  metadata_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint policy_document_chunks_doc_chunk_unique unique (policy_document_id, chunk_index)
);

create index if not exists idx_policy_document_chunks_doc
  on public.policy_document_chunks (policy_document_id);

create table if not exists public.policy_processing_runs (
  id uuid primary key default gen_random_uuid(),
  policy_document_id uuid not null references public.policy_documents (id) on delete cascade,
  run_type text not null
    check (run_type in ('text_extraction', 'fact_extraction', 'graph_sync')),
  status text not null default 'pending'
    check (status in ('pending', 'running', 'completed', 'failed')),
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  error_message text,
  metrics_json jsonb
);

create index if not exists idx_policy_processing_runs_doc
  on public.policy_processing_runs (policy_document_id);

create table if not exists public.policy_knowledge_snapshots (
  id uuid primary key default gen_random_uuid(),
  company_id text not null,
  policy_document_id uuid not null references public.policy_documents (id) on delete cascade,
  version_label text,
  status text not null default 'failed'
    check (status in ('active_for_assistant', 'superseded', 'failed')),
  extraction_method text not null default 'deterministic_v1',
  created_at timestamptz not null default now(),
  superseded_at timestamptz
);

create index if not exists idx_policy_knowledge_snapshots_company
  on public.policy_knowledge_snapshots (company_id);

create index if not exists idx_policy_knowledge_snapshots_doc
  on public.policy_knowledge_snapshots (policy_document_id);

create index if not exists idx_policy_knowledge_snapshots_company_status
  on public.policy_knowledge_snapshots (company_id, status);

create table if not exists public.policy_facts (
  id uuid primary key default gen_random_uuid(),
  snapshot_id uuid not null references public.policy_knowledge_snapshots (id) on delete cascade,
  fact_type text not null
    check (
      fact_type in (
        'benefit',
        'allowance_cap',
        'duration_limit',
        'eligibility_rule',
        'family_rule',
        'assignment_type_rule',
        'destination_rule',
        'approval_requirement',
        'reimbursement_rule',
        'excluded_item',
        'exception_note'
      )
    ),
  category text not null default '',
  subcategory text,
  normalized_value_json jsonb not null default '{}'::jsonb,
  applicability_json jsonb not null default '{}'::jsonb,
  ambiguity_flag boolean not null default false,
  confidence_score real,
  source_chunk_id uuid not null references public.policy_document_chunks (id) on delete restrict,
  source_page integer,
  source_section text,
  source_quote text,
  created_at timestamptz not null default now()
);

create index if not exists idx_policy_facts_snapshot on public.policy_facts (snapshot_id);
create index if not exists idx_policy_facts_type on public.policy_facts (fact_type);
create index if not exists idx_policy_facts_chunk on public.policy_facts (source_chunk_id);

-- Idempotent binding: one active assistant snapshot per company (resolved by graph sync).
create table if not exists public.company_policy_assistant_bindings (
  company_id text primary key,
  active_snapshot_id uuid references public.policy_knowledge_snapshots (id) on delete set null,
  policy_document_id uuid references public.policy_documents (id) on delete set null,
  updated_at timestamptz not null default now()
);

-- RLS (same tenant pattern as policy_documents)
alter table public.policy_document_chunks enable row level security;
alter table public.policy_processing_runs enable row level security;
alter table public.policy_knowledge_snapshots enable row level security;
alter table public.policy_facts enable row level security;
alter table public.company_policy_assistant_bindings enable row level security;

drop policy if exists policy_document_chunks_hr on public.policy_document_chunks;
create policy policy_document_chunks_hr on public.policy_document_chunks
  for all to authenticated
  using (
    exists (
      select 1 from public.policy_documents pd
      join public.profiles p on p.company_id = pd.company_id
      where pd.id = policy_document_chunks.policy_document_id
        and (p.id = auth.uid()::text or p.role = 'ADMIN')
    )
  )
  with check (
    exists (
      select 1 from public.policy_documents pd
      join public.profiles p on p.company_id = pd.company_id
      where pd.id = policy_document_chunks.policy_document_id
        and (p.id = auth.uid()::text or p.role = 'ADMIN')
    )
  );

drop policy if exists policy_processing_runs_hr on public.policy_processing_runs;
create policy policy_processing_runs_hr on public.policy_processing_runs
  for all to authenticated
  using (
    exists (
      select 1 from public.policy_documents pd
      join public.profiles p on p.company_id = pd.company_id
      where pd.id = policy_processing_runs.policy_document_id
        and (p.id = auth.uid()::text or p.role = 'ADMIN')
    )
  )
  with check (
    exists (
      select 1 from public.policy_documents pd
      join public.profiles p on p.company_id = pd.company_id
      where pd.id = policy_processing_runs.policy_document_id
        and (p.id = auth.uid()::text or p.role = 'ADMIN')
    )
  );

drop policy if exists policy_knowledge_snapshots_hr on public.policy_knowledge_snapshots;
create policy policy_knowledge_snapshots_hr on public.policy_knowledge_snapshots
  for all to authenticated
  using (
    exists (
      select 1 from public.profiles p
      where p.company_id = policy_knowledge_snapshots.company_id
        and (p.id = auth.uid()::text or p.role = 'ADMIN')
    )
  )
  with check (
    exists (
      select 1 from public.profiles p
      where p.company_id = policy_knowledge_snapshots.company_id
        and (p.id = auth.uid()::text or p.role = 'ADMIN')
    )
  );

drop policy if exists policy_facts_hr on public.policy_facts;
create policy policy_facts_hr on public.policy_facts
  for all to authenticated
  using (
    exists (
      select 1 from public.policy_knowledge_snapshots s
      join public.profiles p on p.company_id = s.company_id
      where s.id = policy_facts.snapshot_id
        and (p.id = auth.uid()::text or p.role = 'ADMIN')
    )
  )
  with check (
    exists (
      select 1 from public.policy_knowledge_snapshots s
      join public.profiles p on p.company_id = s.company_id
      where s.id = policy_facts.snapshot_id
        and (p.id = auth.uid()::text or p.role = 'ADMIN')
    )
  );

drop policy if exists company_policy_assistant_bindings_hr on public.company_policy_assistant_bindings;
create policy company_policy_assistant_bindings_hr on public.company_policy_assistant_bindings
  for all to authenticated
  using (
    exists (
      select 1 from public.profiles p
      where p.company_id = company_policy_assistant_bindings.company_id
        and (p.id = auth.uid()::text or p.role = 'ADMIN')
    )
  )
  with check (
    exists (
      select 1 from public.profiles p
      where p.company_id = company_policy_assistant_bindings.company_id
        and (p.id = auth.uid()::text or p.role = 'ADMIN')
    )
  );

commit;
