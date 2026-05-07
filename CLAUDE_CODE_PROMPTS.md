# ReloPass — Claude Code Implementation Prompts
> Generated: 26 April 2026  
> Source: 15-task product audit + codebase exploration  
> Each prompt is self-contained. Run them in the order shown. Spikes first — they gate everything else.

---

## HOW TO USE THIS FILE

Paste each prompt block directly into a Claude Code session. Each prompt:
- States what file(s) to read first
- Gives the exact task with acceptance criteria
- References real table names, component paths, and function names from the codebase
- Is self-contained — no prior session context needed

**Priority order:**
1. **SPIKES** (verification, ~3 weeks total) — run all in parallel where possible
2. **P0 FIXES** — must ship before any customer sees the product
3. **PHASE 1.5** — mid-market wedge consolidation

---

# ═══════════════════════════════════════════
# PART 1 — VERIFICATION SPIKES
# Run these before writing any new features.
# ═══════════════════════════════════════════

---

## SPIKE-1 · Tenant Isolation + Audit Log Completeness
**Effort:** 1–2 days · **Priority:** EXISTENTIAL (R5) — run before any customer data enters the system

```
You are doing a security and audit completeness verification on the ReloPass codebase.

READ THESE FILES FIRST:
- /supabase/migrations/20260411140000_audit_logs.sql
- /supabase/migrations/20260221105601_remote_schema.sql
- /backend/services/audit_log_service.py
- /supabase/migrations/20260227000000_hr_command_center.sql

TASK: Produce a written verification report covering the following 5 questions. For each question, show the relevant code/SQL evidence and give a PASS / FAIL / PARTIAL verdict.

QUESTION 1 — Tenant Isolation (EXISTENTIAL)
Check whether any API endpoint or Supabase RLS policy could return data belonging to a different company/tenant. Specifically:
a) List every table that stores company-scoped data and confirm it has either an RLS policy filtering by company_id/hr_user_id/auth.uid(), or a backend query that hard-filters by the authenticated user's company.
b) Find any query that does a SELECT without a WHERE clause scoping to the current user's tenant. Look in /backend/database.py, /backend/app/routers/, and /backend/routes/.
c) Check the `case_assignments`, `relocation_cases`, `mobility_cases`, `policy_versions`, and `audit_logs` tables specifically — do their RLS policies correctly use auth.uid() and does the backend respect company_id boundaries?
VERDICT: PASS (all tenant-scoped correctly) / FAIL (leak found — describe it) / PARTIAL (gaps identified)

QUESTION 2 — Audit Log Coverage
The `public.audit_logs` table (from 20260411140000_audit_logs.sql) has triggers on `mobility_cases`, `case_people`, `case_documents`. Check what is NOT covered:
a) Does `case_assignments` status changes get logged?
b) Does `policy_versions` publish/archive get logged (either by trigger or in application code via audit_log_service.py)?
c) Does `relocation_tasks` status changes get logged?
d) Does the old `audit_log` table (text PK, from remote_schema) overlap with or duplicate `audit_logs` (UUID PK)? Which one is the authoritative table?
e) Are denied/rejected actions (e.g. package rejected, exception denied) logged anywhere?
List every action type that should be auditable for a mid-market HR buyer but currently is not.

QUESTION 3 — Actor Attribution
When `audit_log_service.insert_audit_log()` is called from Python services, is `actor_id` always populated with a real user ID, or are there call sites where it defaults to None/system when a human user triggered the action? Grep for all call sites of `insert_audit_log` in /backend/ and list any where actor_id is None or hardcoded as 'system' when it should be human.

QUESTION 4 — RLS Policy Completeness on audit_logs
Check that the `audit_logs` table itself has RLS enabled and that employees cannot read other employees' audit entries. Verify: can an authenticated employee user query audit_logs rows for a case that isn't theirs?

QUESTION 5 — Cross-Tenant Policy Leak
Check `policy_versions` and `policy_benefit_rules`: can an HR user at Company A read policy data belonging to Company B? Verify both the RLS policies and the backend query in /backend/app/routers/ that returns policy data.

OUTPUT FORMAT:
For each question: verdict label, the specific evidence (file path + line numbers), and a concrete remediation instruction if FAIL or PARTIAL.
At the end: a summary table of all gaps found, sorted by severity (EXISTENTIAL > HIGH > MEDIUM).
```

---

## SPIKE-2 · Task Due Date + Date-Based Triggers Verification
**Effort:** 2 hours to verify, 2–3 weeks to implement if absent · **Priority:** P0

```
You are verifying whether task due dates and date-based deadline triggers are correctly wired in the ReloPass codebase.

READ THESE FILES FIRST:
- /supabase/migrations/20260227000000_hr_command_center.sql  (relocation_tasks table — has due_date date column)
- /supabase/migrations/20260227000001_hr_command_center_risk_rpc.sql
- /backend/relocation_plan_view_schemas.py  (RelocationPlanPhaseTask has due_date: Optional[date])
- /backend/relocation_plan_view_service.py  (full file)
- /backend/database.py  (search for due_date references)

TASK: Answer these 5 questions with code evidence and a PASS/FAIL/PARTIAL verdict each.

QUESTION 1 — Is due_date persisted on task creation?
When a new relocation task is created (find the creation path in database.py or relocation_plan_view_service.py), is a due_date value actually computed and stored? Or is due_date always NULL on creation? Show the INSERT statement used.

QUESTION 2 — Is due_date surfaced to the frontend?
Find the API endpoint that returns tasks to the frontend (likely in /backend/app/routers/ or main.py). Does the response schema include due_date? Does the frontend component that renders tasks (check /frontend/src/pages/HrCommandCenter.tsx and /frontend/src/pages/EmployeeRelocationPlanPage.tsx if it exists, or grep for 'due_date' in /frontend/src/) actually display it?

QUESTION 3 — Is overdue status auto-computed or manually set?
The `relocation_tasks` table has status = 'overdue'. Is this status set automatically by a cron job, Supabase scheduled function, or database trigger when `due_date < current_date AND status != 'done'`? Or must it be set manually?
Check: /supabase/functions/ for any scheduler, /supabase/migrations/ for any trigger on relocation_tasks, /backend/ for any background job.

QUESTION 4 — Does the Command Center KPI "Overdue Tasks" actually count tasks with due_date < today?
Find the SQL function or Python query behind `hrAPI.getCommandCenterKPIs()` in the backend (search for 'overdueTasksCount' or the RPC it calls). Does it query `relocation_tasks WHERE due_date < current_date AND status != 'done'`, or is it reading a manually-set status field?

QUESTION 5 — Is there any date-based trigger for repatriation reminders?
The biggest P0 risk (F8 — forgotten repatriation) requires that when `case_assignments.expected_start_date + assignment_duration` approaches, HR gets an alert. Does any such trigger, cron, or notification logic exist? Search /supabase/functions/, /backend/services/, and /backend/app/routers/admin_notifications.py.

OUTPUT:
For each question: PASS/FAIL/PARTIAL + evidence (file:line).
Final section: "Implementation plan" — if any of Q1–Q5 are FAIL/PARTIAL, write the exact SQL migration and/or Python code needed to fix each gap. For Q3 specifically, write the Supabase migration SQL for a trigger that auto-sets status='overdue' when due_date < current_date.
```

---

## SPIKE-3 · contract_type / move_type Abstraction Depth
**Effort:** 3–5 days to verify · **Priority:** P0 before Phase 1.5 domestic moves

