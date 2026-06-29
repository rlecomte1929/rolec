-- AIQ-1091 (P4-02): requirement_fact_candidates — LLM-extracted requirement facts pending admin review.
-- ─────────────────────────────────────────────────────────────────────────────
-- The P4 fact-extraction pipeline (P4-01 extractor → this endpoint → P4-03 review UI) produces
-- corridor-based facts with a FLOAT confidence_score. The pre-existing public.requirement_facts
-- (20260228025000_structured_requirements.sql) is a DIFFERENT, incompatible system: SG/US-only,
-- entity_id/source_doc_id NOT-NULL FKs, TEXT confidence — so P4 gets its own table here.
-- ─────────────────────────────────────────────────────────────────────────────

create table if not exists public.requirement_fact_candidates (
  id                uuid        primary key default gen_random_uuid(),
  created_at        timestamptz not null default now(),

  source_url        text        not null,
  corridor          text,                       -- e.g. 'IN-DE'; optional context
  requirement_type  text        not null
                      check (requirement_type in ('document','fee','timeline','eligibility','other')),
  fact_text         text        not null,
  confidence_score  numeric     not null check (confidence_score > 0 and confidence_score <= 1),
  source_quote      text,
  extraction_method text        not null default 'llm',

  -- Review lifecycle (P4-03 acts on these)
  status            text        not null default 'pending'
                      check (status in ('pending','approved','rejected')),
  reviewed_by       text,
  reviewed_at       timestamptz
);

create index if not exists idx_requirement_fact_candidates_status     on public.requirement_fact_candidates (status);
create index if not exists idx_requirement_fact_candidates_corridor   on public.requirement_fact_candidates (corridor);
create index if not exists idx_requirement_fact_candidates_created_at on public.requirement_fact_candidates (created_at desc);

-- ── Row Level Security (hard gate: ENABLE + policy + REVOKE anon) ─────────────
alter table public.requirement_fact_candidates enable row level security;

-- Service role full access (backend writes go through this connection).
drop policy if exists "service_role_all_requirement_fact_candidates" on public.requirement_fact_candidates;
create policy "service_role_all_requirement_fact_candidates"
  on public.requirement_fact_candidates for all
  using (auth.role() = 'service_role');

-- Admin-only read (the review surface is admin-internal).
drop policy if exists "admin_read_requirement_fact_candidates" on public.requirement_fact_candidates;
create policy "admin_read_requirement_fact_candidates"
  on public.requirement_fact_candidates for select
  using (auth.role() = 'authenticated' and public.is_admin());

revoke all on public.requirement_fact_candidates from anon;

comment on table public.requirement_fact_candidates is
  'AIQ-1091 (P4-02): LLM-extracted requirement facts (P4-01 extractor) pending admin review (P4-03). Distinct from the SG/US entity-based requirement_facts.';
