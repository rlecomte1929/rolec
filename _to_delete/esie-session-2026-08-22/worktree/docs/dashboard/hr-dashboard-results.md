# HR Dashboard / Command Center — Results

**Date:** 2025-03-19  
**Summary:** Staged loading, company-scoped data, optimized queries, simplified KPIs.

---

## Before/After Dashboard Structure

| Aspect | Before | After |
|--------|--------|-------|
| Shell | "Loading..." until both KPIs and cases done | Shell with KPI placeholders + cases header visible immediately |
| KPI load | Blocked with cases in Promise.all | Independent; KPIs stream in when ready |
| Cases load | Blocked with KPIs in Promise.all | Independent; cases stream in when ready |
| KPI count | 9 cards (incl. placeholder) | 8 cards (placeholder removed) |
| Data scope | hr_user_id only | company_id first, hr_user_id fallback |
| KPI computation | N+1 (compliance, profile, overdue per assignment) | Single assignment query + single overdue aggregate |
| Cases task stats | N+1 (one query per row) | One batch query per page |

---

## Widgets Kept, Deferred, Simplified, Removed

| Widget | Change |
|--------|--------|
| Active Cases | Kept |
| Action Required | Simplified (status=submitted only; no compliance check) |
| Departing Soon | Simplified (expected_start_date; no employee profile) |
| Completed (YTD) | Kept |
| At Risk | Kept |
| Attention Needed | Kept |
| Overdue Tasks | Kept; optimized (single query) |
| **Avg. Visa Duration** | **Removed** (placeholder) |
| Budget Overruns | Kept |
| Cases table | Kept; task stats batch-optimized |

---

## Before/After Request Counts

| Metric | Before | After |
|--------|--------|-------|
| KPIs + cases on entry | 2 (Promise.all) | 2 (independent, parallel) |
| KPI backend queries | 1 + N (compliance) + N (profile) + N (overdue) | 2 (assignments + overdue aggregate) |
| Cases backend queries | 1 + N (tasks per row) | 2 (cases + batch task stats) |

---

## Endpoints Removed from Critical Path

- None removed; company-profile is loaded by HrCompanyContext for header branding and does not block dashboard content.
- `/api/hr/employees` is not used by Command Center.

---

## How Data Coherence Is Guaranteed

- `_command_center_scope(user)` returns `(company_id, hr_user_id)` with company preferred.
- All KPIs and cases use the same scoping (company or hr_user).
- Same join/where logic as `list_assignments_for_company`.

---

## Manual Verification Checklist

- [ ] Command Center loads; shell (KPI placeholders, cases header) appears immediately
- [ ] KPI values populate as response arrives (may see "…" briefly)
- [ ] Cases table shows skeleton then data, or empty state
- [ ] Data is company-scoped (HR sees only their company's cases)
- [ ] Admin sees all cases
- [ ] Risk filter works
- [ ] Pagination works
- [ ] Clicking a case row navigates to detail
- [ ] No blocking on company-profile or employees endpoints
