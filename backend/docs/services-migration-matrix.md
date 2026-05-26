# Services Migration Matrix — AUDIT-A9

> Generated: 2026-05-26  
> Purpose: Complete inventory of `backend/services/` modules (155 files) and every
> cross-import site from `backend/app/` into `backend/services/` (85 lines).
> This document is the prerequisite for AUDIT-A9.2 (ADR) and AUDIT-A9.3 (the move).

---

## Summary

| Metric | Count |
|--------|-------|
| Files in `backend/services/` | 155 |
| Files in `backend/app/services/` (canonical target) | 25 |
| Cross-import lines (`backend/app/ → backend/services/`) | 85 |
| Distinct service modules referenced cross-tree | 40 |
| Reverse cross-imports (`backend/services/ → backend/app/`) | 0 |

**Migration direction:** move all 155 files from `backend/services/` into
`backend/app/services/`, then update all 85 import sites.

**Highest-churn service modules** (most import sites, hardest to miss):

| Service module | Import sites | Subdomain |
|----------------|-------------|-----------|
| `supabase_client` | 29 | infra |
| `audit_log_service` | 5 | analytics |
| `analytics_service` | 4 | analytics |
| `events_tracker` | 3 | analytics |
| `supabase_auth_sync` | 2 | infra |
| `provider_jwt` | 2 | provider/vendor |
| `policy_ingest_reconciler` | 2 | policy |
| `policy_adapter` | 2 | policy |
| `freshness_service` | 2 | knowledge |
| `crawl_scheduler_service` | 2 | knowledge |
| `change_detection_service` | 2 | knowledge |
| `case_context_service` | 2 | mobility |

---

## Part 1 — Full Module Inventory (`backend/services/`)

Files are grouped by subdomain. The subdomain tag will become the sub-package name
when the tree is reorganised (optional, tracked separately). For the AUDIT-A9.3 move,
all files land flat in `backend/app/services/` first; sub-package refactor is out of scope.

### Subdomain: `policy` (69 files)

