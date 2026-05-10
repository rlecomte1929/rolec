# ReloPass — Conway's Law Architecture Audit Report

**Date:** March 2026  
**Scope:** Full repository analysis — backend, frontend, database, AI integrations, workflows

---

## 1. SYSTEM OVERVIEW

| Layer | Technology | Notes |
|-------|------------|-------|
| **Backend** | FastAPI 0.104, Uvicorn 0.24, Python 3.11 | Monolithic `main.py` (~4000 LOC) + modular `app/` sub-app, SQLAlchemy 2.0 + raw SQL |
| **Frontend** | React 18, TypeScript 5.3, Vite 5, Tailwind CSS, React Router 6 | Single SPA, custom Antigravity component library |
| **Database** | SQLite (dev/ephemeral) or PostgreSQL (Supabase, prod) | Dual support via `db_config.py`; migrations in Supabase |
| **AI Integrations** | **None (deterministic)** | No OpenAI, Anthropic, LangChain. "Agents" are rule-based orchestrators (IntakeOrchestrator, ProfileValidator, ReadinessRater, RecommendationEngine). Policy extraction uses regex/keyword matching (python-docx, pdfplumber). |
| **Infrastructure** | Render (static frontend + web service backend), Cloudflare DNS | Ephemeral SQLite on Render; Supabase for persistent Postgres |

---

## 2. DATABASE MODEL

### Tables by Logical Domain

#### **Case & Assignment Domain**
| Table | Purpose | Key Fields | Foreign Keys | Linked Tables |
|-------|---------|------------|--------------|---------------|
| `wizard_cases` | 5-step relocation case draft | id, draft_json, status, dest_country, purpose, target_move_date | — | case_assignments, case_requirements_snapshots |
| `relocation_cases` | Legacy case storage | id, hr_user_id, profile_json | — | case_assignments |
| `relocation_navigator.relocation_cases` | Supabase relocation flows | id, case_id | — | relocation_runs, relocation_sources, relocation_artifacts |
| `case_assignments` | HR → Employee assignment | id, case_id, hr_user_id, employee_user_id, status, submitted_at, decision | case_id | wizard_cases, assignment_invites, hr_feedback, compliance_* |
| `assignment_invites` | Invite tokens for employees | id, case_id, token, status | case_id | case_assignments |
| `case_requirements_snapshots` | Frozen requirements per case | id, case_id, dest_country, snapshot_json | case_id | wizard_cases |

#### **User & Profile Domain**
| Table | Purpose | Key Fields | Foreign Keys | Linked Tables |
|-------|---------|------------|--------------|---------------|
| `users` | Auth users (legacy) | id, username, email | — | sessions, profiles |
| `profiles` | User profiles (Supabase) | id, role, email | auth.users | — |
| `profile_state` | Profile JSON state | user_id, profile_json | — | — |
| `admin_allowlist` | Admin email allowlist | email, enabled | — | — |
| `admin_sessions` | Impersonation sessions | token, actor_user_id, target_user_id | — | — |
| `sessions` | Token sessions (legacy) | token, user_id | — | — |

#### **Intake & Answers Domain**
| Table | Purpose | Key Fields | Foreign Keys | Linked Tables |
|-------|---------|------------|--------------|---------------|
| `answers` | Legacy question answers | user_id, question_id, answer_json | — | — |
| `employee_answers` | Per-assignment answers | assignment_id, question_id, answer_json | assignment_id | case_assignments |
| `employee_profiles` | Per-assignment profile | assignment_id, profile_json | assignment_id | case_assignments |
| `dossier_questions` | Dynamic questions by country/domain | destination_country, domain | — | dossier_answers |
| `dossier_answers` | Case dossier answers | case_id, user_id | — | — |
| `dossier_case_questions` | Custom case questions | case_id, question_text | — | — |
| `dossier_case_answers` | Custom case answers | case_id, user_id | — | — |
| `dossier_source_suggestions` | Suggested sources | case_id, destination_country | — | — |

