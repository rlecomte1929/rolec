# HR Policy — Information Architecture Audit

**Date:** 2025-03-17  
**Purpose:** Compare Policy vs Policy Management and define merged target.

---

## Route/Component Map

| Route | Component | Status |
|-------|-----------|--------|
| `/hr/policy` | HrPolicy | **Canonical** — serves HR, Employee, Admin |
| `/hr/policy-management` | HrPolicyManagement | **Redirects to /hr/policy** (never rendered) |
| `/employee/hr-policy` | — | Redirects to /hr/policy |

**Navigation:** AppShell shows two tabs that both link to `/hr/policy`:
- "Policy" → hrPolicy
- "Policy Management" → hrPolicy (duplicate)

---

## Page Content Comparison

### HrPolicy (canonical)
- **Employee role:** EmployeePolicyContent (getCurrentAssignment → EmployeeResolvedPolicyView)
- **HR/Admin role:**
  - PolicyDocumentIntakeSection — PDF/DOCX upload, document list, health check
  - HrPolicyReviewWorkspace — policies list, normalized view, clauses, publish

### HrPolicyManagement (redirected, never used)
- hrPolicyAPI.list, create, update, upload (JSON/YAML)
- Manual benefit matrix editing
- Different workflow: JSON/YAML upload vs PDF/DOCX document intake
- Has "View assignment policy" → navigates to HrPolicy

---

## Overlapping vs Unique

| Feature | HrPolicy | HrPolicyManagement |
|---------|----------|-------------------|
| Policy document upload (PDF/DOCX) | ✅ PolicyDocumentIntakeSection | ❌ |
| Policy upload (JSON/YAML) | ❌ | ✅ |
| Policy list | ✅ companyPolicyAPI.list (review workspace) | ✅ hrPolicyAPI.list |
| Benefit editing | ✅ HrPolicyReviewWorkspace (normalized) | ✅ Manual matrix |
| Document intake (classify, normalize) | ✅ | ❌ |
| Health check | ✅ policyDocumentsAPI.health | ❌ |

**Overlap:** Both manage policies; HrPolicy is the document-intake + normalized-extraction path. HrPolicyManagement is a legacy manual/JSON path that redirects away.

---

## Requests on Entry (HrPolicy, HR role)

| Request | Source | Trigger |
|---------|--------|---------|
| GET /api/hr/policy-documents | PolicyDocumentIntakeSection | useEffect loadDocs |
| GET /api/hr/policy-documents/health | PolicyDocumentIntakeSection | useEffect loadHealth |
| GET /api/hr/policy-documents | HrPolicyReviewWorkspace | useEffect loadDocumentsAndPolicies |
| GET /api/company-policies | HrPolicyReviewWorkspace | useEffect loadDocumentsAndPolicies |

**Duplicate:** policyDocumentsAPI.list called twice (PolicyDocumentIntakeSection + HrPolicyReviewWorkspace).

---

## Recommendation

1. **Merge:** Keep single "Policy" tab; remove "Policy Management" from nav.
2. **Canonical route:** `/hr/policy`.
3. **Shell on entry:** Title, intro, CTA "Upload company policy" — no document/policy data.
4. **On-demand:** PolicyDocumentIntakeSection + HrPolicyReviewWorkspace render only after user clicks CTA.
5. **HrPolicyManagement:** Keep component for JSON/YAML workflow if needed later; do not surface in main nav. Route stays as redirect.

---

## Content Classification

### A. Critical on first entry
- Page title
- Short intro copy
- CTA: "Upload company policy"

### B. Deferred
- Policy count/summary (only if cheap endpoint exists)
- Last updated (only if cheap)

### C. On-demand only
- policyDocumentsAPI.list
- policyDocumentsAPI.health
- companyPolicyAPI.list
- All document/policy detail endpoints
- HrPolicyReviewWorkspace data
- PolicyDocumentIntakeSection UI and data
