# ReloPass Target Domain Platform Model

**Principal platform architect specification — March 2026**

A Stripe-inspired domain platform model for ReloPass, defining canonical primitives, bounded domains, workflow hierarchy, migration mapping, and technical debt hotspots.

---

## 1. CANONICAL PLATFORM PRIMITIVES

### Core Primitives

| Primitive | Purpose | Key Fields | Relationships | Layer |
|-----------|---------|------------|---------------|-------|
| **RelocationCase** | Single relocation journey: origin → destination, purpose, timeline, company context. The root aggregate. | id, company_id, origin_country, dest_country, dest_city, purpose, target_move_date, status, profile_snapshot, created_at, updated_at | Has many Assignments, Requirements (computed), Evidence (via Assignment), ServiceRequests, Policy (via company) | Core |
| **Assignment** | HR→Employee assignment within a case. The primary unit of work for employee intake and HR review. | id, case_id, hr_user_id, employee_user_id, employee_identifier, status, submitted_at, decision, budget_limit, risk_status, created_at | Belongs to RelocationCase; has CaseParticipant (employee); has Evidence, CaseAction; references Policy for eligibility | Core |
| **Person** | Canonical identity for any human actor (employee, HR, vendor contact). | id, email, display_name, role, company_id (nullable), created_at | Participates in Assignments, CaseActions; may be Provider contact | Core |
| **CaseParticipant** | Junction: Person + RelocationCase + role. Enables multi-participant cases and clear ownership. | id, case_id, person_id, role (relocatee, hr_owner, hr_reviewer, observer), invited_at, joined_at | Belongs to RelocationCase, Person | Core |
| **Requirement** | Computed or stored requirement for a case (immigration, housing, tax, etc.). Scoped by dest_country + purpose + case context. | id, case_id, pillar, title, description, severity, required_fields, status_for_case (MISSING, PROVIDED, NEEDS_REVIEW), citations, computed_at | Belongs to RelocationCase; references source documents | Core |
| **CaseAction** | Immutable record of a state change or decision on a case/assignment. Enables audit, webhooks, replay. | id, case_id, assignment_id (nullable), actor_person_id, action_type, payload, created_at | Belongs to RelocationCase; optional Assignment | Core |

### Supporting Primitives

| Primitive | Purpose | Key Fields | Relationships | Layer |
|-----------|---------|------------|---------------|-------|
| **Evidence** | Document or datum submitted to satisfy a requirement (passport scan, employment letter, etc.). | id, assignment_id, requirement_id (nullable), evidence_type, file_url, metadata, status, submitted_at | Belongs to Assignment; optionally satisfies Requirement | Supporting |
| **Policy** | Company relocation policy: rules, caps, eligibility. Source of truth for eligibility and limits. | id, company_id, title, version, effective_date, status (draft, published), benefits_json, created_at | Belongs to Company; used by Assignments for eligibility | Supporting |
| **ServiceRequest** | Request for a relocation service (housing, movers, schools). Can be internal (selection) or procurement (RFQ). | id, case_id, assignment_id, service_key, category, status, selected_provider_id (nullable), estimated_cost, created_at | Belongs to RelocationCase; may link to RFQ, Provider | Supporting |
| **Provider** | External service provider (mover, school, housing). Canonical vendor/partner entity. | id, name, service_types[], countries[], logo_url, contact_email, status, created_at | Receives RFQs; issues Quotes; referenced by ServiceRequest | Supporting |
| **RFQ** | Request for Quote — formal procurement request to providers. | id, case_id, created_by_person_id, rfq_ref, status (draft, sent, closed), created_at | Belongs to RelocationCase; has Quote(s) | Supporting |
| **Quote** | Provider's response to an RFQ. | id, rfq_id, provider_id, status (proposed, accepted, rejected), total_amount, line_items, created_at | Belongs to RFQ, Provider | Supporting |

### Publishing / Infrastructure Primitives

| Primitive | Purpose | Key Fields | Relationships | Layer |
|-----------|---------|------------|---------------|-------|
| **Resource** | Published relocation content: guide, checklist, link. Country/city-scoped. | id, country_code, city_name, category_key, title, resource_type, body, content_json, status, source_id, created_at | References source; tagged; used by Knowledge domain | Publishing |
| **ReviewItem** | Unified ops queue item: staged content, change event, alert, or support item. Generic workflow for review/approval. | id, item_type, status, priority_band, assigned_to_person_id, source_entity_type, source_entity_id, created_at | Polymorphic source; has CollaborationThread | Publishing |

