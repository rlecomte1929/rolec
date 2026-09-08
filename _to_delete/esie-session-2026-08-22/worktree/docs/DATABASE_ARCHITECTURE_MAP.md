# Database Architecture Map

**ReloPass — Schema audit from Supabase migrations and backend schema files**

---

## 1. Table Catalog

### Case Management

| Table | Purpose | Primary Key | Foreign Keys | Main Columns |
|-------|---------|-------------|--------------|--------------|
| **wizard_cases** | Relocation case drafts (5-step wizard); canonical case for new flow | id | — | draft_json, origin_country, dest_country, purpose, target_move_date, status, requirements_snapshot_id |
| **relocation_cases** | Legacy relocation cases; profile-centric | id | — | hr_user_id, profile_json, company_id, employee_id, status, stage, host_country, home_country |
| **case_assignments** | HR assigns employee to case; primary assignment entity | id | case_id, hr_user_id | employee_user_id, employee_identifier, status, submitted_at, decision, risk_status, budget_limit |
| **assignment_invites** | Invite tokens for employees to claim assignments | id | case_id, hr_user_id | employee_identifier, token, status |
| **case_events** | Audit log for case/assignment events | id | case_id, assignment_id | actor_user_id, event_type, description |
| **case_requirements_snapshots** | Frozen requirements per case at creation | id | case_id | dest_country, purpose, snapshot_json, sources_json |
| **case_feedback** | HR section-specific feedback for employee | id | case_id→wizard_cases, assignment_id | author_user_id, section, message |

### User Identity

| Table | Purpose | Primary Key | Foreign Keys | Main Columns |
|-------|---------|-------------|--------------|--------------|
| **users** | Local auth users (username, email, password) | id | — | username, email, password_hash, role, name |
| **profiles** | Supabase profiles (role, company) | id | — | role, email, full_name, company_id |
| **sessions** | Token-based sessions | token | user_id | user_id, created_at |
| **admin_allowlist** | Admin access control by email | email | — | enabled, added_by_user_id |
| **admin_sessions** | Impersonation sessions | token | — | actor_user_id, target_user_id, mode |
| **profile_state** | User intake state (legacy) | user_id | — | profile_json, updated_at |

### Organizations

| Table | Purpose | Primary Key | Foreign Keys | Main Columns |
|-------|---------|-------------|--------------|--------------|
| **companies** | Tenant organizations | id | — | name, country, size_band, address, hr_contact |
| **employees** | Employee records | id | company_id, profile_id | band, assignment_type, relocation_case_id, status |
| **hr_users** | HR user records | id | company_id, profile_id | permissions_json |

### Documents & Intake

| Table | Purpose | Primary Key | Foreign Keys | Main Columns |
|-------|---------|-------------|--------------|--------------|
| **answers** | Legacy guided-question answers | id | user_id | question_id, answer_json, is_unknown |
| **employee_answers** | Employee answers per assignment | id | assignment_id | question_id, answer_json |
| **employee_profiles** | Employee profile JSON per assignment | assignment_id | — | profile_json, updated_at |

### Compliance & Policy

| Table | Purpose | Primary Key | Foreign Keys | Main Columns |
|-------|---------|-------------|--------------|--------------|
| **compliance_reports** | Compliance check results | id | assignment_id | report_json |
| **compliance_runs** | Raw compliance run outputs | id | assignment_id | report_json |
| **compliance_actions** | HR actions on compliance checks | id | assignment_id | check_id, action_type, actor_user_id |
| **eligibility_overrides** | HR overrides for eligibility | id | assignment_id | category, allowed, expires_at |
| **policy_exceptions** | Policy exception requests | id | assignment_id | category, status, requested_amount |
| **hr_policies** | Legacy HR policy config | id | — | policy_json, status, company_entity |
| **company_policies** | Company policy documents | id | company_id | title, file_url, extraction_status |
| **policy_benefits** | Extracted benefits from policies | id | policy_id | service_category, benefit_key, eligibility, limits |

