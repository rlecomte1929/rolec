# Company display linkage (Phase 4)

## Old behavior

- **`CompanyBrand`** used `useCompany()` → `GET /api/company` for non-HR routes.
- That endpoint reflects the **generic company association** for the logged-in user, which may not match the company on the **HR-created assignment** (especially if the user has multiple ties or legacy data).

## Corrected linkage

- **`EmployeeAssignmentContext`** exposes `primaryAssignmentCompany` from overview `linked[0].company` (backend joins assignment → case / HR → `companies`).
- **`CompanyBrand`** (`frontend/src/components/CompanyBrand.tsx`):
  - For **EMPLOYEE** or **ADMIN** on non-`/hr/*` routes, if `primaryAssignmentCompany.name` is set, **skip** `/api/company` and show that name (and optional id).
  - While assignment overview is loading for that mode, show a loading state instead of a wrong cached company.
  - **HR on `/hr/*`** — unchanged: `HrCompanyContext`.

## UI surfaces updated

- Global header **company name / initials** (all employee flows using `AppShell` + `CompanyBrand`).
- Wizard **“Fill for test”** employer name seeds from the same overview company when available (`CaseWizardPage`).

Logo URL is not yet returned on overview rows; header may show initials until a dedicated field exists.