#### **Compliance & HR Domain**
| Table | Purpose | Key Fields | Foreign Keys | Linked Tables |
|-------|---------|------------|--------------|---------------|
| `compliance_reports` | Compliance report JSON | assignment_id, report_json | assignment_id | case_assignments |
| `compliance_runs` | Run history | assignment_id, report_json | assignment_id | case_assignments |
| `compliance_actions` | HR compliance actions | assignment_id, check_id, action_type | assignment_id | case_assignments |
| `eligibility_overrides` | Category overrides | assignment_id, category, allowed | assignment_id | case_assignments |
| `policy_exceptions` | Policy exception requests | assignment_id, category | assignment_id | case_assignments |
| `hr_policies` | Policy configuration | id, policy_json, status | — | — |
| `hr_feedback` | HR feedback per assignment | assignment_id, hr_user_id | assignment_id | case_assignments |
| `case_feedback` | Wizard case feedback | case_id, assignment_id | case_id, assignment_id | wizard_cases, case_assignments |

#### **Resources & Knowledge Domain**
| Table | Purpose | Key Fields | Foreign Keys | Linked Tables |
|-------|---------|------------|--------------|---------------|
| `country_profiles` | Country research cache | id, country_code, confidence_score | — | — |
| `requirement_items` | Country requirements | id, country_code, purpose, pillar, required_fields_json | — | — |
| `requirement_entities` | Structured requirements | destination_country, domain_area | — | requirement_facts |
| `requirement_facts` | Facts (eligibility, document, step, fee) | entity_id, fact_type | entity_id | requirement_entities |
| `requirement_reviews` | Requirement review state | entity_id | entity_id | requirement_entities |
| `source_records` | Research sources | id, country_code, url, content_hash | — | — |
| `research_source_candidates` | Pending research | id, country_code, status | — | — |
| `resource_categories` | Category taxonomy | key, label | — | country_resources |
| `resource_sources` | Source metadata | source_name, publisher | — | — |
| `resource_tags` | Tag taxonomy | key, label | — | country_resource_tags |
| `country_resources` | Published resources | id, country_code, status, trust_tier | category_id, source_id | country_resource_tags |
| `country_resource_sections` | Legacy sections | country_code, city | — | country_resource_items |
| `country_resource_items` | Legacy items | section_id, item_type | section_id | country_resource_sections |
| `country_events` | Events (legacy) | country_code, city | — | — |
| `rkg_country_events` | RKG events | country_code, city_name, event_type | — | — |
| `country_resource_tags` | Resource–tag join | resource_id, tag_id | resource_id, tag_id | country_resources |
| `case_resource_preferences` | Case budget/preferences | case_id, preferred_budget_tier | case_id | wizard_cases |

#### **Staging & Crawl Domain**
| Table | Purpose | Key Fields | Foreign Keys | Linked Tables |
|-------|---------|------------|--------------|---------------|
| `crawl_runs` | Crawl job runs | id, started_at, finished_at, status | — | crawled_source_documents, staged_* |
| `crawl_schedules` | Crawl schedules | id, schedule_expression, country_code | — | — |
| `crawled_source_documents` | Fetched documents | id, crawl_run_id, source_name, change_type | crawl_run_id | crawled_source_chunks |
| `crawled_source_chunks` | Document chunks | id, document_id, chunk_index | document_id | staged_resource_candidates |
| `staged_resource_candidates` | Extracted resources (pre-publish) | id, country_code, status, confidence_score | crawl_run_id, document_id | review_queue_items |
| `staged_event_candidates` | Extracted events (pre-publish) | id, country_code, status | crawl_run_id, document_id | review_queue_items |
| `staging_review_audit_log` | Staging actions | entity_type, entity_id, action_type | — | staged_* |
| `document_change_events` | Change detection | — | — | review_queue_items |

#### **Review Queue & Ops Domain**
| Table | Purpose | Key Fields | Foreign Keys | Linked Tables |
|-------|---------|------------|--------------|---------------|
| `review_queue_items` | Unified ops queue | id, queue_item_type, status, priority_band | related_staged_*, related_live_* | staged_*, country_resources |
| `review_queue_activity_log` | Queue activity | queue_item_id, action_type, previous_status | queue_item_id | review_queue_items |