| File | Notes |
|------|-------|
| `backend/services/policy_adapter.py` | Adapts policy caps to normalised format |
| `backend/services/policy_applicability_engine.py` | |
| `backend/services/policy_assistant_access.py` | |
| `backend/services/policy_assistant_analytics.py` | |
| `backend/services/policy_assistant_answer_audit_service.py` | |
| `backend/services/policy_assistant_answer_engine.py` | |
| `backend/services/policy_assistant_case_context_service.py` | |
| `backend/services/policy_assistant_classifier.py` | |
| `backend/services/policy_assistant_contract.py` | |
| `backend/services/policy_assistant_embedder.py` | |
| `backend/services/policy_assistant_import_pipeline.py` | |
| `backend/services/policy_assistant_llm_client.py` | Will conflict with new `llm_client.py` in app/services — rename on move (see risk below) |
| `backend/services/policy_assistant_rag_engine.py` | |
| `backend/services/policy_assistant_refusal_service.py` | |
| `backend/services/policy_assistant_session_memory.py` | |
| `backend/services/policy_assistant_session_service.py` | |
| `backend/services/policy_canonical_access.py` | |
| `backend/services/policy_canonical_chunking.py` | |
| `backend/services/policy_canonical_diff.py` | |
| `backend/services/policy_canonical_extraction.py` | |
| `backend/services/policy_canonical_ingestion.py` | |
| `backend/services/policy_canonical_key_matcher.py` | |
| `backend/services/policy_canonical_lta_template.py` | |
| `backend/services/policy_canonical_validation.py` | |
| `backend/services/policy_chunk_indexer.py` | |
| `backend/services/policy_chunk_retriever.py` | |
| `backend/services/policy_company_policy_template_init.py` | |
| `backend/services/policy_comparison_readiness.py` | |
| `backend/services/policy_config_cap_compare.py` | |
| `backend/services/policy_config_matrix_service.py` | |
| `backend/services/policy_config_targeting.py` | |
| `backend/services/policy_config_templates.py` | |
| `backend/services/policy_context_graph_service.py` | |
| `backend/services/policy_document_clauses.py` | |
| `backend/services/policy_document_intake.py` | |
| `backend/services/policy_document_service.py` | |
| `backend/services/policy_entitlement_model.py` | |
| `backend/services/policy_extractor.py` | |
| `backend/services/policy_fact_extraction_service.py` | |
| `backend/services/policy_filetype.py` | |
| `backend/services/policy_grouped_comparison_readiness.py` | |
| `backend/services/policy_grouped_policy_model.py` | |
| `backend/services/policy_hr_grouped_review.py` | |
| `backend/services/policy_hr_review_serializer.py` | |
| `backend/services/policy_hr_review_service.py` | |
| `backend/services/policy_hr_rule_override_layer.py` | |
| `backend/services/policy_ingest_reconciler.py` | |
| `backend/services/policy_intake_errors.py` | |
| `backend/services/policy_knowledge_snapshot_service.py` | |
| `backend/services/policy_lta_grouping_heuristics.py` | |
| `backend/services/policy_normalization.py` | |
| `backend/services/policy_normalization_draft.py` | |
| `backend/services/policy_normalization_errors.py` | |
| `backend/services/policy_normalization_states.py` | |
| `backend/services/policy_normalization_validate.py` | |
| `backend/services/policy_pipeline_analytics.py` | |
| `backend/services/policy_pipeline_diagnostics.py` | |
| `backend/services/policy_pipeline_layers.py` | |
| `backend/services/policy_processing_readiness.py` | |
| `backend/services/policy_publish_gate.py` | |
| `backend/services/policy_query_answering.py` | |
| `backend/services/policy_rendering.py` | |
| `backend/services/policy_resolution.py` | |
| `backend/services/policy_row_to_template_mapper.py` | |
| `backend/services/policy_rule_comparison_readiness.py` | |
| `backend/services/policy_section_c_resolver.py` | |
| `backend/services/policy_section_c_validation.py` | |
| `backend/services/policy_service_comparison.py` | |
| `backend/services/policy_session_pdf.py` | |
| `backend/services/policy_snapshot_diff_service.py` | |
| `backend/services/policy_source_provenance.py` | |
| `backend/services/policy_starter_templates.py` | |
| `backend/services/policy_storage_health.py` | |
| `backend/services/policy_storage_paths.py` | |
| `backend/services/policy_structural_parse.py` | |
| `backend/services/policy_summary_row_parser.py` | |
| `backend/services/policy_taxonomy.py` | |
| `backend/services/policy_template_first_import.py` | |
| `backend/services/policy_text_extraction_service.py` | |

### Subdomain: `employee` (8 files)

| File | Notes |
|------|-------|
| `backend/services/employee_assignment_overview.py` | |
| `backend/services/employee_case_person_service.py` | |
| `backend/services/employee_demand.py` | |
| `backend/services/employee_entitlement_read_model.py` | |
| `backend/services/employee_entitlement_serializer.py` | |
| `backend/services/employee_policy_assistant_service.py` | |
| `backend/services/employee_policy_matrix_bridge.py` | |
| `backend/services/employee_recommendations_filter.py` | |
| `backend/services/employee_services_policy_context.py` | |

### Subdomain: `analytics` (4 files)

| File | Notes |
|------|-------|
| `backend/services/analytics_service.py` | 4 import sites |
| `backend/services/audit_log_service.py` | 5 import sites — highest non-infra |
| `backend/services/events_tracker.py` | 3 import sites |
| `backend/services/outcome_recorder.py` | |

### Subdomain: `infra` (2 files)

| File | Notes |
|------|-------|
| `backend/services/supabase_client.py` | **29 import sites** — most referenced module in cross-tree |
| `backend/services/supabase_auth_sync.py` | 2 import sites |

### Subdomain: `knowledge` (8 files)

| File | Notes |
|------|-------|
| `backend/services/catalog_coverage.py` | |
| `backend/services/catalog_scraper.py` | |
| `backend/services/change_detection_service.py` | 2 import sites |
| `backend/services/crawl_scheduler_service.py` | 2 import sites |
| `backend/services/freshness_service.py` | 2 import sites |
| `backend/services/review_queue_service.py` | |
| `backend/services/scrape_safety.py` | |
| `backend/services/staging_review_service.py` | |

### Subdomain: `admin_ops` (5 files)

