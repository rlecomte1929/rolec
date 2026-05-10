# ReloPass — Implementation Plan for Claude Code

> **Purpose:** Every single modification or improvement to ReloPass MVP, ordered by priority, with the technical detail needed to execute through Claude Code.
> **Source:** Audit final synthesis (26 April 2026). Roadmap from §6 Missing Capabilities.
> **Scope note:** I don't have codebase access. File paths, function names, and exact schemas are educated guesses based on URLs, screenshots, and patterns observed in the audit. Each task starts with "explore + verify" to let Claude Code map the spec to your actual code.

---

## How to Use This Document

### Per task, you get:
- **Priority** (P0 ship-blocker / P1 / P2 / P3)
- **Goal** (one sentence)
- **Why it matters** (linked to audit verdict)
- **Acceptance criteria** (specific testable outcomes)
- **Technical approach** (what to do in code)
- **Schema changes** (database migrations where relevant)
- **Files likely involved** (probable paths — verify in your repo)
- **Dependencies** (what must ship first)
- **Test scenarios** (how to verify it works)
- **Effort estimate** (from audit, ±50%)
- **Claude Code starter prompt** (copy-paste ready)

### Workflow per task:
1. Pick the next task in priority order
2. Open Claude Code in your repo
3. Paste the starter prompt
4. Let CC explore the relevant files first
5. Review the proposed approach before letting CC implement
6. Run the test scenarios
7. Move to the next task

### Execution order:
- Run **Tier 0 (Spikes)** before committing to any Tier 1+ schedule
- Tier 1 in the listed order — sequencing has dependency logic baked in
- Tier 2/3/4 can be reordered based on customer signal

### Key principle:
**No task should ship without verifying the existing audit log captures the action being taken.** If you find an action that doesn't write to audit_log, treat that as part of the task — fix it.

---

## Tier 0 — Pre-Flight Architectural Spikes (Weeks 1-3)

> **Run these BEFORE committing to any Tier 1 schedule.** Spikes verify the architectural assumptions the audit verdict is conditional on. Output: single architectural-readiness report informing Tier 1 scope.
>
> Total verification effort ~3 weeks if run in parallel. The verdict drops from 3-4x to 2-3x if 2+ spikes return mixed results — still a winning verdict, just less aggressive.

### Spike 5 — Tenant Isolation + Audit Log Completeness

**Priority:** **P0 / EXISTENTIAL** — this is the only existential risk in the audit (R5).

**Goal:** Run the existing Prompts 0/A/B audit suite to verify tenant isolation correctness and audit log scope.

**Why it matters:** A cross-tenant data leak ends the company. M10 mid-market unlock (3 → 4 stakeholder confidence) requires verified audit log completeness.

**Acceptance criteria:**
- All three prompts (0/A/B) run successfully against a seeded multi-tenant test environment
- No cross-tenant data exposure detected (Tenant A user cannot see Tenant B data via any endpoint)
- Audit log captures: policy publish, policy version change, case create, case status change, package submit, exception request, HR approve/reject, document upload, message sent, denied actions (cross-tenant attempts, role violations)
- Each audit_log entry contains: actor_user_id, actor_role, organization_id, action, target_type, target_id, metadata (jsonb), status (success/denied/failed), timestamp
- Output: structured discovery report + ingestion report + behavior report

**Technical approach:**
1. Locate the existing Prompts 0/A/B in the project (`/mnt/user-data/uploads/` or in the repo)
2. Spin up a test environment with at least 2 tenants and seeded data
3. Run each prompt; capture output
4. For each gap surfaced, document: severity, affected endpoint, suggested fix
5. Triage: existential gaps fix immediately; cosmetic gaps go on Tier 1 backlog as M3

**Files likely involved:**
- Audit log middleware or service (probable paths: `src/lib/audit.ts`, `src/middleware/audit.ts`, or `src/services/auditLog.ts`)
- Tenant scoping middleware (probable: `src/middleware/auth.ts` or `src/lib/tenant.ts`)
- Database migrations (`prisma/schema.prisma` or `db/migrations/`)
- API routes that should be tenant-scoped (likely `src/pages/api/` or `src/app/api/`)

**Dependencies:** None. Run first.

**Effort:** 1-2 days verification + (0 if clean / 4-6 weeks if rebuild needed).

**Claude Code starter prompt:**
```
I need to run a comprehensive tenant isolation and audit log verification.
The audit prompt suite is in [path to Prompt 0/A/B documents — likely
project files or /mnt/user-data/uploads/].

Step 1: Read all three prompts and explain what they test.
Step 2: Map each test scenario to my actual codebase — for each, identify
the endpoint/function/middleware that should enforce isolation or write to
audit log.
Step 3: For each scenario, write or run an integration test that proves
the protection works.
Step 4: Document gaps with severity (existential/high/medium/cosmetic).
Step 5: For existential gaps only, propose minimal fixes I can review.

Don't implement fixes yet — just verify and report.
```

---

### Spike 2 — Task.due_date + Date Triggers Verification

**Priority:** P0 — 2 hours of work to verify; if absent, it's the highest-leverage Phase 1 build.

**Goal:** Verify whether `Task` entity has `due_date` and whether case-level date triggers (e.g., `case.target_end_date - 90 days`) are wired to a scheduler.

**Why it matters:** F8 (forgotten repat) mitigation depends entirely on this. Without due_date + triggers, the verdict on S7 collapses and the Command Center "Overdue Tasks" KPI cannot compute.

**Acceptance criteria:**
- Confirm presence/absence of `Task.due_date` column
- Confirm presence/absence of any cron/scheduler infrastructure (BullMQ, Inngest, Temporal, pg_cron, Sidekiq, or equivalent)
- Confirm whether any case-level date computation exists (e.g., assignment_end_date - 90 days)
- Output: 1-page verification report

**Technical approach:**
1. Search schema for any field matching `/due/i`, `/deadline/i`, `/expir/i` on Task or related tables
2. Search codebase for scheduler/cron imports (`bull`, `inngest`, `temporal`, `node-cron`, `pg_cron`, `sidekiq`)
3. Search for any computation pattern like `subDays`, `addMonths`, `subtract.*90` near case context

**Files likely involved:**
- Schema: `prisma/schema.prisma`, `db/schema.ts`, or migrations folder
- Tasks: `src/models/Task.*`, `src/services/tasks.*`
- Schedulers: `src/jobs/`, `src/queue/`, `src/scheduler/`

**Dependencies:** None.

**Effort:** 2 hours verification.

**Claude Code starter prompt:**
```
I need to verify whether my Task entity has a due_date field and whether
case-level date triggers exist.

Step 1: Search the schema (Prisma, Drizzle, raw SQL — whatever is used)
for Task model and list its fields.
Step 2: Search the codebase for any scheduler infrastructure
(BullMQ, Inngest, Temporal, node-cron, pg_cron, etc.).
Step 3: Search for any code that computes "X days/months before
[case end date / target date / arrival date]".
Step 4: Report a 1-page summary: present/absent for each, suggested
implementation if absent (use task T1.2 from this plan as the spec).
```

---

### Spike 3 — Case.contract_type / move_type Abstraction

**Priority:** P0 before committing option (b) delivery date.

**Goal:** Determine whether `Case.contract_type` (and proposed `move_type`) cleanly drive different downstream behavior in plan generation, policy application, services catalog, and resources — or whether they're labels only with hardcoded "international LTA" assumptions throughout.

**Why it matters:** F1 mitigation depends on `contract_type` being a real discriminator. Option (b) (domestic moves) requires `move_type` to propagate through 9+ subsystem touchpoints. Effort 3-4 wks if abstract, 6-8 wks if hardcoded.

**Acceptance criteria:**
- Trace `Case.contract_type` from creation through every subsystem
- Identify each hardcoded "international" assumption (visa task always generated, FX always shown, services filter assumes country mismatch, etc.)
- Document each subsystem touchpoint with: current behavior, required behavior for `contract_type=permanent_transfer`, required behavior for `move_type=domestic`
- Output: scoped implementation plan with realistic effort estimate

**Technical approach:**
1. Find Case entity definition; list contract_type/move_type fields
2. Find plan generation logic; identify how phases/tasks are seeded — is it template-driven or hardcoded?
3. Find policy application logic; identify how benefits filter by case context
4. Find services catalog filter; identify how services are shown/hidden per case
5. Find recommendations engine; identify destination/corridor assumptions
6. Find resources surfacing; identify destination filters
7. Find wizard logic; identify which steps are conditional vs always-shown

**Subsystem touchpoints to verify (from audit T9-T11 §C5):**

| Subsystem | What needs to discriminate on move_type/contract_type |
|---|---|
| Plan generation | Skip Immigration phase entirely for `domestic`; suppress repat tasks for `permanent_transfer` |
| Plan generation | Compress Pre-departure for domestic (no passport, no employment letter for visa) |
| Policy application | Suppress `tax_eq`, `cola_method`, `mobility_premium` benefits for inapplicable types |
| Services catalog | Filter visa/permits, international moving, customs for domestic |
| Recommendations | Domestic vendor data sets per region |
| Resources | Domestic content per region (Lyon school district, Lyon vendors) |
| Estimate Review | Single-currency, no FX, simpler math for domestic |
| Wizard | Skip or simplify Employee Profile step 2 (no passport for domestic) |
| Risk classification | Different criteria for domestic (no visa risk, etc.) |