---

## 2. DOMAIN BOUNDARIES

### Domain 1: Case Platform

**Ownership**: RelocationCase, Assignment, CaseParticipant, CaseAction, Person (identity aspect).

| Aspect | Today | Target |
|--------|-------|--------|
| **Tables** | wizard_cases, relocation_cases, case_assignments, assignment_invites, case_events, case_feedback, case_requirements_snapshots, employee_profiles, employee_answers | `relocation_cases` (unified), `assignments`, `case_participants`, `case_actions`, `assignment_invites` |
| **APIs** | `/api/cases/*`, `/api/employee/*`, `/api/hr/*`, `/api/profile/*`, `/api/dashboard` | `GET/POST /cases`, `GET/PATCH /cases/{id}`, `GET/POST /cases/{id}/assignments`, `POST /assignments/{id}/actions` |
| **Services** | main.py (monolithic), app/routers/cases | CaseService, AssignmentService, CaseActionService |
| **Events Emitted** | (none) | `case.created`, `case.updated`, `assignment.created`, `assignment.status_changed`, `assignment.submitted`, `assignment.decided` |
| **Events Consumed** | — | (none; source of truth) |

---

### Domain 2: Compliance Intelligence

**Ownership**: Requirement (computed + stored), Policy, Policy benefits, eligibility rules.

| Aspect | Today | Target |
|--------|-------|--------|
| **Tables** | requirement_items, requirement_entities, requirement_facts, requirement_reviews, compliance_reports, compliance_runs, compliance_actions, eligibility_overrides, policy_exceptions, hr_policies, company_policies, policy_benefits | `requirements` (unified), `policies`, `policy_benefits`, `compliance_runs`, `compliance_actions`, `eligibility_overrides`, `policy_exceptions` |
| **APIs** | `/api/hr/*` (compliance), policy extraction in main.py | `GET /cases/{id}/requirements`, `POST /policies`, `POST /policies/{id}/extract`, `GET /assignments/{id}/eligibility` |
| **Services** | compliance_engine, policy_extractor, policy_adapter, requirements_builder, rules_engine | ComplianceService, PolicyService, RequirementsEngine |
| **Events Emitted** | (none) | `policy.published`, `requirements.computed`, `compliance.check_completed` |
| **Events Consumed** | — | `case.created`, `case.updated`, `assignment.submitted` (to recompute requirements, eligibility) |

---

### Domain 3: Evidence & Document Intelligence

**Ownership**: Evidence, document extraction, dossier answers, guidance packs.

| Aspect | Today | Target |
|--------|-------|--------|
| **Tables** | employee_answers, dossier_questions, dossier_answers, dossier_case_questions, dossier_case_answers, dossier_source_suggestions, relocation_guidance_packs, crawled_source_documents, crawled_source_chunks, company_policies (extraction) | `evidence` (unified), `dossier_questions`, `dossier_answers`, `guidance_packs`, `documents` (crawl output) |
| **APIs** | `/api/dossier/*`, `/api/guidance/*`, policy upload/extract in main.py | `GET/POST /assignments/{id}/evidence`, `GET/POST /cases/{id}/dossier/*`, `POST /guidance/generate`, `POST /policies/{id}/extract` |
| **Services** | dossier, guidance_pack_service, policy_extractor | EvidenceService, DossierService, GuidanceService, DocumentExtractionService |
| **Events Emitted** | (none) | `evidence.submitted`, `guidance.generated`, `document.extracted` |
| **Events Consumed** | — | `assignment.submitted`, `case.updated` (for guidance generation) |

---

### Domain 4: Service Procurement

**Ownership**: ServiceRequest, Provider, RFQ, Quote, recommendations.