| File | Notes |
|------|-------|
| `backend/services/admin_assignment_evaluation_trigger.py` | |
| `backend/services/admin_resources.py` | |
| `backend/services/ops_analytics_service.py` | |
| `backend/services/ops_notification_config.py` | |
| `backend/services/ops_notification_service.py` | |

### Subdomain: `relocation` (4 files)

| File | Notes |
|------|-------|
| `backend/services/relocation_classification.py` | |
| `backend/services/relocation_classifier.py` | |
| `backend/services/relocation_plan_view_service.py` | |
| `backend/services/relocation_profile.py` | |

### Subdomain: `provider_vendor` (2 files)

| File | Notes |
|------|-------|
| `backend/services/provider_jwt.py` | 2 import sites |
| `backend/services/vendor_curation.py` | |

### Subdomain: `prospect` (4 files)

| File | Notes |
|------|-------|
| `backend/services/prospect_enrichment_service.py` | |
| `backend/services/prospect_icp_config.py` | |
| `backend/services/prospect_web_fetcher.py` | |
| `backend/services/prospect_web_search.py` | |

### Subdomain: `resources` (2 files + sub-package)

| File | Notes |
|------|-------|
| `backend/services/country_resources.py` | |
| `backend/services/rkg_resources.py` | |
| `backend/services/resources/__init__.py` | Sub-package — keep directory structure on move |
| `backend/services/resources/context_service.py` | |
| `backend/services/resources/dto.py` | |
| `backend/services/resources/public_repository.py` | |
| `backend/services/resources/public_service.py` | |

### Subdomain: `mobility` (misc — grouped here for clarity)

| File | Notes |
|------|-------|
| `backend/services/case_context_service.py` | 2 import sites |
| `backend/services/mobility_inspect_service.py` | |
| `backend/services/mobility_route_access.py` | |
| `backend/services/next_action_service.py` | |
| `backend/services/requirement_evaluation_service.py` | |

### Subdomain: `misc` (remaining files)

| File | Notes |
|------|-------|
| `backend/services/__init__.py` | Empty or re-exports — verify before deleting |
| `backend/services/ai_trace_logger.py` | |
| `backend/services/assignment_claim_link_service.py` | |
| `backend/services/assignment_mobility_link_service.py` | |
| `backend/services/collaboration_service.py` | |
| `backend/services/dossier.py` | |
| `backend/services/exception_request_service.py` | |
| `backend/services/explicit_pending_link_service.py` | |
| `backend/services/family_propagation.py` | |
| `backend/services/fx_service.py` | |
| `backend/services/guidance_markdown.py` | |
| `backend/services/guidance_pack_service.py` | |
| `backend/services/hr_policy_assistant_service.py` | |
| `backend/services/identity_canonical.py` | |
| `backend/services/identity_data_reconciliation.py` | |
| `backend/services/immigration_regime.py` | |
| `backend/services/normalization_input.py` | |
| `backend/services/passport_case_document_sync_service.py` | |
| `backend/services/pii_log_filter.py` | Used by `backend/app/main.py` (top-level import) |
| `backend/services/pii_masker.py` | |
| `backend/services/plan_scope.py` | |
| `backend/services/service_catalog.py` | |
| `backend/services/service_comparison_engine.py` | |
| `backend/services/signup_reconciliation.py` | |
| `backend/services/unified_assignment_creation.py` | |
| `backend/services/wizard_draft_mapper.py` | |

---

## Part 2 — Cross-Import Map (85 lines)

Every line where `backend/app/` imports from `backend/services/`. Grouped by caller file.
Import style used: `from ...services.<module> import ...` (3-dot relative).

After AUDIT-A9.3 all of these become `from ..<module> import ...` (or stay absolute if
`backend.app.services` is on sys.path).

### `backend/app/main.py` (1 site)

| Line | Service module | Import |
|------|---------------|--------|
| 7 | `pii_log_filter` | `install_pii_log_filter` |

### `backend/app/recommendations/admin_debug.py` (1 site)

| Line | Service module | Import |
|------|---------------|--------|
| 35 | `policy_adapter` | `normalize_policy_caps` |

### `backend/app/recommendations/engine.py` (2 sites)

| Line | Service module | Import |
|------|---------------|--------|
| 189 | `employee_recommendations_filter` | `apply_hr_curation` |
| 28 | `supplier_registry` | `search_by_service_destination` *(2-dot — app/services already)* |