**Files likely involved:**
- Schema: Case model
- Plan: `src/services/planGeneration.*`, `src/lib/casePlan.*`, possibly seed YAML files
- Policy: `src/services/policy.*`, `src/lib/benefitApplication.*`
- Services: `src/services/services.*`, services catalog config

**Dependencies:** None.

**Effort:** 3-5 days of architectural code review.

**Claude Code starter prompt:**
```
I need to map how Case.contract_type (and proposed move_type) flows
through my system. Goal is to determine whether these fields cleanly
drive downstream behavior or whether "international LTA" assumptions
are hardcoded.

Step 1: Find Case model. List all fields. Identify contract_type values
currently supported.
Step 2: Find plan generation. Trace: what determines which phases/tasks
get created? Is there any switching on contract_type?
Step 3: Find policy benefit application. Trace: how are benefits
suppressed based on case attributes?
Step 4: Find services catalog filtering. How do services get
shown/hidden per case?
Step 5: Find resources/destination data filtering.
Step 6: Find wizard step logic. Are any steps conditional on
contract_type or family size?

For each subsystem, report:
- Currently respects contract_type? (yes/no/partial)
- Estimated effort to add `move_type=domestic` discriminator (hours/days)
- Hardcoded "international" assumption flagged

Output: scoped implementation plan with total effort estimate.
```

---

### Spike 4 — Family / Dual-Career Signal Propagation

**Priority:** P1 — affects F11 mitigation; not ship-blocking.

**Goal:** Verify whether `spouse.wants_to_work = true` flag captured in wizard step 3 propagates to (a) destination resource surfacing, (b) services questionnaire, (c) policy application — or whether it's stored and never read.

**Why it matters:** F11 (family invisible) mitigation currently scored 62% conditional on this. If flag is stored-but-not-read, S2 family case verdict softens from 4x to 2.5-3x.

**Acceptance criteria:**
- Trace `spouse_wants_to_work` from wizard storage to all consumers
- For each consumer (resources, services questionnaire, policy), confirm: read or not read
- Output: gap report

**Technical approach:**
1. Find wizard step 3 (FamilyMember capture). Find where `spouse_wants_to_work` is stored
2. Search codebase for any read of that field — by exact name, snake_case, camelCase variants
3. For each read, document the consumer (resource filter, service surface, policy)
4. For each consumer that should read but doesn't, document the gap

**Files likely involved:**
- Wizard: `src/pages/wizard/[step]/`, `src/components/Wizard*`
- Family entity: `src/models/FamilyMember.*` or inline in Case
- Resources: `src/services/resources.*`, `src/lib/resourceFilter.*`
- Services: `src/services/services*`
- Policy: `src/services/policy.*`

**Dependencies:** None.

**Effort:** Half-day verification.

**Claude Code starter prompt:**
```
I need to trace how the "spouse wants to work" flag captured in
wizard step 3 propagates through the system.

Step 1: Find FamilyMember model and the spouse_wants_to_work field.
Step 2: Search the entire codebase for reads of that field.
List every consumer.
Step 3: For each of these expected consumers, report read/not-read:
  - Resources/destination content filtering (e.g., Madrid job-search
    support surfacing for Pierre)
  - Services questionnaire (asking spouse-specific questions)
  - Policy benefit application (spouse-support benefits visible)
  - Recommendations (spouse career-relevant content)

Step 4: Document gaps. Output: 1-page report.
```

---

### Spike 1 — Destination Data Depth Audit

**Priority:** P0 before MVP launch positioning is locked.

**Goal:** Score each non-Singapore destination's content depth against Singapore-as-reference (5/5). Identify the 2-3 corridors closest to Singapore depth for MVP narrow positioning.

**Why it matters:** SME and mid-market international scoring degrades by ~0.5 per metric if destinations beyond Singapore are thin. Verdict drops 3-4x → 2-3x.

**Acceptance criteria:**
- Each candidate destination scored 0-5 on: vendor coverage (movers/schools/neighborhoods), corridor watchouts, cost data freshness, curated resources count
- Top 2-3 destinations identified for MVP narrow positioning
- Per-destination gap list (what content needs to be added to reach Singapore parity)
- Output: destination readiness report

**Technical approach:**
1. List all destinations currently in the system (query Resource/Vendor/Recommendation tables)
2. For each, count: movers, schools, neighborhoods, resources by category, cost data points
3. Compare to Singapore baselines (audit observation: 10 movers, 10 schools, 10 neighborhoods, 12 resource categories)
4. Score each destination 0-5 against Singapore 5/5
5. Recommend launch corridors

**Singapore reference (from audit T3):**
- Movers: 10 vendors with rating, lead time, distance, capacity
- Schools: 10 with fees, currency, application deadline, rating, commute analysis
- Neighborhoods: 10 with safety, green, monthly cost, commute time, lifestyle scoring
- Resources: 12+ categories (admin, community, cost_of_living, daily_life, healthcare, housing, nature, overview, schools_childcare, transport, events, local_culture)
- EP-specific watchouts visible in case detail

**Files likely involved:**
- Resource/Vendor/Recommendation seed files (likely YAML/JSON in `seeds/` or `db/seed/`)
- Admin tooling for destinations (likely `src/pages/admin/destinations/` or similar)

**Dependencies:** None.

**Effort:** 1-2 weeks (mostly content-team work, not engineering).

**Claude Code starter prompt:**
```
I need to audit destination data depth across my product.
Singapore is the showcase destination — I need to know which other
destinations approach Singapore depth.

Step 1: Query the database (or read seed files) to list all destinations
currently with content.
Step 2: For each destination, count:
  - Movers (vendors)
  - Schools
  - Neighborhoods
  - Resources by category (cost_of_living, healthcare, housing, etc.)
  - Cost data points (whether amounts are populated and current)
Step 3: Score each destination 0-5 against Singapore as reference 5/5.
Step 4: Recommend the top 2-3 destinations for MVP narrow positioning.
Step 5: For those 2-3, list what's missing to reach Singapore parity.

Output: destination readiness report.
```

---

## Tier 1 — P0 Critical Path (Weeks 4-12)

> Phase 1 work. Ship-blocking for MVP launch positioning. Total ~12-17 weeks engineering, parallelizable to ~6-9 wall-clock weeks with 2-3 engineers.
>
> **Sequencing logic:**
> - 1.1 (audit gap remediation) blocks nothing but informs everything
> - 1.2 (due_date) is cheap and unblocks 1.8 (Command Center)
> - 1.3 (ExceptionRequest) blocks 1.5 (Estimate Review)
> - 1.4 (FX) blocks 1.5 (Estimate Review)
> - 1.5 (Estimate Review) is the killer screen — depends on 1.3, 1.4
> - 1.6 (Employee Dashboard) is independent — can ship in parallel
> - 1.7, 1.9, 1.10, 1.11 are quick wins — ship anytime

---

### T1.1 — Audit Log Gap Remediation

**Priority:** P0. Foundation of M10 mid-market unlock.

**Goal:** Close any gaps surfaced by Spike 5 in audit_log coverage and tenant isolation.

**Acceptance criteria:**
- Every state-changing action writes to audit_log
- Every denied action (cross-tenant, role violation, prompt injection attempt) is logged
- Tenant isolation tests pass in CI/CD
- Audit log queryable by case_id, organization_id, actor_user_id, time range
- Audit log export functionality (JSON or CSV) for compliance audits

**Technical approach:**
1. Use Spike 5 output as the gap list
2. For each action missing audit_log write, add a write call (likely a middleware decorator or service-layer interceptor)
3. For each isolation gap, add tenant scoping at the query layer
4. Add CI tests for tenant isolation (cannot be skipped)

**Schema changes (if AuditLog entity needs strengthening):**

```sql
-- Likely already exists; verify these columns:
audit_log:
  id: uuid PRIMARY KEY
  organization_id: uuid NOT NULL  -- denormalized for query performance
  actor_user_id: uuid NULL  -- null for system actions
  actor_role: text NOT NULL  -- 'hr' | 'employee' | 'admin' | 'system'
  action: text NOT NULL  -- 'policy.published', 'case.status_changed', etc.
  target_type: text NOT NULL  -- 'Policy', 'Case', etc.
  target_id: uuid NOT NULL
  metadata: jsonb  -- before/after for state changes
  status: text NOT NULL  -- 'success' | 'denied' | 'failed'
  ip_address: text NULL
  user_agent: text NULL
  created_at: timestamp NOT NULL

INDEX (organization_id, created_at DESC)
INDEX (target_type, target_id)
INDEX (actor_user_id, created_at DESC)
```

**Files likely involved:**
- `src/lib/audit.ts` or similar — audit log write helper
- `src/middleware/withAudit.ts` — middleware decorator
- All API route handlers — verify they call audit
- Database migrations

**Dependencies:** Spike 5 output.

**Effort:** 0 (if Spike 5 returns clean) or 4-6 wks remediation.

**Test scenarios:**
- Create a case → verify audit_log entry with action='case.created'
- Publish a policy → verify entry with before/after policy snapshot in metadata
- HR-A from Tenant A attempts to read Case from Tenant B via API → returns 403/404; entry with status='denied'
- HR attempts to delete an audit_log entry → not possible (audit log is append-only)

**Claude Code starter prompt:**
```
Based on Spike 5 output [paste the gap list], close audit log gaps.

For each gap:
1. Identify the API endpoint/service function that performs the action
2. Add audit_log write at the appropriate layer
3. Ensure organization_id is captured (tenant scoping)
4. Add an integration test that verifies the audit entry is written
5. Add an integration test for the denied case (cross-tenant attempt)

After all gaps are closed, add a CI job that runs the Prompt 0/A/B
audit suite on every PR. Tenant isolation must not regress.
```

