-- Policy Assistant RAG (Sprint A): per-company indexed chunks of the
-- loaded policy. Each row is a small piece of human-readable policy text
-- (one benefit row, one Section C override, one extracted fact, etc.)
-- with an embedding for nearest-neighbor retrieval.
--
-- Why a separate table from the matrix benefit row: chunks are the unit
-- the LLM sees. A single benefit row may produce 1+ chunks (the row
-- itself + each Section C override is its own chunk so retrieval can
-- surface "for Singapore directors" without dragging the rest of the
-- benefit). Chunks rebuild on publish; the matrix is the source of truth.
--
-- pgvector: required. Supabase has it available; enable on first apply.
-- The indexer (services/policy_chunk_indexer.py) handles both Postgres
-- with pgvector and SQLite (dev) which falls back to JSON-encoded TEXT
-- + in-Python cosine similarity.

begin;

-- Enable pgvector. Idempotent; no-op if already enabled.
create extension if not exists vector;

create table if not exists public.policy_assistant_chunks (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null,
  -- Optional: when chunk is matrix-derived, this is the published
  -- policy_config_versions.id it came from. NULL for chunks derived
  -- from canonical document extraction (which has its own versioning
  -- in canonical_policy_documents).
  policy_version_id uuid,
  source_type text not null check (source_type in (
    'matrix_benefit',
    'matrix_override',
    'canonical_doc',
    'exclusion',
    'evidence_rule'
  )),
  -- Stable reference back to the source row (e.g.
  -- 'policy_config_benefits.<uuid>' or 'override.<uuid>'). Used by the
  -- frontend to render clickable citation chips that open the
  -- underlying row.
  source_ref text not null,
  chunk_text text not null,
  -- Searchable structured metadata: benefit_key, category, jurisdiction
  -- countries, employee_level, assignment_type. Used for keyword boost
  -- in retrieval and for filtering.
  chunk_metadata jsonb not null default '{}',
  embedding vector(1536),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (company_id, source_type, source_ref)
);

-- Hot path: retrieval filters by company_id then orders by embedding
-- distance. The (company_id, source_type) composite index covers the
-- typical query; pgvector's IVFFlat handles the nearest-neighbor part.
create index if not exists idx_pac_company on public.policy_assistant_chunks (company_id);
create index if not exists idx_pac_company_type
  on public.policy_assistant_chunks (company_id, source_type);

-- IVFFlat with 100 lists is the supabase-recommended default for tables
-- in the 1k-100k-row range. Tune later if any single company crosses
-- 50k chunks (unlikely; expect <500/company).
create index if not exists idx_pac_embedding
  on public.policy_assistant_chunks
  using ivfflat (embedding vector_cosine_ops) with (lists = 100);

comment on table public.policy_assistant_chunks is
  'Policy Assistant RAG chunks (Sprint A). Per-company indexed pieces of the loaded HR policy. Rebuilt on publish_draft. See services/policy_chunk_indexer.py and services/policy_chunk_retriever.py.';

-- updated_at trigger.
create or replace function public.policy_assistant_chunks_set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

drop trigger if exists trg_pac_set_updated_at on public.policy_assistant_chunks;
create trigger trg_pac_set_updated_at
  before update on public.policy_assistant_chunks
  for each row execute function public.policy_assistant_chunks_set_updated_at();

alter table public.policy_assistant_chunks enable row level security;

-- RLS: tenant-scoped read for HR/ADMIN/EMPLOYEE; backend writes only.
-- Employees can read their own company's chunks (the assistant calls on
-- their behalf); HR sees their company's chunks; ADMIN sees any.
-- Inserts/updates/deletes only via the elevated backend tier — the
-- indexer doesn't run as the user.
create policy pac_select_tenant_or_admin
  on public.policy_assistant_chunks
  for select
  to authenticated
  using (
    exists (select 1 from public.profiles where id::uuid = auth.uid() and role = 'ADMIN')
    or company_id in (select company_id::uuid from public.profiles where id::uuid = auth.uid())
  );

-- No write policies for clients; service role is bypass.

-- Audit trigger.
drop trigger if exists trg_audit_pac on public.policy_assistant_chunks;
create trigger trg_audit_pac
  after insert or update or delete on public.policy_assistant_chunks
  for each row execute function public.relopass_audit_row();

commit;