#### **Notifications Domain**
| Table | Purpose | Key Fields | Foreign Keys | Linked Tables |
|-------|---------|------------|--------------|---------------|
| `notifications` | In-app notifications | id, user_id, notification_type | — | — |
| `notification_preferences` | User preferences | user_id, type, in_app | auth.users | — |
| `notification_outbox` | Delivery tracking | notification_id | notifications | — |
| `collaboration_notifications` | Thread mentions/replies | — | — | collaboration_threads |
| `ops_notification_config` | Ops notification config | — | — | — |

#### **Guidance & Knowledge Packs Domain**
| Table | Purpose | Key Fields | Foreign Keys | Linked Tables |
|-------|---------|------------|--------------|---------------|
| `knowledge_packs` | Knowledge packs | id, destination_country, domain | — | knowledge_docs, knowledge_rules |
| `knowledge_docs` | Pack documents | pack_id, title | pack_id | knowledge_packs |
| `knowledge_rules` | Pack rules | pack_id, rule_key | pack_id | knowledge_packs |
| `relocation_guidance_packs` | Per-case guidance | case_id, user_id | — | — |
| `relocation_trace_events` | Trace events | trace_id, case_id | — | — |
| `rule_evaluation_logs` | Rule eval logs | trace_id, case_id | — | — |
| `knowledge_doc_ingest_jobs` | Ingest jobs | id, url, status | candidate_id | — |

#### **Support & Admin Domain**
| Table | Purpose | Key Fields | Foreign Keys | Linked Tables |
|-------|---------|------------|--------------|---------------|
| `companies` | Companies | id, name, country | — | employees, hr_users |
| `employees` | Employee records | id, company_id, profile_id | company_id | companies |
| `hr_users` | HR user records | id, company_id | company_id | companies |
| `support_cases` | Support tickets | id, company_id, status | company_id | support_case_notes |
| `support_case_notes` | Support notes | support_case_id | support_case_id | support_cases |
| `audit_log` | Audit trail | actor_user_id, action_type, target_type | — | — |
| `messages` | Legacy messages | assignment_id | assignment_id | case_assignments |
| `resource_audit_log` | Resource audit | entity_type, entity_id | — | — |

#### **Collaboration Domain**
| Table | Purpose | Key Fields | Foreign Keys | Linked Tables |
|-------|---------|------------|--------------|---------------|
| `collaboration_threads` | Admin collaboration | target_type, target_id | — | collaboration_comments |
| `collaboration_comments` | Thread comments | thread_id, author_user_id | thread_id | collaboration_threads |

---

### Canonical Entities
- **Case**: `wizard_cases` (primary), `relocation_cases` (legacy), `relocation_navigator.relocation_cases` (Supabase)
- **Employee/Assignment**: `case_assignments` is the canonical join between case and employee
- **Document**: `crawled_source_documents`, `knowledge_docs`, `source_records` — no single document entity
- **Resource**: `country_resources` (live), `staged_resource_candidates` (pre-publish)

### Duplicated Entities
- **Case**: `wizard_cases`, `relocation_cases`, `relocation_navigator.relocation_cases` — three case representations
- **Country events**: `country_events`, `rkg_country_events` — overlapping event models
- **Country resources**: `country_resource_sections` + `country_resource_items` (legacy) vs `country_resources` (RKG module)

### Workflow State Tables
- `case_assignments.status` — assignment lifecycle
- `wizard_cases.status` — case draft state
- `review_queue_items.status` — queue workflow
- `staged_resource_candidates.status` / `staged_event_candidates.status` — staging workflow
- `hr_policies.status` — policy draft
- `knowledge_doc_ingest_jobs.status` — ingest jobs
- `crawl_runs` — job run state (queued, running, succeeded, failed)
- `ops_notification` / `collaboration_notifications` — notification status

---

## 3. WORKFLOW MODEL

### Status Fields and State Machines

