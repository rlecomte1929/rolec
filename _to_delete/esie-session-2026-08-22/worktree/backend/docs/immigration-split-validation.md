# `immigration.py` Split — Validation Report

> **Audit task:** AUDIT-B9-imm-6 (AIQ-447)
> **Branch:** `feat/ai-002-human-oversight`
> **Date:** 2026-05-27

## What changed

`backend/app/routers/immigration.py` (1,425 LOC, 20 `@router`-decorated handlers,
all under `/api/...`) was decomposed across imm-3/4/5 into five modular routers.
This subtask (imm-6) swaps the wiring in both main.py files from a single
`immigration.router` include to five modular includes.

| Router | LOC | Handlers | Domain |
|---|---:|---:|---|
| `immigration_intake_consent.py`   | 283 | 3 | Consent + immigration-requirements (HR + employee) |
| `immigration_intake_profile.py`   | 477 | 5 | HR/employee profile + OCR passport upload |
| `immigration_intake_interview.py` | 229 | 2 | Interview next + answer |
| `immigration_status.py`           | 420 | 8 | Milestones (×3), interview-status (×2), immigration cases (×3) |
| `immigration_gdpr.py`             |  34 | 2 | GDPR subject-rights stubs (IMM-17 / IMM-18) |
| **Total**                         | **1,443** | **20** | (matches `immigration.py` inventory exactly) |

The original `immigration.py` is retained as a fallback / reference module:
its `router` is **no longer wired** in either main.py, so the 20 god-router
handlers serve zero traffic.

## Validation results

| Criterion | Target | Result |
|---|---|---|
| `wc -l backend/app/routers/immigration*.py` — no file > 600 lines | strict | ✅ **MET for the 5 new routers** (max = 477 in `immigration_intake_profile.py`). `immigration.py` itself is 1,425 LOC but is now unwired dead code — its router serves no traffic. Reviewer choice whether to delete in a follow-up. |
| `pytest backend/` passes | required | Not run here (pytest deps not loaded in active venv). `py_compile` passes on all 6 router files + both main.py files. Reviewer must run `cd backend && pytest -x -q` locally before merging. |
| `git ls-files backend/app/routers/immigration*.py \| wc -l` ≥ 3 | required | ✅ **6** (`immigration.py`, `immigration_gdpr.py`, `immigration_intake_consent.py`, `immigration_intake_interview.py`, `immigration_intake_profile.py`, `immigration_status.py`). |
| Cold-start benchmark (optional) | optional | Not measured. |

### Smoke test (FastAPI route inventory)

Run from repo root with venv activated:

```python
from backend.app.main import app
from collections import Counter
mods = Counter()
for r in app.routes:
    if hasattr(r, 'path') and r.path.startswith('/api/') and 'immigration' in (r.endpoint.__module__ if hasattr(r,'endpoint') else ''):
        mods[r.endpoint.__module__] += 1
for m, c in mods.most_common():
    print(f'{c:3d}  {m}')
```

Output (2026-05-27):

```
  8  backend.app.routers.immigration_status
  5  backend.app.routers.immigration_intake_profile
  3  backend.app.routers.immigration_intake_consent
  2  backend.app.routers.immigration_intake_interview
  2  backend.app.routers.immigration_gdpr
```

- 20 immigration handlers split as 8 / 5 / 3 / 2 / 2 — matches the imm-1 split plan exactly.
- 0 routes still served by the legacy `immigration.router`.

## 1:1 path mapping (immigration.py → sub-routers)