### Messaging & Notifications

| Table | Purpose | Primary Key | Foreign Keys | Main Columns |
|-------|---------|-------------|--------------|--------------|
| **messages** | HR↔Employee messages | id | assignment_id, hr_user_id | subject, body, status |
| **notifications** | In-app user notifications | id | user_id | assignment_id, case_id, type, title, read_at |
| **notification_preferences** | User delivery preferences | (user_id, type) | user_id→auth.users | in_app, email, muted_until |
| **notification_outbox** | Delivery queue for notifications | id | notification_id | — |

### Support

| Table | Purpose | Primary Key | Foreign Keys | Main Columns |
|-------|---------|-------------|--------------|--------------|
| **support_cases** | Internal support tickets | id | company_id | created_by_profile_id, category, severity, status |
| **support_case_notes** | Notes on support cases | id | support_case_id | author_user_id, note |

### Immigration Knowledge

| Table | Purpose | Primary Key | Foreign Keys | Main Columns |
|-------|---------|-------------|--------------|--------------|
| **requirement_items** | Curated requirements (country, purpose, pillar) | id | — | country_code, purpose, pillar, title, severity, required_fields_json |
| **requirement_entities** | Structured requirement topics | id | — | destination_country, domain_area, topic_key, status |
| **requirement_facts** | Facts per entity (eligibility, document, step) | id | entity_id, source_doc_id | fact_type, fact_text, applies_to, status |
| **requirement_reviews** | Admin approval of entities/facts | id | entity_id, fact_id | reviewer_user_id, action |
| **country_profiles** | Country research metadata | id | — | country_code, last_updated_at, confidence_score |
| **source_records** | Retrieved source documents | id | — | country_code, url, title, content_hash |
| **research_source_candidates** | Pending research candidates | id | — | country_code, purpose, url, status |
| **knowledge_packs** | Curated knowledge by country/domain | id | — | destination_country, domain, status |
| **knowledge_docs** | Docs within packs | id | pack_id | title, source_url, text_content |
| **knowledge_rules** | Rules with guidance + citations | id | pack_id | rule_key, phase, category, guidance_md |
| **knowledge_doc_ingest_jobs** | Ingest job tracking | id | — | url, destination_country, status, error |

### Guidance & Dossier

| Table | Purpose | Primary Key | Foreign Keys | Main Columns |
|-------|---------|-------------|--------------|--------------|
| **relocation_guidance_packs** | Generated guidance per case | id | case_id, user_id | destination_country, profile_snapshot, plan, checklist, markdown |
| **relocation_trace_events** | Trace for guidance generation | id | — | trace_id, case_id, step_name, status, error |
| **rule_evaluation_logs** | Rule evaluation audit | id | — | trace_id, case_id, rule_key, result |
| **dossier_questions** | Dynamic questions by country/domain | id | — | destination_country, domain, question_key, applies_if |
| **dossier_answers** | Answers to dossier questions | id | case_id, question_id | user_id, answer |
| **dossier_case_questions** | Case-specific custom questions | id | case_id | question_text, answer_type, is_mandatory |
| **dossier_case_answers** | Answers to case questions | id | case_id, case_question_id | user_id, answer |
| **dossier_source_suggestions** | Search suggestions per case | id | case_id | destination_country, query, results |

### Relocation Artifacts (Legacy)

| Table | Purpose | Primary Key | Foreign Keys | Main Columns |
|-------|---------|-------------|--------------|--------------|
| **relocation_runs** | AI/classification runs per case | id | case_id→relocation_cases | run_type, input_payload, output_payload |
| **relocation_sources** | Sources per case | id | case_id | country, title, url, source_type |
| **relocation_artifacts** | Artifacts per case | id | case_id | artifact_type, content, content_text |

### Services & Vendors