| Entity | Status Field | Values | Location |
|--------|--------------|--------|----------|
| **case_assignments** | `status` | DRAFT, IN_PROGRESS, EMPLOYEE_SUBMITTED, HR_REVIEW, HR_APPROVED, CHANGES_REQUESTED, HR_REJECTED, CLOSED | `main.py` normalize_status, RPC `transition_assignment` |
| **Assignment (canonical)** | — | created, assigned, awaiting_intake, submitted, approved, rejected, closed | `schemas.AssignmentStatus` |
| **wizard_cases** | `status` | created (default) | `app/models.Case` |
| **review_queue_items** | `status` | new, triaged, assigned, in_progress, blocked, waiting, resolved, rejected, deferred | `review_queue.sql`, `ops_analytics_service` |
| **staged_resource_candidates** | `status` | new, deduped, needs_review, approved_for_import, rejected, approved_new, approved_merged, duplicate, ignored, error | `crawler_staging_tables.sql`, `staging_review_workflow.sql` |
| **staged_event_candidates** | `status` | (same as staged_resource) | Same |
| **resource_status (country_resources)** | — | draft, in_review, approved, published, archived | `resources_module_full_schema.sql` |
| **crawl_runs** | — | queued, running, succeeded, failed, partial_success | `crawl_scheduler_service` |
| **knowledge_doc_ingest_jobs** | `status` | queued, … | `app/models.KnowledgeDocIngestJob` |
| **research_source_candidates** | `status` | pending | `app.models.ResearchSourceCandidate` |
| **hr_policies** | `status` | draft | `remote_schema.sql` |
| **ops_notifications / collaboration** | `status` | open, acknowledged, resolved, suppressed | `ops_notification_service` |
| **assignment_invites** | `status` | — | Text, not enum |

### Progress / Step Fields
- **Wizard steps**: Frontend `WizardSidebar` 5 steps; `ServicesFlowContext` for services flow
- **Readiness**: `ReadinessStatus` (GREEN, AMBER, RED) in `readiness_rater.py`
- **Requirement status**: `statusForCase` = MISSING, PROVIDED, NEEDS_REVIEW in `requirements_builder`
- **Intake progress**: `progress.percentComplete` from `IntakeOrchestrator.get_next_question`

---

## 4. CORE BUSINESS OBJECTS

| Object | Definition | Relations |
|--------|------------|-----------|
| **Case** | Relocation case: origin → destination, purpose, dates. Stored in `wizard_cases.draft_json` or `relocation_cases.profile_json`. | Has assignments, requirements snapshots, guidance packs, resource preferences |
| **Employee** | Person being relocated. Identified by `employee_user_id` or `employee_identifier` on assignment. | Assigned to case via `case_assignments` |
| **Relocation** | End-to-end move; often used interchangeably with "case" in API/routes. | Same as Case |
| **Document** | Not a first-class entity. Appears as: crawled docs, knowledge docs, source records, HR policy uploads. | Used for extraction, research, guidance |
| **Service** | Relocation service category (housing, movers, schools, etc.). Backed by `case_services`, RFQ, recommendations. | Tied to assignment; recommendations from seed data |
| **Provider** | External service provider. In seed data (movers, schools); not a dedicated table. | Referenced in recommendations |
| **Visa rule** | Part of `requirement_items` / `requirement_facts` (eligibility, document, step). | Country + purpose scoped |
| **Task** | No dedicated task entity. Approximations: `review_queue_items`, compliance checks, wizard steps. | Queue items = operational tasks |
| **Resource** | Country-specific content (guide, event). `country_resources` (live), `staged_resource_candidates` (staging). | Category, tags, source |
| **Event** | Time-bound resource. `rkg_country_events`, `staged_event_candidates`. | Country, city, event_type |

---

## 5. API STRUCTURE

