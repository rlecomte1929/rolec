# Case Essentials block (HR case summary)

## Purpose

Give HR an immediate, scannable **who / family / route** context on the case page without scrolling or inferring from other cards.

## UI location

- **Page:** `frontend/src/pages/HrCaseSummary.tsx`
- **Placement:** Directly under the main case action card, **above** Case Readiness, compliance, and timeline.
- **Component:** `frontend/src/features/cases/CaseEssentialsCard.tsx`
- **Derivation logic:** `frontend/src/features/cases/caseEssentials.ts` (`deriveCaseEssentials`)

## Fields shown

| Label        | Meaning                          |
|-------------|-----------------------------------|
| Employee    | Full name (best available)        |
| Email       | Work/login email where known      |
| Family      | Single vs family / dependants copy |
| Origin      | From country or region text        |
| Destination | To country or region text          |

Missing values use explicit placeholders (**Not provided** or **To be completed**) — never a blank cell.

## Data sources (no duplicate storage)

All data is read from the **existing** `GET /api/hr/assignments/{assignment_id}` response (same request as the rest of the page).

### Backend enrichment (same handler)

`backend/main.py` → `get_hr_assignment` adds optional fields on `AssignmentDetail`:

| API field                 | Source |
|---------------------------|--------|
| `employeeEmail`           | `profiles.email` for `case_assignments.employee_user_id` |
| `linkedEmployeeFullName`  | `profiles.full_name` for the same id |
| `caseOriginHint`          | `relocation_cases`: `relocationBasics.originCountry` inside `profile_json` if present, else `home_country` |
| `caseDestinationHint`     | `relocation_cases`: `relocationBasics.destCountry` if present, else `host_country` |

If `case_id` does not resolve to a `relocation_cases` row, hints stay `null`.

### Frontend precedence

Documented in **`caseEssentials.ts`** file header comments. Summary:

1. **Name:** `profile.primaryApplicant.fullName` → `linkedEmployeeFullName` → `employeeFirstName` + `employeeLastName` → **Not provided** (identifier is **not** used as the display name in the essentials grid).
2. **Email:** `employeeEmail` → if `employeeIdentifier` looks like an email, use it → **Not provided**.
3. **Family:** Only from `RelocationProfile` (`maritalStatus`, `spouse`, `dependents`, `familySize` hint). If nothing usable → **To be completed**.
4. **Origin:** `movePlan.origin` → `caseOriginHint` → **Not provided**.
5. **Destination:** `movePlan.destination` → `caseDestinationHint` → **Not provided**.

## Performance

- **No extra network calls** for the essentials block.
- Backend does **in-process** lookups already bounded by the assignment load: one optional `get_case_by_id`, one optional `get_profile_record` — same request lifecycle as the existing detail endpoint.

## Acceptance checklist

- [x] Name, email, family, origin, destination visible near top.
- [x] Uses linked `profiles` + `relocation_cases` + intake `profile` only.
- [x] Missing fields show placeholders.
- [x] No new client-side fetch fan-out.
