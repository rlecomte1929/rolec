-- Run in Supabase SQL Editor after deploying policy engine migrations.
-- Verifies all policy tables exist and are usable.

-- 1. Table existence
SELECT tablename
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN (
    'policy_documents',
    'policy_document_clauses',
    'policy_versions',
    'policy_benefit_rules',
    'policy_rule_conditions',
    'policy_exclusions',
    'policy_evidence_requirements',
    'policy_assignment_type_applicability',
    'policy_family_status_applicability',
    'policy_tier_overrides',
    'policy_source_links',
    'resolved_assignment_policies',
    'resolved_assignment_policy_benefits',
    'resolved_assignment_policy_exclusions',
    'assignment_policy_service_comparisons',
    'company_policies'
  )
ORDER BY tablename;

-- Expected: 16 rows

-- 2. policy_versions status constraint (must include 'published')
SELECT conname, pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE conrelid = 'public.policy_versions'::regclass
  AND conname = 'policy_versions_status_check';

-- 3. Row counts (should be 0 initially)
SELECT 'policy_documents' AS tbl, COUNT(*) AS n FROM public.policy_documents
UNION ALL SELECT 'policy_document_clauses', COUNT(*) FROM public.policy_document_clauses
UNION ALL SELECT 'policy_versions', COUNT(*) FROM public.policy_versions
UNION ALL SELECT 'policy_benefit_rules', COUNT(*) FROM public.policy_benefit_rules
UNION ALL SELECT 'resolved_assignment_policies', COUNT(*) FROM public.resolved_assignment_policies;
