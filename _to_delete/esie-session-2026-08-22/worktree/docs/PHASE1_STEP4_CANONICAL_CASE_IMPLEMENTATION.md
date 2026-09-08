# Phase 1 Step 4: canonical_case_id Implementation

## Exact Files Changed

| File | Changes |
|------|---------|
| `supabase/migrations/20260324000000_canonical_case_id_phase1.sql` | New migration: add column, backfill, indexes |
| `backend/database.py` | Add canonical_case_id to INSERT in create_assignment, insert_case_event, ensure_case_participant, insert_case_evidence, upsert_case_services, upsert_case_service_answers, create_rfq; SQLite schema extensions |

---

## Migration SQL

See `supabase/migrations/20260324000000_canonical_case_id_phase1.sql`.

Summary:
- Add nullable `canonical_case_id text` to 16 tables
- Backfill: `canonical_case_id = case_id` where `case_id` exists in `wizard_cases`
- Create indexes on canonical_case_id for: case_assignments, case_events, case_participants, case_evidence, rfqs, relocation_guidance_packs

---

## Database Methods Updated

| Method | Change |
|--------|--------|
| `create_assignment` | INSERT includes `canonical_case_id = case_id` |
| `insert_case_event` | INSERT includes `canonical_case_id = case_id` |
| `ensure_case_participant` | INSERT and ON CONFLICT DO UPDATE include `canonical_case_id` |
| `insert_case_evidence` | INSERT includes `canonical_case_id = case_id` |
| `upsert_case_services` | INSERT and ON CONFLICT DO UPDATE include `canonical_case_id` |
| `upsert_case_service_answers` | INSERT and ON CONFLICT DO UPDATE include `canonical_case_id` |
| `create_rfq` | INSERT includes `canonical_case_id = case_id` |

---

## Live Write Paths Updated

| Endpoint / Flow | Database Method |
|-----------------|-----------------|
| POST /api/hr/cases/{id}/assign | create_assignment |
| assign_case (main.py) | insert_case_event, ensure_case_participant |
| claim_assignment (main.py) | ensure_case_participant, insert_case_event |
| POST /api/assignments/{id}/evidence | insert_case_evidence |
| upsert_assignment_services | upsert_case_services |
| upsert_service_answers | upsert_case_service_answers |
| create_rfq | create_rfq |

---

## Diagnostic SQL Query