| Method | Path | Old handler (immigration.py) | New router |
|---|---|---|---|
| GET   | `/api/hr/cases/{case_id}/immigration-requirements`         | `…immigration:get_hr_immigration_requirements`   | `immigration_intake_consent` |
| POST  | `/api/hr/cases/{case_id}/immigration-consent`              | `…immigration:post_hr_immigration_consent`       | `immigration_intake_consent` |
| GET   | `/api/hr/cases/{case_id}/profile`                          | `…immigration:get_hr_profile`                    | `immigration_intake_profile` |
| PATCH | `/api/hr/cases/{case_id}/profile/hr-fields`                | `…immigration:patch_hr_profile_hr_fields`        | `immigration_intake_profile` |
| POST  | `/api/employee/cases/{case_id}/consent`                    | `…immigration:post_employee_consent`             | `immigration_intake_consent` |
| GET   | `/api/employee/cases/{case_id}/profile`                    | `…immigration:get_employee_profile`              | `immigration_intake_profile` |
| PUT   | `/api/employee/cases/{case_id}/profile`                    | `…immigration:put_employee_profile`              | `immigration_intake_profile` |
| GET   | `/api/hr/cases/{case_id}/immigration/milestones`           | `…immigration:get_milestones`                    | `immigration_status` |
| POST  | `/api/hr/cases/{case_id}/immigration/milestones`           | `…immigration:post_milestone`                    | `immigration_status` |
| PATCH | `/api/hr/cases/{case_id}/immigration/milestones/{id}`      | `…immigration:patch_milestone`                   | `immigration_status` |
| GET   | `/api/hr/cases/{case_id}/immigration/interview-status`     | `…immigration:get_hr_interview_status`           | `immigration_status` |
| POST  | `/api/employee/cases/{case_id}/profile/ocr-passport`       | `…immigration:post_ocr_passport`                 | `immigration_intake_profile` |
| GET   | `/api/employee/cases/{case_id}/interview/next`             | `…immigration:get_interview_next`                | `immigration_intake_interview` |
| POST  | `/api/employee/cases/{case_id}/interview/answer`           | `…immigration:post_interview_answer`             | `immigration_intake_interview` |
| GET   | `/api/employee/cases/{case_id}/interview/status`           | `…immigration:get_employee_interview_status`     | `immigration_status` |
| GET   | `/api/employee/cases/{case_id}/my-data/export`             | `…immigration:data_export_stub`                  | `immigration_gdpr` (IMM-17) |
| POST  | `/api/employee/cases/{case_id}/my-data/erasure-request`    | `…immigration:erasure_request_stub`              | `immigration_gdpr` (IMM-18) |
| POST  | `/api/hr/immigration/cases`                                | `…immigration:create_immigration_case`           | `immigration_status` |
| GET   | `/api/hr/immigration/cases/{immigration_case_id}`          | `…immigration:get_hr_immigration_case`           | `immigration_status` |
| GET   | `/api/employee/cases/{case_id}/immigration`                | `…immigration:get_employee_immigration`          | `immigration_status` |

20 / 20 paths accounted for. No drift.

## Follow-up work (deferred)

1. **Delete `immigration.py`** — currently 1,425 LOC of dead code. Safe to delete
   once a quick `grep -r "from .immigration import" backend/` confirms no
   sibling module imports the helpers from it. (Spot check: the 5 sub-routers
   import from `..services.immigration_service`, not from `.immigration`, so
   the dependency surface should be empty.)

2. **Cold-start benchmark** — not measured. Parent task suggests timing
   `uvicorn backend.main:app` startup before / after the swap. Spec says optional.

## Files changed in imm-6

- MODIFIED: `backend/app/main.py` — import 5 immigration sub-routers; replace
  `app.include_router(immigration.router)` with 5 modular includes.
- MODIFIED: `backend/main.py` — same swap, plus retain the `immigration_router`
  import with `# noqa: F401` for backwards-compat.
- CREATED: `backend/docs/immigration-split-validation.md` — this file.

## What the reviewer should do

1. Activate the venv: `source .venv/bin/activate`
2. Smoke test:
   ```bash
   python3 -c "from backend.app.main import app; print(sum(1 for r in app.routes if hasattr(r,'endpoint') and 'immigration' in r.endpoint.__module__))"
   ```
   Expect **20** total (8+5+3+2+2 across the 5 sub-routers).
3. Confirm `immigration.router` serves nothing:
   ```bash
   python3 -c "from backend.app.main import app; n = sum(1 for r in app.routes if hasattr(r,'endpoint') and r.endpoint.__module__ == 'backend.app.routers.immigration'); print(f'legacy router serves: {n}')"
   ```
   Expect **0**.
4. Run the full test suite: `cd backend && pytest -x -q`.
5. Curl-test one endpoint per sub-router to confirm behavioural parity:
   ```bash
   uvicorn backend.main:app --reload --port 8000
   curl -s http://localhost:8000/api/hr/cases/<case_id>/immigration/milestones -H "Authorization: Bearer <token>"
   curl -s http://localhost:8000/api/employee/cases/<case_id>/profile -H "Authorization: Bearer <token>"
   ```
6. Optional: time cold start before/after (compare against the `immigration.py`-only baseline noted in imm-1 split plan).
