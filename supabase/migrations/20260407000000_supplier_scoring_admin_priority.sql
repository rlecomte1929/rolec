-- Admin ranking controls for supplier recommendations
begin;

alter table public.supplier_scoring_metadata
  add column if not exists admin_score numeric null,
  add column if not exists manual_priority int null;

comment on column public.supplier_scoring_metadata.admin_score is '0-100 score boost for ranking (admin-tunable)';
comment on column public.supplier_scoring_metadata.manual_priority is 'Relative priority (higher = rank higher in recommendations)';

commit;