```
You are tracing how Case contract_type and move_type propagate through the ReloPass system to determine whether domestic moves and permanent transfers can be supported without a full rewrite.

READ THESE FILES FIRST:
- /backend/relocation_plan_view_schemas.py
- /backend/relocation_plan_view_service.py
- /backend/relocation_plan_draft_normalize.py
- /backend/policy_engine.py
- /backend/database.py  (search for 'contract_type', 'assignment_type', 'move_type')
- /backend/app/models.py

TASK: Trace the value `contract_type` (or `assignment_type`) from intake through to plan generation, policy application, and services catalog, and answer these questions.

QUESTION 1 — Where is assignment_type / contract_type stored?
Find the column in the database schema (check case_assignments, relocation_cases, mobility_cases, employees tables). What are the allowed enum values? Is 'permanent_transfer' or 'domestic' present as a valid value, or only 'long_term_assignment' / 'short_term_assignment'?

QUESTION 2 — Does plan generation branch on contract_type?
In /backend/relocation_plan_view_service.py and /backend/database.py, does the task list generation differ based on contract_type? For example: does a permanent_transfer case skip the "Repatriation" phase? Or are all cases generated with the same default 5-phase template regardless of assignment type?

QUESTION 3 — Does policy_engine.py branch on contract_type?
In /backend/policy_engine.py, does the benefit calculation or document requirement generation change based on whether the assignment is permanent vs temporary vs domestic? Specifically: does a permanent transfer correctly exclude repatriation-related benefits?

QUESTION 4 — Does the services/recommendations layer filter on assignment_type?
Check /backend/app/recommendations/plugins/ — do movers, schools, housing recommendations behave differently for domestic vs international cases? Is there any filtering based on whether origin_country == destination_country?

QUESTION 5 — Is there hardcoded 'international' assumption anywhere?
Grep for hardcoded strings like 'international', 'long_term_assignment' as literals in plan generation, policy application, or services logic. List every location where the code assumes international LTA and would need changing for domestic support.

OUTPUT:
For each question: evidence (file:line) + verdict.
Final assessment: Is domestic move support (option b) a 3–4 week clean implementation, or a 6–8 week refactor? State the key architectural changes required.
```

---

## SPIKE-4 · Family / Dual-Career Signal Propagation
**Effort:** 2–3 hours · **Priority:** P1

```
You are tracing whether the spouse 'wantsToWork' flag captured at intake actually propagates to downstream systems.

READ THESE FILES FIRST:
- /backend/policy_engine.py  (lines around spouse.wantsToWork — already found at line 97)
- /backend/relocation_plan_draft_normalize.py
- /backend/app/recommendations/plugins/  (all files)
- /backend/services/case_context_service.py

TASK: Trace the field `spouse.wantsToWork` (also known as `wantsToWork` on the spouse object in the profile JSON) from intake wizard through to:

TRACE 1 — Destination resource surfacing
When `spouse.wantsToWork = true`, does the resources/recommendations layer surface job-search support resources, dual-career support, or language lessons for the spouse? Check /backend/services/country_resources.py and /backend/app/recommendations/. If not, what would need to change?

TRACE 2 — Services questionnaire
Does the services questionnaire (Step in the employee journey — check /frontend/src/pages/ for ServicesQuestions.tsx or similar) ask about spouse employment preferences when wantsToWork is true? Or is this flag invisible to the services selection flow?

TRACE 3 — Policy benefit visibility
In /backend/policy_engine.py line 97, `required_docs` adds spouseWork documents when wantsToWork=true. Does this also trigger the `SPOUSE_SUPPORT` benefit category (visible in /backend/app/models.py line 197) to be included in the estimate? Trace from policy_engine → policy benefit rules → Estimate screen.

TRACE 4 — Case context / mobility graph
Check /backend/app/routers/mobility_context.py. When the mobility case context is built, is the spouse employment flag included as a signal? Is it passed to any recommendation scoring?

OUTPUT:
For each trace: PROPAGATES (with evidence) / STORED-BUT-NOT-READ (flag exists but nothing reads it downstream) / MISSING (flag not even stored).
Final section: list every downstream consumer that should read wantsToWork but currently doesn't, with the specific code change needed in each.
```

---

## SPIKE-5 · Destination Data Depth Audit
**Effort:** 1–2 weeks of content audit · **Priority:** Pre-launch

```
You are auditing the depth of destination data in the ReloPass recommendations and resources system to determine which corridors are ready for pilot launch.

READ THESE FILES FIRST:
- /backend/app/recommendations/datasets/  (all JSON files — movers.json, schools.json, living_areas.json, etc.)
- /backend/services/country_resources.py
- /backend/app/recommendations/plugins/schools.py
- /backend/app/recommendations/plugins/living_areas.py
- /backend/app/recommendations/plugins/movers.py

TASK: For each destination represented in the datasets, score it against the Singapore reference (which is known to be at 5/5 depth from the audit):

SCORING RUBRIC (score each 0–5):
a) Movers: how many movers are listed with real names, scores, and lead-time data?
b) Schools: how many schools with real names, fees, application deadlines, quality scores?
c) Neighborhoods/Living areas: how many with lifestyle scoring, monthly cost, commute data?
d) Resource categories: how many of the 12+ resource categories (banking, mobile, healthcare, transport, expat groups, etc.) have real curated content vs placeholder?
e) Corridor-specific compliance watchouts: are there any destination-specific visa/permit notes?

PRODUCE:
1. A table: destination | movers | schools | neighborhoods | resources | watchouts | TOTAL/25 | READY?
2. A ranked list of the top 3 destinations by depth score after Singapore (these become the Phase 1 launch corridors).
3. For the bottom destinations (score < 10/25): list exactly what data is missing and estimate how long it would take a content researcher to bring them to 20/25.
4. Identify any destinations where JSON data exists but is clearly placeholder/synthetic (e.g. generic vendor names, zero fees, missing addresses).
```

---

# ═══════════════════════════════════════════
# PART 2 — P0 FIXES
# Ship all of these before any customer pilot.
# ═══════════════════════════════════════════

---

## P0-1 · Strip Dev Tooling from Production UI
**Effort:** 2–4 hours · **Priority:** P0 (ship immediately)

```
You are cleaning up developer-only UI elements that must not appear in a production environment.

READ THESE FILES FIRST:
- /frontend/src/pages/AssignmentDebugPage.tsx
- /frontend/src/pages/AssignmentDebugPanel.tsx
- /frontend/src/pages/DebugAuth.tsx
- /frontend/src/pages/NavigationAudit.tsx
- /frontend/src/components/AppShell.tsx
- /frontend/src/App.tsx or wherever routes are defined (grep for 'debug' or 'Debug' in /frontend/src/)

TASK:
1. Find every route that renders a debug or dev-only page (AssignmentDebugPage, DebugAuth, NavigationAudit, AssignmentDebugPanel, and any similar pages).
2. Gate each debug route behind an environment check: `import.meta.env.DEV` in Vite. The route should only render in development; in production it should redirect to `/` or return a 404 component.
3. Find any components that render raw UUIDs, internal session tokens, or developer-facing JSON blobs visible to end users. Search for:
   - Raw UUID display (regex: /[0-9a-f]{8}-[0-9a-f]{4}/)  in employee-facing components (not admin)
   - Any `JSON.stringify` or `<pre>` tags in non-admin pages
   - Any component that renders internal error stack traces to the user
4. Check /frontend/src/components/AppShell.tsx for any performance panel, debug toggle, or dev-mode indicator — gate it behind `import.meta.env.DEV`.
5. Verify /frontend/src/pages/admin/ routes are properly gated so only users with role='ADMIN' can access them (check the route guard logic).

ACCEPTANCE CRITERIA:
- No debug routes accessible when VITE_ENV=production
- No raw UUIDs rendered in employee-facing pages (/employee/* routes)
- No stack traces or JSON blobs visible to non-admin users
- All admin/* routes return 403 for non-admin users
- Write a brief test comment in each modified file noting what was gated and why
```

---

## P0-2 · Hide RFQ Screen + Reframe Funnel Ending
**Effort:** 2–4 hours · **Priority:** P0 (hides a broken feature from buyers)

