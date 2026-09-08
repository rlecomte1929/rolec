-- Extend policy_versions status for HR review workflow: draft, review_required, reviewed, published
-- Runs AFTER 20260331000000_policy_normalization.sql which creates policy_versions.
begin;

alter table public.policy_versions drop constraint if exists policy_versions_status_check;
alter table public.policy_versions add constraint policy_versions_status_check check (
  status in (
    'draft', 'auto_generated', 'in_review', 'approved', 'archived',
    'review_required', 'reviewed', 'published'
  )
);

commit;