### `backend/app/recommendations/router.py` (3 sites)

| Line | Service module | Import |
|------|---------------|--------|
| 54 | `policy_adapter` | `normalize_policy_caps` |
| 158 | `analytics_service` | `emit_event, EVENT_RECOMMENDATIONS_GENERATED` |
| 241 | `analytics_service` | `emit_event, EVENT_RECOMMENDATIONS_GENERATED` |

### `backend/app/routers/admin.py` (3 sites)

| Line | Service module | Import |
|------|---------------|--------|
| 16 | `audit_log_service` | (multi-symbol) |
| 538 | `policy_ingest_reconciler` | `find_orphaned_policy_documents` |
| 552 | `policy_ingest_reconciler` | `reconcile_orphaned_policy_ingest_jobs` |

### `backend/app/routers/admin_collaboration.py` (1 site)

| Line | Service module | Import |
|------|---------------|--------|
| 13 | `collaboration_service` | (multi-symbol) |

### `backend/app/routers/admin_freshness.py` (6 sites)

| Line | Service module | Import |
|------|---------------|--------|
| 12 | `change_detection_service` | (multi-symbol) |
| 16 | `crawl_scheduler_service` | (multi-symbol) |
| 32 | `freshness_service` | (multi-symbol) |
| 136 | `crawl_scheduler_service` | `get_schedule` |
| 278 | `change_detection_service` | `run_change_detection_for_crawl_run` |
| 279 | `freshness_service` | `refresh_freshness_metrics` |

### `backend/app/routers/admin_mobility.py` (3 sites)

| Line | Service module | Import |
|------|---------------|--------|
| 10 | `admin_assignment_evaluation_trigger` | `run_evaluation_for_assignment` |
| 11 | `case_context_service` | `CaseContextError, CaseContextService` |
| 12 | `mobility_inspect_service` | (multi-symbol) |

### `backend/app/routers/admin_notifications.py` (1 site)

| Line | Service module | Import |
|------|---------------|--------|
| 11 | `ops_notification_service` | (multi-symbol) |

### `backend/app/routers/admin_ops_analytics.py` (1 site)

| Line | Service module | Import |
|------|---------------|--------|
| 12 | `ops_analytics_service` | (multi-symbol) |

### `backend/app/routers/admin_prospects.py` (3 sites)

| Line | Service module | Import |
|------|---------------|--------|
| 26 | `prospect_enrichment_service` | (multi-symbol) |
| 30 | `prospect_icp_config` | `ICP_CONFIG` |
| 31 | `prospect_web_search` | (multi-symbol) |

### `backend/app/routers/admin_resources.py` (1 site)

| Line | Service module | Import |
|------|---------------|--------|
| 11 | `admin_resources` | (multi-symbol) |

### `backend/app/routers/admin_review_queue.py` (1 site)

| Line | Service module | Import |
|------|---------------|--------|
| 13 | `review_queue_service` | (multi-symbol) |

### `backend/app/routers/admin_staging.py` (1 site)

| Line | Service module | Import |
|------|---------------|--------|
| 12 | `staging_review_service` | (multi-symbol) |

### `backend/app/routers/advisors.py` (3 sites)

| Line | Service module | Import |
|------|---------------|--------|
| 185 | `supabase_client` | `get_supabase_admin_client` |
| 203 | `supabase_client` | `get_supabase_admin_client` |
| 294 | `supabase_client` | `get_supabase_admin_client` |

### `backend/app/routers/analytics_query.py` (1 site)

| Line | Service module | Import |
|------|---------------|--------|
| 38 | `supabase_client` | `get_supabase_admin_client` |

### `backend/app/routers/auth.py` (4 sites)

| Line | Service module | Import |
|------|---------------|--------|
| 45 | `assignment_claim_link_service` | `reconcile_pending_assignment_claims` |
| 46 | `audit_log_service` | (multi-symbol) |
| 125 | `supabase_auth_sync` | `sync_relopass_user_to_supabase_auth` |
| 565 | `supabase_auth_sync` | `revoke_supabase_session` |

### `backend/app/routers/branding.py` (2 sites)

