-- AIQ-684 / P1-07a: case_outcomes — anonymized flywheel outcome store.
--
-- Anonymization is enforced BY CONSTRUCTION: the table has no PII columns
-- (no name, email, DOB, employer, address, or user_id). The only link back to
-- a case is case_ref_hash (a SHA-256 of the real case id), mirroring the
-- assignment_outcomes.rated_by precedent. A BEFORE-trigger additionally rejects
-- any free-text column that smuggles an email-shaped value.
--
-- Schema follows the parent P1-07 (AIQ-201) spec so it carries every field the
-- processing-time model (P2-04) and confidence calibration (P1-04) consume.
-- Service-role-only RLS (CLAUDE.md 3 hard-gates). Written by the P1-07d ingest
-- endpoint; no anon/authenticated access.

begin;

create table if not exists public.case_outcomes (
  id                            uuid        primary key default gen_random_uuid(),
  created_at                    timestamptz not null default now(),
  updated_at                    timestamptz not null default now(),

  -- Anonymized link to the originating case (SHA-256 hex of the real case id).
  -- One outcome row per case.
  case_ref_hash                 text        not null unique
                                  check (case_ref_hash ~ '^[0-9a-f]{64}$'),

  -- Categorical, non-PII descriptors
  pathway_type                  text,
  origin_country_code           text        check (origin_country_code is null or origin_country_code ~ '^[A-Z]{2}$'),
  dest_country_code             text        check (dest_country_code   is null or dest_country_code   ~ '^[A-Z]{2}$'),

  -- Terminal outcome of the case
  outcome                       text        not null
                                  check (outcome in ('APPROVED','REJECTED','WITHDRAWN','PENDING')),

  -- Quantitative signal for the flywheel
  processing_time_days_actual   integer     check (processing_time_days_actual is null or processing_time_days_actual >= 0),
  rejection_reason_code         text,
  specialist_corrections_count  integer     not null default 0
                                  check (specialist_corrections_count >= 0),

  submitted_at                  timestamptz,
  decided_at                    timestamptz,

  -- A rejection reason is only meaningful when the outcome is REJECTED.
  constraint case_outcomes_rejection_reason_only_when_rejected
    check (rejection_reason_code is null or outcome = 'REJECTED'),

  -- Decisions cannot precede submission.
  constraint case_outcomes_decided_after_submitted
    check (decided_at is null or submitted_at is null or decided_at >= submitted_at)
);

create index if not exists idx_case_outcomes_corridor_outcome
  on public.case_outcomes (origin_country_code, dest_country_code, outcome);
create index if not exists idx_case_outcomes_created_at
  on public.case_outcomes (created_at desc);

-- ── Anonymization guard: reject email-shaped values in free-text columns ──
create or replace function public.case_outcomes_reject_pii()
returns trigger
language plpgsql
as $$
begin
  if coalesce(new.pathway_type, '') ~ '@'
     or coalesce(new.rejection_reason_code, '') ~ '@' then
    raise exception 'case_outcomes: PII-shaped value rejected (email pattern in a code column)';
  end if;
  new.updated_at := now();
  return new;
end;
$$;

drop trigger if exists trg_case_outcomes_guard on public.case_outcomes;
create trigger trg_case_outcomes_guard
  before insert or update on public.case_outcomes
  for each row execute function public.case_outcomes_reject_pii();

-- ── RLS hard-gates (CLAUDE.md): service-role-only ──
alter table public.case_outcomes enable row level security;

drop policy if exists case_outcomes_service_all on public.case_outcomes;
create policy case_outcomes_service_all
  on public.case_outcomes
  for all to service_role
  using (true) with check (true);

revoke all on public.case_outcomes from anon;
revoke all on public.case_outcomes from authenticated;
grant select, insert, update, delete on public.case_outcomes to service_role;

comment on table public.case_outcomes is
  'AIQ-684/P1-07a anonymized case outcome flywheel store. No PII by construction; case_ref_hash = SHA-256 of the real case id. Service-role-only. Written by the P1-07d ingest endpoint.';

commit;
