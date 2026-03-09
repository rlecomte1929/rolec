# Workflow Logic Report

**ReloPass — Workflow state models, transitions, and dependencies**

**Conclusion: The system has several independent workflow models, not a single unified one.**

---

## 1. Workflow State Models

| # | Model | States | Canonical Source |
|---|-------|--------|------------------|
| 1 | **Assignment (case_assignments)** | created, assigned, awaiting_intake, submitted, approved, rejected, closed | `schemas.AssignmentStatus` (backend), `types.AssignmentStatus` (frontend) |
| 2 | **Resources (country_resources)** | draft, in_review, approved, published, archived | `admin_resources._TRANSITIONS` |
| 3 | **Events (rkg_country_events)** | draft, in_review, approved, published, archived | Same as resources |
| 4 | **Review Queue (review_queue_items)** | new, triaged, assigned, in_progress, blocked, waiting, resolved, rejected, deferred, reopened | `review_queue_service._STATUS_TRANSITIONS` |
| 5 | **Ops Notifications** | open, acknowledged, resolved, suppressed | `ops_notification_service._STATUSES` |
| 6 | **Collaboration Threads** | open, resolved, closed | `collaboration_service` (implicit) |
| 7 | **Staged Candidates** | new, needs_review, approved_new, approved_merged, rejected, duplicate, ignored, error, approved_for_import, deduped | `staging_review_service._STAGING_STATUSES` |
| 8 | **Wizard Cases** | created (default) | `app.models.Case.status` |
| 9 | **Crawl Job Runs** | queued, running, succeeded, failed, cancelled, partial_success | `crawl_job_runs` table |
| 10 | **Crawl Runs** | running, completed, failed, cancelled | `crawl_runs` table |
| 11 | **Requirement Entities/Facts** | pending, approved, rejected | Migration check constraints |
| 12 | **RFQs** | draft, sent, closed | `rfqs` table |
| 13 | **Quotes** | proposed, accepted, rejected | `quotes` table |
| 14 | **Freshness (sources)** | fresh, stale, overdue, error | `crawl_scheduler_service.compute_source_freshness` |
| 15 | **HR Policies** | draft, published | `hr_policies` table |
| 16 | **Company Policies** | extraction_status: pending, extracted, failed | `company_policies` table |

---

## 2. Files Implementing Workflow Transitions

### Assignment

| File | What |
|------|------|
| `supabase/migrations/20260219194500_transition_assignment.sql` | RPC `transition_assignment` — EMPLOYEE_SUBMIT, EMPLOYEE_UNSUBMIT, HR_REOPEN |
| `supabase/migrations/20260219193000_reopen_unsubmit_functions.sql` | RPCs `employee_unsubmit_assignment`, `hr_reopen_assignment` |
| `backend/main.py` | `normalize_status()`, `assert_canonical_status()`, `set_assignment_submitted()`, `update_assignment_status()` |
| `backend/database.py` | `update_assignment_status()`, `set_assignment_submitted()` |

### Resources & Events (CMS)

| File | What |
|------|------|
| `backend/services/admin_resources.py` | `_can_transition()`, `_TRANSITIONS` dict; `submit_resource_for_review`, `approve_resource`, `publish_resource`, `archive_resource`, `restore_resource`; same for events |
| `backend/app/routers/admin_resources.py` | HTTP endpoints calling admin_resources transitions |

### Review Queue

| File | What |
|------|------|
| `backend/services/review_queue_service.py` | `_STATUS_TRANSITIONS`, `_validate_status_transition()`, `change_queue_item_status()`, `reopen_queue_item()` |
| `backend/app/routers/admin_review_queue.py` | Endpoints: status update, assign, resolve, defer, reopen |

### Ops Notifications

| File | What |
|------|------|
| `backend/services/ops_notification_service.py` | `acknowledge_notification()`, `resolve_notification()`, `suppress_notification()`, `reopen_notification()` |
| `backend/app/routers/admin_notifications.py` | HTTP endpoints for acknowledge, resolve, reopen |

### Collaboration Threads

| File | What |
|------|------|
| `backend/services/collaboration_service.py` | `resolve_thread()`, `reopen_thread()`, `close_thread()` |
| `backend/app/routers/admin_collaboration.py` | Endpoints for resolve, reopen, close |

### Staged Candidates