| Table | Purpose | Primary Key | Foreign Keys | Main Columns |
|-------|---------|-------------|--------------|--------------|
| **case_services** | Service selections per case/assignment | id | case_id, assignment_id | service_key, category, selected, estimated_cost |
| **case_service_answers** | Service-specific answers | id | case_id | service_key, answers |
| **vendors** | Service providers | id | — | name, service_types, countries, status |
| **vendor_users** | Vendor user access | user_id | vendor_id | role |
| **service_recommendations** | Vendor recommendations per case | id | case_id, vendor_id | service_key, match_score |
| **case_vendor_shortlist** | Shortlisted vendors per case | id | case_id, vendor_id | service_key, selected |
| **rfqs** | Requests for quote | id | case_id, created_by_user_id | rfq_ref, status |
| **rfq_items** | Line items per RFQ | id | rfq_id | service_key, requirements |
| **rfq_recipients** | Vendors receiving RFQ | id | rfq_id, vendor_id | status |
| **quotes** | Vendor quotes | id | rfq_id, vendor_id | total_amount, status |
| **quote_lines** | Quote line items | id | quote_id | label, amount |
| **quote_conversations** | RFQ/quote threads | id | rfq_id | thread_type, case_id |
| **quote_participants** | Participants in quote threads | (conversation_id, user_id) | conversation_id, user_id | role |
| **quote_messages** | Messages in quote threads | id | conversation_id | sender_user_id, body |

### Resources (RKG + Legacy)

| Table | Purpose | Primary Key | Foreign Keys | Main Columns |
|-------|---------|-------------|--------------|--------------|
| **resource_categories** | Canonical resource sections | id | — | key, label, sort_order |
| **resource_sources** | Provenance/trust for resources | id | — | source_name, source_type, trust_tier |
| **resource_tags** | Tags for filtering | id | — | key, label, tag_group |
| **country_resources** | Live resource content (RKG) | id | category_id, source_id | country_code, city_name, title, resource_type, audience_type |
| **country_resource_tags** | M2M resource↔tag | id | resource_id, tag_id | — |
| **rkg_country_events** | Live events (RKG) | id | source_id | country_code, city_name, title, event_type, start_datetime |
| **country_resource_sections** | Legacy section-based content | id | — | country_code, city, section_key, content_json |
| **country_events** | Legacy events (simpler schema) | id | — | country_code, city, name, category, start_date |
| **country_resource_items** | Legacy items in sections | id | section_id | item_type, title, url |
| **case_resource_preferences** | User filter prefs per case | id | case_id | preferred_budget_tier, family_mode |
| **resource_audit_log** | CMS audit log | id | — | entity_type, entity_id, action |

### Crawl & Staging (Admin CMS)

| Table | Purpose | Primary Key | Foreign Keys | Main Columns |
|-------|---------|-------------|--------------|--------------|
| **crawl_runs** | Crawl execution runs | id | — | status, documents_fetched, chunks_created, resources_staged |
| **crawled_source_documents** | Fetched pages/documents | id | crawl_run_id | source_name, source_url, parse_status, extraction_status |
| **crawled_source_chunks** | Chunked document text | id | document_id | chunk_index, chunk_text |
| **staged_resource_candidates** | Extracted resource candidates | id | crawl_run_id, document_id | country_code, title, status, confidence_score, review_reason |
| **staged_event_candidates** | Extracted event candidates | id | crawl_run_id, document_id | country_code, title, status, start_datetime |
| **staging_review_audit_log** | Staging review actions | id | — | entity_type, entity_id, action_type, performed_by_user_id |
| **crawl_schedules** | Recurring crawl plans | id | — | name, schedule_expression, source_scope_type, next_run_at |
| **crawl_job_runs** | Scheduled/manual job runs | id | schedule_id, crawl_run_id | job_type, status, documents_fetched_count |
| **document_change_events** | Detected doc changes | id | job_run_id, source_document_id | source_name, change_type, change_score |
| **freshness_snapshots** | Aggregated freshness metrics | id | — | snapshot_scope_type, country_code, fresh_sources_count |
| **freshness_alerts** | Actionable freshness alerts | id | related_schedule_id, related_job_run_id | alert_type, severity, status |

