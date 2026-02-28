# HR Command Center — Implementation Summary

## Overview

The HR Command Center provides HR users with a portfolio and risk dashboard across all relocation cases. It is visible only to HR and ADMIN roles.

---

## 1. Database Changes

### Migration: `20260227000000_hr_command_center.sql`

**A) case_assignments table (updated)**
- `risk_status` text, check (green/yellow/red), default 'green'
- `budget_limit` numeric
- `budget_estimated` numeric
- `expected_start_date` date
- Indexes: `risk_status`, `expected_start_date`

**B) case_events table (new)**
- Light audit log for task completed, document uploaded, status change, etc.
- RLS: HR reads all events for their cases; employees read events for their own assignment

**C) relocation_tasks table (new)**
- Tasks with phase, owner_role, status (todo/in_progress/done/overdue), due_date
- RLS for HR and employee visibility

---

## 2. Risk Scoring RPC

### Migration: `20260227000001_hr_command_center_risk_rpc.sql`

**recalculate_case_risk(assignment_id)**
- If any task status = 'overdue' → risk = 'yellow'
- If overdue > 7 days → risk = 'red'
- If budget_estimated > budget_limit → risk = 'red'
- Else → 'green'

**Triggers**
- `relocation_tasks`: INSERT/UPDATE/DELETE → recalculate risk
- `case_assignments`: UPDATE budget_limit, budget_estimated → recalculate risk

**Notifications**
- When risk changes to yellow or red, inserts into `notifications` for HR (uses existing bell)

---

## 3. Backend API

- `GET /api/hr/command-center/kpis` — aggregate KPIs
- `GET /api/hr/command-center/cases` — paginated cases (page, limit, risk_filter)
- `GET /api/hr/command-center/cases/{id}` — case detail with phases, tasks, events

All require HR role. Admin sees all cases; HR users see only their assignments.

---

## 4. Frontend Routes

- `/hr/command-center` — Command Center dashboard (KPI row + cases table)
- `/hr/command-center/cases/:id` — Case detail (timeline, tasks, budget, activity log)

Nav link "Command Center" added to HR nav ribbon. Role check: non-HR/ADMIN redirects to landing.

---

## 5. Components

**KPICard** — Reusable card for Active Cases, At Risk, Attention Needed, Overdue Tasks, Budget Overruns, Avg Visa Duration (placeholder)

**RiskBadge** — Green / yellow / red dot with optional label

---

## 6. Implementation Choices

| Choice | Reason |
|--------|--------|
| Risk/budget on case_assignments | Assignment-centric HR flow; avoids complex joins with relocation_cases |
| relocation_tasks vs tasks | Avoid conflict with existing `tasks` table if any |
| SQLite schema in database.py | Local dev uses SQLite; migrations target Postgres (Supabase) |
| KPIs from assignment list | Simple aggregation; no separate RPC for MVP |
| Pagination at 25 | Spec: paginate if > 25 |
| Notification on risk change | Uses existing `notifications` table and bell UI |

---

## 7. Next Steps (Optional)

1. Add tasks via UI (currently backend-ready, no create/edit UI)
2. Log case_events from task completion, document upload, etc.
3. Seed demo tasks for demo-ready state
4. Add visa duration tracking for "Avg. Visa Duration" KPI
