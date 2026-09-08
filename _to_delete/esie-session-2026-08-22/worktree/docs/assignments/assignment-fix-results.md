# Assignment Fix Results

**Date:** 2025-03-19  
**Purpose:** Summary of what was wrong, what was fixed, and verification checklist.

---

## What Was Wrong

### Domain and Guardrails

1. **HR company resolution inconsistency:** assign_case and create_case used `profile.company_id`; list used `_get_hr_company_id`. HR with `hr_users.company_id` but null `profiles.company_id` could list but not create/assign.
2. **No company required on assign:** When hr_company_id was null, assignment could be created without case company linkage.
3. **Admin assignment creation:** Did not pass employee_first_name, employee_last_name (inconsistent with HR flow).

### Assignments Page Load

1. **Parallel effects causing aborts:** getCompanyProfile and loadAssignments ran in parallel. When getCompanyProfile returned no company and redirected, the component unmounted and aborted loadAssignments.
2. **No company-first gate:** Assignments were fetched before confirming company context; redirect could cancel in-flight requests.

---

## What Was Fixed

### Backend

1. **Unified HR company resolution:** create_case and assign_case now use `_get_hr_company_id(effective)`.
2. **Company required:** Both endpoints return 400 "No company linked to your profile. Please complete your company profile first." when company_id is null.
3. **Admin creation alignment:** AdminCreateAssignmentRequest now accepts optional employee_first_name, employee_last_name; passed to create_assignment.

### Frontend

1. **Sequenced load:** Single useEffect: getCompanyProfile first → if company exists, loadAssignments. No assignments load when redirecting.
2. **Single owner for list:** One loadAssignments call per page entry; no parallel fetch-and-abort.

---

## Before/After Request Behavior

| Scenario | Before | After |
|----------|--------|-------|
| HR with company, first load | listAssignments + getCompanyProfile in parallel; 5× getAssignment after list | getCompanyProfile → listAssignments → 5× getAssignment |
| HR without company | listAssignments in flight; getCompanyProfile redirects → abort | getCompanyProfile redirects; listAssignments never starts |
| React Strict Mode double-mount | First mount abort, second mount new requests | Same; but no redundant start-then-abort from redirect race |

---

## Before/After Data Model Clarity

| Aspect | Before | After |
|--------|--------|-------|
| HR company for assign | profile.company_id | _get_hr_company_id (hr_users first) |
| HR company for create case | profile.company_id | _get_hr_company_id |
| Admin assignment names | Not stored | employee_first_name, employee_last_name optional |
| Company required | Implicit (could be null) | Explicit 400 when null |

---

## Before/After Claim Flow

- No code changes to claim flow.
- Documented in assignment-claim-flow.md.
- Identity match remains the primary guard; idempotent attach; no duplicate records.

---

## Remaining Risks or Follow-Ups

1. **Backend bulk list with details:** Consider an endpoint that returns list + essential display fields to avoid N getAssignment calls.
2. **React Strict Mode:** Development double-mount may still cause one aborted list request; behavior is acceptable.
3. **assignment_invites.assignment_id:** Schema has no assignment_id; token-based claim would need join. Documented; no change in this pass.
4. **Duplicate employees:** No automated deduplication; manual review if observed.

---

## Manual Verification Checklist

- [ ] **HR sees only own company employees/cases:** Log in as HR for company A; list assignments; verify only company A data.
- [ ] **Admin can assign correctly:** Create assignment from Admin Assignments with company, HR, employee; verify it appears in HR list for that company.
- [ ] **HR can assign correctly:** Create case, assign with employee email; verify assignment created with company_id on case.
- [ ] **Existing-account employee can claim/connect:** Employee with account; HR assigns with their email; employee logs in and claims (or dashboard auto-attaches); verify case visible.
- [ ] **New-account employee can register then claim:** HR assigns to new email; employee registers with that email; logs in; claim or dashboard connects; verify case visible.
- [ ] **No duplicate/conflicting records:** After claim, verify single employee_user_id on assignment; no duplicate assignments for same case+identifier.
- [ ] **Assignments page loads reliably:** No repeated/canceled requests in network tab; single list + 5 details on first load.