### Review Queue & Ops

| Table | Purpose | Primary Key | Foreign Keys | Main Columns |
|-------|---------|-------------|--------------|--------------|
| **review_queue_items** | Unified ops queue | id | related_staged_*, related_change_*, related_live_*, related_alert_id | queue_item_type, status, priority_band, assigned_to_user_id |
| **review_queue_activity_log** | Queue item activity | id | queue_item_id | action_type, previous_status, new_status |
| **ops_notifications** | Admin notifications | id | related_queue_item_id, related_change_*, related_schedule_id | notification_type, severity, status, dedupe_key |
| **ops_notification_events** | Ops notification events | id | notification_id | event_type, actor_user_id |
| **audit_log** | General audit log | id | — | actor_user_id, action_type, target_type, target_id |

### Collaboration

| Table | Purpose | Primary Key | Foreign Keys | Main Columns |
|-------|---------|-------------|--------------|--------------|
| **collaboration_threads** | Threads on queue items, notifications, etc. | id | — | thread_target_type, thread_target_id, status |
| **collaboration_comments** | Comments with replies | id | thread_id, parent_comment_id | author_user_id, body |
| **collaboration_comment_mentions** | @mentions in comments | id | comment_id | mentioned_user_id |
| **collaboration_thread_participants** | Thread participation | id | thread_id | user_id, last_read_at, is_subscribed |
| **collaboration_notifications** | Notifications for mentions/replies | id | thread_id, comment_id | user_id, notification_type, read_at |

### Debug / Internal

| Table | Purpose | Primary Key | Foreign Keys | Main Columns |
|-------|---------|-------------|--------------|--------------|
| **rp_debug_kv** | Debug key-value store | id | — | key, value |

---

## 2. Domain Grouping

| Domain | Tables |
|--------|--------|
| **Case Management** | wizard_cases, relocation_cases, case_assignments, assignment_invites, case_events, case_requirements_snapshots, case_feedback |
| **User Identity** | users, profiles, sessions, admin_allowlist, admin_sessions, profile_state |
| **Organizations** | companies, employees, hr_users |
| **Documents** | answers, employee_answers, employee_profiles, crawled_source_documents, crawled_source_chunks |
| **Services** | case_services, case_service_answers, vendors, vendor_users, service_recommendations, case_vendor_shortlist, rfqs, rfq_items, rfq_recipients, quotes, quote_lines, quote_conversations, quote_participants, quote_messages |
| **Immigration Knowledge** | requirement_items, requirement_entities, requirement_facts, requirement_reviews, country_profiles, source_records, research_source_candidates, knowledge_packs, knowledge_docs, knowledge_rules, knowledge_doc_ingest_jobs |
| **Resources** | resource_categories, resource_sources, resource_tags, country_resources, country_resource_tags, rkg_country_events, country_resource_sections, country_events, country_resource_items, case_resource_preferences, resource_audit_log |
| **Admin CMS** | crawl_runs, crawled_source_documents, crawled_source_chunks, staged_resource_candidates, staged_event_candidates, staging_review_audit_log, crawl_schedules, crawl_job_runs, document_change_events, freshness_snapshots, freshness_alerts, review_queue_items, review_queue_activity_log, ops_notifications, ops_notification_events |
| **Compliance & Policy** | compliance_reports, compliance_runs, compliance_actions, eligibility_overrides, policy_exceptions, hr_policies, company_policies, policy_benefits |
| **Messaging** | messages, notifications, notification_preferences, notification_outbox |
| **Collaboration** | collaboration_threads, collaboration_comments, collaboration_comment_mentions, collaboration_thread_participants, collaboration_notifications |
| **Guidance & Dossier** | relocation_guidance_packs, relocation_trace_events, rule_evaluation_logs, dossier_questions, dossier_answers, dossier_case_questions, dossier_case_answers, dossier_source_suggestions |
| **Support** | support_cases, support_case_notes |
| **Legacy/Artifacts** | relocation_runs, relocation_sources, relocation_artifacts, relocation_tasks |

