# HR policy → employee comparison: verification matrix

This document ties **product scenarios** to **expected UX/API behavior** and **backend instrumentation**, so you can prove the policy model works and degrades safely.

Related: [policy-degraded-states.md](./policy-degraded-states.md), [comparison-readiness-and-fallback.md](./comparison-readiness-and-fallback.md), [policy-performance-hardening.md](./policy-performance-hardening.md).

---

## 1. Instrumentation (where to look)

Events are emitted via `emit_event` in [`backend/services/analytics_service.py`](../../backend/services/analytics_service.py). Each line is logged as:

`analytics event=<name> {<json payload without redundant "event" key>}`

If `analytics_events` exists, rows are persisted (failures are non-fatal).

Wrappers live in [`backend/services/policy_pipeline_analytics.py`](../../backend/services/policy_pipeline_analytics.py).

### 1.1 Event catalog

| Event name | When | Key `extra` fields |
|------------|------|-------------------|
| `policy_upload_started` | HR upload: after validation, before storage | `company_id`, `filename`, `file_size_bytes` |
| `policy_upload_completed` | Upload finished (200 or 207 partial) | `document_id`, `processing_status`, `clause_count`, `duration_ms` |
| `policy_classify_started` | Before `process_uploaded_document` | `document_id`, `source` (`upload` \| `reprocess`) |
| `policy_classify_completed` | Classify/extract succeeded (`processing_status` ≠ `failed`) | `processing_status`, `detected_document_type`, `source` |
| `policy_classify_failed` | Extract/classify failed or exception | `extraction_error`, `source` |
| `policy_normalize_started` | Start of `POST .../policy-documents/{id}/normalize` | `document_id`, `company_id` |
| `policy_normalize_completed` | Normalize + auto-publish succeeded | `policy_id`, `policy_version_id`, `summary`, `auto_published` |
| `policy_normalize_failed` | Invalid input (422), validation (400), or runtime (500) | `error_code`, `detail`, `http_status` |
| `policy_publish_started` | Start of `_hr_publish_policy_version` | `policy_id`, `policy_version_id`, `source` (`manual` \| `normalize`) |
| `policy_publish_completed` | Publish persisted | same as started |
| `policy_publish_failed` | Publish gate or DB update failed | `error_code`, `detail`, `source` |
| `policy_employee_resolution` | After employee resolution finalization | `has_policy`, `comparison_ready`, `comparison_available`, `comparison_blockers`, `employee_ux_mode`, `resolution_cache_hit`, ids |
| `employee_policy_fallback_triggered` | Same request, when `comparison_available` is false | `employee_ux_mode`, `has_policy`, blockers |
| `employee_policy_comparison_triggered` | Same request, when `comparison_available` is true | `policy_id`, `policy_version_id` |

**Notes**

- Manual publish from the HR workspace uses `policy_publish_*` with `source=manual`. Normalize auto-publish uses `source=normalize` (you will see `policy_normalize_completed` plus `policy_publish_*`).
- Each employee policy resolution emits **one** `policy_employee_resolution` and **one** of `employee_policy_fallback_triggered` **or** `employee_policy_comparison_triggered`.

---

## 2. Scenario matrix

Use a dedicated test company + assignment. Record **actual** results after each run (screenshots optional). `analytics event=...` lines in backend logs should align with the “Instrumentation checks” column.

