-- Parker Step E — RLHF-lite: human feedback table from Notion Human Review
-- ─────────────────────────────────────────────────────────────────────────────
-- Closes the loop between the Notion Human Review queue and model quality.
-- When a reviewer approves / rejects / edits an AI output, the verdict is POSTed
-- to /api/ai/feedback and stored here, attributed to the prompt-registry version
-- and canary arm (Step D) that served the original request.
--
-- preference_dataset_builder turns these verdicts into DPO-style {prompt, chosen,
-- rejected} pairs and per-version win rates (Wilson 95% CI).
--
-- Attribution columns:
--   * prompt_version_id → public.prompt_versions.id (Step D). REAL FK, enforced.
--   * trace_session_id  → policy_assistant_traces.id. That trace table is a LEGACY
--     bootstrap table created in backend/database.py with a TEXT primary key (not a
--     Supabase migration, possibly absent on a fresh DB before the backend boots),
--     so this is a typed logical reference (indexed text), NOT a hard FK.
--   * reviewer_user_id is the legacy users.id (a string from the session token), so
--     it is text, not uuid.
--
-- RLS (CLAUDE.md hard gate): human verdicts are review metadata →
-- SELECT gated to admins via public.is_admin(), writes restricted to service_role
-- (the backend), service_role ALL, REVOKE ALL FROM anon (defense in depth).
-- ─────────────────────────────────────────────────────────────────────────────

begin;

create table if not exists public.ai_human_feedback (
  id                 uuid        primary key default gen_random_uuid(),
  trace_session_id   text        not null,
  reviewer_user_id   text        not null,
  verdict            text        not null
                       check (verdict in ('approved', 'rejected', 'edited')),
  edited_output_json jsonb,
  comment            text,
  prompt_version_id  uuid        references public.prompt_versions (id),
  canary_arm         text,
  created_at         timestamptz not null default now(),
  -- Idempotency: one verdict per (trace, reviewer); re-POST upserts.
  unique (trace_session_id, reviewer_user_id)
);

-- Win-rate aggregation reads per (version, verdict).
create index if not exists idx_ai_human_feedback_version_verdict
  on public.ai_human_feedback (prompt_version_id, verdict);

-- Logical link back to the trace (no hard FK — see header).
create index if not exists idx_ai_human_feedback_trace
  on public.ai_human_feedback (trace_session_id);

-- ── RLS ───────────────────────────────────────────────────────────────────────
alter table public.ai_human_feedback enable row level security;

-- Admins read all verdicts (review dashboard / win rates).
drop policy if exists ai_human_feedback_admin_select on public.ai_human_feedback;
create policy ai_human_feedback_admin_select on public.ai_human_feedback
  for select to authenticated using (public.is_admin());

-- Only the backend (service_role) writes — the Notion skill posts through the API.
drop policy if exists ai_human_feedback_service_all on public.ai_human_feedback;
create policy ai_human_feedback_service_all on public.ai_human_feedback
  for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');

-- Grants PostgREST needs (RLS still gates rows). No anon access at all.
grant select on public.ai_human_feedback to authenticated;

revoke all on public.ai_human_feedback from anon;

comment on table public.ai_human_feedback is
  'Parker Step E: human review verdicts (approved/rejected/edited) from Notion, attributed to a prompt-registry version/arm. Source for DPO pairs + win rates.';
comment on column public.ai_human_feedback.trace_session_id is
  'Logical ref to policy_assistant_traces.id (legacy text PK; no hard FK).';
comment on column public.ai_human_feedback.edited_output_json is
  'The reviewer-edited output when verdict=edited; becomes the chosen side of a DPO pair.';

commit;

-- ── Rollback (manual) ─────────────────────────────────────────────────────────
-- drop table if exists public.ai_human_feedback;