```
You are hiding the RFQ (Request for Quote) flow from the employee journey because it currently terminates in a localStorage state and shows "sending requests from here is not available yet." This must not be visible to pilot customers.

READ THESE FILES FIRST:
- /frontend/src/pages/EmployeeJourney.tsx  (look at FLOW_STEPS array — step 4 is "(Soon) Request quotes")
- grep -r "ServicesRfq\|rfq\|RFQ\|QuoteRfq\|QuotesInbox" /frontend/src/ --include="*.tsx" to find all RFQ-related components and pages
- /frontend/src/App.tsx or router file to find all routes

TASK:
1. Find every route and navigation link that leads to the RFQ flow (ServicesRfqNew, QuoteRfqDetail, QuotesInbox, and any similar).
2. Remove these routes from the main router OR gate them behind a feature flag `VITE_FEATURE_RFQ_ENABLED=true` that defaults to false. Do not delete the component files — just prevent navigation to them.
3. In EmployeeJourney.tsx, update the FLOW_STEPS array to remove step "4. (Soon) Request quotes" OR replace it with a message that accurately reflects the current state: the flow ends at "Review budget vs policy" and next steps happen directly with HR.
4. Find where the employee journey funnel ends after ServicesEstimate/budget review. Update the final CTA on that page to say something like: "Your selection is complete. HR will review your package and be in touch." — do NOT show a button that goes to a broken RFQ screen.
5. In the employee navigation sidebar (check AppShell.tsx or the nav component), find any link labelled "Quotes", "RFQ", "Providers" or similar that leads to the broken flow and hide it.

ACCEPTANCE CRITERIA:
- No path through the employee UI can reach a page that says "sending requests from here is not available yet"
- The employee journey funnel has a clean, confident ending that sets expectations correctly
- All RFQ component files are preserved (not deleted) so Phase 2 can resurrect them
- Add a TODO comment in the router: "// RFQ: re-enable when VITE_FEATURE_RFQ_ENABLED=true, see Phase 2 roadmap"
```

---

## P0-3 · Employee Dashboard Redesign (First-Impression Fix)
**Effort:** 1–2 weeks · **Priority:** P0

```
You are rebuilding the employee-facing dashboard/journey entry point. The current EmployeeJourney.tsx exposes raw UUIDs, "Section A/B" jargon, 9+ navigation items, and requires manual copy-paste of an assignment ID. This is the first thing a relocated employee sees and it currently looks like an internal engineering tool.

READ THESE FILES FIRST:
- /frontend/src/pages/EmployeeJourney.tsx  (full file — the current implementation)
- /frontend/src/contexts/EmployeeAssignmentContext.tsx  (if it exists — check the context)
- /frontend/src/types/employeeAssignmentOverview.ts  (EmployeeLinkedOverviewRow type)
- /frontend/src/components/AppShell.tsx  (nav structure)
- /frontend/src/api/client.ts  (find employeeAPI methods available)

DESIGN REQUIREMENTS (from product audit):
The employee entry experience must accomplish 3 things:
1. Show the employee their current case status clearly — phase they're in, what's done, what's next
2. NOT expose any UUIDs, internal IDs, "Section A/B" labels, or implementation details
3. Reduce navigation to maximum 4 items: Plan | Estimate | Resources | Messages

SPECIFIC TASKS:

TASK 1 — Magic-link / auto-claim (eliminate manual UUID entry)
The current EmployeeJourney.tsx shows a "Manual Claim" form where employees paste their Assignment ID UUID. This must be replaced with:
- If the user arrives via a magic link (URL contains ?token= or ?assignment_id=), auto-claim silently and redirect to their case view
- If the user is already linked to an assignment (check employeeAPI for a "get my assignments" endpoint), show their case directly without the claim form
- Only show the manual claim form as a LAST RESORT with better copy: instead of "Assignment ID (UUID)", use "Code from HR" and give an example that doesn't look like a UUID

TASK 2 — Nav reduction
In the AppShell or the employee nav section, reduce visible navigation to exactly 4 items:
- Plan (their relocation plan / task list)
- Estimate (budget vs policy review)
- Resources (destination guide)
- Messages (HR communication)
Hide everything else behind a "More" dropdown or remove it entirely.

TASK 3 — Clean status display
The FLOW_STEPS array currently shows "3. Review budget vs policy" and "4. (Soon) Request quotes". Replace this with a clean progress indicator that shows:
- Current phase name (Pre-departure / Immigration / Logistics / Arrival / Post-arrival)
- Number of tasks completed vs total
- Next action with a clear label (no internal codes)

TASK 4 — Zero UUID exposure
Audit every string rendered in the employee view. Any value matching UUID regex `/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i` must be replaced with a human-readable alternative or hidden entirely.

ACCEPTANCE CRITERIA:
- An employee who receives a magic-link email never sees a UUID or is asked to paste one
- Navigation shows exactly 4 items in the primary nav
- No "Section A", "Section B", or snake_case identifiers visible
- No UUID strings rendered anywhere in the employee view
- Page renders a loading skeleton (not a blank screen) while data loads
```

---

## P0-4 · ECB FX Rate Snapshot Persistence
**Effort:** 1–2 weeks · **Priority:** P0 (required for Estimate Review reliability)

```
You are implementing ECB (European Central Bank) foreign exchange rate fetching and persistence. This is a dependency for the Estimate Review screen — without live FX rates, the budget vs policy comparison cannot be multi-currency.

READ THESE FILES FIRST:
- /supabase/migrations/  (list all — find if any fx_rates table exists)
- /backend/app/models.py
- /backend/app/main.py or /backend/main.py  (to understand where to add a scheduled task)
- /backend/policy_engine.py  (to understand how currency is handled today)
- grep -r "currency\|fx_rate\|exchange_rate" /backend/ --include="*.py" | head -40

TASK: Implement a complete FX rate persistence layer.

STEP 1 — Database migration
Create a new Supabase migration file: /supabase/migrations/YYYYMMDD000000_fx_rates.sql
Create the table:
```sql
create table if not exists public.fx_rates (
  id uuid primary key default gen_random_uuid(),
  currency_code text not null,        -- ISO 4217 e.g. 'USD', 'GBP', 'SGD'
  rate_to_eur numeric(18, 6) not null, -- ECB rates are EUR-based
  source text not null default 'ECB',
  source_date date not null,           -- The date ECB published this rate
  fetched_at timestamptz default now(),
  created_at timestamptz default now()
);
create unique index if not exists idx_fx_rates_currency_source_date 
  on public.fx_rates (currency_code, source_date);
create index if not exists idx_fx_rates_source_date 
  on public.fx_rates (source_date desc);
```
Add RLS: authenticated users can SELECT; only service role can INSERT.

STEP 2 — ECB fetch service
Create /backend/services/fx_rate_service.py implementing:

```python
ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"

def fetch_ecb_rates() -> dict[str, float]:
    """Fetch today's ECB EUR reference rates. Returns {currency_code: rate_to_eur}."""
    # Parse the ECB XML envelope format
    # Return dict of {currency: rate} where rate = how many EUR per 1 currency_unit
    # i.e. rate_to_eur = 1 / ECB_rate (ECB gives how many currency units per 1 EUR)

def upsert_fx_rates(conn, rates: dict[str, float], source_date: date) -> int:
    """Upsert rates into fx_rates table. Returns count of rows upserted."""
    # Use INSERT ... ON CONFLICT (currency_code, source_date) DO NOTHING

def get_latest_rate(conn, currency_code: str) -> dict | None:
    """Returns {rate_to_eur, source_date, fetched_at} for the most recent rate."""
    # SELECT from fx_rates WHERE currency_code = :code ORDER BY source_date DESC LIMIT 1

def convert_to_eur(conn, amount: float, from_currency: str) -> dict:
    """Returns {eur_amount, rate_used, source_date, warning: bool}
    warning=True if source_date is older than 7 days"""
```

STEP 3 — API endpoint
Add a route to the backend (in /backend/app/routers/ or /backend/main.py):
`GET /api/fx-rates/latest` — returns the most recent rates for the 10 most common currencies (EUR, USD, GBP, SGD, NOK, SEK, CHF, JPY, AUD, CAD)

STEP 4 — Scheduled refresh
Add a daily fetch job. Check if there's an existing scheduler in /backend/ (look for APScheduler, Celery, or cron references). If not, add a Supabase Edge Function at /supabase/functions/refresh-fx-rates/index.ts that calls the ECB URL and upserts into the fx_rates table via the Supabase service role key. Configure it to run daily at 16:30 CET.

ACCEPTANCE CRITERIA:
- fx_rates table exists and has RLS
- fetch_ecb_rates() correctly parses ECB XML and returns a dict
- convert_to_eur() returns a warning flag when rates are stale (> 7 days)
- GET /api/fx-rates/latest returns current rates
- If ECB returns no data (weekend/holiday), the endpoint returns the most recent available rate with source_date clearly indicated
- Unit test: test_fx_rate_service.py with a mocked ECB XML response
```