| File | What |
|------|------|
| `backend/services/staging_review_service.py` | `approve_resource_as_new()`, `approve_resource_merge()`, `reject_resource()`, etc. — updates status via direct Supabase update |
| `backend/app/routers/admin_staging.py` | Endpoints calling staging_review_service |

### Other

| File | What |
|------|------|
| `backend/services/crawl_scheduler_service.py` | `update_job_run_status()` |
| `backend/app/crud.py` | `update_research_candidate_status()`, `update_ingest_job_status()` |
| `backend/database.py` | `update_requirement_fact_status()` |

---

## 3. Controllers / Endpoints Updating State

| Domain | Router/File | Endpoints |
|--------|-------------|-----------|
| Assignment | `main.py` | `POST /api/hr/assignments/{id}/decision`, `POST /api/employee/assignments/{id}/submit`; RPCs via frontend |
| Resources | `admin_resources.py` | `POST .../submit-for-review`, `.../approve`, `.../publish`, `.../archive`, `.../restore` |
| Events | Same | Same pattern |
| Review Queue | `admin_review_queue.py` | `PATCH .../status`, `POST .../assign`, `POST .../resolve`, `POST .../defer`, `POST .../reopen` |
| Ops Notifications | `admin_notifications.py` | `POST .../acknowledge`, `POST .../resolve`, `POST .../reopen` |
| Collaboration | `admin_collaboration.py` | `POST .../threads/{id}/resolve`, `.../reopen`, `.../close` |
| Staging | `admin_staging.py` | `POST .../staging/resources/{id}/approve-as-new`, `.../reject`, etc. |

---

## 4. Tables Storing Workflow State

| Table | Status Column | Notes |
|-------|---------------|-------|
| case_assignments | status | Core assignment workflow |
| wizard_cases | status | Mostly "created"; minimal workflow |
| country_resources | status | CMS workflow |
| rkg_country_events | status | CMS workflow |
| review_queue_items | status | Review queue workflow |
| ops_notifications | status | Ops notification workflow |
| collaboration_threads | status | Thread lifecycle |
| staged_resource_candidates | status | Staging review |
| staged_event_candidates | status | Staging review |
| crawl_runs | status | Crawl execution |
| crawl_job_runs | status | Job run lifecycle |
| crawled_source_documents | parse_status, extraction_status | Per-document pipeline |
| requirement_entities | status | Admin approval |
| requirement_facts | status | Admin approval |
| rfqs | status | RFQ lifecycle |
| rfq_recipients | status | Vendor response |
| quotes | status | Quote lifecycle |
| hr_policies | status | Policy lifecycle |
| company_policies | extraction_status | Document extraction |
| assignment_invites | status | Invite lifecycle |
| messages | status | Message draft/sent |
| support_cases | status | Support ticket |
| freshness_alerts | status | Alert lifecycle |

---

## 5. UI Components Depending on State

### Assignment Status

| Component | Depends On | Usage |
|-----------|------------|-------|
| `CaseWizardPage.tsx` | assignmentStatus | Show wizard vs read-only; "awaiting_intake", "submitted", "approved", etc. |
| `HrAssignmentReview.tsx` | assignment.status | stageLabel: "Intake - Profile Review", "Approved", "Rejected", "In progress" |
| `HrCaseSummary.tsx` | assignment.status | statusBadge, reopen button visibility |
| `HrDashboard.tsx` | assignment.status | caseStatusBadge, filter by status |
| `CaseContextBar.tsx` | stage | Displays stage label |
| `EmployeeJourney.tsx` | (assignment) | Post-submission view |

### Resources / Events Status

| Component | Depends On | Usage |
|-----------|------------|-------|
| `ResourceRowActions.tsx` | status | VALID_TRANSITIONS: draft→submit, in_review→approve, approved→publish, etc. |
| `EventRowActions.tsx` | status | Same pattern |
| `AdminResourceEditor.tsx` | form.status | Show publish/approve UI when approved |
| `AdminResources.tsx` | — | Calls submit, approve via onAction |
| `AdminEvents.tsx` | status filter | Filter by approved, etc. |

### Review Queue Status

| Component | Depends On | Usage |
|-----------|------------|-------|
| `ReviewQueueStatusBadge.tsx` | status | STYLES for new, triaged, assigned, in_progress, blocked, waiting, resolved, rejected, deferred, reopened |
| `AdminReviewQueuePage.tsx` | byStatus | Group by status |
| `AdminReviewQueueDetailPage.tsx` | item.status | handleReopen, handleAssign, resolve, defer |
| `AdminReviewQueueWorkloadPage.tsx` | openStatuses | Filter open items |

