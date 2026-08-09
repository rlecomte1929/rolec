# Case-ID Resolution Audit — every raw route-id surface

**AIQ-1710 · Subtask 5 of [AIQ-1704].** Closes Expected-Output (3) / criterion 3 of the parent.

Status: **partially closed — see the coverage note below.** Every case-scoped surface *in the
guard's scope* either resolves the id through a canonical resolver, is confirmed safe with a
stated reason, or is recorded as a known gap. A regression guard fails CI if a new one appears.

Snapshot: 2026-08-04, against `origin/main` (`a5a5f451`). Every row below was generated from the
tree, not transcribed — see [How this was produced](#how-this-was-produced).

> ### ⚠️ Coverage correction — AIQ-1775, 2026-08-04
>
> An earlier revision of this document said the class was **"closed structurally"**, without
> qualification. That was **overstated**, and measurably so.
>
> At the time, the regression guard scanned a hardcoded list of **four** routers. Applying its
> own criterion to the rest of `backend/app/routers/` found **60 further matching functions** —
> 20 in the unwired `cases.py`, **40 in live routers**. The defect class that produced ≥5 shipped
> bugs was guarded in 4 files and unguarded in roughly 20.
>
> AIQ-1775 widened the guard's scope from a hardcoded list to **every router, derived**, so it
> can no longer fall behind the codebase. The 40 newly-visible functions were classified:
>
> | verdict | count | meaning |
> |---|---|---|
> | safe, with a reason | 13 | employee-scoped SQL, an alternative access helper, or a resolving caller |
> | **known gap** | **29** | genuinely keyed on the raw id — recorded in `_KNOWN_UNRESOLVED`, **not** excused |
>
> The dominant root cause is shared: **`_assert_case_access(user, case_id)`
> (`case_service.py:147`) accepts *either* a `public.cases` UUID *or* an `assignment_id` — its
> own docstring says so — and returns `None` rather than the resolved id.** Twelve callers
> therefore validate access for either form and then run `WHERE case_id = :raw_value`. Pass an
> assignment id and the access check succeeds while the SQL matches nothing: silent-empty, which
> is the F16 failure this audit is about. `require_case_access` (`auth_deps.py:245`) has the same
> shape but *does* return the assignment row, so its five callers could derive the canonical id
> and simply do not.
>
> That this already ships is not hypothetical. `employee_quotes.list_hr_quote_requests` records
> in its own docstring that it is *"keyed on the canonical case_id, while the HR case-detail
> route param is an assignment id — 0 of its 51 rows match one, so its only frontend caller
> displayed an empty panel for every case and was removed."*
>
> **Fixing the 29 is deliberately out of scope for AIQ-1775** (measurement first — its Validation
> Criterion 5). ~29 endpoints across 9 routers is too large a blast radius for one change. They
> are tracked in `_KNOWN_UNRESOLVED`, and a test asserts that register can only ever shrink.
>
> Until it is empty, **this class is not closed** — it is measured, bounded and guarded against
> getting worse.

> ### Progress — AIQ-1776, 2026-08-09
>
> The block above is left as written: it is the accurate record of what AIQ-1775 measured on
> 2026-08-04. What follows is what has changed since.
>
> **`_assert_case_access` now returns the resolved canonical case id**, and the twelve callers
> that keyed on the raw path param key on the return value instead. `_KNOWN_UNRESOLVED` is
> **29 → 17**. The entries were *removed*, not moved to `_ALLOWLIST` — the debt is paid, not
> re-justified.
>
> Two details worth carrying forward:
>
> - The helper resolves with the **same `COALESCE(NULLIF(TRIM(canonical_case_id), ''), case_id)`
>   precedence as `resolve_case_forms_case_id`**, so the two resolvers agree by construction
>   rather than by review. A test asserts they never disagree across all four id forms.
> - `case_form_pdf.py` was carrying its **own drifted copy** of the helper — it queried
>   `public.cases` only, so an assignment id 404'd instead of resolving, and it raised 500 on a
>   DB error, violating the B24-REGRESSION fail-safe. One of the twelve was therefore
>   misattributed. The duplicate is deleted; the module imports the canonical helper.
>
> The remaining **17** are a different shape, and are deferred for the same blast-radius reason
> AIQ-1775 gave: they are mostly `require_case_access` callers that already hold the assignment
> row and simply do not read `canonical_case_id` off it.
>
> **This class is still not closed.** 17 endpoints can still return silent-empty for an
> assignment id.

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

A fifth, since AIQ-1776: **capture what `_assert_case_access` returns.** It accepts all three id
forms and now returns the resolved canonical id, satisfying the same fail-closed contract (it
raises 403/404 rather than returning an unresolved value). The guard requires the return value to
be *assigned* — a bare `_assert_case_access(user, case_id)` on its own line still counts as
unresolved, because calling it and then keying on the argument is precisely the bug.

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

The allowlist held exactly the two helpers in §3 while the guard's scope was four routers. The
eight forms/dossier reads that were once on it were resolved by AIQ-1719 and removed.

**Since AIQ-1775** the guard scans every router (derived, not hardcoded) and keeps two separate
registers, so a known gap can never masquerade as coverage:

- **`_ALLOWLIST`** — 13 entries, each genuinely safe, each with the reason.
- **`_KNOWN_UNRESOLVED`** — **17** entries (29 before AIQ-1776), each genuinely unsafe, each
  carrying a follow-up ref. `test_known_unresolved_register_only_shrinks` fails if an entry is
  fixed but left behind, and `test_the_two_registers_are_disjoint` stops a function being called
  both safe and unsafe.

`test_scope_is_derived_not_hardcoded` fails if anyone reverts the router list to a literal —
which is what allowed the under-coverage in the first place.

**`frontend/src/utils/__tests__/employeeAssignmentScope.guard.test.ts`** asserts the FE contract
directly: `caseIdForAssignment` and `assignmentIdForScopeId` each return `null` on a miss, never
the raw id.

---

## How this was produced

The backend table was generated by re-running the guard's own AST logic
(`test_case_id_resolution_guard.py` — same `_RESOLVERS`, `_CASE_SQL` regex and `_resolves`
predicate) over the tree at `a5a5f451`, so the inventory cannot drift from what the guard
enforces. The frontend table came from `grep -rn 'caseIdForAssignment('` across `frontend/src`,
excluding tests and the defining module.

**A caution this document learned the hard way.** Generating the table from the guard's own logic
guarantees the inventory matches *what the guard checks* — it says nothing about whether the
guard checks the right **scope**. Both times this guard was found under-covering, the audit table
was accurate and the conclusion drawn from it was not:

- **AIQ-1735** — the `_CASE_SQL` regex was blind to `CAST(case_id AS TEXT) = :cid`, the style the
  codebase actively prefers (`::text` is Postgres-only and breaks the sqlite tests). Two
  unresolved handlers sat inside an *already-scanned* router while the guard stayed green.
- **AIQ-1775** — `_ROUTERS` was a hardcoded four. Twenty routers were never looked at.

So when re-verifying, check the *scope* as well as the rows: does the guard scan every router,
and does its regex match every predicate style actually written in the tree?

To re-verify after changes, run the guard **from the repo root** — `_ROUTERS` holds
repo-root-relative paths, so `cd backend && pytest …` silently fails to find them:

```bash
pytest backend/tests/test_case_id_resolution_guard.py -v          # from the repo root
cd frontend && npx vitest run src/utils/__tests__/employeeAssignmentScope.guard.test.ts
```

If either fails, this document is out of date — fix the code, then regenerate the tables.
