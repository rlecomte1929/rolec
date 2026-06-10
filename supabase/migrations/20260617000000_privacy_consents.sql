-- PRIV-005 / AIQ-473 — privacy_consents: Art. 13 notice acknowledgement log.
--
-- Records one append-only row each time a data subject acknowledges the
-- privacy notice at a point of collection (onboarding, task submission).
-- Distinct from public.consent_records (which logs per-purpose lawful-basis
-- consent for an immigration case) — this table is the GDPR Art. 13
-- *transparency notice* acknowledgement, keyed by notice_version so a
-- material copy change triggers re-acknowledgement.
--
-- Column conventions mirror consent_records: TEXT ids (the hybrid auth model
-- yields legacy text caller ids like 'seed-emp-testingapril' as well as
-- UUIDs — never FK to auth.users/profiles here or legacy ids 500 on a uuid
-- cast), append-only (no updated_at).

begin;

create table if not exists public.privacy_consents (
  id              text PRIMARY KEY DEFAULT gen_random_uuid()::text,
  user_id         text NOT NULL,            -- caller id (legacy text or uuid)
  notice_version  text NOT NULL,            -- e.g. '2026-06-03-v1.0'
  acknowledged_at timestamptz NOT NULL DEFAULT now(),
  context         text,                     -- 'onboarding' | 'task_submission'
  ip_address      text,                     -- optional, fraud/impersonation diagnostics
  user_agent      text,                     -- same
  created_at      timestamptz NOT NULL DEFAULT now()
  -- NO updated_at — this table is append-only
);

create index if not exists idx_privacy_consents_user
  on public.privacy_consents (user_id, created_at DESC);

create index if not exists idx_privacy_consents_version
  on public.privacy_consents (notice_version);

-- Security hard-gate (root CLAUDE.md): every new public table must enable RLS,
-- have >=1 policy, and revoke anon. Acknowledgements are written by the backend
-- via the service engine (service_role bypasses RLS). For the anon-key-exposed
-- PostgREST surface, a subject may read only their own rows; the anon role gets
-- nothing.
alter table public.privacy_consents enable row level security;

drop policy if exists privacy_consents_subject_self on public.privacy_consents;
create policy privacy_consents_subject_self
  on public.privacy_consents
  for select
  to authenticated
  using (user_id = auth.uid()::text);

revoke all on public.privacy_consents from anon;

commit;