| Prefix | Domain | Backend Module | Notes |
|--------|--------|----------------|-------|
| `/` | Root | main.py | Health, debug |
| `/api/auth/*` | Auth | main.py | register, login, logout |
| `/api/admin/*` | Admin | main.py, admin_resources, admin_staging, admin_freshness, admin_review_queue, admin_notifications, admin_ops_analytics, admin_collaboration | Context, impersonate, companies, users, support, actions |
| `/api/cases/*` | Cases | app/routers/cases | GET/PATCH case, research, requirements, create |
| `/api/profile/*` | Profile | main.py | current, next-question, answer, complete |
| `/api/employee/*` | Employee | main.py | assignments, journey, submit, photo, messages |
| `/api/hr/*` | HR | main.py | cases, assignments, feedback, compliance, policy |
| `/api/dashboard` | Dashboard | main.py | KPI tiles |
| `/api/recommendations/*` | Recommendations | app/recommendations/router | categories, {category}/schema, POST {category} |
| `/api/resources/*` | Resources | routes/resources | country, page, context, recommendations |
| `/api/relocation/*` | Relocation | routes/relocation | Case CRUD via Supabase |
| `/api/dossier/*` | Dossier | main.py | questions, answers, search-suggestions, case-questions |
| `/api/guidance/*` | Guidance | main.py | generate, latest, trace, explain |
| `/api/requirements/*` | Requirements | main.py | sufficiency |
| `/api/services/*` | Services | main.py | answers, employee assignment services |
| `/api/rfqs` | RFQ | main.py | Create RFQ |
| `/relocation/*` | Relocation (alt) | routes/relocation | Non-API prefix |
| `/api/admin/review-queue/*` | Review Queue | app/routers/admin_review_queue | List, assign, resolve, defer |
| `/api/admin/staging/*` | Staging | app/routers/admin_staging | List/approve/merge/reject staged candidates |
| `/api/admin/freshness/*` | Freshness | app/routers/admin_freshness | Overview, crawl schedules, job runs |
| `/api/admin/.../crawl/*` | Crawl | admin_freshness.crawl_router | Schedules, job runs |
| `/api/admin/.../changes/*` | Changes | admin_freshness.changes_router | Document changes |
| `/api/relocation/classify/*` | Classification | routes/relocation_classify | Case classification |

---

## 6. AI SYSTEM

**There is no AI/LLM integration in the codebase.**

### What Exists (Deterministic)
- **Agents**: Rule-based components in `backend/agents/`:
  - `IntakeOrchestrator`: Question flow, dependencies, completion
  - `ProfileValidator`: Required-field validation
  - `ReadinessRater`: 0–100 score, GREEN/AMBER/RED
  - `RecommendationEngine`: Scoring from seed data (housing, schools, movers)
- **Policy extraction**: `policy_extractor.py` — keyword/regex on DOCX/PDF (python-docx, pdfplumber)
- **Compliance engine**: `compliance_engine.py` — deterministic rule checks
- **Dossier**: `dossier.py` — rule-based `evaluate_applies_if`, no LLM
- **Guidance pack**: `guidance_pack_service.py` — rule evaluation over knowledge rules; no prompts

### Potential AI Extension Points
- Policy extraction could use LLM for unstructured policy text
- Dossier Q&A could add RAG over `source_records` / `knowledge_docs`
- Requirements builder could use LLM for extraction from official sources
- `extraction_method` on staged candidates includes `llm_structured_extraction` (placeholder)

---

## 7. DOMAIN BOUNDARIES

| Domain | Boundaries | Coupling |
|--------|------------|----------|
| **Case Management** | wizard_cases, case_assignments, relocation flows | Strong: assignments drive employee journey, HR review |
| **Compliance Rules** | requirement_items, requirement_entities, requirement_facts, compliance_* | Couples to case (dest_country, purpose) and assignment |
| **Document Processing** | crawled_*, staged_*, document_change_events | Couples to resources, review queue |
| **Services Marketplace** | case_services, RFQ, recommendations (seed) | Couples to assignment; no provider DB |
| **Resources Knowledge Base** | country_resources, staged_*, rkg_country_events | Split: legacy sections/items vs RKG module; crawl feeds staging |
| **User Management** | users, profiles, sessions, admin_allowlist | Used by all domains for auth |
| **Ops / Review Queue** | review_queue_items, ops_notifications | Couples staging, freshness, support |

### Cross-Domain Coupling
- **Case ↔ Assignment**: Assignment is the main join; status drives UI flows
- **Resources ↔ Staging**: Staged candidates become country_resources on approve
- **Review Queue ↔ Staging/Freshness/Support**: Queue items reference staged_*, change events, alerts
- **Requirements ↔ Case**: Computed from case dest_country + purpose + draft

---

## 8. CONWAY RISKS

### 1. Duplicated Workflow States
- **Assignment status**: Legacy (DRAFT, EMPLOYEE_SUBMITTED, HR_REVIEW…) vs canonical (created, assigned, submitted…). Normalization in main.py; RPC still uses legacy transitions.
- **Resource status**: `resource_status` enum vs `staged_*_candidates.status` freeform text — different lifecycles.