---

### T1.2 — Task.due_date + Date Triggers

**Priority:** P0. Highest leverage per engineering week.

**Goal:** Add `due_date` field to Task entity. Wire case-level date triggers (repat 90-day pre-end, document expiry warnings, deadline alerts) to a scheduler.

**Why it matters:** F8 (forgotten repat) mitigation depends entirely on this. Command Center "Overdue Tasks", "Departing Soon", "At Risk" KPIs depend on date logic.

**Acceptance criteria:**
- `Task.due_date` field exists; nullable; populated by template default OR HR-set OR derived from case date
- Tasks render in UI with due_date when set; styled differently when overdue
- A scheduler fires CaseTriggers reliably (idempotent — same trigger fires once per case-date)
- 90 days before `case.target_end_date`: Repat phase activates with associated tasks
- Document expiry: 60 days before passport expires → task created reminding employee to renew
- Command Center shows: count of overdue tasks per HR, count of cases departing in next 60 days, count of at-risk cases (≥1 overdue task OR policy near cap)

**Schema changes:**

```sql
-- Add to Task table:
ALTER TABLE task ADD COLUMN due_date date NULL;
ALTER TABLE task ADD COLUMN due_date_source text NULL;
  -- 'template_default' | 'hr_set' | 'derived_from_case_date'
ALTER TABLE task ADD COLUMN trigger_offset interval NULL;
  -- e.g., '-90 days' relative to case.target_end_date

-- New table:
CREATE TABLE case_trigger (
  id uuid PRIMARY KEY,
  case_id uuid NOT NULL REFERENCES case(id) ON DELETE CASCADE,
  organization_id uuid NOT NULL,  -- for tenant scoping
  trigger_type text NOT NULL,
    -- 'repat_planning_window' | 'pre_arrival_60d' | 'visa_renewal_due'
    -- 'assignment_end' | 'document_expiry_60d' | 'check_in'
  fires_at date NOT NULL,
  fired_at timestamp NULL,
  status text NOT NULL DEFAULT 'pending',
    -- 'pending' | 'fired' | 'acknowledged' | 'dismissed'
  metadata jsonb,
  created_at timestamp NOT NULL DEFAULT now()
);

CREATE INDEX idx_case_trigger_pending ON case_trigger (fires_at)
  WHERE status = 'pending';
CREATE INDEX idx_case_trigger_case ON case_trigger (case_id);
```

**Technical approach:**
1. **Schema migration:** add fields to Task, create case_trigger table
2. **Task UI:** render due_date when set; overdue tasks visually distinct; show due_date in Plan view
3. **Plan generation:** when case is created, populate due_dates from template defaults or compute from case dates (e.g., "Upload passport copy" → target_move_date - 60 days)
4. **Scheduler:** add a scheduler (BullMQ if Node, Sidekiq if Rails, pg_cron if minimal). Daily job at 06:00 UTC: query `case_trigger WHERE fires_at <= today AND status = 'pending'`. For each, execute the appropriate handler (create_repat_tasks, send_reminder_email, etc.). Mark as fired.
5. **Idempotency:** trigger has a unique constraint on (case_id, trigger_type, fires_at) so re-runs don't double-fire
6. **Repat trigger handler:** when 'repat_planning_window' fires, create tasks: "Schedule repat tax briefing", "Book return shipment", "Plan return travel", "Coordinate end-of-assignment paperwork". Notify employee + HR via email + in-app.

**Files likely involved:**
- Schema: `prisma/schema.prisma` or `db/schema/`
- Task model: `src/models/Task.*` or service layer
- Plan generation: `src/services/planGeneration.*`
- Scheduler: `src/jobs/` or `src/queue/` (likely needs to be created if absent)
- Trigger handlers: `src/jobs/handlers/triggerHandler.*`
- Plan view: `src/components/PlanView*` or `src/pages/cases/[id]/plan.tsx`
- Command Center: `src/pages/dashboard/index.tsx` or admin dashboard

**Dependencies:** Spike 2 output. Choose scheduler infrastructure if absent.

**Effort:** 2-3 weeks.

**Test scenarios:**
- Create a case with target_end_date 100 days from now → verify case_trigger row created for repat_planning_window with fires_at = target_end_date - 90 days
- Manually advance time (or seed fires_at to today) → verify scheduler picks up trigger, creates repat tasks, notifies employee and HR
- Trigger has already fired (status='fired') → scheduler does not re-fire
- Task with due_date in the past renders with "Overdue" indicator
- Command Center shows accurate count of overdue tasks for the logged-in HR's tenant only (cross-tenant test)

**Claude Code starter prompt:**
```
Implement Task.due_date + case-level date triggers per the spec.
Goal: enable F8 mitigation (forgotten repat) and Command Center KPIs.

Step 1: Add Task.due_date, due_date_source, trigger_offset columns
(migration).
Step 2: Create case_trigger table (migration). Idempotent unique constraint
on (case_id, trigger_type, fires_at).
Step 3: Update plan generation to populate due_dates from template
defaults or compute from case.target_move_date / case.target_end_date.
Step 4: Add a scheduler if absent (BullMQ if Node, etc.). Daily job at
06:00 UTC queries pending triggers and dispatches to handlers.
Step 5: Implement repat_planning_window handler: create repat tasks,
notify employee + HR, mark trigger as fired.
Step 6: Update Plan view to render due_date and overdue styling.
Step 7: Update Command Center KPIs to count overdue tasks, cases
departing in 60 days, at-risk cases.
Step 8: Tests: idempotency, tenant isolation, repat flow end-to-end.

Reference the audit's "Side-Output A" Estimate Review spec — task
due_dates may inform that screen later.
```

---

### T1.3 — ExceptionRequest Entity + Workflow

**Priority:** P0. Required for Estimate Review (T1.5) to ship complete.

**Goal:** Implement structured exception request flow when employee selects above-policy services. Includes the entity, the request UI (employee side), the review UI (HR side), and the approval/denial flow.

**Why it matters:** Without this, Estimate Review surfaces a problem with no structured solution. Exceptions stay ad-hoc (F6 mitigation 0%). M10 mid-market unlock requires structured exception trail.

**Acceptance criteria:**
- ExceptionRequest entity exists with all required fields
- Employee can file an exception from Estimate Review with: reason text, proposed coverage % from employer, optional supporting note
- HR sees pending exceptions in their dashboard with full case context
- HR can approve / deny / request changes; each writes to audit_log
- On approval: PackageSelection effective_coverage updates; employee notified
- On denial: employee can edit selection or proceed with personal cost acknowledged
- Email notifications on every state change

**Schema changes:**

```sql
CREATE TABLE exception_request (
  id uuid PRIMARY KEY,
  case_id uuid NOT NULL REFERENCES "case"(id) ON DELETE CASCADE,
  organization_id uuid NOT NULL,
  package_selection_id uuid NULL REFERENCES package_selection(id),
  benefit_rule_id uuid NULL REFERENCES benefit_rule(id),
  
  reason text NOT NULL,
  amount_over numeric NULL,           -- auto-computed at request time
  proposed_coverage_pct int NULL,     -- 0-100, employee asks for X%
  supporting_note text NULL,
  
  status text NOT NULL DEFAULT 'pending',
    -- 'pending' | 'approved' | 'denied' | 'withdrawn'
  
  requested_by_user_id uuid NOT NULL REFERENCES "user"(id),
  requested_at timestamp NOT NULL DEFAULT now(),
  reviewed_by_user_id uuid NULL REFERENCES "user"(id),
  reviewed_at timestamp NULL,
  decision_note text NULL,
  
  audit_log_entry_id uuid NULL REFERENCES audit_log(id)
);

CREATE INDEX idx_exception_pending_by_org ON exception_request 
  (organization_id, status) WHERE status = 'pending';
CREATE INDEX idx_exception_by_case ON exception_request (case_id);
```

**Technical approach:**
1. **Schema migration**
2. **Employee-side request form:** modal triggered from Estimate Review "Request exception" button. Pre-populates `amount_over` from line item delta. Form fields: reason (textarea), proposed_coverage_pct (slider 0-100%), supporting_note (optional)
3. **HR-side review UI:** new section in HR dashboard "Pending Exceptions" with case context, employee details, package summary. Approve / Deny / Request Changes buttons
4. **State transitions:**
   - Created → pending
   - HR approves → approved (PackageSelection.effective_coverage updates; employee notified)
   - HR denies → denied (employee notified; can edit or withdraw)
   - Employee withdraws → withdrawn
5. **Notifications:** email to HR on creation; email to employee on decision
6. **Audit log:** every state change writes audit entry

**API contract (illustrative):**

```typescript
POST /api/cases/:caseId/exceptions
  body: { 
    package_selection_id?: uuid, 
    benefit_rule_id?: uuid,
    reason: string, 
    proposed_coverage_pct?: number,
    supporting_note?: string 
  }
  response: ExceptionRequest

PATCH /api/exceptions/:exceptionId
  body: { 
    status: 'approved' | 'denied' | 'withdrawn',
    decision_note?: string 
  }
  response: ExceptionRequest

GET /api/exceptions?status=pending&organization_id=...
  response: ExceptionRequest[]
```

