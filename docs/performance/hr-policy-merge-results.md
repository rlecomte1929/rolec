# HR Policy Merge — Results

**Date:** 2025-03-17

---

## Before / After Page Structure

### Before
- Two nav tabs: "Policy" and "Policy Management" (both → /hr/policy)
- On entry: PolicyDocumentIntakeSection + HrPolicyReviewWorkspace rendered immediately
- 4 requests on entry: policy-documents, health, policy-documents (dup), company-policies
- Health check on critical path

### After
- Single nav tab: "Policy"
- On entry: Shell with title, intro, CTA "Upload company policy"
- 0 policy-related requests on entry
- Document workflow (PolicyDocumentIntakeSection + HrPolicyReviewWorkspace) only after user clicks "Upload company policy"
- "← Back to overview" returns to shell

---

## Request Counts

| Scenario | Before | After |
|----------|--------|-------|
| Initial tab click | 4 requests | 0 requests |
| After "Upload company policy" | — | 4 requests (same as before, but deferred) |

---

## Removed from Initial Load
- GET /api/hr/policy-documents (×2)
- GET /api/hr/policy-documents/health
- GET /api/company-policies

---

## Manual Verification Checklist (Chrome DevTools)

1. Open DevTools → Network tab
2. Clear network log
3. Navigate to /hr/policy as HR user
4. **Verify:** No policy-documents or company-policies requests
5. Click "Upload company policy"
6. **Verify:** policy-documents, health, company-policies requests fire
7. Click "← Back to overview"
8. Navigate away and back to /hr/policy
9. **Verify:** Shell shows again, no policy requests until CTA clicked
