# Case-ID Resolution Audit — every raw route-id surface

**AIQ-1710 · Subtask 5 of [AIQ-1704].** Closes Expected-Output (3) / criterion 3 of the parent.

Status: **the class is closed structurally.** Every case-scoped surface that consumes a
route/URL id either resolves it through a canonical resolver or is confirmed safe with a stated
reason. A regression guard fails CI if a new one appears.

Snapshot: 2026-08-04, against `origin/main` (`a5a5f451`). Every row below was generated from the
tree, not transcribed — see [How this was produced](#how-this-was-produced).

---

## 1. The defect class

A case-scoped endpoint keyed its SQL on the **raw path id**. A URL may carry any of three id
forms — the assignment PK (`case_assignments.id`), the `case_id`, or the `canonical_case_id` —
so when the caller passed an assignment id to a query keyed on `case_id`, it matched no rows and
returned **silent-empty** rather than an error. Silent-empty is the dangerous part: the page
renders, just with nothing in it.

Five shipped defects came from this one confusion before it was closed structurally:

| # | Ticket | Surface |
|---|---|---|
| 1 | F16 | the original case/assignment id confusion |
| 2 | AIQ-1648 | case-scoped read returning empty for an assignment id |
| 3 | — | `GET /cases/{id}/vendors` |
| 4 | AIQ-1692 / AIQ-1699 | roadmap paywall entitlement lookup |
| 5 | AIQ-1703 | RFQ read |

---

## 2. The canonical boundary

### Backend — `resolve_case_ids`

`backend/db/cases.py:274` — `CasesMixin.resolve_case_ids(any_id, request_id=None) -> CaseIds | None`

> Accepts **any** of the three id forms and returns a `CaseIds` context, or `None` when the id
> resolves to no assignment.

**Fail-closed contract.** Callers key their case-scoped query on the returned
`canonical_case_id` and return 4xx on `None` — *never silently empty and never fail open*. The
endpoint stops caring which id form it was handed. It is a thin wrapper over
`get_assignment_by_case_id`, which already matches all three forms; `resolve_case_ids` adds the
fail-closed contract and the resolved-id context handlers need.

Two narrower resolvers satisfy the same contract and are equally accepted:

| Resolver | Used by |
|---|---|
| `_canonical_case_id_or_404` | messages, vendors, budget lines, dossier list |
| `resolve_case_forms_case_id` | the forms/dossier read family (AIQ-1719) |

A fourth pattern is also recognised: authorize with `require_case_access`, then key on the
`canonical_case_id` that the returned assignment already carries — reusing the fetch instead of
re-querying. This is the `services_state` shape.

### Frontend — `caseIdForAssignment`

`frontend/src/utils/employeeAssignmentScope.ts:37`

```ts
export function caseIdForAssignment(
  linkedSummaries: EmployeeLinkedOverviewRow[],
  id: string | null,
): string | null
```

**Fail-closed contract (AIQ-1320).** Returns `null` on a miss — never the raw id, which would be
an assignment id that a case-keyed endpoint reads as the wrong case. Callers that still want the
raw id as a last resort must opt in **explicitly** (`?? pathCaseId`, `?? id`), so the fallback is
visible at the call site rather than hidden in the resolver.

Sibling resolvers in the same module: `assignmentIdForScopeId` (`:85`, same fail-closed rule) and
`persistableCaseId` (`:65`), which returns `null` until linked summaries have loaded so a
debounced save cannot fire with an unresolved id (AIQ-1691).

---

## 3. Backend inventory

Every function in the case-scoped routers that takes a `case_id` param **and** contains an inline
`case_id = :` SQL predicate. 20 functions: **18 FIXED, 2 CONFIRMED-SAFE.**

### `backend/app/routers/cases_read.py` — 15

| Line | Function | Status |
|---|---|---|
| 494 | `_load_form_with_template` | FIXED — `resolve_case_forms_case_id` |
| 1206 | `_load_case_form_summaries` | FIXED — `resolve_case_forms_case_id` |
| 1330 | `list_form_documents` | FIXED — `resolve_case_forms_case_id` |
| 1467 | `list_form_comments` | FIXED — `resolve_case_forms_case_id` |
| 1521 | `list_form_events` | FIXED — `resolve_case_forms_case_id` |
| 1582 | `get_form_original` | FIXED — `resolve_case_forms_case_id` |
| 1785 | `get_dossier_zip` | FIXED — `resolve_case_forms_case_id` |
| 1860 | `list_dossiers` | FIXED — `_canonical_case_id_or_404` |
| 1913 | `get_dossier` | FIXED — `resolve_case_forms_case_id` |
| 1962 | `get_dossier_pdf` | FIXED — `resolve_case_forms_case_id` |
| 2111 | `_case_service_estimates` | **CONFIRMED-SAFE** — internal helper; `get_budget_summary` resolves `case_id` before calling it |
| 2142 | `_selected_services_for_case` | **CONFIRMED-SAFE** — internal helper; `get_budget_summary` resolves `case_id` before calling it |
| 2424 | `list_case_messages` | FIXED — `_canonical_case_id_or_404` |
| 2481 | `list_case_vendors` | FIXED — `_canonical_case_id_or_404` (defect #3 above) |
| 2553 | `list_case_budget_lines` | FIXED — `_canonical_case_id_or_404` |

### `backend/app/routers/hr_coordination.py` — 3

| Line | Function | Status |
|---|---|---|
| 70 | `get_case_providers` | FIXED — `resolve_case_ids` |
| 167 | `get_case_rfqs` | FIXED — `resolve_case_ids` (defect #5, AIQ-1703) |
| 282 | `dispatch_case_rfq` | FIXED — `resolve_case_ids` |

### `backend/app/routers/services_state.py` — 2

| Line | Function | Status |
|---|---|---|
| 124 | `get_services_state` | FIXED — `require_case_access` → `canonical_case_id` |
| 180 | `put_services_state` | FIXED — `require_case_access` → `canonical_case_id` |

### `backend/app/routers/payment.py` — 0

**CONFIRMED-SAFE — no inline `case_id` SQL predicate exists.** The roadmap paywall path
(defect #4, AIQ-1692/1699) authorizes with `require_case_access(case_id, user)`
(`payment.py:204`) and then reads entitlement through `lookup_entitlement(case_id)` (`:209`)
rather than hand-writing a case-keyed query. The router is still scanned by the guard so that
adding one later is caught.

---

## 4. Frontend inventory

Every page consuming a route/URL id for case-scoped state. All route through
`caseIdForAssignment`; none reads the raw path id as a case id.

| Surface | Line | Status |
|---|---|---|
| `frontend/src/features/platform-v2/intake/EmployeeIntakePage.tsx` | 974 | FIXED — `?? resolvedIds.caseId` (explicit fallback) |
| `frontend/src/pages/ProvidersPage.tsx` | 373 | FIXED — `?? pathCaseId ?? ''` |
| `frontend/src/pages/services/ServicesEstimate.tsx` | 49, 53 | FIXED |
| `frontend/src/pages/services/ServicesQuestions.tsx` | 67, 96 | FIXED |
| `frontend/src/pages/services/ServicesRecommendations.tsx` | 51, 56 | FIXED |
| `frontend/src/pages/services/ServicesRfqNew.tsx` | 57 | FIXED |

6 pages, 9 call sites. Where a raw-id fallback remains it is written at the call site
(`?? pathCaseId`), which is correct for a URL that genuinely carries a `case_id` — the point of
the AIQ-1320 change was to make that choice explicit rather than implicit in the resolver.

---

## 5. The regression guard

**`backend/tests/test_case_id_resolution_guard.py`** (AIQ-1709, PR #1677) walks the AST of the
four routers above, flags any function taking `case_id` whose body contains a `case_id = :`
predicate without a recognised resolver, and fails unless it is on an explicit `_ALLOWLIST` with
a justification. A new endpoint keyed on the raw id fails CI.

Two properties keep it honest:

- **`test_allowlist_stays_honest`** — an allowlisted function that later starts resolving must be
  *removed* from the allowlist, so the list keeps meaning something.
- **`CaseSqlPatternTests`** pins the predicate styles the regex must see. This matters: the
  original pattern matched only bare `case_id = :cid` and was blind to
  `CAST(case_id AS TEXT) = :cid` — the form this codebase *prefers*, because `::text` is
  Postgres-only and breaks the sqlite tests. Two unresolved handlers (`get_case_rfqs`,
  `dispatch_case_rfq`) sat inside an already-scanned router while the guard stayed green
  (AIQ-1735). Weakening that test reopens the hole.

The allowlist currently holds exactly the two helpers in §3. The eight forms/dossier reads that
were once on it were resolved by AIQ-1719 and removed.

**`frontend/src/utils/__tests__/employeeAssignmentScope.guard.test.ts`** asserts the FE contract
directly: `caseIdForAssignment` and `assignmentIdForScopeId` each return `null` on a miss, never
the raw id.

---

## How this was produced

The backend table was generated by re-running the guard's own AST logic
(`test_case_id_resolution_guard.py` — same `_ROUTERS`, `_RESOLVERS`, `_CASE_SQL` regex and
`_resolves` predicate) over the tree at `a5a5f451`, so the inventory cannot drift from what the
guard enforces. The frontend table came from `grep -rn 'caseIdForAssignment('` across
`frontend/src`, excluding tests and the defining module.

To re-verify after changes, run the guard **from the repo root** — `_ROUTERS` holds
repo-root-relative paths, so `cd backend && pytest …` silently fails to find them:

```bash
pytest backend/tests/test_case_id_resolution_guard.py -v          # from the repo root
cd frontend && npx vitest run src/utils/__tests__/employeeAssignmentScope.guard.test.ts
```

If either fails, this document is out of date — fix the code, then regenerate the tables.