---

## 3. Duplicated Concepts

### case_id

`case_id` appears across multiple domains with **inconsistent semantics**:

| Table | case_id references | Notes |
|-------|--------------------|-------|
| case_assignments | Not formal FK; logically wizard_cases or legacy cases | Text; may be wizard_cases.id or relocation_cases.id |
| case_services | case_id, assignment_id | Text; both present |
| case_service_answers | case_id | Text |
| case_requirements_snapshots | case_id | VarChar |
| case_feedback | wizard_cases(id) | Formal FK |
| case_events | case_id (text) | No FK |
| case_resource_preferences | case_id (uuid) | No FK; type mismatch |
| dossier_* | case_id (text) | No formal FK |
| relocation_guidance_packs | case_id (uuid) | Type mismatch with text case_id |
| relocation_trace_events | case_id (uuid) | Same |
| rfqs | case_id (text) | No FK |

**Risk**: No single canonical case entity. `wizard_cases` vs `relocation_cases` vs `case_assignments` as "the case" is ambiguous.

### Events (duplicate models)

| Table | Purpose |
|-------|---------|
| **country_events** | Legacy; country/city/name/category |
| **rkg_country_events** | RKG; richer schema (start_datetime, event_type, is_family_friendly) |

### Resources (duplicate models)

| Table | Purpose |
|-------|---------|
| **country_resource_sections** + **country_resource_items** | Legacy section-based content |
| **country_resources** (RKG) | Entity-based; category_id, tags, audience_type |

### Requirements (duplicate models)

| Table | Purpose |
|-------|---------|
| **requirement_items** | Flat; country_code, purpose, pillar |
| **requirement_entities** + **requirement_facts** | Hierarchical; entity → facts |

---

## 4. Workflow Fields

### status

| Table | Values / Notes |
|-------|----------------|
| wizard_cases | created, (other wizard states) |
| case_assignments | DRAFT, IN_PROGRESS, EMPLOYEE_SUBMITTED, HR_REVIEW, HR_APPROVED, CHANGES_REQUESTED |
| assignment_invites | pending, claimed, expired |
| relocation_cases | (legacy) |
| employees | (assignment status) |
| hr_policies | draft, published |
| messages | draft, sent |
| support_cases | open, in_progress, resolved |
| research_source_candidates | pending, ingested |
| knowledge_doc_ingest_jobs | queued, running, completed, failed |
| knowledge_packs | active, inactive |
| requirement_entities | pending, approved, rejected |
| requirement_facts | pending, approved, rejected |
| vendors | active, pending |
| rfqs | draft, sent, closed |
| rfq_recipients | sent, viewed, replied, declined |
| quotes | proposed, accepted, rejected |
| crawl_runs | running, completed, failed, cancelled |
| crawled_source_documents | parse_status, extraction_status |
| staged_resource_candidates | new, deduped, needs_review, approved_for_import, rejected, approved_new, approved_merged |
| staged_event_candidates | (same as above) |
| crawl_job_runs | queued, running, succeeded, failed, cancelled |
| freshness_alerts | open, acknowledged, resolved |
| review_queue_items | new, triaged, assigned, in_progress, blocked, waiting, resolved, rejected, deferred |
| ops_notifications | open, acknowledged, resolved, suppressed |
| collaboration_threads | open, resolved |
| company_policies | extraction_status: pending, extracted, failed |

### stage

| Table | Notes |
|-------|-------|
| relocation_cases | stage (text) |

