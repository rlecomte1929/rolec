# HR Policy — Route Merge Audit

**Date:** 2025-03-17  
**Purpose:** Audit Policy vs Policy Management routes and define migration plan.

---

## Current Route Map

| Route | Component | Nav Tab | Status |
|-------|-----------|---------|--------|
| `/hr/policy` | HrPolicy | Policy | **Canonical** |
| `/hr/policy-management` | HrPolicyManagement | (removed) | Redirects → /hr/policy |
| `/employee/hr-policy` | — | — | Redirects → /hr/policy |

---

## Tab/Nav Ownership

| Nav Item | Target Route | Before | After |
|----------|--------------|--------|-------|
| Policy | /hr/policy | ✓ | ✓ (only tab) |
| Policy Management | /hr/policy | ✓ (duplicate) | **Removed** |

---

## Overlapping UI Sections

| Section | HrPolicy | HrPolicyManagement |
|---------|----------|-------------------|
| Page title / header | ✓ | ✓ |
| Policy list | ✓ (HrPolicyReviewWorkspace) | ✓ (hrPolicyAPI.list) |
| Policy upload | ✓ (PDF/DOCX via PolicyDocumentIntakeSection) | ✓ (JSON/YAML) |
| Benefit editing | ✓ (normalized, HrPolicyReviewWorkspace) | ✓ (manual matrix) |

**Overlap:** Both pages manage policies. HrPolicy uses document-intake (PDF/DOCX) + normalized extraction. HrPolicyManagement uses manual form + JSON/YAML upload. HrPolicy is the richer, canonical path.

---

## Overlapping Requests/Hooks

| Request | HrPolicy | HrPolicyManagement |
|---------|----------|-------------------|
| policy-documents list | PolicyDocumentIntakeSection, HrPolicyReviewWorkspace | — |
| policy-documents/health | PolicyDocumentIntakeSection | — |
| company-policies list | HrPolicyReviewWorkspace | — |
| hr/policies list | — | hrPolicyAPI.list |

**Duplicate:** policyDocumentsAPI.list was called twice from HrPolicy (both PolicyDocumentIntakeSection and HrPolicyReviewWorkspace). Fixed by deferring both until user opens document workflow.

---

## Recommended Canonical Route

**Keep:** `/hr/policy` (HrPolicy)

**Reasons:**
- Document-intake (PDF/DOCX) is the primary policy creation path
- HrPolicyReviewWorkspace provides normalized benefit extraction and publish flow
- HrPolicyManagement uses different API (hrPolicyAPI) and manual JSON/YAML; less central
- Single source of truth for policy management

---

## Migration Plan

1. **Keep** /hr/policy as canonical
2. **Redirect** /hr/policy-management → /hr/policy (already in place)
3. **Remove** Policy Management nav tab (already done)
4. **Update** internal links (HrEmployees, HrEmployeeDetail) to use hrPolicy + "Policy" label
5. **Shell + CTA** on initial load; document workflow on explicit user click
6. **Retain** HrPolicyManagement component for potential JSON/YAML path; do not surface in nav