**Files likely involved:**
- Schema migration
- API routes: `src/pages/api/exceptions/` or `src/app/api/exceptions/`
- Employee modal: `src/components/Estimate/RequestException.tsx` (new)
- HR review UI: `src/pages/dashboard/exceptions/index.tsx` (new)
- Email templates: `src/lib/email/templates/`
- Notification service

**Dependencies:** Audit log working (T1.1). Should ship before or alongside T1.5.

**Effort:** 3-4 weeks.

**Test scenarios:**
- Employee files exception → ExceptionRequest row created with status='pending', audit entry written
- HR approves → status='approved', audit entry, employee email sent, PackageSelection updated
- HR denies → status='denied', audit entry, employee email
- Cross-tenant: HR-A from Tenant A cannot see exceptions from Tenant B (test by URL manipulation)
- Employee withdraws an exception → status='withdrawn'
- Approve same exception twice → second call returns 409 Conflict

**Claude Code starter prompt:**
```
Implement ExceptionRequest entity + workflow per the spec.

Step 1: Schema migration for exception_request table with the fields
listed in the implementation plan.
Step 2: API endpoints (POST, PATCH, GET) with tenant scoping.
Step 3: Employee-side request modal triggered from Estimate Review
"Request exception" button (the Estimate Review screen itself comes
in T1.5, but this modal needs a stub trigger now).
Step 4: HR-side pending exceptions UI in dashboard.
Step 5: Email notifications on state changes.
Step 6: Audit log integration on every state transition.
Step 7: Tests including tenant isolation, idempotency, audit coverage.

This task ships ahead of T1.5 (Estimate Review buildout) so Estimate
Review can integrate with it cleanly when it's built.
```

---

### T1.4 — FX Rate Snapshot + ECB Integration

**Priority:** P0. Required for Estimate Review (T1.5) reliability.

**Goal:** Persist daily FX rates from European Central Bank reference rates. Use stored rates in Estimate Review. Stamp source_date on every conversion.

**Why it matters:** Without persistent FX rates, Estimate Review is unreliable across time (same case viewed yesterday and today shows different totals). ECB is the EU regulatory standard for cross-border financial reporting.

**Acceptance criteria:**
- FXRate table exists; populated daily at 16:30 CET
- Daily job fetches from ECB XML feed; idempotent (re-running same day is no-op)
- Estimate Review uses latest FXRate row for conversion; displays source_date in footer
- Currencies not in ECB list display in source currency only with "outside ECB list" badge
- Weekend/holiday: latest published rate used; footer notes "Last published [date]"
- Source date older than 7 days: hard warning to admin

**Schema changes:**

```sql
CREATE TABLE fx_rate (
  id uuid PRIMARY KEY,
  currency_code text NOT NULL,        -- 'USD', 'GBP', 'JPY', 'SGD', etc.
  rate_to_eur numeric(12, 6) NOT NULL,
  source text NOT NULL DEFAULT 'ECB',
  source_date date NOT NULL,           -- the date ECB stamped this rate
  fetched_at timestamp NOT NULL DEFAULT now(),
  
  UNIQUE (currency_code, source_date)  -- idempotency
);

CREATE INDEX idx_fx_rate_lookup ON fx_rate 
  (currency_code, source_date DESC);
```

**Technical approach:**

1. **ECB feed:** `https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml` (XML, free, no auth required)
2. **Daily fetch job:** scheduled at 16:30 CET. Parse XML, upsert each currency for the source_date
3. **Conversion service:** `convertToEur(amount, sourceCurrency, sourceDate?)` — looks up FXRate for the most recent date ≤ sourceDate (or today if not specified)
4. **Estimate Review integration:** every LineItem stores its computed total in EUR + source_currency + fx_source_date. Footer displays "Exchange rates from ECB, [DD Mon YYYY]"
5. **Admin alerting:** if daily fetch fails 2 days in a row, alert via Slack/email

**Code sketch (Node/TypeScript):**

```typescript
// src/services/fxRate.ts
import { parseStringPromise } from 'xml2js';

export async function fetchECBRates(): Promise<FXRate[]> {
  const response = await fetch(
    'https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml'
  );
  const xml = await response.text();
  const parsed = await parseStringPromise(xml);
  
  const cube = parsed['gesmes:Envelope'].Cube[0].Cube[0];
  const sourceDate = cube.$.time;
  
  return cube.Cube.map((c: any) => ({
    currency_code: c.$.currency,
    rate_to_eur: 1 / parseFloat(c.$.rate),  // ECB gives EUR→X; we store X→EUR
    source: 'ECB',
    source_date: sourceDate,
  }));
}

// Daily job
export async function dailyFXRateFetch() {
  const rates = await fetchECBRates();
  await db.fxRate.createMany({
    data: rates,
    skipDuplicates: true,  // idempotency
  });
}

export async function convertToEur(
  amount: number,
  sourceCurrency: string,
  asOfDate?: Date
): Promise<{ eur: number; source_date: Date }> {
  if (sourceCurrency === 'EUR') {
    return { eur: amount, source_date: asOfDate ?? new Date() };
  }
  
  const rate = await db.fxRate.findFirst({
    where: {
      currency_code: sourceCurrency,
      source_date: { lte: asOfDate ?? new Date() },
    },
    orderBy: { source_date: 'desc' },
  });
  
  if (!rate) {
    throw new FXRateUnavailableError(sourceCurrency);
  }
  
  return {
    eur: amount * rate.rate_to_eur,
    source_date: rate.source_date,
  };
}
```

**Files likely involved:**
- Schema migration
- New service: `src/services/fxRate.ts`
- New job: `src/jobs/dailyFXFetch.ts`
- Estimate Review integration: any place that displays Money values

**Dependencies:** Scheduler infrastructure from T1.2.

**Effort:** 1-2 weeks.

**Test scenarios:**
- Run daily job → verify FX rates populated for that day
- Run daily job twice on same day → second call is no-op (no duplicates)
- Convert 1000 USD as of today → returns EUR with today's rate
- Convert 1000 INR (not in ECB list) → throws FXRateUnavailableError
- Convert 1000 USD as of weekend → returns most recent prior weekday rate
- Source date older than 7 days → admin alert fires

**Claude Code starter prompt:**
```
Implement FX rate snapshot persistence with ECB integration.

Step 1: Schema migration for fx_rate table.
Step 2: ECB XML feed parser at
https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml.
Note: ECB gives EUR → X rates. Invert and store X → EUR.
Step 3: Daily job at 16:30 CET. Idempotent.
Step 4: convertToEur(amount, sourceCurrency, asOfDate?) service.
Returns most recent rate ≤ asOfDate.
Step 5: Update any Money-displaying screens to use the conversion
service. Currently mostly Estimate Review (T1.5) and Recommendations.
Step 6: Admin alerting on stale rates (>7 days).
Step 7: Tests: idempotency, weekend/holiday, missing currency,
stale rate alerting.
```

---

### T1.5 — Estimate Review Buildout (THE Killer Screen)

**Priority:** P0. The single screen most responsible for the value prop.

**Goal:** Build out Estimate Review per Side-Output A specification (full spec in audit Appendix A).

**Why it matters:** Currently the lightest surface (T3 score 2/5) despite being the screen that must carry the value prop. Post-buildout: tied with Topia Horizon at category-leading depth. Drives M10 mid-market 3 → 4 unlock.

**Acceptance criteria:**
- Layout per Appendix A: case header, total package summary, per-service breakdown, "if you proceed" totals, "what happens next"
- Color signaling: green ≤80%, yellow 80-100%, red >100%, grey no-cap, outline excluded
- 80% yellow threshold tenant-configurable (Path A: ReloPass admin)
- Multiplier transparency: "€15,000 × 1 child × 3 years = €45,000" not just "€45,000"
- ECB FX integration with source_date in footer (depends on T1.4)
- ExceptionRequest integration: "Request exception" button creates ExceptionRequest (depends on T1.3)
- All edge cases handled (Appendix A §A.6): no policy yet, partial coverage, currency mismatch, multiplier ambiguity, % of salary, tax-eq, annualized toggle
- HR view of same screen: same layout, action buttons become Approve/Approve with exception/Request changes
- Audit log entry on every state change (selections changed, exception filed, approval given)

**Technical approach:**

This is the largest single task in Tier 1. Recommended sequencing within the task:

**Sub-step 1: Calculation engine (1-2 wks)**

Build a pure function `computeEstimateReview(case, package, policy, fxAsOfDate?)` that returns:

```typescript
type EstimateReview = {
  case_header: { ... };
  totals: {
    estimated_package_cost: Money;
    policy_budget: Money;
    delta: Money;
    personal_cost: Money;
    overall_color: 'green' | 'yellow' | 'red';
  };
  line_items: LineItem[];
  fx: {
    display_currency: string;
    source: 'ECB';
    source_date: Date;
  };
  warnings: Warning[];
};

type LineItem = {
  service_category: string;
  vendor_name: string;
  unit_cost: Money;
  unit: 'one_time' | 'per_month' | 'per_year' | 'per_dependent';
  multiplier: number;
  multiplier_explanation: string;  // "× 1 child × 3 years"
  total_cost: Money;
  
  cap: Money | null;
  cap_explanation: string;  // "€15,000/child/yr × 3 yr = €45,000"
  cap_total: Money | null;
  
  delta: Money;
  status: 'within_policy' | 'over_policy' | 'no_cap_defined' | 'excluded';
  color: 'green' | 'yellow' | 'red' | 'grey' | 'outline';
  personal_cost: Money;
};
```

