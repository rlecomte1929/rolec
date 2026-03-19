# HR Policy — Route Merge Results

**Date:** 2025-03-17

---

## Route Kept

- **Canonical route:** `/hr/policy` (HrPolicy)
- **Nav tab:** Policy (single tab)

---

## Route/Tab Removed

- **Removed tab:** Policy Management (was duplicate; both pointed to same content)
- **Removed route from nav:** `/hr/policy-management` still exists but **redirects** to `/hr/policy`
- **Internal links updated:** HrEmployees, HrEmployeeDetail now link to `hrPolicy` with label "Policy"

---

## Content Merged

| Before | After |
|--------|-------|
| Policy tab → HrPolicy | Policy tab → HrPolicy |
| Policy Management tab → HrPolicy (duplicate) | Removed |
| PolicyDocumentIntakeSection + HrPolicyReviewWorkspace on entry | Same components, but **only after** user clicks "Upload company policy" |

---

## Content Hidden by Default

- Policy document upload (PDF/DOCX)
- Policy document list
- PolicyDocumentsAPI health check
- HrPolicyReviewWorkspace (policy list, normalized view, clauses, publish)
- All policy-document and company-policy data fetching

---

## Requests Removed from Initial Page Load

| Request | Before | After |
|---------|--------|-------|
| GET /api/hr/policy-documents | On entry | On-demand only |
| GET /api/hr/policy-documents/health | On entry | On-demand only |
| GET /api/company-policies | On entry | On-demand only |

---

## Before/After Request Count on Page Entry

| Scenario | Before | After |
|----------|--------|-------|
| Initial tab click / route entry | 4 requests | 0 requests |

---

## Component Architecture

- **HrPolicyOverview** — Shell: title, intro, CTA. No data fetching.
- **PolicyDocumentIntakeSection** — Upload, document list, health. Mounts only when workflow opened.
- **HrPolicyReviewWorkspace** — Policies, normalized view, publish. Mounts only when workflow opened.

---

## Instrumentation

With `VITE_PERF_DEBUG=1`:
- `route_entry` — route entered
- `shell_first_render` — page shell rendered
- `policy_upload_cta_click` — user clicked "Upload company policy"
- `policy_upload_ui_shown` — document workflow UI mounted

---

## Follow-up Recommendations

1. **Deduplicate policy-documents list:** PolicyDocumentIntakeSection and HrPolicyReviewWorkspace both call `policyDocumentsAPI.list` when workflow opens. Consider a shared fetch or context.
2. **HrPolicyManagement:** Component remains for JSON/YAML manual policy path. Route redirects to /hr/policy. Consider deprecating or folding into Policy page if JSON/YAML upload is needed.