| Line | Service module | Import |
|------|---------------|--------|
| 67 | `supabase_client` | `get_supabase_admin_client` |
| 172 | `supabase_client` | `get_supabase_admin_client` |

### `backend/app/routers/case_form_pdf.py` (1 site)

| Line | Service module | Import |
|------|---------------|--------|
| 184 | `supabase_client` | `get_supabase_admin_client` |

### `backend/app/routers/cases.py` (6 sites)

| Line | Service module | Import |
|------|---------------|--------|
| 16 | `relocation_plan_view_service` | `invalidate_relocation_plan_cache` |
| 22 | `audit_log_service` | (multi-symbol) |
| 260 | `analytics_service` | `emit_event, EVENT_CASE_CREATED` |
| 2119 | `supabase_client` | `get_supabase_admin_client` |
| 2193 | `supabase_client` | `get_supabase_admin_client` |
| 2523 | `supabase_client` | `get_supabase_admin_client` |

### `backend/app/routers/exception_requests.py` (2 sites)

| Line | Service module | Import |
|------|---------------|--------|
| 32 | `audit_log_service` | (multi-symbol) |
| 397 | `supabase_client` | `get_supabase_admin_client` |

### `backend/app/routers/hr_analytics.py` (3 sites)

| Line | Service module | Import |
|------|---------------|--------|
| 143 | `supabase_client` | `get_supabase_admin_client` |
| 165 | `supabase_client` | `get_supabase_admin_client` |
| 187 | `supabase_client` | `get_supabase_admin_client` |

### `backend/app/routers/hr_coordination.py` (2 sites)

| Line | Service module | Import |
|------|---------------|--------|
| 21 | `events_tracker` | `track as track_event` |
| 22 | `outcome_recorder` | `record_outcome` |

### `backend/app/routers/hr_policies.py` (1 site)

| Line | Service module | Import |
|------|---------------|--------|
| 25 | `supabase_client` | `get_supabase_admin_client` |

### `backend/app/routers/integrations_bamboohr.py` (1 site)

| Line | Service module | Import |
|------|---------------|--------|
| 77 | `supabase_client` | `get_supabase_admin_client` |

### `backend/app/routers/integrations_personio_settings.py` (1 site)

| Line | Service module | Import |
|------|---------------|--------|
| 36 | `supabase_client` | `get_supabase_admin_client` |

### `backend/app/routers/integrations_personio_webhook.py` (1 site)

| Line | Service module | Import |
|------|---------------|--------|
| 42 | `supabase_client` | `get_supabase_admin_client` |

### `backend/app/routers/marketplace.py` (3 sites)

| Line | Service module | Import |
|------|---------------|--------|
| 85 | `supabase_client` | `get_supabase_admin_client` |
| 112 | `supabase_client` | `get_supabase_admin_client` |
| 130 | `supabase_client` | `get_supabase_admin_client` |

### `backend/app/routers/mobility_context.py` (4 sites)

| Line | Service module | Import |
|------|---------------|--------|
| 9 | `case_context_service` | `CaseContextService, CaseContextError` |
| 10 | `mobility_route_access` | `enforce_mobility_graph_read_access` |
| 11 | `next_action_service` | `NextActionService` |
| 12 | `requirement_evaluation_service` | `RequirementEvaluationService` |

### `backend/app/routers/policy_canonical.py` (5 sites)

| Line | Service module | Import |
|------|---------------|--------|
| 12 | `policy_canonical_access` | (multi-symbol) |
| 18 | `policy_canonical_chunking` | `chunk_canonical_policy_document` |
| 19 | `policy_canonical_extraction` | `extract_canonical_policy_facts` |
| 20 | `policy_canonical_ingestion` | `ingest_canonical_policy_document` |
| 21 | `policy_query_answering` | `answer_company_scoped_policy_query` |
| 22 | `policy_rendering` | `render_canonical_policy_markdown` |

### `backend/app/routers/policy_templates.py` (1 site)

| Line | Service module | Import |
|------|---------------|--------|
| 18 | `supabase_client` | `get_supabase_admin_client` |

### `backend/app/routers/prescreening.py` (1 site)

| Line | Service module | Import |
|------|---------------|--------|
| 25 | `supabase_client` | `get_supabase_admin_client` |

