-- Phase 1 Step 3: case_evidence as first-class evidence primitive.
-- Minimal, production-safe. No migration of legacy employee_answers or compliance_reports.

begin;

-- =============================================================================
-- 1. Create case_evidence table
-- =============================================================================
create table if not exists public.case_evidence (
  id uuid primary key default gen_random_uuid(),
  case_id text not null references public.wizard_cases(id) on delete cascade,
  assignment_id text null references public.case_assignments(id) on delete set null,
  participant_id text null,
  requirement_id text null,
  evidence_type text not null,
  file_url text null,
  metadata jsonb not null default '{}',
  status text not null default 'submitted' check (status in ('submitted','verified','rejected')),
  submitted_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create index if not exists idx_case_evidence_case_id on public.case_evidence (case_id);
create index if not exists idx_case_evidence_assignment_id on public.case_evidence (assignment_id);
create index if not exists idx_case_evidence_participant_id on public.case_evidence (participant_id);
create index if not exists idx_case_evidence_requirement_id on public.case_evidence (requirement_id);

comment on table public.case_evidence is 'Phase 1 evidence primitive. Stores submitted evidence items per case/assignment.';

commit;