| # | Scenario | HR setup | Expected HR UI / API | Expected employee UI / API | Instrumentation checks (order may vary) |
|---|----------|----------|----------------------|----------------------------|----------------------------------------|
| 1 | Upload document, **metadata/classify only**, **not** normalized | `POST /api/hr/policy-documents/upload` succeeds; **do not** call normalize | Pipeline: **`uploaded_not_normalized`** (or similar) in [`hrPolicyDegradedState`](../../frontend/src/features/policy/hrPolicyDegradedState.ts); no published `policy_versions` for that policy yet | `GET /api/employee/me/assignment-package-policy` → `no_policy_found` **or** `has_policy: false` until a **published** version exists; comparison off | `policy_upload_started` → `policy_classify_started` → `policy_classify_completed` (or `policy_classify_failed`) → `policy_upload_completed`. **No** `policy_normalize_*` / `policy_publish_*`. Employee: `policy_employee_resolution` with `employee_ux_mode=fallback_no_policy` |
| 2 | **Normalize fails** (bad payload / invalid input) | Provoke `422` from normalize (e.g. document not ready per [`normalization_input`](../../backend/services/normalization_input.py)) | Actionable error payload (`normalization_input_invalid`, issues list); HR banner/error path | Employee unchanged vs scenario 1: **still** no published policy or same fallback; **no** comparison | `policy_normalize_started` → `policy_normalize_failed` (`error_code=normalization_input_invalid`). **No** `policy_normalize_completed` |
| 3 | **Normalize succeeds**, published, **missing comparison fields** | Complete normalize + publish; published version lacks required comparison benefit signals ([`EMPLOYEE_COMPARISON_REQUIRED_BENEFIT_KEYS`](../../backend/services/policy_comparison_readiness.py)) | HR: **`published_not_comparison_ready`** banner; `published_comparison_readiness` shows blockers | `comparison_available: false`; summary-only / partial copy ([`EmployeeResolvedPolicyView`](../../frontend/src/features/policy/EmployeeResolvedPolicyView.tsx), Services `comparison_not_ready`) | `policy_normalize_completed`; `policy_publish_*` with `source=normalize`. Employee: `policy_employee_resolution` with `employee_ux_mode=fallback_summary`, `employee_policy_fallback_triggered` |
| 4 | **Normalize succeeds** and **comparison-ready** | Ensure housing, schooling, shipment rules have decision signals; publish | HR: **`published_comparison_ready`** | Package/Services: comparison bars / caps where implemented; `comparison_available: true` | Same pipeline events as 3 plus employee: `employee_ux_mode=comparison`, `employee_policy_comparison_triggered` |
| 5 | **No published policy** for company/assignment | No `policy_versions.status=published` for resolving company | N/A (HR may show empty or draft-only workspace) | Fast `no_policy_found` / static fallback copy; **no** long ambiguous spinner ([`employeePolicyMessages`](../../frontend/src/features/policy/employeePolicyMessages.ts)) | `policy_employee_resolution` + `employee_policy_fallback_triggered`; **no** normalize/publish events from that flow |

---

## 3. Expected vs actual results (fill in during QA)

| # | Expected (summary) | Actual result | Pass? | Notes / links |
|---|-------------------|---------------|-------|----------------|
| 1 | HR incomplete; employee no comparison | *To be filled* | ☐ | |
| 2 | HR actionable failure; employee safe fallback | *To be filled* | ☐ | |
| 3 | HR not comparison-ready; employee summary-only | *To be filled* | ☐ | |
| 4 | Employee policy-aware comparison | *To be filled* | ☐ | |
| 5 | Employee static fallback quickly | *To be filled* | ☐ | |

---

## 4. Remaining gaps (as of doc authoring)

| Gap | Impact | Suggested follow-up |
|-----|--------|----------------------|
| **Manual QA not executed in CI** | “Actual results” above are placeholders until someone runs the matrix | Run once per release or gate with checklist |
| **Upload early-failure paths** | Storage/validation failures before `document_id` exists do not emit `policy_upload_failed` (only classify/upload completion paths are fully covered) | Add `policy_upload_failed` with `error_code` on 4xx/5xx returns if you need full funnel metrics |
| **Legacy `POST /api/company-policies/upload`** | Separate code path; not instrumented here | Align on single upload path or mirror events |
| **Volume / sampling** | Every employee policy GET emits 2–3 analytics events | If noisy in production, gate with env flag or sample rate |
| **Cross-service correlation** | `request_id` is present on HR uploads; employee events use the same `request_id` when passed through `_resolve_published_policy_for_employee` | Ensure API gateway or log pipeline preserves `request_id` for trace joins |

---

## 5. Quick log grep (local)

```bash
# Backend stdout / log file
grep 'analytics event=policy_' your-backend.log
grep 'analytics event=employee_policy_' your-backend.log
```

Confirm ordering for scenarios 1–4 by following a single `request_id` through HR actions, then loading the employee HR Policy page and grepping `policy_employee_resolution` for that session’s assignment.