| Aspect | Today | Target |
|--------|-------|--------|
| **Tables** | case_services, case_service_answers, vendors, vendor_users, service_recommendations, case_vendor_shortlist, rfqs, rfq_items, rfq_recipients, quotes, quote_lines, quote_conversations, quote_participants, quote_messages | `service_requests`, `providers`, `provider_users`, `rfqs`, `rfq_items`, `rfq_recipients`, `quotes`, `quote_lines`, `quote_conversations`, `quote_messages` |
| **APIs** | `/api/services/*`, `/api/recommendations/*`, `/api/rfqs` (minimal) | `GET/POST /cases/{id}/service-requests`, `GET/POST /providers`, `GET/POST /rfqs`, `GET/POST /quotes` |
| **Services** | recommendation_engine, app/recommendations (plugins) | ServiceRequestService, ProviderService, RFQService, RecommendationService |
| **Events Emitted** | (none) | `rfq.sent`, `quote.received`, `quote.accepted` |
| **Events Consumed** | — | `case.created`, `assignment.status_changed` (for recommendations) |

---

### Domain 5: Knowledge & Operations

**Ownership**: Resource, ReviewItem, crawl pipeline, staging, review queue, ops notifications, collaboration.

| Aspect | Today | Target |
|--------|-------|--------|
| **Tables** | country_resources, rkg_country_events, country_resource_sections, country_resource_items, country_events, resource_categories, resource_sources, resource_tags, country_resource_tags, staged_resource_candidates, staged_event_candidates, crawl_runs, crawled_source_documents, crawled_source_chunks, crawl_schedules, crawl_job_runs, document_change_events, freshness_snapshots, freshness_alerts, review_queue_items, review_queue_activity_log, ops_notifications, ops_notification_events, collaboration_threads, collaboration_comments | `resources`, `resource_events` (unified), `staged_candidates`, `crawl_runs`, `crawl_documents`, `crawl_chunks`, `crawl_schedules`, `crawl_job_runs`, `document_changes`, `freshness_alerts`, `review_items`, `ops_notifications`, `collaboration_threads`, `collaboration_comments` |
| **APIs** | `/api/resources/*`, `/api/admin/*` (staging, review queue, freshness, collaboration) | `GET /resources`, `GET/POST /admin/staging/*`, `GET/PATCH /admin/review-items/*`, `GET/POST /admin/notifications/*`, `GET/POST /admin/collaboration/*` |
| **Services** | admin_resources, staging_review_service, review_queue_service, ops_notification_service, collaboration_service, crawl_scheduler_service, country_resources | ResourceService, StagingService, ReviewQueueService, OpsNotificationService, CollaborationService, CrawlService |
| **Events Emitted** | (none) | `resource.published`, `staged_candidate.approved`, `review_item.resolved`, `ops_notification.acknowledged` |
| **Events Consumed** | — | `staged_candidate.approved` (to create Resource); `review_item.resolved` (to sync ops_notifications) |

---

## 3. WORKFLOW HIERARCHY

### Core Workflows

| Workflow | Owner | States | Triggers |
|----------|-------|--------|----------|
| **Assignment Lifecycle** | Case Platform | created → assigned → awaiting_intake → submitted → approved \| rejected → closed | assign, claim, submit, decide, close |
| **Case Lifecycle** | Case Platform | draft → active → closed | create, activate, close |

### Supporting Workflows

| Workflow | Owner | States | Triggers |
|----------|-------|--------|----------|
| **Policy Lifecycle** | Compliance Intelligence | draft → published → archived | publish, archive |
| **RFQ Lifecycle** | Service Procurement | draft → sent → closed | send, close |
| **Quote Lifecycle** | Service Procurement | proposed → accepted \| rejected | accept, reject |
| **Eligibility Override** | Compliance Intelligence | (override state) | HR override |

### Publishing Workflows

| Workflow | Owner | States | Triggers |
|----------|-------|--------|----------|
| **Resource/Event CMS** | Knowledge & Operations | draft → in_review → approved → published → archived | submit, approve, publish, archive |
| **Staged Candidate** | Knowledge & Operations | new → needs_review → approved_new \| approved_merged \| rejected \| duplicate \| ignored | approve, reject, merge |
| **Review Item** | Knowledge & Operations | new → triaged → assigned → in_progress → resolved \| rejected \| deferred | assign, resolve, defer, reopen |
| **Ops Notification** | Knowledge & Operations | open → acknowledged → resolved \| suppressed | acknowledge, resolve, suppress, reopen |
| **Collaboration Thread** | Knowledge & Operations | open → resolved \| closed | resolve, close, reopen |

