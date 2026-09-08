-- Speed published-version lookup per company policy and filter by status (employee resolution + HR publish).
create index if not exists idx_policy_versions_policy_id_status
  on public.policy_versions (policy_id, status);

-- Typical document listing: policies by company, newest first.
create index if not exists idx_policy_documents_company_uploaded
  on public.policy_documents (company_id, uploaded_at desc);