Multiplier rules:
- movers: 1
- housing: case.duration_months
- schools: case.duration_years × case.family.children_count
- language training: case.family.size_eligible (per-person)
- tax_eq: not a cost; show as "Included" or "Not included"

**Sub-step 2: UI shell (1 wk)**

Build the layout boxes per Appendix A with placeholder data first. Get the visual rhythm right before connecting the engine.

**Sub-step 3: Connect engine to UI (0.5 wk)**

Render real values. Handle loading/error states.

**Sub-step 4: Edge cases (1 wk)**

Implement each from Appendix A §A.6. Each as a unit test.

**Sub-step 5: HR view (0.5 wk)**

Same screen, different action buttons. Add HR notes field.

**Sub-step 6: Tenant-configurable threshold (0.5 wk)**

Path A: ReloPass admin sets `organization.fx_yellow_threshold_pct` per customer. Default 80%.

**Schema changes:**

```sql
ALTER TABLE organization 
  ADD COLUMN estimate_review_yellow_threshold_pct int DEFAULT 80;

-- Possibly add to LineItem if we persist:
-- (Or compute on-the-fly each render — preferred for simplicity)
```

**API contract:**

```typescript
GET /api/cases/:caseId/estimate-review
  query: { display_currency?: 'EUR' | 'USD' | ... }
  response: EstimateReview

POST /api/cases/:caseId/package/submit
  // changes package status from 'draft' to 'submitted'
  response: Package

PATCH /api/packages/:packageId
  // HR approves, requests changes
  body: { status, hr_note?: string }
  response: Package
```

**Files likely involved:**
- Calculation engine: `src/services/estimateReview.ts` (new)
- API route: `src/pages/api/cases/[id]/estimate-review.ts` (new or replacement)
- UI: `src/pages/services/estimate.tsx` (existing — major rebuild)
- HR view variant: `src/pages/dashboard/cases/[id]/estimate.tsx` (new or refactor)
- Components: `src/components/EstimateReview/*` (new directory)
- Edge case tests: `tests/estimateReview/*`

**Dependencies:** T1.3 (ExceptionRequest), T1.4 (FX), audit log working (T1.1).

**Effort:** 3-5 weeks.

**Test scenarios (table):**

| # | Scenario | Expected |
|---|---|---|
| 1 | All selections within 80% of cap | Total green, all line items green |
| 2 | One selection 85% of cap | That line yellow; total yellow |
| 3 | One selection 110% of cap | That line red; total red; personal_cost > 0 |
| 4 | Service with no policy cap | That line grey ("No cap defined in policy") |
| 5 | Service excluded by policy | That line outline ("Not covered by policy") |
| 6 | Schooling with 2 kids × 3 years | Multiplier explanation "× 2 children × 3 years" |
| 7 | Housing in SGD, display in EUR | Conversion via ECB; source_date in footer |
| 8 | INR cost (not in ECB) | Shown in INR with "outside ECB list" badge |
| 9 | Policy not yet published | Banner: "HR is finalizing your policy"; comparison hidden |
| 10 | Employee clicks "Request exception" | Modal opens; creates ExceptionRequest |
| 11 | Employee clicks "Proceed anyway" with red lines | Required ExceptionRequest before allowed |
| 12 | HR view — Approve as-is | Package status → approved; audit log entry |
| 13 | Cross-tenant: User A views Case from Tenant B | 403/404; audit log entry status='denied' |
| 14 | Tenant configures yellow threshold to 70% | Yellow triggers at 70% not 80% |

**Claude Code starter prompt:**
```
Build the Estimate Review screen per the audit's Side-Output A specification.
This is the killer screen for the value prop — invest the time.

Read the spec from the audit final synthesis Appendix A. Then:

Step 1: Build the pure calculation engine
computeEstimateReview(case, package, policy, fxAsOfDate?) returning the
EstimateReview type defined in the spec. All multiplier rules + status
+ color computation in one place. Heavy unit testing.
Step 2: Build the UI shell with the 5 layout boxes (case header, total
package, per-service breakdown, "if you proceed", "what happens next").
Use placeholder data first to get the rhythm right.
Step 3: Connect the engine. Handle loading/error states.
Step 4: Implement every edge case from spec §A.6. Each as a test.
Step 5: HR variant of the screen with Approve/Deny/Request Changes.
Step 6: Tenant-configurable yellow threshold (default 80%).
Step 7: Integrate ExceptionRequest from T1.3 (the modal triggered from
"Request exception" button).

Reference T1.4 FX conversion service for currency. Reference T1.3
ExceptionRequest for the exception modal. Reference T1.1 audit log
for state-change logging.
```

---

### T1.6 — Employee Dashboard P0 Redesign

**Priority:** P0. The worst surface in the product (T3 score 1/5).

**Goal:** Replace current Employee Dashboard with a redesigned single-page experience. Magic-link auto-claim. Hide UUIDs. Collapse nav from 9 to 3-4 items. Remove implementation jargon.

**Why it matters:** First impression an employee gets is currently the worst surface. Anxiety-elevating for a persona already anxious.

**Acceptance criteria:**
- New employee landing page after auth shows: "Welcome [Name], your move from [Origin] to [Destination] is ready"
- Above-the-fold: case status, current phase, next 1-3 actions, quick policy summary
- Magic-link auto-claim: if employee follows invite link with valid token, case auto-binds; no manual UUID entry
- Nav collapsed to 3-4 items: My Move (Plan + Tasks), My Services (current selections + Estimate), Resources, Messages — exact items TBD with design
- All UUIDs hidden from user-facing copy
- "Section A / Section B" language replaced with semantic labels
- "Common mistake" warning removed (manual claim deprecated)
- Mobile-responsive (employees often check on mobile)

**Technical approach:**
1. **Magic-link claim flow:** invite token in URL → on auth complete, look up Case by invite_token → bind Case.employee_user_id to current user → invalidate token
2. **Landing page:** new Next.js page (or equivalent). Server-side fetch case + plan + active tasks + policy summary
3. **Nav consolidation:** combine related routes
4. **Microcopy pass:** systematic replacement of "Section A", UUIDs, etc.
5. **Mobile:** verify Tailwind classes responsive at sm/md breakpoints

**Schema changes:** None (Case.invite_token presumably already exists).

**Files likely involved:**
- Auth flow: `src/pages/auth/` (existing — modify magic-link handler)
- Employee landing: `src/pages/dashboard/index.tsx` (existing — major rebuild)
- Nav component: `src/components/Layout/EmployeeNav.tsx` or similar
- New components: `src/components/Dashboard/CaseStatus.tsx`, `NextActions.tsx`, `PolicySummary.tsx`

**Dependencies:** None. Can ship in parallel with T1.5.

**Effort:** 1-2 weeks.

**Test scenarios:**
- Employee follows invite link → auth → landed on dashboard with case bound
- Employee with no invite link → sees "Awaiting case assignment" message
- Employee at different phases (intake_in_progress, services_in_progress, active) sees appropriate "next action"
- Mobile viewport (375px) — layout coherent
- No "Section A", "Section B", or UUID strings present anywhere on page (regex test)

**Claude Code starter prompt:**
```
Redesign the Employee Dashboard. Currently it's the worst surface in
the product — Section A / Section B language, UUIDs visible, manual
claim form, 9 nav items.

Step 1: Read the current implementation at [src/pages/dashboard/...
or equivalent].
Step 2: Implement magic-link auto-claim. Invite token in URL →
auto-bind Case to user.
Step 3: Rebuild landing page above-the-fold:
  - "Welcome [Name], your move from [Origin] to [Destination] is ready"
  - Case status badge + current phase
  - Next 1-3 priority actions (from Plan)
  - Quick policy summary card
Step 4: Collapse navigation from 9 items to 3-4. Recommended:
  - My Move (Plan + Tasks)
  - My Services (current selections + link to Estimate Review)
  - Resources
  - Messages
Step 5: Microcopy pass: remove all "Section A", "Section B", UUIDs,
"Common mistake" warnings, manual claim form. Replace with semantic
labels.
Step 6: Mobile responsive at 375px breakpoint.
Step 7: Tests: magic-link claim, no UUID/Section regex check.
```

---

### T1.7 — Case `paused` Status

**Priority:** P0. Edge-case realism.

**Goal:** Add `paused` status to Case lifecycle. Pause/resume UI for HR.

**Why it matters:** Cases can stall (visa rejection, medical emergency, family events). Currently no clean way to express this — case appears active when it isn't.

**Acceptance criteria:**
- Case.status enum includes 'paused'
- Case.pause_reason and Case.paused_at fields
- HR can pause case from case detail with reason; resume any time
- Paused cases excluded from "active" KPIs in Command Center
- Paused cases visually distinct in case list
- Audit log on pause and resume

**Schema changes:**

```sql
-- Update enum (depends on DB):
-- For Postgres with text status: no migration needed beyond data validation
-- For Postgres with enum type: ALTER TYPE case_status ADD VALUE 'paused';

ALTER TABLE "case" ADD COLUMN pause_reason text NULL;
ALTER TABLE "case" ADD COLUMN paused_at timestamp NULL;
ALTER TABLE "case" ADD COLUMN paused_by_user_id uuid NULL REFERENCES "user"(id);
```

**Files likely involved:**
- Case model + status logic
- Case detail UI: pause/resume button
- Command Center filters: exclude paused
- Case list: visual indicator

**Dependencies:** Audit log working.

**Effort:** 1 week.