### Orchestration Rules

| Rule | Description |
|------|-------------|
| **Assignment → Requirements** | When assignment status → submitted, Compliance Intelligence recomputes requirements and eligibility. |
| **Assignment → Guidance** | When case profile/dossier changes, Evidence & Document Intelligence can regenerate guidance (on-demand today). |
| **Staged Candidate → Review Item** | Staging creates ReviewItem; resolving ReviewItem does not auto-update staged candidate (manual today; should sync). |
| **Review Item Resolved → Ops Notification** | When a ReviewItem linked to an OpsNotification is resolved, notification auto-resolves (sync_resolved_notifications). |
| **Staged Candidate Approved → Resource** | Approve-as-new creates draft Resource; approve-merge updates existing Resource. |
| **Case → ServiceRequest** | Service selections (case_services) map to ServiceRequest; RFQ creation can be triggered from ServiceRequest. |

---

## 4. MIGRATION MAPPING

### Case Platform

| Current Table | Action | Target |
|---------------|--------|--------|
| wizard_cases | **merge** | relocation_cases (canonical) — migrate draft_json → profile_snapshot, add company_id, standardize status |
| relocation_cases | **merge** | Same — consolidate with wizard_cases; deprecate profile_json in favor of structured fields |
| case_assignments | **keep** → rename | assignments — keep schema; fix case_id FK to relocation_cases; normalize status to canonical enum |
| assignment_invites | **keep** | assignment_invites — add formal FK to case_id |
| case_events | **replace** | case_actions — immutable event log with action_type, payload |
| case_feedback | **keep** | case_feedback — or fold into case_actions with action_type=feedback |
| case_requirements_snapshots | **keep** | case_requirements_snapshots — or move to Compliance domain as requirement_snapshots |
| employee_profiles | **merge** | assignments.employee_profile_json (denormalized) or evidence + dossier |
| employee_answers | **merge** | evidence + dossier_answers |
| profile_state | **deprecate** | Remove; use assignment-scoped profile |
| answers | **deprecate** | Legacy; migrate to dossier_answers if needed |
| relocation_navigator.relocation_cases | **deprecate** | Consolidate into relocation_cases |

### Compliance Intelligence

| Current Table | Action | Target |
|---------------|--------|--------|
| requirement_items | **merge** | requirements — flatten or keep as template; add requirement_snapshots for case-specific computed |
| requirement_entities | **merge** | requirements (hierarchical) — entity = requirement group |
| requirement_facts | **merge** | requirements (facts as sub-items) or requirement_details |
| requirement_reviews | **keep** | requirement_reviews — admin approval workflow |
| compliance_reports | **keep** | compliance_runs (rename) — run output |
| compliance_runs | **merge** | compliance_runs |
| compliance_actions | **keep** | compliance_actions |
| eligibility_overrides | **keep** | eligibility_overrides |
| policy_exceptions | **keep** | policy_exceptions |
| hr_policies | **deprecate** | policies (unified with company_policies) |
| company_policies | **keep** → rename | policies — add company_id if missing |
| policy_benefits | **keep** | policy_benefits |

### Evidence & Document Intelligence

| Current Table | Action | Target |
|---------------|--------|--------|
| dossier_questions | **keep** | dossier_questions |
| dossier_answers | **keep** | dossier_answers |
| dossier_case_questions | **keep** | dossier_case_questions |
| dossier_case_answers | **keep** | dossier_case_answers |
| dossier_source_suggestions | **keep** | dossier_source_suggestions |
| relocation_guidance_packs | **keep** | guidance_packs |
| relocation_trace_events | **keep** | trace_events (for debugging) |
| rule_evaluation_logs | **keep** | rule_evaluation_logs |
| crawled_source_documents | **keep** | documents (crawl) — or rename for clarity |
| crawled_source_chunks | **keep** | document_chunks |

### Service Procurement

