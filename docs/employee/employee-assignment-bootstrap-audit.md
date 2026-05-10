# Employee assignment bootstrap audit (Phase 1)

## Request sequence (typical)

1. **Login** — `POST /api/auth/login` → token stored; no assignment APIs yet.
2. **First employee shell render** — `EmployeeAssignmentProvider` runs when route matches `shouldLoadEmployeeAssignmentOverview` (see `frontend/src/utils/employeeAssignmentScope.ts`).
3. **Overview** — `GET /api/employee/assignments/overview` (compact linked + pending rows, includes `company`, `case_id`, destination hints).
4. **Optional / cached** — `GET /api/employee/assignments/current` via `employeeAPI.getCurrentAssignment()` (30s client cache). Used where full assignment rows are needed; **not** required for every wizard step after this audit.

## Who called what (before fixes)

| Consumer | Endpoint | Trigger |
|----------|----------|---------|
| `EmployeeAssignmentProvider` | `overview` | **Every pathname change** inside employee/services/quotes/resources because `loadAssignment` depended on `pathname` → refetch on each wizard step. |
| `CaseWizardPage` | `current` | `useEffect` on `[assignmentId, navigate]` calling `getCurrentAssignment` for status + HR notes. |
| `employeeAPI.getCurrentAssignment` | `current` | Any other callers (cached 30s). |
| `CompanyBrand` + `useCompany` | `GET /api/company` | Generic company for header; could disagree with assignment-linked company. |

## Duplicate / redundant calls

- Overview refetch on **every wizard step** (pathname `/wizard/1` → `/wizard/2` …).
- Wizard **plus** provider both touching assignment resolution (`current` + `overview`).
- `handleSave` in wizard: **PATCH** + **GET relocation case** (requirements) + **notify-hr** on every save.
- Step 5 also loads relocation case independently.

## Likely root causes of 500s on overview / current

1. **Non-JSON-serializable row values** from Postgres (e.g. `UUID`, `datetime`, `Decimal`) in assignment/overview payloads → FastAPI response serialization failure → **500** (browser often reports CORS because error response omits CORS headers).
2. **SQL errors** in overview joins (`relocation_cases` ↔ `case_assignments`) on mixed uuid/text schemas → uncaught exception → **500**.
3. Partial failures in one sub-query (linked vs pending) previously failing the whole handler.

## Recommended canonical bootstrap path (implemented)

1. **Single overview fetch** when entering employee-related routes, **not** on every nested path change (same `shouldFetch` while staying in scope).
2. **Client cache** for overview (`employee:assignments-overview`, 60s TTL) aligned with `current` cache invalidation on claim/link/logout.
3. **Derive primary assignment id + company** from `overview.linked[0]` (precedence: same as before; multi-assignment still uses `?assignment=` via existing helpers).
4. **Wizard status** from overview row for the route’s `assignmentId` instead of a parallel `current` call per mount cycle.

See also: [canonical-employee-case-context.md](./canonical-employee-case-context.md).
