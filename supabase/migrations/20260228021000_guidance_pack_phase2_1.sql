-- Guidance Pack Phase 2.1: baseline rules + coverage

begin;

alter table public.knowledge_rules
  add column if not exists is_baseline boolean not null default false;

alter table public.relocation_guidance_packs
  add column if not exists coverage jsonb not null default '{}'::jsonb;

-- Seed: add baseline flags + more curated docs/rules if missing.
-- Keep additive, conservative, and official sources only.

-- Add extra docs for SG/US if not present
insert into public.knowledge_docs (pack_id, title, publisher, source_url, text_content)
select p.id, 'IRAS Individual Income Tax Basics', 'Singapore Government', 'https://www.iras.gov.sg', 'Official guidance summary placeholder (curated).'
from public.knowledge_packs p
where p.destination_country = 'SG' and p.domain = 'registration'
on conflict do nothing;

insert into public.knowledge_docs (pack_id, title, publisher, source_url, text_content)
select p.id, 'SSA – Social Security Number Overview', 'US Government', 'https://www.ssa.gov/ssnumber/', 'Official guidance summary placeholder (curated).'
from public.knowledge_packs p
where p.destination_country = 'US' and p.domain = 'registration'
on conflict do nothing;

-- Baseline rules (SG)
insert into public.knowledge_rules
  (pack_id, rule_key, applies_if, title, phase, category, guidance_md, citations, is_baseline)
select p.id, 'sg_baseline_pre_move_immigration', null,
  'Confirm immigration pathway with employer and review MOM overview',
  'pre_move', 'immigration',
  'Review the official MOM overview and confirm with your employer which pass type applies. Prepare documents and timelines before submission.',
  jsonb_build_array(d.id), true
from public.knowledge_packs p
join public.knowledge_docs d on d.pack_id = p.id
where p.destination_country = 'SG' and p.domain = 'immigration'
on conflict do nothing;

insert into public.knowledge_rules
  (pack_id, rule_key, applies_if, title, phase, category, guidance_md, citations, is_baseline)
select p.id, 'sg_baseline_arrival_registration', null,
  'Review ICA entry and arrival requirements',
  'arrival', 'registration',
  'Confirm entry/arrival requirements with ICA and complete any required arrival steps promptly.',
  jsonb_build_array(d.id), true
from public.knowledge_packs p
join public.knowledge_docs d on d.pack_id = p.id
where p.destination_country = 'SG' and p.domain = 'registration'
on conflict do nothing;

insert into public.knowledge_rules
  (pack_id, rule_key, applies_if, title, phase, category, guidance_md, citations, is_baseline)
select p.id, 'sg_baseline_first90_records', null,
  'Keep employment and housing records organized',
  'first_90_days', 'other',
  'Maintain copies of key documents (pass approval, employment letter, lease) for ongoing compliance and renewals.',
  jsonb_build_array(d.id), true
from public.knowledge_packs p
join public.knowledge_docs d on d.pack_id = p.id
where p.destination_country = 'SG' and p.domain in ('immigration','registration')
on conflict do nothing;

insert into public.knowledge_rules
  (pack_id, rule_key, applies_if, title, phase, category, guidance_md, citations, is_baseline)
select p.id, 'sg_baseline_first_tax_year', null,
  'Confirm tax residency and payroll coordination',
  'first_tax_year', 'tax',
  'Confirm payroll setup and any tax residency considerations with official guidance and your employer.',
  jsonb_build_array(d.id), true
from public.knowledge_packs p
join public.knowledge_docs d on d.pack_id = p.id
where p.destination_country = 'SG' and p.domain = 'registration'
on conflict do nothing;

-- Baseline rules (US)
insert into public.knowledge_rules
  (pack_id, rule_key, applies_if, title, phase, category, guidance_md, citations, is_baseline)
select p.id, 'us_baseline_pre_move_immigration', null,
  'Confirm visa category with employer and review USCIS overview',
  'pre_move', 'immigration',
  'Review USCIS guidance with your employer and confirm the intended visa category and required documents.',
  jsonb_build_array(d.id), true
from public.knowledge_packs p
join public.knowledge_docs d on d.pack_id = p.id
where p.destination_country = 'US' and p.domain = 'immigration'
on conflict do nothing;

insert into public.knowledge_rules
  (pack_id, rule_key, applies_if, title, phase, category, guidance_md, citations, is_baseline)
select p.id, 'us_baseline_arrival_entry', null,
  'Review entry and arrival requirements with State Department',
  'arrival', 'registration',
  'Confirm entry requirements and keep copies of key travel and visa documents available on arrival.',
  jsonb_build_array(d.id), true
from public.knowledge_packs p
join public.knowledge_docs d on d.pack_id = p.id
where p.destination_country = 'US' and p.domain = 'registration'
on conflict do nothing;

insert into public.knowledge_rules
  (pack_id, rule_key, applies_if, title, phase, category, guidance_md, citations, is_baseline)
select p.id, 'us_baseline_first90_records', null,
  'Organize employment and housing documentation',
  'first_90_days', 'other',
  'Keep employment documents and housing records organized for onboarding and future renewals.',
  jsonb_build_array(d.id), true
from public.knowledge_packs p
join public.knowledge_docs d on d.pack_id = p.id
where p.destination_country = 'US' and p.domain in ('immigration','registration')
on conflict do nothing;

insert into public.knowledge_rules
  (pack_id, rule_key, applies_if, title, phase, category, guidance_md, citations, is_baseline)
select p.id, 'us_baseline_first_tax_year', null,
  'Plan for first tax year record-keeping',
  'first_tax_year', 'tax',
  'Coordinate with your employer on payroll setup and keep records for the first tax year.',
  jsonb_build_array(d.id), true
from public.knowledge_packs p
join public.knowledge_docs d on d.pack_id = p.id
where p.destination_country = 'US' and p.domain = 'registration'
on conflict do nothing;

commit;