### 2. UI-Driven Data Models
- `wizard_cases.draft_json` and `relocation_cases.profile_json` are JSON blobs shaped by wizard steps and intake questions.
- `case_assignments` has both `employee_identifier` and `employee_user_id` — identifier-first for invite flow.
- Requirements `statusForCase` (MISSING, PROVIDED) is computed per request, not stored.

### 3. Multiple Sources of Truth
- **Case**: wizard_cases (app/crud), relocation_cases (legacy), relocation_navigator (Supabase).
- **Country content**: country_resource_sections/items vs country_resources vs rkg_country_events.
- **Requirements**: requirement_items (static) vs requirement_entities/facts (structured) vs computed per case.

### 4. Cross-Domain Table Dependencies
- `review_queue_items` has 6+ optional FKs (staged_resource, staged_event, change_event, live_resource, live_event, alert) — queue is a hub for many domains.
- `case_assignments` is referenced by compliance, feedback, eligibility, policy exceptions, messages.

### 5. Features Not Anchored to a Core Object
- **Support cases**: Tied to company, not to relocation case.
- **Ops notifications**: Can reference queue items, staging, but config is separate.
- **Collaboration threads**: Target_type/target_id polymorphic — can attach to many entities.

---

## 9. ARCHITECTURE DIAGRAM (TEXT)

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React + Vite)                      │
│  Landing | Auth | Employee Journey | HR Dashboard | Services | Admin │
└─────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         API LAYER (FastAPI)                          │
│  main.py (legacy) | compat | cases | admin_* | resources | relocation│
└─────────────────────────────────────────────────────────────────────┘
                                      │
        ┌─────────────────────────────┼─────────────────────────────┐
        ▼                             ▼                             ▼
┌───────────────┐           ┌─────────────────┐           ┌─────────────────┐
│ Case Engine   │           │ Compliance      │           │ Resources       │
│ (app/crud,    │           │ Engine          │           │ Module          │
│  cases router)│           │ (deterministic) │           │ (RKG + legacy)  │
└───────┬───────┘           └────────┬────────┘           └────────┬────────┘
        │                            │                            │
        │    ┌───────────────────────┼───────────────────────┐    │
        │    ▼                       ▼                       ▼    │
        │  ┌─────────────┐   ┌─────────────┐   ┌─────────────────┐│
        │  │ Policy      │   │ Rules       │   │ Staging /       ││
        │  │ Engine      │   │ Engine      │   │ Crawl Pipeline  ││
        │  └─────────────┘   └─────────────┘   └────────┬────────┘│
        │                                               │         │
        │    ┌──────────────────────────────────────────┘         │
        │    ▼                                                    │
        │  ┌─────────────────┐   ┌─────────────────┐              │
        │  │ Review Queue    │   │ Ops Analytics   │              │
        │  │ Service         │   │ & Notifications │              │
        │  └────────┬────────┘   └────────┬────────┘              │
        │           │                     │                        │
        └───────────┴─────────────────────┴────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    DATABASE (SQLite / Postgres)                      │
│  wizard_cases | case_assignments | country_resources | staged_*     │
│  review_queue_items | compliance_* | notifications | ...            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 10. STRIPE-LIKE PLATFORM POTENTIAL

| Primitive | Reusability | Notes |
|-----------|-------------|-------|
| **Relocation case** | High | Core object; could be productized as "RelocationCase" with standard schema, webhooks |
| **Eligibility rules** | High | requirement_entities/facts + rules_engine already parameterized by country/purpose |
| **Documents** | Medium | Multiple doc types; unified "Document" with extraction pipelines could be a primitive |
| **Service quotes / RFQ** | Medium | RFQ exists but providers are seed data; add provider registry for marketplace |
| **Resources** | High | country_resources + staging workflow = content CMS; could expose as "Resource" API |
| **Policy engine** | High | hr_policies + policy_engine + policy_extractor = configurable policy layer |
| **Review queue** | High | Generic queue with assignee, SLA, resolution — could be "ReviewQueue" primitive |
| **Compliance checks** | Medium | Tied to assignment; could generalize to "ComplianceRun" on any subject |

### Platform Readiness
- **Strong**: Case, Resources, Policy, Review Queue — clear domains with APIs.
- **Moderate**: Requirements, Dossier, Guidance — need clearer abstraction boundaries.
- **Weak**: Services/RFQ — no provider entity; recommendations from static seed.