**Test scenarios:**
- HR pauses case with reason → status='paused', audit entry, KPIs update
- HR resumes case → status returns to previous state, audit entry
- Paused case in case list shows pause indicator and reason
- KPIs (active cases count, overdue tasks) exclude paused cases

**Claude Code starter prompt:**
```
Add 'paused' status to Case lifecycle.

Step 1: Schema migration for pause_reason, paused_at, paused_by_user_id.
Add 'paused' to status enum.
Step 2: API endpoints: POST /api/cases/:id/pause body: {reason} and
POST /api/cases/:id/resume.
Step 3: HR UI: pause/resume button on case detail with reason modal.
Step 4: Update Command Center KPI queries to exclude paused.
Step 5: Update case list to visually indicate paused.
Step 6: Audit log on pause and resume.
Step 7: Tests including tenant isolation.
```

---

### T1.8 — Command Center Simplification (3 Admin-Configurable KPIs)

**Priority:** P0. KPI honesty (no aspirational scaffolding).

**Goal:** Reduce Command Center to 3 KPIs that actually compute correctly. ReloPass admin can configure which 3 KPIs each customer sees (Path A: hardcoded internal config).

**Why it matters:** Currently the surface shows scaffolding for KPIs that can't compute (e.g., "Overdue Tasks" without due_date). Better to show 3 working KPIs than 6 broken ones.

**Acceptance criteria:**
- Command Center renders exactly 3 KPIs by default
- Available KPIs (each must compute correctly): Active cases count, Cases departing in next 60 days, Overdue tasks count, At-risk cases count, Pending exceptions count, Cases by phase distribution
- ReloPass admin can configure per-customer which 3 KPIs render (Path A: organization.command_center_kpis: jsonb config)
- Each KPI clickable → drill down to filtered case list

**Schema changes:**

```sql
ALTER TABLE organization 
  ADD COLUMN command_center_kpis jsonb 
    DEFAULT '["active_cases", "departing_60d", "overdue_tasks"]';
```

**Technical approach:**
1. Define each KPI as a server-side query function
2. Path A: ReloPass admin tool to set `organization.command_center_kpis` per customer (could be a hardcoded YAML/DB seed initially; full UI in Phase 1.5)
3. Frontend reads config, renders matching components

**Files likely involved:**
- Schema migration
- KPI service: `src/services/commandCenter.ts` or similar
- Command Center page: `src/pages/dashboard/index.tsx`

**Dependencies:** T1.2 (due_date for Overdue Tasks KPI). T1.3 (ExceptionRequest for Pending Exceptions KPI).

**Effort:** 1-2 weeks.

**Claude Code starter prompt:**
```
Simplify the HR Command Center to exactly 3 admin-configurable KPIs.

Step 1: Schema: organization.command_center_kpis jsonb config.
Step 2: Define KPI query functions for: active_cases, departing_60d,
overdue_tasks, at_risk_cases, pending_exceptions, cases_by_phase.
Each must compute correctly with current data.
Step 3: Command Center renders configured 3 KPIs only.
Step 4: Each KPI tile clickable → drill down to filtered case list.
Step 5: Path A admin config: hardcoded YAML or seed for now; UI in
Phase 1.5.
Step 6: Tests: tenant scoping on every KPI query, default config works.
```

---

### T1.9 — Hide RFQ Screen + Reframe Funnel Ending

**Priority:** P0. Buyer perception.

**Goal:** Remove the broken "Request for quotation" screen from the employee services funnel. Cut the funnel at "package selection" with a coherent ending.

**Why it matters:** Currently the employee fills 5 steps and lands on a "sending requests from here is not available yet" screen. Bad UX. RFQ is committed Phase 2.

**Acceptance criteria:**
- /services/quotes route either redirects to a coherent ending or is removed
- Employee experience after package submission: "Your package is saved. HR will review and confirm." with clear next-step
- HR experience: receives package; can approve / request changes
- No "coming soon" or "not available yet" messaging visible to employees

**Files likely involved:**
- `src/pages/services/quotes.tsx` (existing — remove or redirect)
- Services funnel router
- HR review surface for submitted packages

**Dependencies:** None.

**Effort:** 0.5 weeks.

**Claude Code starter prompt:**
```
Remove the broken RFQ ("Request for quotation") screen from the
employee services funnel. The funnel currently ends on a "sending
requests from here is not available yet" message.

Step 1: Find /services/quotes route.
Step 2: Either remove route entirely (preferred) or redirect to a
new "Package submitted" confirmation page.
Step 3: After package submission, employee lands on confirmation:
"Your package is saved. HR will review and confirm next steps."
Plus link back to dashboard.
Step 4: HR receives the submitted package as actionable item in
their dashboard (likely already exists; verify).
Step 5: Search codebase for any "coming soon" / "not available yet"
strings; replace or remove.
```

---

### T1.10 — Dev Tooling Strip from Production UI

**Priority:** P0. Production hygiene.

**Goal:** Remove all dev-only controls visible in production builds. "Test controls", "Fill for test", debug panels, etc.

**Acceptance criteria:**
- Production build contains zero dev-only UI elements
- Wrap dev tools in `process.env.NODE_ENV !== 'production'` guards or feature flags
- Search for and remove: "Test controls", "Fill for test", "Debug", "DEV", developer-mode toggles

**Files likely involved:**
- Wizard pages (where "Fill for test" was observed)
- Any admin/internal pages

**Dependencies:** None.

**Effort:** 0.5 weeks.

**Claude Code starter prompt:**
```
Strip all dev-only UI from production.

Step 1: Search codebase for: "Test controls", "Fill for test", "Debug",
"DEV", "developer", "test mode".
Step 2: For each match, wrap in process.env.NODE_ENV !== 'production'
or behind a feature flag.
Step 3: Verify production build (npm run build && start) shows zero
dev controls.
Step 4: Add CI test that fails the build if dev tooling strings are
detected in production bundle.
```

---

### T1.11 — UUID and Internal Identifier Cleanup (User-Facing)

**Priority:** P1 within Tier 1 (cosmetic but high signal).

**Goal:** Hide UUIDs from user-facing copy. Replace with semantic labels or human-readable IDs.

**Acceptance criteria:**
- Employee-side: no UUID strings visible (case ID, message ID, document ID, task ID)
- HR-side: UUIDs may be visible only in admin/internal tools
- Where ID is genuinely needed (e.g., support ticket reference), use a short human-friendly format (e.g., "Case #4F3K" derived from a UUID hash)

**Files likely involved:**
- Most user-facing pages — broad search

**Dependencies:** None.

**Effort:** 0.5-1 weeks.

**Claude Code starter prompt:**
```
Hide UUIDs from user-facing UI.

Step 1: Search all user-facing pages for UUID rendering. UUIDs are
36-char strings with hyphens, e.g., a1b2c3d4-...
Step 2: For each, replace with semantic label or human-readable
short ID. Likely patterns:
  - "Case [uuid]" → "Move to [destination_city]" or similar
  - "Message [uuid]" → use timestamp + sender
  - "Task [uuid]" → use task title
  - "Document [uuid]" → use document type + filename
Step 3: Where an ID is genuinely needed for support reference,
generate a short hash like "ABC-123" from the UUID.
Step 4: Add a regex-based test that fails if any user-facing page
renders a string matching the UUID pattern.
```

---

## Tier 2 — P1 Mid-Market Wedge Consolidation (Phase 1.5, Weeks 13+)

> Total ~25-35 weeks engineering, parallelizable to ~15-20 wall-clock weeks.
>
> Within Tier 2, sequencing logic:
> - 2.1 (move_type/contract_type) is a strategic anchor — informs 2.2, 2.6, 2.7
> - 2.4 (destination expansion) is mostly content work, parallel to engineering
> - 2.2 (CaseStakeholder) blocks future enterprise complement positioning
> - 2.3 (family signal) closes F11 mitigation gap
> - 2.5 (granular dependencies), 2.6 (bulk creation), 2.7 (copy cleanup), 2.8 (SSO) are independent

---

### T2.1 — Case.move_type / contract_type Propagation (Option B)

**Priority:** P0 if French wedge prioritized; P1 otherwise.

**Goal:** Make `move_type` (international/domestic) and `contract_type` (assignment/permanent_transfer/local_hire) real discriminators throughout plan generation, policy application, services catalog, and resources.

**Why it matters:** Unlocks domestic move support (Anywr-displacement opportunity in French market). F1 mitigation for permanent transfers (currently softens S4 verdict).

**Acceptance criteria:**
- Case has `move_type` (international/domestic) and `contract_type` (assignment/permanent_transfer/local_hire/temporary_assignment) fields
- Plan generation respects both: domestic skips Immigration phase; permanent_transfer suppresses Repat
- Policy application respects both: domestic suppresses tax_eq/cola/mobility_premium; permanent_transfer suppresses repat-specific benefits
- Services catalog filters: domestic hides visa/permits/international moving; STA hides schools (typically) and household goods
- Resources surface domestic content for domestic moves
- Wizard simplifies for domestic (no passport upload, no employment letter for visa)
- Estimate Review handles single-currency for domestic (no FX needed)

**Schema changes:**

```sql
ALTER TABLE "case" ADD COLUMN move_type text NOT NULL DEFAULT 'international';
  -- 'international' | 'domestic'
-- contract_type likely already exists; verify enum values
```

**Technical approach:**

This is the biggest single Tier 2 task. Approach depends entirely on Spike 3 output. Two paths:

**Path A (clean abstraction): 3-4 weeks.** If plan generation is template-driven and policy filters are config-driven, just add the discriminators and update the templates/configs.

**Path B (hardcoded): 6-8 weeks.** If "international LTA" assumptions are hardcoded, refactor first then add discrimination.

Recommended approach in either case:

1. **Plan generation refactor:** make plan templates explicitly parametrized by (move_type, contract_type). Domestic plan template, international LTA template, international STA template, permanent_transfer template, local_hire template.
2. **Policy benefit applicability rules:** each BenefitRule gets `applicable_move_types` and `applicable_contract_types` (jsonb arrays). Filter at application time.
3. **Services catalog config:** each Service gets visibility rules per move_type/contract_type.
4. **Resources scope:** add domestic resource collections per region (initially: France domestic).
5. **Wizard step conditionality:** step 2 (Employee profile + passport) skips passport for domestic.

**Effort:** 3-8 weeks depending on Spike 3 result.

**Claude Code starter prompt:**
```
Implement move_type and contract_type as real discriminators throughout
the system.

Reference Spike 3 output for the architectural assessment. If Spike 3
returned "clean abstraction", this is 3-4 weeks. If "hardcoded",
6-8 weeks with refactoring first.

Step 1: Schema migration for case.move_type field.
Step 2: For each subsystem touchpoint identified in Spike 3:
  - Plan generation: parametrize templates by (move_type, contract_type)
  - Policy: add applicable_move_types and applicable_contract_types
    to BenefitRule
  - Services catalog: visibility rules per (move_type, contract_type)
  - Resources: add domestic resource scope
  - Wizard: conditional steps for domestic
  - Estimate Review: single-currency path for domestic
Step 3: Templates for: domestic, international LTA, international STA,
permanent_transfer, local_hire.
Step 4: Tests for each (move_type, contract_type) combination ending
in a coherent case file.
```

---

### T2.2 — CaseStakeholder Model (Minimum Viable RACI)

**Priority:** P1.

**Goal:** Implement first-class stakeholder model. Enable hiring manager, mobility committee, finance approver, external advisors as case actors.

**Schema changes:**

```sql
CREATE TABLE case_stakeholder (
  id uuid PRIMARY KEY,
  case_id uuid NOT NULL REFERENCES "case"(id) ON DELETE CASCADE,
  organization_id uuid NOT NULL,
  
  user_id uuid NULL REFERENCES "user"(id),  
  external_contact jsonb NULL,  -- {name, email, role, organization}
  
  stakeholder_type text NOT NULL,
    -- 'mobility_specialist' | 'hrbp' | 'manager' 
    -- 'payroll_home' | 'payroll_host' | 'tax_advisor'
    -- 'immigration_counsel' | 'rmc_contact' | 'finance_approver'
    -- 'mobility_committee' | 'dependent_advocate' | 'other'
  authority text NOT NULL,  
    -- 'owner' | 'approver' | 'informed' | 'consulted' (RACI-flavored)
  active boolean NOT NULL DEFAULT true,
  added_at timestamp NOT NULL DEFAULT now(),
  removed_at timestamp NULL
);
```

**Effort:** 6-8 weeks.

**Claude Code starter prompt:**
```
Implement CaseStakeholder model per spec. This is a foundation for
multi-actor approval workflows in Phase 2.

Step 1: Schema migration.
Step 2: API endpoints: add/remove/update stakeholders on a case.
Step 3: HR UI on case detail: "Stakeholders" section with add/remove.
Step 4: Permissions: external stakeholders can see scoped case data
(specific phases or document types) — not full case access.
Step 5: Notification routing uses stakeholder list.
Step 6: ExceptionRequest from T1.3 can route to specific approver
(mobility_committee or finance_approver) instead of generic HR.
Step 7: Audit log on every stakeholder change.
Step 8: Tests including tenant isolation.
```

---

### T2.3 — Family / Dual-Career Signal Propagation

**Priority:** P1. F11 mitigation 62% → 90%+.

**Goal:** Close gap from Spike 4 — make `spouse_wants_to_work` flag actually drive surfacing.

**Acceptance criteria:**
- When `spouse_wants_to_work=true`: destination resources surface job-search support, language schools, professional networks for spouse
- Services questionnaire asks spouse-employment-related preferences
- Policy application surfaces spouse-support benefits if defined
- Recommendations include spouse-relevant content where applicable

**Effort:** 2-4 weeks (depending on Spike 4 gap size).

**Claude Code starter prompt:**
```
Propagate spouse_wants_to_work signal per Spike 4 output.

For each consumer identified in the Spike 4 gap report:
- Resources: add filter for spouse-job-search content; surface in
  destination resource pack when flag is true
- Services questionnaire: add spouse-employment preference question
  when flag is true
- Policy: surface spouse-support benefits visibility
- Recommendations: include spouse-relevant items

Tests: case with spouse_wants_to_work=true vs false → verify different
content appears.
```

---

### T2.4 — Destination Data Expansion (2-3 Additional Corridors)

**Priority:** P0 — verdict scoring depends on this.

**Goal:** Add 2-3 destinations at Singapore depth. Build admin tooling to make destination addition repeatable.

**Acceptance criteria:**
- Each new destination has Singapore-equivalent: 10 movers, 10 schools, 10 neighborhoods, 12+ resource categories, corridor watchouts
- Admin UI to add/edit destination (vendor entries, school entries, etc.)
- Vendor onboarding flow
- Watchout authoring tool
- Quarterly content refresh process documented

**Approach:**
- Per-destination cold-start: 3-4 weeks of mobility-domain content (mostly content team work, parallelizable with engineering)
- Tooling: 6-8 weeks engineering — admin UI, vendor onboarding, watchout authoring

**Effort:** 6-9 weeks content + 6-8 weeks tooling, parallelizable.

**Claude Code starter prompt:**
```
Build destination admin tooling per spec. Goal: make adding new
destinations repeatable for content team without engineering work
per destination.

Step 1: Admin UI for destinations at /admin/destinations.
Step 2: Per-destination editor: vendors (movers, schools, neighborhoods,
banks, etc.), resources, watchouts, currency settings.
Step 3: CSV import for bulk vendor addition.
Step 4: Watchout authoring: per-corridor (e.g., FR→ES apostille, FR→DE
Anmeldung) with markdown-style editor.
Step 5: Preview as employee: see how destination renders for an
employee at that destination.
Step 6: Tests: tenant-aware (some vendor preferences are per-org).

Content team will populate destinations after tooling lands. Engineering
ships the tools; content owns the data.
```

---

### T2.5 — Granular Task Dependencies (Parallel-Task Support)

**Priority:** P1.

**Goal:** Allow tasks within a phase to run in parallel where dependencies don't strictly require sequential.

**Acceptance criteria:**
- Task.depends_on already supports per-task dependencies (verify in Spike 2 schema)
- Plan view renders parallel-eligible tasks side-by-side or with parallelism indicator
- "Soft dependency" type added: visa application can proceed in parallel with housing search; tax briefing in parallel with shipping
- Time-to-launch measurably compresses (target: 1-2 weeks per case in mid-market routine)

**Effort:** 2 weeks.

---

### T2.6 — Bulk Case Creation (Admin Import)

**Priority:** P1.

**Goal:** HR can upload CSV of new cases (e.g., M&A acquisition with 50 employees needing relocation) and create cases in bulk.

**Acceptance criteria:**
- CSV upload at HR dashboard: name, email, origin_city, destination_city, target_move_date, salary_band, contract_type
- Validation per row; clear error messaging
- Each row creates a Case with invite token
- Magic-link invitation emails sent in bulk

**Effort:** 2 weeks.

---

### T2.7 — Copy / Jargon Cleanup Pass

**Priority:** P1. Universal trust improvement.

**Goal:** Systematic pass to remove engineering jargon from user-facing copy.

**Acceptance criteria:**
- "Layer-2 rows" → semantic alternative
- "baseline / extraction / evidence rules" → user-facing language
- snake_case task IDs → human-readable task titles only
- Internal-only fields hidden from user view
- Style guide created for ongoing copy decisions

**Files likely involved:** broad search; many files.

**Effort:** 1-2 weeks.

**Claude Code starter prompt:**
```
Conduct a copy/jargon cleanup pass on user-facing UI.

Step 1: Search codebase for these strings (case-insensitive):
"Layer-2", "baseline", "extraction rules", "evidence rules",
"Section A", "Section B".
Step 2: For each match in user-facing files, replace with semantic
alternative:
  - "Layer-2 rows" → "Detailed rules" or "Per-benefit configuration"
  - "baseline" → "Starting policy" or "Template defaults"
  - "extraction rules" → "Auto-detected from your document"
  - "evidence rules" → "Source references"
  - "Section A/B" → semantic labels per context
Step 3: Search for snake_case strings rendered in UI; replace with
title-cased human labels.
Step 4: Establish a style guide doc at docs/copy-style.md for future
PRs.
Step 5: Add CI lint for snake_case strings in user-facing JSX.
```

---

### T2.8 — SSO (SAML / OIDC)

**Priority:** P1. Mid-market procurement requirement.

**Goal:** Add SAML/OIDC support so mid-market customers can integrate with their identity provider.

**Acceptance criteria:**
- SAML 2.0 supported via standard library (e.g., `passport-saml`)
- OIDC supported (Auth0, Okta, Azure AD)
- Per-organization configuration (Path A: ReloPass admin sets per customer initially; full UI in Phase 2)
- JIT (just-in-time) provisioning: new users from SSO auto-create with default role per org config
- Existing magic-link flow remains for invited employees

