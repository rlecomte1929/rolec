-- HR Policy Engine verification queries
-- Run these against production Supabase after migrations and end-to-end flow.

-- A. Upload: confirm policy_documents row created
SELECT id, company_id, filename, processing_status, uploaded_at
FROM public.policy_documents
ORDER BY uploaded_at DESC
LIMIT 5;

-- B. Clause segmentation: confirm policy_document_clauses rows created
SELECT pd.id as doc_id, pd.filename, COUNT(pdc.id) as clause_count
FROM public.policy_documents pd
LEFT JOIN public.policy_document_clauses pdc ON pdc.policy_document_id = pd.id
GROUP BY pd.id, pd.filename
ORDER BY pd.uploaded_at DESC
LIMIT 5;

-- C. Normalize: confirm policy_versions + policy_benefit_rules rows created
SELECT pv.id, pv.policy_id, pv.version_number, pv.status,
       (SELECT COUNT(*) FROM public.policy_benefit_rules pbr WHERE pbr.policy_version_id = pv.id) as benefit_count
FROM public.policy_versions pv
ORDER BY pv.created_at DESC
LIMIT 5;

-- D. Publish: confirm one policy_version is published
SELECT id, policy_id, version_number, status, updated_at
FROM public.policy_versions
WHERE status = 'published'
ORDER BY updated_at DESC
LIMIT 5;

-- E. Resolve: confirm resolved_assignment_policies and resolved_assignment_policy_benefits
SELECT rap.id, rap.assignment_id, rap.policy_version_id, rap.resolution_status, rap.resolved_at,
       (SELECT COUNT(*) FROM public.resolved_assignment_policy_benefits rapb WHERE rapb.resolved_policy_id = rap.id) as benefit_count
FROM public.resolved_assignment_policies rap
ORDER BY rap.resolved_at DESC
LIMIT 5;

-- F. Table existence check (all policy engine tables)
SELECT tablename FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN (
    'policy_documents', 'policy_document_clauses',
    'policy_versions', 'policy_benefit_rules', 'policy_rule_conditions',
    'policy_exclusions', 'policy_evidence_requirements', 'policy_source_links',
    'resolved_assignment_policies', 'resolved_assignment_policy_benefits',
    'resolved_assignment_policy_exclusions', 'company_policies'
  )
ORDER BY tablename;
