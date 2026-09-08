-- Persist rich normalization draft (metadata, clause/rule candidates, readiness) alongside Layer-2 rows.
-- See backend/services/policy_normalization_draft.py

begin;

alter table public.policy_versions
  add column if not exists normalization_draft_json jsonb;

comment on column public.policy_versions.normalization_draft_json is
  'Version-scoped normalized draft: document metadata, clause candidates, rule candidates, readiness snapshots (HR/diagnostics; not employee consumption).';

commit;