**Effort:** 3-4 weeks.

---

## Tier 3 — P2 Phase 2 Strategic (6-9 Months Post-MVP)

> Total ~55-75 weeks engineering across 6-9 wall-clock months. These are the moves that enable complement positioning + scaling.

### T3.1 — Topia One Export Integration (CORE complement-positioning)

**Goal:** Export ReloPass case data in Topia One-compatible format. Enable enterprise customers using Topia operationally to add ReloPass as their employee-experience layer.

**Acceptance criteria:**
- Per-case export: case metadata, package selections, policy applied, audit trail, exception history
- Output formats: JSON, optional CSV
- Optional: real-time sync via webhook to customer's Topia instance
- Integration tested against actual Topia One API (if accessible) or against documented Topia One schema

**Effort:** 4-6 weeks.

### T3.2 — RFQ Flow Build-Out

**Goal:** Implement vendor RFQ from request creation through quote receipt and selection.

**Effort:** 8-12 weeks.

### T3.3 — Vendor Relationship Management (SLA, Contract, Swap)

**Effort:** 4-6 weeks.

### T3.4 — Conditional Policy Rules (If-Then)

**Goal:** Express policy rules like "if location=tier-1 city, housing cap = €X; else €Y".

**Effort:** 4-6 weeks.

### T3.5 — Hierarchical Benefits

**Goal:** Express bundled benefits ("relocation package = X + Y + Z").

**Effort:** 3-4 weeks.

### T3.6 — Corridor-Scoped Policies

**Goal:** Multi-corridor customers can express different policies per origin/destination pair.

**Effort:** 4-6 weeks.

### T3.7 — External System Ingest Layer (Webhooks)

**Goal:** Ingest events from external systems (Topia, Workday, immigration vendor portals) so ReloPass case state stays current without manual updates.

**Effort:** 6-8 weeks.

### T3.8 — Tax Provider Integration Interface

**Goal:** Standardized interface for tax provider integrations (Big-4 firms) to push tax-equalization computations into Case context.

**Effort:** 6-8 weeks.

### T3.9 — Spouse-as-User (Limited Scope)

**Goal:** Spouse can authenticate and access family-relevant case data (own visa status, dependent's school search, dual-career resources). F11 full mitigation.

**Effort:** 6-8 weeks.

---

## Tier 4 — P3 Phase 3+ (Customer-Demand-Driven)

These are not roadmap commitments. Each ships when specific customer demand triggers.

- **T4.1 Side-letter generation** — generate per-case assignment side-letters from policy + case data. 4-6 weeks.
- **T4.2 Government portal integrations** — direct integration with country-specific portals (e.g., Singapore MOM, France ANEF). 6+ weeks per portal.
- **T4.3 Multi-language UI** — i18n framework + translations. 8-12 weeks.
- **T4.4 White-label / per-tenant branding** — customers can apply own branding. 4-6 weeks.
- **T4.5 Mobile native apps** — iOS/Android. 12-16 weeks.
- **T4.6 Multi-region deployment + data residency** — EU-only data residency option. 8-12 weeks.
- **T4.7 Conditional policy rules — advanced** (hierarchical, conditional, inheritance). 4-6 weeks.

---

## Cross-Cutting Concerns (Apply to Every Task)

### CC1 — Tenant Isolation Discipline

Every API endpoint must enforce `organization_id` scoping. Every database query must filter by `organization_id` (or join through tables that do). Every CI run must include cross-tenant tests that prove a user from Tenant A cannot read/write Tenant B data.

### CC2 — Audit Log Completeness

Every state-changing action writes an audit_log entry. No exceptions. Audit log is the foundation of the M10 mid-market unlock.

### CC3 — Test Coverage on Critical Paths

For each task in Tier 1 and Tier 2:
- Unit tests for pure functions (calculations, policy application)
- Integration tests for state transitions (case lifecycle, policy publish, exception request)
- Cross-tenant tests where applicable

### CC4 — Error Handling and User-Visible Errors

Internal errors do not leak implementation details to users. Errors visible to users use friendly language. Errors are logged with sufficient context for debugging.

### CC5 — Performance Sanity

For each query/endpoint added:
- Verify no N+1 queries (use database join planning, ORM include hints)
- Add database indexes where queries hit them
- Measure response time on representative data volumes (1000 cases, 100 policies)

---

## How to Drive This with Claude Code

### Recommended workflow per task:

**1. Open Claude Code in the repo.**

**2. Paste the task's starter prompt.**

**3. Let Claude Code explore first.** Don't have it implement immediately. Ask it to:
- Read the relevant files
- Confirm the spec aligns with current code
- Flag any assumptions in the spec that don't match reality
- Propose its implementation approach

**4. Review the proposed approach.** Push back on anything that looks wrong. Ask for tradeoff analysis if the approach has multiple viable paths.

**5. Greenlight implementation.** Have Claude Code write the code, tests, and migration in one or more focused commits.

**6. Review the diff.** Pay attention to:
- Audit log writes added (CC2)
- Tenant scoping on every query (CC1)
- Test coverage (CC3)
- Microcopy quality

**7. Run the test scenarios manually** before merging. The acceptance criteria become your test plan.

**8. Move to the next task in priority order.**

### Patterns that work well with Claude Code:

- **Single task per session.** Don't try to ship Tier 1 in one go. Each task gets its own session, its own branch, its own PR.
- **Spike → spec → implementation.** Spikes inform spec; spec drives implementation. Don't skip the spike for ambiguous architecture.
- **Show your existing code first.** When asking Claude Code to implement, point it at relevant existing files first ("read these files, then implement T1.3 against them").
- **Acceptance criteria as the test plan.** Each task has acceptance criteria; ask Claude Code to write tests for each.
- **Push back on jargon.** If Claude Code generates "Layer-2" or other internal-jargon UI strings, push back. The audit specifically called this out.

### Patterns that don't work well:

- **Vague prompts.** "Improve the dashboard" gives bad output. Use the specific task spec.
- **Skipping spike output.** If Spike 3 says contract_type is hardcoded, T2.1 is 6-8 weeks not 3-4. Trust the spike.
- **Conflating tasks.** T1.5 (Estimate Review) depends on T1.3 (ExceptionRequest) and T1.4 (FX). Ship them in order.

---

## Priority Summary (One-Page Reference)

| Tier | Item | Why now |
|---|---|---|
| 0 | Spike 5 (tenant isolation + audit log) | **Existential.** Run first. |
| 0 | Spike 2 (due_date verification) | 2 hrs. Informs T1.2 scope. |
| 0 | Spike 3 (move_type abstraction) | Informs T2.1 effort (3-4 vs 6-8 wks). |
| 0 | Spike 4 (family signal) | Informs T2.3 scope. |
| 0 | Spike 1 (destination depth) | Informs MVP positioning narrowness. |
| 1 | T1.1 Audit log gap remediation | Foundation of M10 unlock. |
| 1 | T1.2 Task.due_date + triggers | Highest-leverage Phase 1 build. F8 mitigation. |
| 1 | T1.3 ExceptionRequest entity + workflow | Required for T1.5 Estimate Review. |
| 1 | T1.4 FX rate snapshot + ECB | Required for T1.5 Estimate Review. |
| 1 | T1.5 Estimate Review buildout | **The killer screen.** |
| 1 | T1.6 Employee Dashboard P0 redesign | Worst surface. First impression. |
| 1 | T1.7 Case paused status | Edge-case realism. Quick win. |
| 1 | T1.8 Command Center simplification | KPI honesty. |
| 1 | T1.9 Hide RFQ + reframe funnel | Buyer perception. Quick win. |
| 1 | T1.10 Dev tooling strip | Production hygiene. Quick win. |
| 1 | T1.11 UUID cleanup user-facing | Trust. Quick win. |
| 2 | T2.1 move_type/contract_type propagation | Domestic moves + permanent transfers. |
| 2 | T2.2 CaseStakeholder model | Mid-market multi-actor + Phase 2 foundation. |
| 2 | T2.3 Family signal propagation | F11 mitigation 62% → 90%+. |
| 2 | T2.4 Destination expansion | Verdict scoring depends on this. |
| 2 | T2.5 Granular task deps | Time-to-launch compression. |
| 2 | T2.6 Bulk case creation | Mid-market scaling. |
| 2 | T2.7 Copy/jargon cleanup | Trust. |
| 2 | T2.8 SSO | Mid-market procurement requirement. |
| 3 | T3.1 Topia One export | Phase 2 complement positioning core. |
| 3 | T3.2 RFQ build-out | Vendor outreach automation. |
| 3 | T3.3 Vendor relationship mgmt | Approaches Topia parity. |
| 3 | T3.4-T3.9 Various Phase 2 capabilities | Strategic; customer-demand-driven. |
| 4 | T4.1-T4.7 Phase 3+ | Customer-demand-triggered. |

---

*Implementation plan complete. Total scope: ~95-130 weeks of engineering work across all tiers, with Tier 1 being the ship-blocking ~12-17 weeks. Customer-discovery wave (R9 mitigation from audit) should run in parallel with Tier 1 — highest-leverage non-engineering investment.*

*Audit context: April 2026. Verdict locked: 3-4x vs legacy, 2-3x vs closest tech competitors, complement-not-replace for tax-heavy and enterprise. Three operating principles: protect Policy + Estimate Review anchors; out-segment for MVP; honest narrow positioning.*