### Staging Status

| Component | Depends On | Usage |
|-----------|------------|-------|
| `AdminStagingResourceDetail.tsx` | status | isApproved, handleApproveNew, handleReject |
| `AdminStagingEventDetail.tsx` | (same) | Same pattern |

### Ops Notifications Status

| Component | Depends On | Usage |
|-----------|------------|-------|
| `AdminNotificationDetailPage.tsx` | — | handleReopen, acknowledge, resolve |
| `AdminNotificationsPage.tsx` | status filter | List by status |

### Collaboration Status

| Component | Depends On | Usage |
|-----------|------------|-------|
| `InternalThreadPanel.tsx` | thread.status | reopenThread, "Thread closed — reopen to add comments", disable reply when closed |

### Crawl / Freshness Status

| Component | Depends On | Usage |
|-----------|------------|-------|
| `AdminCrawlJobRuns.tsx` | j.status | statusColor(), statusFilter |
| `AdminCrawlJobRunDetail.tsx` | job status | Display run state |

---

## 6. Transition Matrices

### Assignment (canonical)

```
created → assigned (assign)
assigned → awaiting_intake (employee claims)
awaiting_intake → submitted (employee submit)  [RPC EMPLOYEE_SUBMIT; DB writes EMPLOYEE_SUBMITTED then normalized]
submitted → awaiting_intake (employee unsubmit) [RPC EMPLOYEE_UNSUBMIT]
submitted → approved | rejected (HR decision)
submitted → awaiting_intake (HR reopen) [RPC HR_REOPEN]
approved → closed (HR)
rejected → closed (HR)
```

Legacy DB values (DRAFT, IN_PROGRESS, etc.) are normalized to canonical in `main.py`.

### Resources / Events

```
draft → in_review (submit_for_review)
in_review → approved | draft (approve | revert)
approved → published | draft (publish | revert)
published → archived (archive)
archived → approved (restore)
```

### Review Queue

```
new → triaged | assigned | rejected | deferred
triaged → assigned | rejected | deferred
assigned → in_progress | rejected | deferred
in_progress → blocked | waiting | resolved | rejected | deferred
blocked → in_progress | deferred
waiting → in_progress | resolved | deferred
resolved → reopened (→ new)
rejected → reopened (→ new)
deferred → new | triaged | assigned
```

### Ops Notifications

```
open → acknowledged (acknowledge)
acknowledged → resolved (resolve)
open → suppressed (suppress)
resolved | suppressed → open (reopen)
```

### Collaboration Threads

```
open → resolved (resolve)
open → closed (close)
resolved | closed → open (reopen)
```

---

## 7. Cross-Domain Workflow Coupling

| Coupling | Description |
|----------|-------------|
| **Ops Notifications ↔ Review Queue** | `sync_resolved_notifications()` auto-resolves notifications when linked queue item is resolved/rejected. Ops notifications created from queue items. |
| **Staged Candidates → Review Queue** | Queue items created for staged candidates; resolving queue item does not auto-update staged candidate status. |
| **Staged Candidates → country_resources/rkg_country_events** | Approve-as-new creates draft resource/event; approve-merge updates existing. |
| **Assignment ↔ Wizard** | Assignment status gates whether employee sees wizard (editable) or read-only; no shared state machine. |

---

## 8. Summary: Single vs Multiple Workflows

**The system has multiple independent workflow models.**

| Aspect | Finding |
|--------|---------|
| **State machines** | At least 10 distinct state machines with different states and transitions |
| **Shared engine** | No shared workflow engine; each domain implements its own transition logic |
| **Naming** | "status" used generically; semantics differ per table |
| **Reopen pattern** | reopen/unsubmit appears in assignment, review queue, ops notifications, collaboration — similar pattern, different implementations |
| **Approval pattern** | Resources, events, requirement entities, requirement facts, staging candidates all have approve/reject — no shared abstraction |
| **Normalization** | Only assignment has explicit `normalize_status()` for legacy compatibility |

**Recommendation**: For future consistency, consider a shared workflow/state-machine module with declarative transition rules, or at least document each workflow's state diagram in one place.
