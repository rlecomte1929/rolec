-- Policy assistant hardening: append-only snapshots, extraction locks, answer audits, chunk versioning.

begin;

-- Allow multiple chunk sets per document (one per snapshot revision)
alter table public.policy_document_chunks
  drop constraint if exists policy_document_chunks_doc_chunk_unique;

-- ---------------------------------------------------------------------------
-- policy_knowledge_snapshots: revision graph columns FIRST (chunks FK references this)
-- ---------------------------------------------------------------------------
alter table public.policy_knowledge_snapshots
  add column if not exists revision_number integer not null default 1,
  add column if not exists parent_snapshot_id uuid references public.policy_knowledge_snapshots(id) on delete set null,
  add column if not exists superseded_by_snapshot_id uuid references public.policy_knowledge_snapshots(id) on delete set null,
  add column if not exists activation_state text,
  add column if not exists activated_at timestamptz,
  add column if not exists activated_by_user_id text;

update public.policy_knowledge_snapshots
set activation_state = case
  when status = 'active_for_assistant' then 'active_for_assistant'
  when status = 'superseded' then 'superseded'
  when status = 'failed' then 'failed'
  else 'failed'
end
where activation_state is null;

alter table public.policy_knowledge_snapshots
  alter column activation_state set not null;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'policy_knowledge_snapshots_activation_state_check'
  ) then
    alter table public.policy_knowledge_snapshots
      add constraint policy_knowledge_snapshots_activation_state_check
      check (
        activation_state in (
          'candidate',
          'active_for_assistant',
          'superseded',
          'failed',
          'archived'
        )
      );
  end if;
end $$;

create index if not exists idx_policy_knowledge_snapshots_doc_revision
  on public.policy_knowledge_snapshots(policy_document_id, revision_number desc);

create index if not exists idx_policy_knowledge_snapshots_company_activation
  on public.policy_knowledge_snapshots(company_id, activation_state);

-- ---------------------------------------------------------------------------
-- policy_document_chunks: link rows to the snapshot they were produced for (append-only history)
-- ---------------------------------------------------------------------------
alter table public.policy_document_chunks
  add column if not exists snapshot_id uuid references public.policy_knowledge_snapshots(id) on delete set null;

create index if not exists idx_policy_document_chunks_snapshot_id
  on public.policy_document_chunks(snapshot_id);

comment on column public.policy_document_chunks.snapshot_id is
  'Set for new extractions; older chunk rows remain for prior snapshots.';

create unique index if not exists policy_document_chunks_snapshot_chunk_idx
  on public.policy_document_chunks(snapshot_id, chunk_index)
  where snapshot_id is not null;

create unique index if not exists policy_document_chunks_doc_chunk_legacy_idx
  on public.policy_document_chunks(policy_document_id, chunk_index)
  where snapshot_id is null;

-- ---------------------------------------------------------------------------
-- Extraction locks (one active extract per document; stale expiry)
-- ---------------------------------------------------------------------------
create table if not exists public.policy_extraction_locks (
  id uuid primary key default gen_random_uuid(),
  policy_document_id uuid not null references public.policy_documents(id) on delete cascade,
  company_id text not null,
  locked_by_user_id text not null,
  lock_token uuid not null,
  acquired_at timestamptz not null default now(),
  expires_at timestamptz not null,
  status text not null default 'active'
    check (status in ('active', 'released', 'expired')),
  metadata_json jsonb,
  constraint policy_extraction_locks_document_unique unique (policy_document_id)
);

create index if not exists idx_policy_extraction_locks_company on public.policy_extraction_locks(company_id);
create index if not exists idx_policy_extraction_locks_expires on public.policy_extraction_locks(expires_at);

alter table public.policy_extraction_locks enable row level security;

drop policy if exists policy_extraction_locks_hr on public.policy_extraction_locks;
create policy policy_extraction_locks_hr on public.policy_extraction_locks
  for all to authenticated
  using (
    exists (
      select 1 from public.profiles p
      where p.company_id = policy_extraction_locks.company_id
        and (p.id = auth.uid()::text or p.role = 'ADMIN')
    )
  )
  with check (
    exists (
      select 1 from public.profiles p
      where p.company_id = policy_extraction_locks.company_id
        and (p.id = auth.uid()::text or p.role = 'ADMIN')
    )
  );

-- ---------------------------------------------------------------------------
-- Answer audits (full traceability for assistant answers)
-- ---------------------------------------------------------------------------
create table if not exists public.policy_assistant_answer_audits (
  id uuid primary key default gen_random_uuid(),
  company_id text not null,
  case_id uuid,
  asked_by_user_id text not null,
  question_session_id text,
  policy_document_id uuid references public.policy_documents(id) on delete set null,
  snapshot_id uuid references public.policy_knowledge_snapshots(id) on delete set null,
  extraction_run_id uuid references public.policy_processing_runs(id) on delete set null,
  question_text text not null,
  normalized_question_topic text,
  answer_text text not null,
  evidence_status text not null
    check (
      evidence_status in (
        'direct_fact_match',
        'chunk_supported_only',
        'ambiguous',
        'insufficient_case_data',
        'insufficient_policy_evidence',
        'out_of_scope'
      )
    ),
  fact_ids_json jsonb not null default '[]'::jsonb,
  chunk_ids_json jsonb not null default '[]'::jsonb,
  applicability_decision_json jsonb not null default '{}'::jsonb,
  ambiguity_flags_json jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_policy_assistant_answer_audits_company
  on public.policy_assistant_answer_audits(company_id, created_at desc);
create index if not exists idx_policy_assistant_answer_audits_case
  on public.policy_assistant_answer_audits(case_id);
create index if not exists idx_policy_assistant_answer_audits_snapshot
  on public.policy_assistant_answer_audits(snapshot_id);
create index if not exists idx_policy_assistant_answer_audits_evidence
  on public.policy_assistant_answer_audits(evidence_status);

alter table public.policy_assistant_answer_audits enable row level security;

drop policy if exists policy_assistant_answer_audits_hr on public.policy_assistant_answer_audits;
create policy policy_assistant_answer_audits_hr on public.policy_assistant_answer_audits
  for all to authenticated
  using (
    exists (
      select 1 from public.profiles p
      where p.company_id = policy_assistant_answer_audits.company_id
        and (p.id = auth.uid()::text or p.role = 'ADMIN')
    )
  )
  with check (
    exists (
      select 1 from public.profiles p
      where p.company_id = policy_assistant_answer_audits.company_id
        and (p.id = auth.uid()::text or p.role = 'ADMIN')
    )
  );

commit;