| Current Table | Action | Target |
|---------------|--------|--------|
| vendors | **keep** → rename | providers |
| vendor_users | **keep** → rename | provider_users |
| case_services | **keep** → rename | service_requests |
| case_service_answers | **merge** | service_requests.answers_json or separate service_answers |
| service_recommendations | **keep** | service_recommendations |
| case_vendor_shortlist | **keep** | case_vendor_shortlist |
| rfqs | **keep** | rfqs |
| rfq_items | **keep** | rfq_items |
| rfq_recipients | **keep** | rfq_recipients |
| quotes | **keep** | quotes |
| quote_lines | **keep** | quote_lines |
| quote_conversations | **keep** | quote_conversations |
| quote_participants | **keep** | quote_participants |
| quote_messages | **keep** | quote_messages |

### Knowledge & Operations

| Current Table | Action | Target |
|---------------|--------|--------|
| country_resources | **keep** | resources — rename |
| rkg_country_events | **merge** | resource_events — unify with country_events |
| country_resource_sections | **deprecate** | Migrate content to resources; or keep as legacy read path during transition |
| country_resource_items | **deprecate** | Same |
| country_events | **merge** | resource_events |
| resource_categories | **keep** | resource_categories |
| resource_sources | **keep** | resource_sources |
| resource_tags | **keep** | resource_tags |
| country_resource_tags | **keep** | resource_tags (rename table) |
| staged_resource_candidates | **keep** | staged_candidates (unified with events? or keep separate) |
| staged_event_candidates | **keep** | staged_event_candidates (or merge into staged_candidates with type) |
| crawl_runs | **keep** | crawl_runs |
| crawl_schedules | **keep** | crawl_schedules |
| crawl_job_runs | **keep** | crawl_job_runs |
| document_change_events | **keep** | document_change_events |
| freshness_snapshots | **keep** | freshness_snapshots |
| freshness_alerts | **keep** | freshness_alerts |
| review_queue_items | **keep** → rename | review_items |
| review_queue_activity_log | **keep** | review_item_activity_log |
| ops_notifications | **keep** | ops_notifications |
| ops_notification_events | **keep** | ops_notification_events |
| collaboration_threads | **keep** | collaboration_threads |
| collaboration_comments | **keep** | collaboration_comments |
| collaboration_* (mentions, participants, notifications) | **keep** | Same |

### Shared / Cross-Cutting

| Current Table | Action | Target |
|---------------|--------|--------|
| users | **deprecate** | Use auth.users + profiles; Person = profile extended |
| profiles | **extend** | Person — add to Case Platform or Identity service |
| companies | **keep** | companies |
| employees | **deprecate** | CaseParticipant + Assignment replaces |
| hr_users | **deprecate** | Person with role + company |
| messages | **keep** | messages — or merge into collaboration |
| notifications | **keep** | notifications |
| support_cases | **keep** | support_cases — consider linking to ReviewItem |
| audit_log | **keep** | audit_log |
| relocation_runs, relocation_sources, relocation_artifacts | **deprecate** | Legacy AI/classification; remove or archive |

---

## 5. TECHNICAL DEBT HOTSPOTS

**Top 10 blockers to a Stripe-like platform, in priority order.**

### 1. Monolithic main.py (~4000 LOC)

**Problem**: Single file owns auth, cases, assignments, profile, dossier, guidance, HR, services, RFQ, policy extraction. No domain boundaries, no event emission, no webhook surface.

**Impact**: Cannot extract domains without massive refactor. No way to offer `assignment.submitted` webhooks.

**Action**: Extract routers per domain; introduce `CaseEventEmitter` (or similar) that publishes to internal event bus. Start with Assignment transitions.

---

### 2. No Canonical Case Identity

**Problem**: `wizard_cases`, `relocation_cases`, `relocation_navigator.relocation_cases` — three case representations. `case_id` is sometimes UUID, sometimes text; FKs are missing or weak.

**Impact**: Every cross-domain feature (dossier, guidance, RFQ, services) references "case" ambiguously. Migrations are risky.

**Action**: Choose `relocation_cases` (or new `cases`) as canonical. Add `company_id`, formal FKs. Migrate wizard_cases into it. Deprecate relocation_navigator.

---

### 3. JSON Blob Data Models (draft_json, profile_json)

**Problem**: `wizard_cases.draft_json` and `relocation_cases.profile_json` are opaque JSON. Schema lives in frontend wizard steps and backend heuristics. No validation, no queryability.

