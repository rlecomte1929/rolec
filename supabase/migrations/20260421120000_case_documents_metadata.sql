-- Optional provenance / storage hints for graph documents (single-type sync from case_evidence)

begin;

alter table public.case_documents
  add column if not exists metadata jsonb not null default '{}'::jsonb;

comment on column public.case_documents.metadata is
  'e.g. case_evidence_id, file_url; does not replace case_evidence as source of truth.';

-- At most one passport graph row per mobility case (idempotent sync target)
create unique index if not exists case_documents_one_passport_copy_per_case
  on public.case_documents (case_id)
  where document_key = 'passport_copy';

commit;
