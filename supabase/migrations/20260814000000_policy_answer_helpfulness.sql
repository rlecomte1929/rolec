-- WS-E — end-user "was this answer helpful?" capture for policy answers
-- ─────────────────────────────────────────────────────────────────────────────
-- ai_human_feedback captures INTERNAL REVIEWER verdicts (approved/rejected/edited)
-- from the Notion Human Review queue. There was no equivalent capture for the
-- END USER's reaction to a policy answer. This table records a single thumbs
-- up/down ("was this answer helpful?") per (policy answer, user).
--
-- helpfulness_dataset_builder turns these votes into eval golden-set CANDIDATES
-- (query_hash + net sentiment) for a human to curate into the real golden set —
-- mirroring how preference_dataset_builder turns ai_human_feedback into DPO pairs.
--
-- Columns:
--   * trace_session_id → policy_assistant_traces.id. That trace table is a LEGACY
--     bootstrap table created in backend/database.py with a TEXT primary key (not
--     a Supabase migration), so this is a typed logical reference (indexed text),
--     NOT a hard FK — identical to ai_human_feedback.trace_session_id.
--   * company_id is the tenant the answer belongs to (derived from the trace).
--   * user_id is the legacy users.id (a string from the session token), so it is
--     text, not uuid — it does NOT match auth.uid().
--
-- RLS (CLAUDE.md hard gate): because user_id / company_id here are LEGACY text
-- ids (not the Supabase auth uuid), an end user's session never carries an
-- auth.uid() that equals these columns, so a user-scoped USING (auth.uid() = ...)
-- policy would match nothing. We therefore copy the ai_human_feedback pattern
-- exactly: writes restricted to service_role (the backend writes through the
-- /api/policy-assistant/helpfulness endpoint), SELECT gated to admins via
-- public.is_admin(), and REVOKE ALL FROM anon (defense in depth).
-- ─────────────────────────────────────────────────────────────────────────────

begin;

create table if not exists public.policy_answer_helpfulness (
  id                 uuid        primary key default gen_random_uuid(),
  trace_session_id   text        not null,
  company_id         text,
  user_id            text        not null,
  helpful            boolean     not null,
  comment            text,
  created_at         timestamptz not null default now(),
  -- Idempotency: one vote per (answer, user); re-POST upserts.
  unique (trace_session_id, user_id)
);

-- Candidate builder reads per company and per trace.
create index if not exists idx_policy_answer_helpfulness_company
  on public.policy_answer_helpfulness (company_id);

create index if not exists idx_policy_answer_helpfulness_trace
  on public.policy_answer_helpfulness (trace_session_id);

-- ── RLS ───────────────────────────────────────────────────────────────────────
alter table public.policy_answer_helpfulness enable row level security;

-- Admins read all votes (eval-candidate curation / dashboards).
drop policy if exists policy_answer_helpfulness_admin_select on public.policy_answer_helpfulness;
create policy policy_answer_helpfulness_admin_select on public.policy_answer_helpfulness
  for select to authenticated using (public.is_admin());

-- Only the backend (service_role) writes — the end user posts through the API.
drop policy if exists policy_answer_helpfulness_service_all on public.policy_answer_helpfulness;
create policy policy_answer_helpfulness_service_all on public.policy_answer_helpfulness
  for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');

-- Grants PostgREST needs (RLS still gates rows). No anon access at all.
grant select on public.policy_answer_helpfulness to authenticated;

revoke all on public.policy_answer_helpfulness from anon;

comment on table public.policy_answer_helpfulness is
  'WS-E: end-user thumbs up/down on a policy answer, keyed to its trace. Source for eval golden-set candidates via helpfulness_dataset_builder.';
comment on column public.policy_answer_helpfulness.trace_session_id is
  'Logical ref to policy_assistant_traces.id (legacy text PK; no hard FK).';
comment on column public.policy_answer_helpfulness.user_id is
  'Legacy users.id (session-token string); not the Supabase auth uuid.';

commit;

-- ── Rollback (manual) ─────────────────────────────────────────────────────────
-- drop table if exists public.policy_answer_helpfulness;
