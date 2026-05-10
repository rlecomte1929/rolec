# HR Policy — Request Audit

**Date:** 2025-03-17  
**Page:** `/hr/policy` (HR role)

---

## Before Refactor: Request Sequence on Entry

| # | Endpoint | Source | Critical? |
|---|----------|--------|-----------|
| 1 | GET /api/hr/policy-documents | PolicyDocumentIntakeSection loadDocs | On-demand |
| 2 | GET /api/hr/policy-documents/health | PolicyDocumentIntakeSection loadHealth | On-demand |
| 3 | GET /api/hr/policy-documents | HrPolicyReviewWorkspace loadDocumentsAndPolicies | On-demand |
| 4 | GET /api/company-policies | HrPolicyReviewWorkspace loadDocumentsAndPolicies | On-demand |

**Duplicate:** policyDocumentsAPI.list called twice.

**Problem:** All four fired on page entry before any user interaction.

---

## After Refactor: Request Sequence

### On initial entry (shell only)
- **No policy-related requests.**

### After user clicks "Upload company policy"
- PolicyDocumentIntakeSection mounts → loadDocs, loadHealth
- HrPolicyReviewWorkspace mounts → loadDocumentsAndPolicies (policyDocumentsAPI.list + companyPolicyAPI.list)

**Deduplication:** PolicyDocumentIntakeSection and HrPolicyReviewWorkspace both call policyDocumentsAPI.list. Consider sharing a single fetch or having workspace consume documents from intake. For now, both load when workflow opens; duplicate list call remains but only after explicit user action.

---

## Request Classification

| Request | Critical on entry? | Deferred? | On-demand? |
|---------|-------------------|-----------|------------|
| policy-documents | No | No | **Yes** |
| policy-documents/health | No | No | **Yes** |
| company-policies | No | No | **Yes** |

---

## Health Check

- **Before:** Fired on page entry.
- **After:** Fires only when user opens document workflow (clicks "Upload company policy").
- **Removed from critical path:** Yes.
