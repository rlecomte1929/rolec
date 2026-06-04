-- AIQ-756 backfill — public.specialist_review_calibration (view)
-- Prod-applied out-of-band (schema_migrations version 20260604072026, name
-- "specialist_review_calibration_view") with no definition in the repo.
-- Definition is prod-as-oracle (pg_get_viewdef, 2026-06-04). CREATE OR REPLACE
-- is idempotent. Parent tables specialist_review_events + roadmap_review_status
-- are created by 20260601010000_specialist_review_events.sql, before this version.

begin;

create or replace view public.specialist_review_calibration as
  select
    sre.id        as review_event_id,
    sre.case_id,
    sre.step_id,
    sre.reviewer_id,
    sre.reviewed_at,
    sre.action::text      as specialist_outcome,
    sre.reason_code::text as reason_code,
    upper(nullif(coalesce(
      sre.original_step_json::jsonb #>> '{confidence,overall}'::text[],
      sre.original_step_json::jsonb #>> '{confidence_level}'::text[],
      sre.original_step_json::jsonb #>> '{confidence}'::text[]), ''::text)) as confidence_at_time,
    nullif(coalesce(
      sre.original_step_json::jsonb #>> '{confidence,score}'::text[],
      sre.original_step_json::jsonb #>> '{confidence_score}'::text[]), ''::text)::numeric as confidence_score_at_time,
    sre.edited_step_json is not null as was_edited,
    rrs.released_to_user        as roadmap_released,
    rrs.regeneration_requested  as roadmap_regen_requested
  from public.specialist_review_events sre
    left join public.roadmap_review_status rrs on rrs.case_id::text = sre.case_id::text;

revoke all on public.specialist_review_calibration from anon;

commit;
