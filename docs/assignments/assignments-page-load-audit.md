# Assignments Page Load Audit

**Date:** 2025-03-19  
**Purpose:** Document the Assignments page (HrDashboard) load flow, identify causes of canceled/duplicate requests, and recommend fixes.

---

## Request Sequence on Page Load

### Initial Mount (HrDashboard at `/hr/dashboard`)

| Order | Request | Trigger | Component/Hook |
|-------|---------|---------|----------------|
| 1 | `GET /api/hr/assignments` | `loadAssignments(ac.signal)` | `useEffect` (deps: `[]`) |
| 2 | `GET /api/hr/company-profile` | `hrAPI.getCompanyProfile()` | `useEffect` (deps: `[navigate]`) |
| 3–7 | `GET /api/hr/assignments/{id}` × 5 | `loadAssignmentDetails(data, 5, signal)` | After step 1 succeeds |

**Total:** 1 list + 1 company profile + 5 detail requests = **7 requests** on first load.

### Backend Resolution (listAssignments)

- **Admin (non-impersonating):** `db.list_all_assignments()` — no company filter.
- **HR with company_id:** `db.list_assignments_for_company(company_id)` — company-scoped.
- **HR without company_id:** `db.list_assignments_for_hr(effective["id"])` — by `hr_user_id` only (assignments created by this HR).

Company resolution uses `_get_hr_company_id(effective)` (hr_users first, then profile). No explicit company is passed from the frontend.

---

## Causes of Canceled or Duplicate Requests

### 1. AbortController cleanup on unmount

```tsx
useEffect(() => {
  const ac = new AbortController();
  loadAssignments(ac.signal);
  return () => ac.abort();
}, []);
```

When the component unmounts (route change, tab switch, layout re-render), the cleanup aborts the in-flight `listAssignments` request. Any `loadAssignmentDetails` calls that share the same signal are also aborted.

**Observed effect:** Network tab shows canceled `GET /api/hr/assignments` and canceled `GET /api/hr/assignments/{id}` when navigating away during load.

### 2. React Strict Mode double-mount (development)

In React 18 Strict Mode, effects run twice in development: mount → unmount → mount. The first mount’s `loadAssignments` is aborted; the second mount starts a new request. This produces:

- One canceled `listAssignments`
- One successful `listAssignments`
- Potential for 5 canceled + 5 new `getAssignment` calls

### 3. getCompanyProfile redirect

The second `useEffect` calls `getCompanyProfile()`. If `res.company` is null, it navigates to `hrCompanyProfile` via `safeNavigate(navigate, 'hrCompanyProfile')`. That unmounts HrDashboard and aborts `loadAssignments` and `loadAssignmentDetails`.

**Observed effect:** HR user without a company profile sees a canceled assignments request when redirected.

### 4. loadAssignmentDetails fan-out

After `listAssignments` returns, `loadAssignmentDetails(data, 5, signal)` fires 5 parallel `getAssignment` calls. Additional behavior:

- “Load remaining details” triggers `loadAssignmentDetails(assignments, assignments.length, undefined)` — N more `getAssignment` calls (no limit).
- Each assignment row can trigger UI that expects `assignmentDetails[id]`; missing details show “—” until loaded.

### 5. Manual refresh and post-action refetches

- **Refresh button:** `onClick={() => loadAssignments()}` — full refetch, then another 5 `getAssignment` calls.
- **handleAssign success:** `await loadAssignments()` — same pattern.
- **handleRemoveSelected success:** `await loadAssignments()` — same pattern.

Each of these causes 1 list + 5 detail requests. No deduplication or cache.

### 6. No company context guard

`listAssignments` is called immediately on mount. There is no wait for company resolution. If `_get_hr_company_id` returns null, the backend uses `list_assignments_for_hr`, which is hr-owner–scoped, not company-scoped. The frontend does not know whether the result is company-scoped or owner-scoped.

---

## What Should Load on First Render

| Data | When | Owner |
|------|------|-------|
| Assignments list | On mount, after company context is known | Single `loadAssignments` call |
| Company profile | On mount (to gate redirect) | `getCompanyProfile` — can run in parallel |
| Assignment details | After list loads; first N only | `loadAssignmentDetails` with limit |

**Preferred flow:**

1. Resolve company context first (or run in parallel with list).
2. Fire `listAssignments` once when company is known (or when HR user is known).
3. Defer detail loading: load first 5 immediately, load more on “Load remaining” or on scroll/expand.

---

## What Should Be Deferred

| Data | Defer Until |
|------|-------------|
| Full details for all assignments | User clicks “Load remaining details” or expands rows |
| Compliance reports | Already per-assignment in `getAssignment`; avoid extra calls |
| Policy resolution | Only when HR opens assignment detail view |

---

## Recommendations

### 1. Single owner for assignments list

- Use one `loadAssignments` call per page entry.
- Avoid duplicate list calls from multiple components.
- Consider React Query or SWR with a stable key like `['hr', 'assignments', companyId]` to avoid duplicate fetches and enable caching.

### 2. Resolve company before assignments

- Option A: Call `getCompanyProfile` first, then `listAssignments`. If no company, redirect without calling `listAssignments`.
- Option B: Keep both in parallel but do not call `listAssignments` until company (or HR user) is resolved. Backend already handles null company via `list_assignments_for_hr`.

### 3. Avoid aborting on redirect

- If `getCompanyProfile` triggers a redirect, skip calling `loadAssignments` in that render, or use a ref to avoid firing assignments load when a redirect is pending.

### 4. Reduce detail fan-out

- Option A: Backend provides a “list with summary fields” that includes essential display data (name, destination, status) so the initial list does not need 5+ `getAssignment` calls.
- Option B: Keep N-details strategy but increase the initial batch size or load on expand, and avoid loading details for off-screen rows.

### 5. Stable AbortController usage

- Use a ref for the AbortController so unmount/remount (e.g. Strict Mode) does not cause unnecessary aborts.
- Or disable abort-on-unmount when the user is still on the Assignments page (e.g. only abort on actual route change).

### 6. Avoid duplicate list fetches

- After `handleAssign` or `handleRemoveSelected`, either:
  - Optimistically update local state and skip a full refetch, or
  - Refetch once and avoid cascading into another `loadAssignmentDetails` if the list content is unchanged.

---

## References

- `frontend/src/pages/HrDashboard.tsx`: `loadAssignments`, `loadAssignmentDetails`, `useEffect`
- `frontend/src/api/client.ts`: `hrAPI.listAssignments`, `hrAPI.getAssignment`, `hrAPI.getCompanyProfile`
- `backend/main.py`: `list_hr_assignments`, `_get_hr_company_id`
- `backend/database.py`: `list_assignments_for_company`, `list_assignments_for_hr`
