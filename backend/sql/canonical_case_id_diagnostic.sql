-- Phase 1 Step 4: canonical_case_id diagnostic report
-- Run after migration 20260324000000. Requires all Step 4 tables to exist.

SELECT
  t.tbl,
  t.total,
  t.populated,
  t.null_count,
  round(100.0 * t.populated / nullif(t.total, 0), 2) AS pct_populated
FROM (
  SELECT 'case_assignments' AS tbl,
    (SELECT COUNT(*) FROM public.case_assignments) AS total,
    (SELECT COUNT(*) FROM public.case_assignments WHERE canonical_case_id IS NOT NULL) AS populated,
    (SELECT COUNT(*) FROM public.case_assignments WHERE canonical_case_id IS NULL) AS null_count
  UNION ALL SELECT 'case_events',
    (SELECT COUNT(*) FROM public.case_events),
    (SELECT COUNT(*) FROM public.case_events WHERE canonical_case_id IS NOT NULL),
    (SELECT COUNT(*) FROM public.case_events WHERE canonical_case_id IS NULL)
  UNION ALL SELECT 'case_participants',
    (SELECT COUNT(*) FROM public.case_participants),
    (SELECT COUNT(*) FROM public.case_participants WHERE canonical_case_id IS NOT NULL),
    (SELECT COUNT(*) FROM public.case_participants WHERE canonical_case_id IS NULL)
  UNION ALL SELECT 'case_evidence',
    (SELECT COUNT(*) FROM public.case_evidence),
    (SELECT COUNT(*) FROM public.case_evidence WHERE canonical_case_id IS NOT NULL),
    (SELECT COUNT(*) FROM public.case_evidence WHERE canonical_case_id IS NULL)
  UNION ALL SELECT 'case_requirements_snapshots',
    (SELECT COUNT(*) FROM public.case_requirements_snapshots),
    (SELECT COUNT(*) FROM public.case_requirements_snapshots WHERE canonical_case_id IS NOT NULL),
    (SELECT COUNT(*) FROM public.case_requirements_snapshots WHERE canonical_case_id IS NULL)
  UNION ALL SELECT 'case_feedback',
    (SELECT COUNT(*) FROM public.case_feedback),
    (SELECT COUNT(*) FROM public.case_feedback WHERE canonical_case_id IS NOT NULL),
    (SELECT COUNT(*) FROM public.case_feedback WHERE canonical_case_id IS NULL)
  UNION ALL SELECT 'case_services',
    (SELECT COUNT(*) FROM public.case_services),
    (SELECT COUNT(*) FROM public.case_services WHERE canonical_case_id IS NOT NULL),
    (SELECT COUNT(*) FROM public.case_services WHERE canonical_case_id IS NULL)
  UNION ALL SELECT 'case_service_answers',
    (SELECT COUNT(*) FROM public.case_service_answers),
    (SELECT COUNT(*) FROM public.case_service_answers WHERE canonical_case_id IS NOT NULL),
    (SELECT COUNT(*) FROM public.case_service_answers WHERE canonical_case_id IS NULL)
  UNION ALL SELECT 'case_resource_preferences',
    (SELECT COUNT(*) FROM public.case_resource_preferences),
    (SELECT COUNT(*) FROM public.case_resource_preferences WHERE canonical_case_id IS NOT NULL),
    (SELECT COUNT(*) FROM public.case_resource_preferences WHERE canonical_case_id IS NULL)
  UNION ALL SELECT 'rfqs',
    (SELECT COUNT(*) FROM public.rfqs),
    (SELECT COUNT(*) FROM public.rfqs WHERE canonical_case_id IS NOT NULL),
    (SELECT COUNT(*) FROM public.rfqs WHERE canonical_case_id IS NULL)
  UNION ALL SELECT 'dossier_answers',
    (SELECT COUNT(*) FROM public.dossier_answers),
    (SELECT COUNT(*) FROM public.dossier_answers WHERE canonical_case_id IS NOT NULL),
    (SELECT COUNT(*) FROM public.dossier_answers WHERE canonical_case_id IS NULL)
  UNION ALL SELECT 'dossier_case_questions',
    (SELECT COUNT(*) FROM public.dossier_case_questions),
    (SELECT COUNT(*) FROM public.dossier_case_questions WHERE canonical_case_id IS NOT NULL),
    (SELECT COUNT(*) FROM public.dossier_case_questions WHERE canonical_case_id IS NULL)
  UNION ALL SELECT 'dossier_case_answers',
    (SELECT COUNT(*) FROM public.dossier_case_answers),
    (SELECT COUNT(*) FROM public.dossier_case_answers WHERE canonical_case_id IS NOT NULL),
    (SELECT COUNT(*) FROM public.dossier_case_answers WHERE canonical_case_id IS NULL)
  UNION ALL SELECT 'dossier_source_suggestions',
    (SELECT COUNT(*) FROM public.dossier_source_suggestions),
    (SELECT COUNT(*) FROM public.dossier_source_suggestions WHERE canonical_case_id IS NOT NULL),
    (SELECT COUNT(*) FROM public.dossier_source_suggestions WHERE canonical_case_id IS NULL)
  UNION ALL SELECT 'relocation_guidance_packs',
    (SELECT COUNT(*) FROM public.relocation_guidance_packs),
    (SELECT COUNT(*) FROM public.relocation_guidance_packs WHERE canonical_case_id IS NOT NULL),
    (SELECT COUNT(*) FROM public.relocation_guidance_packs WHERE canonical_case_id IS NULL)
  UNION ALL SELECT 'relocation_trace_events',
    (SELECT COUNT(*) FROM public.relocation_trace_events),
    (SELECT COUNT(*) FROM public.relocation_trace_events WHERE canonical_case_id IS NOT NULL),
    (SELECT COUNT(*) FROM public.relocation_trace_events WHERE canonical_case_id IS NULL)
) t
ORDER BY t.tbl;