```sql
-- Phase 1 Step 4: canonical_case_id diagnostic report
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
  UNION ALL
  SELECT 'case_events',
    (SELECT COUNT(*) FROM public.case_events),
    (SELECT COUNT(*) FROM public.case_events WHERE canonical_case_id IS NOT NULL),
    (SELECT COUNT(*) FROM public.case_events WHERE canonical_case_id IS NULL)
  UNION ALL
  SELECT 'case_participants',
    (SELECT COUNT(*) FROM public.case_participants),
    (SELECT COUNT(*) FROM public.case_participants WHERE canonical_case_id IS NOT NULL),
    (SELECT COUNT(*) FROM public.case_participants WHERE canonical_case_id IS NULL)
  UNION ALL
  SELECT 'case_evidence',
    (SELECT COUNT(*) FROM public.case_evidence),
    (SELECT COUNT(*) FROM public.case_evidence WHERE canonical_case_id IS NOT NULL),
    (SELECT COUNT(*) FROM public.case_evidence WHERE canonical_case_id IS NULL)
  UNION ALL
  SELECT 'case_requirements_snapshots',
    (SELECT COUNT(*) FROM public.case_requirements_snapshots),
    (SELECT COUNT(*) FROM public.case_requirements_snapshots WHERE canonical_case_id IS NOT NULL),
    (SELECT COUNT(*) FROM public.case_requirements_snapshots WHERE canonical_case_id IS NULL)
  UNION ALL
  SELECT 'case_feedback',
    (SELECT COUNT(*) FROM public.case_feedback),
    (SELECT COUNT(*) FROM public.case_feedback WHERE canonical_case_id IS NOT NULL),
    (SELECT COUNT(*) FROM public.case_feedback WHERE canonical_case_id IS NULL)
  UNION ALL
  SELECT 'case_services',
    (SELECT COUNT(*) FROM public.case_services),
    (SELECT COUNT(*) FROM public.case_services WHERE canonical_case_id IS NOT NULL),
    (SELECT COUNT(*) FROM public.case_services WHERE canonical_case_id IS NULL)
  UNION ALL
  SELECT 'case_service_answers',
    (SELECT COUNT(*) FROM public.case_service_answers),
    (SELECT COUNT(*) FROM public.case_service_answers WHERE canonical_case_id IS NOT NULL),
    (SELECT COUNT(*) FROM public.case_service_answers WHERE canonical_case_id IS NULL)
  UNION ALL
  SELECT 'case_resource_preferences',
    (SELECT COUNT(*) FROM public.case_resource_preferences),
    (SELECT COUNT(*) FROM public.case_resource_preferences WHERE canonical_case_id IS NOT NULL),
    (SELECT COUNT(*) FROM public.case_resource_preferences WHERE canonical_case_id IS NULL)
  UNION ALL
  SELECT 'rfqs',
    (SELECT COUNT(*) FROM public.rfqs),
    (SELECT COUNT(*) FROM public.rfqs WHERE canonical_case_id IS NOT NULL),
    (SELECT COUNT(*) FROM public.rfqs WHERE canonical_case_id IS NULL)
  UNION ALL
  SELECT 'dossier_answers',
    (SELECT COUNT(*) FROM public.dossier_answers),
    (SELECT COUNT(*) FROM public.dossier_answers WHERE canonical_case_id IS NOT NULL),
    (SELECT COUNT(*) FROM public.dossier_answers WHERE canonical_case_id IS NULL)
  UNION ALL
  SELECT 'dossier_case_questions',
    (SELECT COUNT(*) FROM public.dossier_case_questions),
    (SELECT COUNT(*) FROM public.dossier_case_questions WHERE canonical_case_id IS NOT NULL),
    (SELECT COUNT(*) FROM public.dossier_case_questions WHERE canonical_case_id IS NULL)
  UNION ALL
  SELECT 'dossier_case_answers',
    (SELECT COUNT(*) FROM public.dossier_case_answers),
    (SELECT COUNT(*) FROM public.dossier_case_answers WHERE canonical_case_id IS NOT NULL),
    (SELECT COUNT(*) FROM public.dossier_case_answers WHERE canonical_case_id IS NULL)
  UNION ALL
  SELECT 'dossier_source_suggestions',
    (SELECT COUNT(*) FROM public.dossier_source_suggestions),
    (SELECT COUNT(*) FROM public.dossier_source_suggestions WHERE canonical_case_id IS NOT NULL),
    (SELECT COUNT(*) FROM public.dossier_source_suggestions WHERE canonical_case_id IS NULL)
  UNION ALL
  SELECT 'relocation_guidance_packs',
    (SELECT COUNT(*) FROM public.relocation_guidance_packs),
    (SELECT COUNT(*) FROM public.relocation_guidance_packs WHERE canonical_case_id IS NOT NULL),
    (SELECT COUNT(*) FROM public.relocation_guidance_packs WHERE canonical_case_id IS NULL)
  UNION ALL
  SELECT 'relocation_trace_events',
    (SELECT COUNT(*) FROM public.relocation_trace_events),
    (SELECT COUNT(*) FROM public.relocation_trace_events WHERE canonical_case_id IS NOT NULL),
    (SELECT COUNT(*) FROM public.relocation_trace_events WHERE canonical_case_id IS NULL)
) t
ORDER BY t.tbl;
```

---

## Rollback Notes

To rollback the migration:

```sql
begin;

-- Drop indexes
drop index if exists public.idx_case_assignments_canonical_case_id;
drop index if exists public.idx_case_events_canonical_case_id;
drop index if exists public.idx_case_participants_canonical_case_id;
drop index if exists public.idx_case_evidence_canonical_case_id;
drop index if exists public.idx_rfqs_canonical_case_id;
drop index if exists public.idx_relocation_guidance_packs_canonical_case_id;

-- Drop columns (optional; keeps data but removes column)
alter table public.case_assignments drop column if exists canonical_case_id;
alter table public.case_events drop column if exists canonical_case_id;
alter table public.case_participants drop column if exists canonical_case_id;
alter table public.case_evidence drop column if exists canonical_case_id;
alter table public.case_requirements_snapshots drop column if exists canonical_case_id;
alter table public.case_feedback drop column if exists canonical_case_id;
alter table public.case_services drop column if exists canonical_case_id;
alter table public.case_service_answers drop column if exists canonical_case_id;
alter table public.case_resource_preferences drop column if exists canonical_case_id;
alter table public.rfqs drop column if exists canonical_case_id;
alter table public.dossier_answers drop column if exists canonical_case_id;
alter table public.dossier_case_questions drop column if exists canonical_case_id;
alter table public.dossier_case_answers drop column if exists canonical_case_id;
alter table public.dossier_source_suggestions drop column if exists canonical_case_id;
alter table public.relocation_guidance_packs drop column if exists canonical_case_id;
alter table public.relocation_trace_events drop column if exists canonical_case_id;

commit;
```

Backend changes (Database methods) must be reverted via git to stop writing canonical_case_id. Legacy reads are unaffected; case_id remains.