### approval_state / progress

| Table | Field | Notes |
|-------|-------|-------|
| case_assignments | decision | Approve / request changes |
| relocation_tasks | status | todo, in_progress, done, overdue |
| relocation_trace_events | status | ok, error |

---

## 5. Relational Diagram Summary

```
wizard_cases
 ├── case_assignments (case_id)
 ├── case_requirements_snapshots (case_id)
 ├── case_feedback (case_id)
 ├── case_services (case_id)
 ├── case_service_answers (case_id)
 ├── case_resource_preferences (case_id)
 ├── dossier_answers (case_id)
 ├── dossier_case_questions (case_id)
 ├── dossier_case_answers (case_id)
 ├── dossier_source_suggestions (case_id)
 ├── relocation_guidance_packs (case_id)
 ├── relocation_trace_events (case_id)
 ├── rfqs (case_id)
 └── case_events (case_id)

relocation_cases (legacy)
 ├── relocation_runs (case_id)
 ├── relocation_sources (case_id)
 └── relocation_artifacts (case_id)

case_assignments
 ├── employee_answers (assignment_id)
 ├── employee_profiles (assignment_id)
 ├── compliance_reports (assignment_id)
 ├── compliance_runs (assignment_id)
 ├── compliance_actions (assignment_id)
 ├── eligibility_overrides (assignment_id)
 ├── policy_exceptions (assignment_id)
 ├── case_services (assignment_id)
 ├── case_feedback (assignment_id)
 ├── case_events (assignment_id)
 ├── relocation_tasks (assignment_id)
 └── assignment_invites (case_id → case)

companies
 ├── employees (company_id)
 ├── hr_users (company_id)
 ├── company_policies (company_id)
 └── support_cases (company_id)

crawl_runs
 ├── crawled_source_documents (crawl_run_id)
 ├── staged_resource_candidates (crawl_run_id)
 └── staged_event_candidates (crawl_run_id)

crawled_source_documents
 ├── crawled_source_chunks (document_id)
 ├── staged_resource_candidates (document_id)
 ├── staged_event_candidates (document_id)
 └── document_change_events (source_document_id)

staged_resource_candidates
 ├── review_queue_items (related_staged_resource_candidate_id)
 └── staging_review_audit_log (entity_type+entity_id)

staged_event_candidates
 ├── review_queue_items (related_staged_event_candidate_id)
 └── staging_review_audit_log (entity_type+entity_id)

review_queue_items
 ├── ops_notifications (related_queue_item_id)
 ├── review_queue_activity_log (queue_item_id)
 └── collaboration_threads (thread_target_type+id)

country_resources (RKG)
 ├── country_resource_tags (resource_id)
 └── resource_audit_log (entity)

rkg_country_events
 └── resource_audit_log (entity)

knowledge_packs
 ├── knowledge_docs (pack_id)
 └── knowledge_rules (pack_id)

collaboration_threads
 ├── collaboration_comments (thread_id)
 ├── collaboration_thread_participants (thread_id)
 └── collaboration_notifications (thread_id)

collaboration_comments
 ├── collaboration_comment_mentions (comment_id)
 └── collaboration_notifications (comment_id)
```

---

## 6. Recommendations

1. **Unify case identity**: Choose one canonical case table (`wizard_cases` recommended) and add formal FKs. Migrate `relocation_cases` usage or deprecate.
2. **Resolve resource duality**: Consolidate `country_resource_sections`/`country_resource_items` with RKG or document migration path.
3. **Resolve events duality**: Consolidate `country_events` and `rkg_country_events`.
4. **Standardize case_id type**: Use uuid or text consistently; fix `case_resource_preferences`, `relocation_guidance_packs`, `relocation_trace_events` type mismatches.
5. **Document workflow state machines**: Create explicit state diagrams for case_assignments, review_queue_items, ops_notifications, staged_* status values.