**Impact**: Cannot index on "destination country" or "has children" without parsing JSON. Cannot evolve schema safely.

**Action**: Extract critical fields to columns (origin_country, dest_country, purpose, target_move_date, has_dependents). Keep extensible JSON for nested details but enforce a JSON Schema for the rest.

---

### 4. Assignment Status Dual Representation

**Problem**: DB stores legacy values (DRAFT, IN_PROGRESS, EMPLOYEE_SUBMITTED, HR_REVIEW); API normalizes to canonical (created, assigned, awaiting_intake, submitted, approved, rejected, closed). Supabase RPCs use legacy. Frontend uses canonical.

**Impact**: Confusion, bugs when RPCs bypass normalization. Hard to add new transitions.

**Action**: Migrate DB to canonical enum. Update RPCs. Single source of truth for status.

---

### 5. No Event or Webhook Layer

**Problem**: State changes are synchronous only. No `assignment.submitted` event, no `policy.published` webhook. Integrations cannot react.

**Impact**: ReloPass cannot be a platform. Partners cannot build on top.

**Action**: Add `case_actions` (or event store) as append-only log. Emit domain events on transitions. Add webhook delivery (signatures, retries) for critical events.

---

### 6. Resource/Event Duplication (Legacy vs RKG)

**Problem**: `country_resource_sections` + `country_resource_items` vs `country_resources`. `country_events` vs `rkg_country_events`. Two content models, two code paths.

**Impact**: Duplicated logic, migration paralysis. Admins unsure which to use.

**Action**: Migrate legacy content to RKG schema. Deprecate legacy tables. Single `resources` and `resource_events` API.

---

### 7. Review Queue Polymorphism Without Abstraction

**Problem**: `review_queue_items` has 6+ optional FKs (staged_resource, staged_event, change_event, live_resource, live_event, alert). Logic branches on `queue_item_type`. No `ReviewItem` abstraction in code.

**Impact**: Adding a new source type requires schema + service + UI changes in many places.

**Action**: Introduce `source_entity_type` + `source_entity_id` polymorphic pattern. Single service interface. Generic ReviewItem API.

---

### 8. Requirements Computed On-Demand, Not Stored

**Problem**: `statusForCase` (MISSING, PROVIDED, NEEDS_REVIEW) is computed per request in `requirements_builder`. No persistence. No history.

**Impact**: Cannot show "requirements changed" or "previously provided, now missing". Compliance audit is weak.

**Action**: Store computed requirements in `requirement_snapshots` or `case_requirements` with `computed_at`. Recompute on case/assignment change. Expose as immutable history.

---

### 9. Provider/Vendor Weakness in Service Procurement

**Problem**: `vendors` exists but recommendations come from seed data (`get_housing_seed`, `get_schools_seed`, `get_movers_seed`). No provider registry. RFQ is built but underused.

**Impact**: Cannot scale to marketplace. ServiceRequest → Provider linkage is weak.

**Action**: Populate `providers` from seed; make recommendations query providers. Strengthen RFQ ↔ ServiceRequest linkage. Add provider onboarding flow.

---

### 10. No Idempotency or Idempotency Keys

**Problem**: POST endpoints (submit assignment, create RFQ, approve resource) are not idempotent. Retries can create duplicates. No idempotency key support.

**Impact**: Unreliable integrations. Clients cannot safely retry.

**Action**: Add `Idempotency-Key` header support for mutating endpoints. Store key → response in Redis or DB. Return cached response on replay.

---

## Summary

| Section | Key Takeaway |
|---------|--------------|
| **Primitives** | 14 canonical models: 6 core, 5 supporting, 3 publishing. Case and Assignment are the heart. |
| **Domains** | 5 bounded domains with clear ownership, APIs, and event contracts. |
| **Workflows** | Core (Assignment, Case) → Supporting (Policy, RFQ, Quote) → Publishing (Resource, ReviewItem, Ops). |
| **Migration** | Merge wizard_cases + relocation_cases; keep assignments, RFQ, quotes; deprecate legacy resources/events, relocation_navigator. |
| **Debt** | Monolithic main.py, case identity chaos, JSON blobs, status duality, no events/webhooks, resource duplication, review queue polymorphism, ephemeral requirements, weak providers, no idempotency. |