---

## P0-5 · ExceptionRequest Entity + Workflow
**Effort:** 3–4 weeks · **Priority:** P0 (required to complete Estimate Review)

```
You are implementing the ExceptionRequest entity — the mechanism by which an employee can request that HR covers a cost that exceeds their policy cap. This is a hard dependency for the Estimate Review screen.

READ THESE FILES FIRST:
- /supabase/migrations/20260221105601_remote_schema.sql  (existing policy/case tables)
- /supabase/migrations/20260227000000_hr_command_center.sql  (case_assignments, relocation_tasks)
- /backend/app/models.py  (existing SQLAlchemy models)
- /backend/app/routers/  (list all routers to understand the API structure)
- /backend/services/audit_log_service.py  (to log exception events)
- /frontend/src/types.ts  (PolicyException type already exists — check it)

TASK: Implement a complete ExceptionRequest workflow.

STEP 1 — Database migration
Create /supabase/migrations/YYYYMMDD000001_exception_requests.sql:

```sql
create table if not exists public.exception_requests (
  id uuid primary key default gen_random_uuid(),
  assignment_id text not null references public.case_assignments(id) on delete cascade,
  employee_user_id text not null,
  service_category text not null,  -- e.g. 'schools', 'housing', 'movers'
  vendor_name text,
  requested_amount numeric,
  policy_cap numeric,
  currency text default 'EUR',
  over_amount numeric generated always as (requested_amount - policy_cap) stored,
  employee_reason text not null,    -- Required: why does employee need this exception?
  status text not null default 'pending' 
    check (status in ('pending','approved','rejected','withdrawn')),
  hr_notes text,
  reviewed_by text,
  reviewed_at timestamptz,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create index if not exists idx_exception_requests_assignment on public.exception_requests(assignment_id);
create index if not exists idx_exception_requests_status on public.exception_requests(status);
```
Add RLS: employees can SELECT/INSERT their own rows; HR can SELECT/UPDATE for their company's assignments.
Add trigger: updated_at auto-updates on change.

STEP 2 — Backend models + router
In /backend/app/models.py, add the ExceptionRequest SQLAlchemy model.
Create /backend/app/routers/exception_requests.py with:
- POST /api/exception-requests — employee submits a request (body: assignment_id, service_category, vendor_name, requested_amount, policy_cap, currency, employee_reason)
- GET /api/exception-requests?assignment_id=X — returns all requests for an assignment (accessible by employee for their own, by HR for their company's)
- PATCH /api/exception-requests/{id} — HR approves/rejects (body: status, hr_notes)
Each write operation must call insert_audit_log() from audit_log_service.py with the appropriate action_type ('exception_request_created', 'exception_request_approved', 'exception_request_rejected').

STEP 3 — Frontend types
In /frontend/src/types.ts, ensure ExceptionRequest type exists:
```typescript
export interface ExceptionRequest {
  id: string;
  assignmentId: string;
  serviceCategory: string;
  vendorName?: string;
  requestedAmount: number;
  policyCap: number;
  currency: string;
  overAmount: number;
  employeeReason: string;
  status: 'pending' | 'approved' | 'rejected' | 'withdrawn';
  hrNotes?: string;
  reviewedBy?: string;
  reviewedAt?: string;
  createdAt: string;
}
```

STEP 4 — Exception submission form component
Create /frontend/src/components/ExceptionRequestForm.tsx:
- Props: { serviceCategory, vendorName, requestedAmount, policyCap, currency, assignmentId, onSubmit, onCancel }
- Form fields: employeeReason (textarea, required, min 20 chars), a summary showing "You are requesting €X above your €Y policy cap for [serviceCategory]"
- On submit: calls POST /api/exception-requests, shows success state
- Validation: reason must be at least 20 characters

STEP 5 — HR exception review component
Create /frontend/src/components/ExceptionRequestReview.tsx:
- Shows pending exception requests for HR (fetch from GET /api/exception-requests)
- Each item: employee name, service category, over-policy amount, employee reason
- Actions: Approve (with optional hr_notes) / Reject (with required hr_notes)
- After action: item moves to resolved state with green/red badge

ACCEPTANCE CRITERIA:
- Employee can submit exception request from Estimate Review
- HR sees pending exceptions in their case detail view
- Both approve and reject paths work with audit log entries written
- Employee can see the status of their exception request
- Over-policy "Proceed" button is disabled until either: exception approved, or employee explicitly acknowledges personal cost
```

---

## P0-6 · Estimate Review — Full Buildout (The Killer Screen)
**Effort:** 3–5 weeks · **Priority:** P0 (the single most important feature for buyer conversion)

```
You are building the Estimate Review screen — the screen that shows employees their selected services compared against policy caps, surfacing any over-budget items and their personal cost. This is the product's core value proposition for buyers.

READ THESE FILES FIRST:
- /backend/policy_engine.py  (how policy caps and estimates are computed today)
- /backend/schemas_policy_caps.py  (PolicyCap schema)
- /frontend/src/types.ts  (PolicyException, PolicyCap, PolicyConfig, PolicySpendStatus, PolicySpendItem, PolicyResponse)
- /frontend/src/api/client.ts  (find the endpoint that returns policy spend data)
- /backend/services/fx_rate_service.py  (after P0-4 is done — needed for currency conversion)

THE SPEC (implement exactly this):

SECTION 1 — Case Header
At the top of the page, show:
"{Employee name} · {Origin city} → {Destination city} · Move {start date} · {duration} mo · {family composition e.g. '1 spouse + 1 child'}"
"Policy: {policy name} ({tier: Standard/Premium/etc.}) · {display currency}"

SECTION 2 — Total Package Summary Card
Show three lines:
- "Estimated package cost ({duration} mo)" — right-aligned total
- "Your policy budget" — right-aligned cap total
- Separator line
- "Above/Below policy by €X" with status badge

If above policy: amber/red warning box: "If you proceed with these selections, you would pay €X from your own pocket over the assignment."
Three action buttons: [Edit selections] [Request exception] [Proceed anyway]
"Proceed anyway" must be disabled if any service is over policy AND no exception is approved.

SECTION 3 — Per-Service Breakdown
For each selected service, render a row with:
- Status icon (✓ green if within policy, ⚠ yellow if 80-99% of cap, 🔴 red if over, ⓘ grey if no cap defined, — if excluded)
- Service label + vendor name
- "€X/unit × Y {unit_label} = €Z total" — always show the math
- "Cap: €A/{unit_label} × Y = €B total" — show cap math too
- Status text: "Within policy. Fully covered." / "Above policy by €X. Personal cost: €Y/year."
- [Why?] link that opens the policy rule that defines this cap

COLOR RULES (implement exactly):
- Green: actual ≤ 80% of cap
- Yellow: 80% < actual ≤ 100% of cap
- Red: actual > 100% of cap
- Grey (⚪): no cap defined in policy for this benefit
- Strikethrough (—): benefit explicitly excluded by policy

SECTION 4 — Summary Footer
"Covered by your employer: €X (within policy)"
"Your personal cost: €Y (above policy)"
"Total package: €Z"
"Currency note: Estimates shown in EUR. Exchange rates from ECB, [date]. [Link to ECB]"

MULTI-CURRENCY HANDLING:
- All amounts stored in source currency (may be SGD, USD, etc.)
- Use fx_rate_service.convert_to_eur() for display
- Show source currency in tooltip on hover
- If FX rate older than 24h: show footer warning "Exchange rates last refreshed [date]. Refresh available."

MULTIPLIER DISPLAY RULES (show the math, never just the total):
- movers: "one-time" (multiplier = 1)
- housing: "€X/mo × {duration_months} mo"
- schools: "€X/yr × {children_count} child × {duration_years} yr"
- language training: "€X/person × {eligible_family_members} people"

EDGE CASES TO HANDLE:
1. No policy published yet → Banner: "HR is finalizing your policy. Figures below are estimates only." Hide cap columns.
2. Partial policy coverage → per-service status differs, show "No cap defined" not zero
3. Policy cap expressed as % of salary → compute against salary_band midpoint, add footnote
4. Selection above policy + "Proceed anyway" → MUST create ExceptionRequest record, cannot proceed silently
5. HR view of same screen → action buttons become [Approve as-is] [Approve with exception] [Request changes]

BACKEND ENDPOINT REQUIRED:
`GET /api/assignments/{id}/estimate-review` returns:
```json
{
  "caseHeader": { "employeeName", "origin", "destination", "startDate", "durationMonths", "familyComposition", "policyName", "policyTier", "displayCurrency" },
  "totals": { "estimatedTotal", "policyBudget", "coveredAmount", "personalCost", "currency" },
  "lineItems": [{
    "serviceCategory", "vendorName", "unitCost", "unit", "multiplier", "totalCost",
    "cap", "capUnit", "capTotal", "delta", "status", "personalCost",
    "sourceCurrency", "fxRate", "fxSourceDate"
  }],
  "fxMeta": { "displayCurrency", "ecbDate", "isStale": bool }
}
```

ACCEPTANCE CRITERIA:
- Always shows the math (never just a final number)
- Over-policy items are red with explicit personal cost in euros and per-month breakdown
- "Proceed anyway" is blocked unless exception is approved OR employee explicitly accepts personal cost
- FX source date shown on every page load
- HR can see the same screen with approve/reject actions
- Every state change (employee views, proceeds, requests exception) writes to audit_log
- Mobile-responsive (readable on a phone)
```

---

## P0-7 · Task Due Date Wiring + Overdue Auto-Classification
**Effort:** 2–3 weeks · **Priority:** P0 (run only if Spike-2 confirms gaps)

```
PREREQUISITE: Run SPIKE-2 first. Only run this prompt if Spike-2 returned FAIL or PARTIAL on any of its 5 questions.

You are wiring task due dates and automatic overdue classification into the ReloPass task system.

READ THESE FILES FIRST:
- /supabase/migrations/20260227000000_hr_command_center.sql  (relocation_tasks schema — due_date column exists)
- /backend/relocation_plan_view_service.py
- /backend/relocation_plan_view_schemas.py  (RelocationPlanPhaseTask has due_date field)
- /backend/database.py  (search for relocation_tasks INSERT/UPDATE)

TASK 1 — Compute and store due_date on task creation
When a relocation task is created (find the insertion path), compute due_date based on case context:
- "Pre-departure" phase tasks: due_date = case.expected_start_date - 30 days
- "Immigration" phase tasks: due_date = case.expected_start_date - 60 days
- "Logistics" phase tasks: due_date = case.expected_start_date - 14 days
- "Arrival" phase tasks: due_date = case.expected_start_date + 7 days
- "Post-arrival" phase tasks: due_date = case.expected_start_date + 30 days
- "Repatriation" tasks: due_date = case.expected_end_date - 30 days (if expected_end_date exists)

Store this on INSERT into relocation_tasks.

TASK 2 — Auto-overdue trigger
Create a Supabase migration with a Postgres function that runs daily via pg_cron (or create a Supabase Edge Function):
```sql
-- Mark tasks as overdue when due_date has passed and task is not done
UPDATE public.relocation_tasks
SET status = 'overdue', updated_at = now()
WHERE status NOT IN ('done', 'overdue')
  AND due_date IS NOT NULL
  AND due_date < current_date;
```
If pg_cron is not available, create /supabase/functions/mark-overdue-tasks/index.ts as an Edge Function callable via a daily cron in the Supabase dashboard.

TASK 3 — Repatriation deadline alert
Create a notification trigger: when a task in the "Post-arrival" or "Repatriation" phase has due_date = today + 14 days and status != 'done', insert a row into a notifications table (or case_events table) with event_type = 'repatriation_deadline_approaching'. Check /backend/app/routers/admin_notifications.py to understand the existing notification infrastructure.

TASK 4 — Expose due_date to frontend
Ensure the API endpoint that returns tasks to the frontend includes due_date. In /frontend/src/pages/HrCommandCenter.tsx, in the CaseRow type and the table rendering, add a "Due" column that shows:
- Green: due > 7 days
- Yellow: due 1-7 days
- Red: overdue or due today

ACCEPTANCE CRITERIA:
- Every task created for a case with expected_start_date gets a computed due_date
- Tasks auto-transition to 'overdue' status when past due
- Repatriation tasks generate a warning 14 days before due
- Frontend table shows due dates with color coding
- Overdue count in Command Center KPIs accurately reflects tasks with status='overdue' OR (due_date < today AND status != 'done')
```

---

## P0-8 · Audit Log Gap Remediation
**Effort:** 4–6 weeks · **Priority:** P0 (run after Spike-1 identifies specific gaps)

```
PREREQUISITE: Run SPIKE-1 first. This prompt addresses the specific gaps identified by that spike.

You are extending audit log coverage to all events required for a mid-market HR buyer's compliance and accountability needs.

READ THESE FILES FIRST:
- /backend/services/audit_log_service.py  (the insert_audit_log function)
- /supabase/migrations/20260411140000_audit_logs.sql  (current triggers: mobility_cases, case_people, case_documents)
- /supabase/migrations/20260227000000_hr_command_center.sql  (case_assignments, relocation_tasks)
- /backend/app/routers/  (all router files — find where writes happen without audit calls)

TASK 1 — Extend Postgres triggers to cover critical tables
Create a new migration that adds the relopass_audit_row() trigger to:
- public.case_assignments (status changes, decision changes)
- public.relocation_tasks (status changes)
- public.policy_versions (status: draft → approved, approved → archived)
- public.exception_requests (when built in P0-5)

TASK 2 — Audit application-level events (not row changes)
These events cannot be captured by DB triggers — they must be logged in Python code.
For each of the following events, find where it happens in the codebase and add an insert_audit_log() call with the appropriate actor_id:

a) Policy publish: when an HR user publishes a policy version, log:
   entity_type='policy_version', action_type='published', actor_type='human', actor_id=<hr_user_id>

b) Package submitted by employee: when employee submits their services selection, log:
   entity_type='case_assignment', action_type='package_submitted'

c) HR approves/rejects package: 
   action_type='package_approved' or 'package_rejected'

d) Exception request created/approved/rejected (covered in P0-5 but list here for completeness)

e) Document uploaded:
   entity_type='case_document', action_type='document_uploaded'

f) Case manually set to risk status (green/yellow/red):
   entity_type='case_assignment', action_type='risk_status_changed', new_value={'risk_status': 'red'}

TASK 3 — Unified audit trail API endpoint
Create GET /api/assignments/{id}/audit-trail that returns a chronological list of all audit events for a case, joining:
- audit_logs rows where entity_id matches the assignment_id or its linked case_id
- case_events rows for the assignment
Format each entry as: { timestamp, actor, action, detail_text }
HR can access this; employees see a filtered view (their own actions + status changes only).

TASK 4 — Fix actor attribution gaps
From Spike-1 Q3, find all call sites of insert_audit_log() where actor_id is None or 'system' when it should carry the authenticated user's ID. Fix each by threading the user_id through from the request context. In FastAPI, the current user should be available from the auth dependency.

ACCEPTANCE CRITERIA:
- All 6 application-level events (a-f above) produce audit_log rows on every occurrence
- No audit row has actor_type='human' with a null actor_id
- GET /api/assignments/{id}/audit-trail returns a correctly ordered timeline
- A test in /backend/tests/ verifies that a package submission followed by HR approval produces 2 audit rows with correct actor attribution
```

---

## P0-9 · Command Center Simplification
**Effort:** 1–2 weeks · **Priority:** P0

```
You are simplifying the HR Command Center KPI panel to show only meaningful, accurate metrics.

READ THESE FILES FIRST:
- /frontend/src/pages/HrCommandCenter.tsx  (full file — currently shows 8 KPIs)
- /frontend/src/components/command-center/KPICard.tsx
- /backend/  (find the endpoint that serves getCommandCenterKPIs — search for 'command_center' or 'kpi' in routers)

CURRENT STATE:
The Command Center shows 8 KPIs: Active Cases, Action Required, Departing Soon, Completed (YTD), At Risk, Attention Needed, Overdue Tasks, Budget Overruns.
Some of these (Budget Overruns, Overdue Tasks) may be inaccurate until P0-6 (Estimate Review) and P0-7 (due dates) are complete.

TASK 1 — Reduce to 3 primary KPIs + expandable secondary
Primary (always visible, always accurate):
1. Active Cases — count of cases with status not in ('closed', 'rejected')
2. Action Required — cases where HR has a pending task (package awaiting review, exception request pending, etc.)
3. Departing Soon — cases with expected_start_date within next 30 days

Secondary (shown as a collapsed "More metrics" section, visually lower weight):
4. At Risk (red)
5. Completed (YTD)

Deferred (hide until Estimate Review and due_date wiring are done):
- Budget Overruns → add a feature flag `VITE_FEATURE_BUDGET_KPI=false`, render as grayed-out "Coming soon" card when false
- Overdue Tasks → same feature flag pattern

TASK 2 — Admin-configurable KPI labels
In the backend endpoint, make the 3 primary KPI labels configurable per-tenant (stored in a company_settings JSON column or a simple key-value table). Default labels are the ones above. This allows HR teams to rename "Action Required" to their internal terminology.

TASK 3 — Empty state
When Active Cases = 0 (new tenant, no cases yet), show a helpful empty state: "No active cases. Create your first case to get started." with a CTA button.

ACCEPTANCE CRITERIA:
- Primary nav shows exactly 3 KPI cards prominently
- Budget Overruns and Overdue Tasks are hidden behind a feature flag (both default to hidden)
- Empty state renders correctly
- KPI values load with a skeleton shimmer, not a blank box
- Each KPI card has a tooltip explaining what it counts (shown on hover)
```

---

## P0-10 · Case `paused` Status
**Effort:** 1 week · **Priority:** P0

```
You are adding a 'paused' status to cases, enabling HR to suspend a relocation temporarily (e.g. employee changes mind, visa delays) without closing or deleting the case.

READ THESE FILES FIRST:
- /supabase/migrations/20260221105601_remote_schema.sql  (find the status enum for case_assignments or relocation_cases)
- /frontend/src/types.ts  (AssignmentStatus enum)
- /backend/app/routers/  (find PATCH endpoint for case status updates)
- /frontend/src/pages/HrCommandCenter.tsx  (case status rendering)

TASK 1 — Add 'paused' to status enums
In the database: alter the status check constraint on case_assignments to add 'paused':
```sql
ALTER TABLE public.case_assignments 
  DROP CONSTRAINT IF EXISTS case_assignments_status_check;
ALTER TABLE public.case_assignments 
  ADD CONSTRAINT case_assignments_status_check 
  CHECK (status IN ('created','assigned','awaiting_intake','submitted','approved','rejected','closed','paused'));
```
In /frontend/src/types.ts, add 'paused' to AssignmentStatus type.

TASK 2 — Pause/resume UI in HR case detail
In the HR case detail view (check /frontend/src/pages/HrCaseSummary.tsx or HrCommandCenterCaseDetail.tsx), add:
- A "Pause case" button visible when case status is active (created/assigned/awaiting_intake/submitted)
- Clicking shows a modal: "Reason for pausing (optional)" textarea + Confirm/Cancel
- A "Resume" button visible when case status is 'paused'
- Paused cases show a yellow "Paused" badge in the case list

TASK 3 — Backend PATCH endpoint
The PATCH /api/assignments/{id} endpoint (or equivalent) should accept status='paused' with an optional pause_reason. Write the pause_reason to case_events (event_type='case_paused') and log to audit_log.

TASK 4 — Exclude paused cases from certain KPIs
In the Command Center KPIs: "Departing Soon" and "Action Required" should exclude paused cases. "Active Cases" should include them but show a sub-count "(X paused)".

ACCEPTANCE CRITERIA:
- HR can pause and resume any active case
- Paused cases are visually distinct (yellow badge) in all list views
- Pause action writes to audit_log with reason
- Paused cases excluded from Departing Soon and Action Required KPIs
- No data is deleted when a case is paused
```

---

# ═══════════════════════════════════════════
# PART 3 — PHASE 1.5 FEATURES
# After all P0 fixes are shipped and at least 1 pilot is running.
# ═══════════════════════════════════════════

---

## P1.5-1 · Domestic Move Support (move_type abstraction)
**Effort:** 3–4 weeks (clean) or 6–8 weeks (if hardcoded) · **Priority:** High (French mid-market wedge)

```
PREREQUISITE: Run SPIKE-3 first. The effort estimate here depends on what Spike-3 found.

You are adding domestic move support — enabling ReloPass to manage within-country relocations (e.g. Paris → Lyon) as a first-class case type.

READ THESE FILES FIRST:
- /backend/relocation_plan_view_service.py
- /backend/relocation_plan_draft_normalize.py
- /backend/policy_engine.py
- /supabase/migrations/20260227000000_hr_command_center.sql  (case_assignments)
- SPIKE-3 output (the hardcoded international assumption locations found)

TASK 1 — Add move_type to case schema
Add move_type column to case_assignments:
```sql
ALTER TABLE public.case_assignments 
  ADD COLUMN IF NOT EXISTS move_type text 
  CHECK (move_type IN ('international_lta','international_sta','permanent_transfer','domestic','local_hire'))
  DEFAULT 'international_lta';
```
In the case creation wizard (frontend/src/pages/Step1RelocationBasics.tsx or CaseWizardPage.tsx), add move_type selection.

TASK 2 — Branch plan generation on move_type
In /backend/relocation_plan_view_service.py, make the task template selection conditional on move_type:
- domestic cases: omit Immigration phase entirely, omit visa-related tasks
- permanent_transfer cases: omit Repatriation phase, modify Post-arrival tasks
- international cases: current behavior (no change)

TASK 3 — Branch policy engine on move_type
In /backend/policy_engine.py, skip immigration-related document requirements for domestic cases. For permanent transfers, exclude repatriation-related benefits.

TASK 4 — Branch recommendations on move_type
In /backend/app/recommendations/, for domestic cases: movers plugin should filter for domestic movers (add a `domestic_moves: bool` field to movers.json dataset); schools plugin can run normally; housing plugin should filter for the destination city without international-housing filters.

TASK 5 — Case wizard intake for domestic
In the intake wizard, when move_type='domestic': skip the visa/immigration questions (Step2EmployeeProfile nationality fields, work permit questions), show only the relevant domestic logistics questions.

ACCEPTANCE CRITERIA:
- Domestic case can be created without immigration questions
- Domestic case plan has no Immigration phase
- Permanent transfer plan has no Repatriation phase
- Recommendations for domestic cases only show domestic-capable vendors
- All existing international case behavior is unchanged (regression test)
- Unit test: create a domestic case, verify plan has exactly 4 phases (no Immigration)
```

---

## P1.5-2 · CaseStakeholder Model (Minimum Viable RACI)
**Effort:** 6–8 weeks · **Priority:** High (mid-market multi-actor cases)

```
You are adding a CaseStakeholder model — enabling multiple humans to be formally associated with a relocation case beyond just HR and the employee.

READ THESE FILES FIRST:
- /supabase/migrations/20260221105601_remote_schema.sql
- /backend/app/models.py
- /frontend/src/types.ts  (Assignment, AssignmentDetail)
- /backend/app/routers/  (find the case detail endpoint)

STAKEHOLDER ROLES TO SUPPORT (minimum viable set):
- hr_lead (current HR user — already exists)
- employee (current employee — already exists)
- hiring_manager — can view case status, cannot edit
- finance_approver — receives exception request notifications, can approve/reject budget exceptions
- hr_delegate — another HR person who can act on behalf of hr_lead

TASK 1 — Database
Create /supabase/migrations/YYYYMMDD000002_case_stakeholders.sql:
```sql
create table if not exists public.case_stakeholders (
  id uuid primary key default gen_random_uuid(),
  assignment_id text not null references public.case_assignments(id) on delete cascade,
  user_id text not null,
  role text not null check (role in ('hr_lead','employee','hiring_manager','finance_approver','hr_delegate')),
  invited_by text,
  invited_at timestamptz default now(),
  last_viewed_at timestamptz,
  created_at timestamptz default now(),
  unique(assignment_id, user_id, role)
);
```
Add RLS: hr_lead can manage stakeholders for their cases; each stakeholder can read their own row.

TASK 2 — Invite flow
In the HR case detail view, add a "Team" tab:
- Shows current stakeholders with their roles
- "Add stakeholder" button: email input + role dropdown + optional note
- Sends an invite email via the existing send-notification-email edge function
- Invited user gets a link to a read-only case view scoped to their permissions

TASK 3 — Permission enforcement
- hiring_manager: can GET case status and plan, cannot POST/PATCH anything
- finance_approver: can GET exception requests for their cases, can PATCH exception_requests status
- hr_delegate: same permissions as hr_lead

TASK 4 — Finance approver notification
When an exception_request is created (from P0-5), if a finance_approver stakeholder exists on the case, send them a notification (via case_events or the notification system) rather than routing to hr_lead only.

ACCEPTANCE CRITERIA:
- HR can add a hiring_manager who can view (not edit) the case
- Finance approver receives exception request notifications if assigned
- HR delegate can perform all HR actions on assigned cases
- All stakeholder additions are logged in audit_log
- Stakeholder table renders in case detail with role badges
```

---

## P1.5-3 · Copy + Jargon Cleanup Pass
**Effort:** 1–2 weeks · **Priority:** High (trust improvement, affects all users)

```
You are doing a complete jargon and copy cleanup pass across all employee-facing and HR-facing UI components. Internal engineering terms must not appear in production copy.

READ THESE FILES FIRST:
- /frontend/src/pages/EmployeeJourney.tsx
- /frontend/src/pages/HrCommandCenter.tsx
- /frontend/src/pages/HrPolicy.tsx
- /frontend/src/pages/HrPolicyManagement.tsx
- /frontend/src/components/AppShell.tsx

PATTERNS TO FIND AND REPLACE throughout /frontend/src/ (run grep for each):

1. "Layer-2" or "layer_2" → replace with "Override" or remove
2. "baseline" (when used as internal label visible to user) → replace with "Policy default"
3. "Section A" / "Section B" → replace with "Basic info" / "Family info" (or remove)
4. snake_case task IDs rendered as task titles (e.g. "passport_upload") → convert to Title Case ("Upload passport")
5. Raw UUID strings in user-facing text → hide or replace with human-readable identifiers
6. "evidence_rule" / "policy_rule" / "clause_type" as visible labels → replace with plain English
7. Status values like "awaiting_intake" → "Awaiting information", "in_progress" → "In progress"
8. "HR" used as a person's name ("HR will contact you") → use "Your mobility team" or "Your HR contact"

SPECIFIC COMPONENTS:
- In HrPolicyManagement.tsx: find any "auto_generated", "review_status", "confidence" labels shown to HR users → replace with "AI-drafted", "Pending your review", "Confidence score"
- In policy benefit rule display: "benefit_key" raw values → format as benefit names (e.g. "school_fees" → "School fees")
- In compliance check display: "FAIL" status → "Needs attention", "PASS" → "Complete", "WARN" → "Review needed"
- Any "null" or "undefined" rendered as text in the UI → replace with "-" or appropriate empty state

MICROCOPY PRINCIPLES (apply these throughout):
- Never use "approved" before HR has actually approved. Use "within policy" or "covered"
- Personal costs are named directly: "Your out-of-pocket cost" not "delta" or "overrun"
- Dates: always show "Month Day, Year" format, never ISO strings to end users
- Loading states: "Loading your plan..." not "Loading..."
- Error states: "We couldn't load your information. Please refresh or contact support." not "Error 500"

ACCEPTANCE CRITERIA:
- Zero occurrences of snake_case identifiers in employee-facing text (grep test)
- Zero occurrences of "Layer-2", "baseline", "Section A/B" in any user-visible component
- Zero raw UUID strings in employee-facing pages
- All status values display human-readable labels
- Run: grep -r "layer_2\|Layer-2\|Section A\|Section B\|auto_generated\|evidence_rule" /frontend/src/pages/ --include="*.tsx" → zero results
```

---

## P1.5-4 · SSO (SAML / OIDC) for Mid-Market Procurement
**Effort:** 3–4 weeks · **Priority:** High (mid-market procurement requirement)

```
You are adding SSO support so that mid-market HR teams can authenticate with their company identity provider (Okta, Azure AD, Google Workspace) instead of using email/password.

READ THESE FILES FIRST:
- /supabase/migrations/20260221105601_remote_schema.sql  (auth setup)
- /frontend/src/pages/Auth.tsx  (current auth flow)
- /backend/app/auth_deps.py  (authentication dependency)
- /frontend/src/utils/demo.ts  (getAuthItem — understand current auth storage)

CONTEXT: Supabase supports SAML 2.0 SSO natively in the Enterprise plan. The implementation here adds the configuration layer and frontend flow.

TASK 1 — Company SSO configuration table
```sql
create table if not exists public.company_sso_config (
  id uuid primary key default gen_random_uuid(),
  company_id text not null references public.companies(id),
  provider text not null check (provider in ('saml','oidc')),
  metadata_url text,      -- for SAML: IdP metadata URL
  client_id text,         -- for OIDC
  issuer_url text,        -- for OIDC
  domain_hint text,       -- e.g. 'acme.com' — used to auto-route login
  enabled boolean default false,
  created_at timestamptz default now()
);
```

TASK 2 — SSO login detection
On the login page (/frontend/src/pages/Auth.tsx):
- Add "Sign in with SSO" button below the email/password form
- When clicked: show an email domain input ("Enter your work email to continue")
- Query GET /api/sso/config?domain=acme.com to check if SSO is configured for that domain
- If yes: redirect to the Supabase SSO flow (`supabase.auth.signInWithSSO({ domain })`)
- If no: show "SSO is not configured for your organization. Contact your IT team."

TASK 3 — Auto-detect SSO from email
When a user enters their email in the standard login form:
- After email blur/tab, check the domain against company_sso_config
- If domain match found and enabled: show a banner "Your organization uses SSO. [Continue with SSO →]"

TASK 4 — Admin configuration UI
In the admin panel (/frontend/src/pages/admin/AdminCompanyDetail.tsx), add an "SSO Configuration" section where admins can enable SSO for a company and input the metadata URL or OIDC credentials.

TASK 5 — Backend SSO config endpoint
GET /api/sso/config?domain=X — returns { enabled: bool, provider: string } (no secrets)
POST /api/sso/config — admin-only endpoint to configure SSO for a company

ACCEPTANCE CRITERIA:
- User can sign in via SSO if their company has it configured
- SSO is auto-detected from email domain on login form
- Admin can enable/disable SSO per company
- Standard email/password login still works for companies without SSO
- SSO login writes to audit_log with actor_type='human'
```

---

## P1.5-5 · Family / Dual-Career Signal Full Propagation
**Effort:** 2–4 weeks · **Priority:** High (run after Spike-4 identifies specific gaps)

```
PREREQUISITE: Run SPIKE-4 first. This prompt fixes whichever traces came back as STORED-BUT-NOT-READ.

You are wiring the spouse.wantsToWork flag (and broader family composition data) to all downstream consumers so that a relocating employee's family situation is reflected in their plan, recommendations, and resources.

READ THESE FILES FIRST:
- /backend/policy_engine.py  (spouse.wantsToWork handling at line 97)
- /backend/relocation_plan_draft_normalize.py  (familyMembers normalization)
- /backend/app/recommendations/plugins/  (all plugins)
- /backend/services/country_resources.py
- SPIKE-4 output (specific traces that returned STORED-BUT-NOT-READ)

TASK 1 — Destination resources for dual-career
In /backend/services/country_resources.py (or wherever destination resources are assembled for the employee):
When spouse.wantsToWork = true, include in the resources pack:
- A "Spouse employment" resource category with: work permit requirements for accompanying spouse, job boards in the destination country, language requirements for the job market
- A "Language support" resource with links to local language courses
Flag these resources with `target_audience: 'spouse'` so they display in a dedicated section.

TASK 2 — Services questionnaire awareness
In the services questions flow (check /frontend/src/pages/ for the services intake), when family data includes a spouse with wantsToWork=true:
- Add a services question: "Will your partner need employment support? (job search, work permit, language training)"
- If yes: include 'language_training' and 'spouse_career_support' as selectable service categories in ServicesRecommendations

TASK 3 — Plan task for dual-career
In /backend/relocation_plan_view_service.py, when spouse.wantsToWork=true, add a task to the Immigration phase:
```
task_code: 'spouse_work_permit'
title: 'Partner work permit application'
owner: HR
why_this_matters: '30-40% of assignment failures are linked to the partner not being able to work at destination. Starting this early is critical.'
```

TASK 4 — Dependent age-aware school recommendations
In /backend/app/recommendations/plugins/schools.py, filter school recommendations based on dependent ages (from familyMembers.dependents[].dob). Only surface schools appropriate for the children's age groups:
- Under 3: childcare/daycare facilities only
- 3-5: nursery/kindergarten
- 5-18: primary/secondary based on age

ACCEPTANCE CRITERIA:
- Employee with wantsToWork=true spouse sees spouse employment resources in destination guide
- Services questionnaire asks about partner employment support when relevant
- Plan includes spouse work permit task when wantsToWork=true
- School recommendations filter by child ages
- All existing non-family-case behavior unchanged
```

---

## P1.5-6 · Bulk Case Creation (Admin Import)
**Effort:** 2 weeks · **Priority:** Medium (scaling to 30+ cases/year customers)

```
You are adding the ability for HR to create multiple relocation cases at once via CSV import, enabling mid-market customers running 30+ cases/year to onboard efficiently.

READ THESE FILES FIRST:
- /frontend/src/pages/HrEmployees.tsx
- /backend/app/routers/  (find the case creation endpoint)
- /frontend/src/types.ts  (Assignment creation payload types)

TASK 1 — CSV template
Create a downloadable CSV template with columns:
employee_email, employee_first_name, employee_last_name, origin_country, destination_country, expected_start_date (YYYY-MM-DD), assignment_type (international_lta/international_sta/permanent_transfer/domestic), policy_tier (Entry/Manager/Director/VP/C-suite)

TASK 2 — Import endpoint
POST /api/assignments/bulk-import accepts multipart/form-data with a CSV file.
Backend processing:
1. Parse CSV, validate each row (required fields, enum values, date format)
2. For valid rows: create case_assignment record + invite email to employee
3. For invalid rows: collect errors with row number and field
4. Return: { created: N, failed: M, errors: [{row, field, message}] }
Processing must be synchronous for ≤50 rows, async (background job) for >50 rows.

TASK 3 — Import UI
In /frontend/src/pages/HrEmployees.tsx (or a new HrBulkImport.tsx):
- "Import cases" button → opens a modal
- Step 1: Download template / Upload CSV
- Step 2: Preview first 5 rows with validation state
- Step 3: Confirm import → show progress
- Step 4: Results summary with downloadable error report

TASK 4 — Duplicate detection
Before creating: check if a case_assignment already exists for the same employee_user_id with status not in ('closed','rejected'). If yes: include in the error report as "Active case already exists for this employee."

ACCEPTANCE CRITERIA:
- CSV template downloads with correct headers and example row
- Import of 50 valid rows creates 50 cases and sends 50 invite emails
- Invalid rows produce clear per-row error messages
- Duplicate detection prevents creating a second active case for the same employee
- Bulk import writes one audit_log entry per case created (not one per import batch)
```

---

## P1.5-7 · Additional Destination Corridors at Singapore Depth
**Effort:** 6–9 weeks content + 6–8 weeks tooling (run in parallel) · **Priority:** High

```
PREREQUISITE: Run SPIKE-5 first to identify which corridors are closest to Singapore depth.

You are building the destination data admin tooling that allows the ReloPass team to efficiently curate and publish destination data for new corridors without code changes.

READ THESE FILES FIRST:
- /backend/app/recommendations/datasets/  (all JSON files — understand the data structure)
- /backend/app/recommendations/plugins/schools.py
- /backend/app/recommendations/plugins/living_areas.py
- /backend/app/recommendations/plugins/movers.py
- /frontend/src/pages/admin/AdminSuppliers.tsx  (existing supplier admin — extend this pattern)

TASK 1 — Destination admin UI
Create /frontend/src/pages/admin/CountryDetailPage.tsx (may already partially exist — check):
A form for managing destination data per country:
- Tab: Movers (CRUD for mover vendor entries: name, score, lead_time_days, domestic_capable, contact_url)
- Tab: Schools (CRUD: name, type, fees_annual, currency, application_deadline_month, quality_score, age_range_min/max)
- Tab: Neighborhoods (CRUD: name, monthly_rent_eur, safety_score, green_score, commute_from_city_centre_min, lifestyle_tags[])
- Tab: Resources (CRUD: category, title, url, description, last_verified_at)
- Tab: Watchouts (corridor-specific compliance/visa notes: title, body, severity)

TASK 2 — Data versioning
Add a destination_data_version column to a country_destinations table (or equivalent). When data is edited via the admin UI, increment the version and record who edited it and when. This creates an audit trail for content changes.

TASK 3 — Completeness score
For each destination, compute a completeness score (0-100%) based on:
- Movers: 5+ entries = 20 points
- Schools: 5+ entries = 20 points
- Neighborhoods: 5+ entries = 20 points
- Resources: 10+ categorized entries = 20 points
- Watchouts: 1+ entries = 20 points
Display this score in the admin corridor list so the content team can prioritize.

TASK 4 — Launch-ready gate
A destination is only surfaced to employees if completeness_score >= 80. Add this filter to the recommendations engine. Below 80: the destination is available to employees but shows a banner "Destination data for [city] is being finalized. Some recommendations may be limited."

ACCEPTANCE CRITERIA:
- Admin can add/edit/delete any destination data item through the UI without code changes
- Completeness score is computed and displayed per destination
- Destinations below 80% show a "limited data" banner to employees
- All content changes are versioned and attributed to the editor
- Singapore remains at 100% completeness and all its data is correct (regression test)
```

---

# ═══════════════════════════════════════════
# QUICK REFERENCE — EXECUTION ORDER
# ═══════════════════════════════════════════

```
WEEK 1-3 (all in parallel):
  SPIKE-1  Tenant isolation + audit log
  SPIKE-2  Task due_date wiring  
  SPIKE-3  contract_type abstraction
  SPIKE-4  Family signal propagation
  SPIKE-5  Destination data depth

P0 FIXES (start immediately after spike-1 gives all-clear on tenant isolation):
  P0-1    Strip dev tooling  [2-4 hrs]
  P0-2    Hide RFQ screen    [2-4 hrs]
  P0-3    Employee dashboard redesign  [1-2 wks]
  P0-4    ECB FX rates       [1-2 wks]  — do in parallel with P0-3
  P0-5    ExceptionRequest   [3-4 wks]  — P0-6 depends on this
  P0-6    Estimate Review    [3-5 wks]  — depends on P0-4 + P0-5
  P0-7    Task due_dates     [2-3 wks]  — only if Spike-2 found gaps
  P0-8    Audit log gaps     [4-6 wks]  — only after Spike-1 report
  P0-9    Command Center simplification  [1-2 wks]
  P0-10   Case paused status [1 wk]

PHASE 1.5 (after first pilot is running):
  P1.5-1  Domestic move support      [3-8 wks, depends on Spike-3]
  P1.5-2  CaseStakeholder RACI       [6-8 wks]
  P1.5-3  Copy/jargon cleanup        [1-2 wks]
  P1.5-4  SSO SAML/OIDC              [3-4 wks]
  P1.5-5  Family signal propagation  [2-4 wks, depends on Spike-4]
  P1.5-6  Bulk case import           [2 wks]
  P1.5-7  Additional corridors       [6-9 wks content, 6-8 wks tooling]
```

---

*Total estimated engineering: ~37 weeks parallelized to ~21-29 wall-clock weeks with 2-3 engineers.*  
*Critical path: SPIKE-1 → P0-1 through P0-6 must complete before first customer pilot.*
*R5 (tenant isolation) is the only existential risk — do not skip SPIKE-1.*