### `backend/app/routers/provider_portal.py` (3 sites)

| Line | Service module | Import |
|------|---------------|--------|
| 31 | `provider_jwt` | `verify_provider_token` |
| 32 | `supabase_client` | `get_supabase_admin_client` |
| 33 | `events_tracker` | `track as track_event` |

### `backend/app/routers/providers.py` (2 sites)

| Line | Service module | Import |
|------|---------------|--------|
| 37 | `supabase_client` | `get_supabase_admin_client` |
| 38 | `provider_jwt` | `generate_provider_token, verify_provider_token, hash_token` |

### `backend/app/routers/relocation_profile.py` (2 sites)

| Line | Service module | Import |
|------|---------------|--------|
| 145 | `supabase_client` | `get_supabase_admin_client` |
| 157 | `supabase_client` | `get_supabase_admin_client` |

### `backend/app/routers/rules.py` (1 site)

| Line | Service module | Import |
|------|---------------|--------|
| 176 | `supabase_client` | `get_supabase_admin_client` |

### `backend/app/routers/services_state.py` (1 site)

| Line | Service module | Import |
|------|---------------|--------|
| 32 | `audit_log_service` | (multi-symbol) |

### `backend/app/routers/suppliers.py` (1 site)

| Line | Service module | Import |
|------|---------------|--------|
| 117 | `analytics_service` | `emit_event, EVENT_SUPPLIER_VIEWED` |

### `backend/app/routers/support.py` (2 sites)

| Line | Service module | Import |
|------|---------------|--------|
| 36 | `supabase_client` | `get_supabase_admin_client` |
| 37 | `events_tracker` | `track` |

### `backend/app/services/requirements_sufficiency.py` (1 site)

| Line | Service module | Import |
|------|---------------|--------|
| 10 | `guidance_pack_service` | `build_profile_snapshot` |

### `backend/app/services/timeline_service.py` (3 sites)

| Line | Service module | Import |
|------|---------------|--------|
| 317 | `plan_scope` | `active_phases_for_case_type` |
| 373 | `family_propagation` | `FamilyPropagator` |
| 412 | `immigration_regime` | `ImmigrationRegimeRouter` |

---

## Part 3 — Risks and Notes for AUDIT-A9.3

| Risk | Detail | Mitigation |
|------|--------|-----------|
| **Name collision: `policy_assistant_llm_client`** | `backend/services/policy_assistant_llm_client.py` will land next to new `backend/app/services/llm_client.py`. Different names, so no collision — but verify imports within policy_assistant modules don't accidentally resolve to the new `llm_client.py`. | Grep for `from .llm_client` inside policy_assistant files after move. |
| **`resources/` sub-package** | `backend/services/resources/` is a sub-directory with its own `__init__.py`. It must be moved as a directory, not flattened. | `cp -r backend/services/resources backend/app/services/resources` |
| **`backend/services/__init__.py`** | May re-export symbols used by `backend/main.py`. Check before deleting. | `grep -r "from backend.services import" backend/` before removing. |
| **`backend/app/main.py` uses 2-dot relative import** | `from ..services.pii_log_filter import ...` — this is already a cross-tree import from `app/main.py`. After move it becomes `from .services.pii_log_filter import ...`. | Update line 7 of `backend/app/main.py`. |
| **`backend/app/services/timeline_service.py` internal cross-import** | `timeline_service.py` (already in app/services) imports 3 modules from `backend/services/`. These become sibling imports after the move. | Update 3 lines in `timeline_service.py`. |
| **`backend/app/services/requirements_sufficiency.py` internal cross-import** | Imports `guidance_pack_service` from `backend/services/`. After move, becomes sibling. | Update 1 line in `requirements_sufficiency.py`. |

---

## Validation Commands (for AUDIT-A9.3 executor)

Run these after the move is complete. All must pass before marking Done.

```bash
# 1. Only one services directory remains
find backend -type d -name services
# Expected: backend/app/services  (exactly one line)

# 2. No cross-tree imports remain
grep -r "from \.\.\.services\.\|from backend\.services\." backend/app/
# Expected: (empty output)

# 3. Tests pass
python -m pytest -q backend/tests/

# 4. App imports cleanly
python -c "import backend.app.main"
# Expected: exits 0, no ImportError
```
