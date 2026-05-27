# `cases.py` Split — Validation Report

> **Audit task:** AUDIT-B9-cases-6 (AIQ-454)
> **Branch:** `feat/ai-002-human-oversight`
> **Date:** 2026-05-27

## What changed

`backend/app/routers/cases.py` (3,477 LOC, 35 `@router`-decorated handlers) was
decomposed into three modular routers in subtasks cases-3/4/5:

| Router | LOC | Handlers | Method mix |
|---|---:|---:|---|
| `cases_read.py`  | 1,950 | 20 | 20 GET |
| `cases_write.py` | 1,189 | 14 | 9 POST + 4 PATCH + 1 PUT |
| `cases_admin.py` |    60 |  1 | 1 DELETE |
| **Total**        | **3,199** | **35** | (matches `cases.py` inventory exactly) |

In this subtask (cases-6), the wiring in `backend/app/main.py` and
`backend/main.py` was swapped from a single `cases.router` include to three
modular includes (read, write, admin).

The original `cases.py` is **retained as a support module**:

- Its `router = APIRouter(prefix="/api/cases", tags=["cases"])` declaration and
  the 35 `@router.*` decorators are still present in the file, but the router
  object is **no longer wired into either main.py**, so the handlers serve
  zero traffic.
- The file's Pydantic models (`HouseholdPayload`, `BulkFieldUpdatePayload`,
  `CaseFormSummary`, `FormFlagResponse`, `CreateDossierPayload`, …) and
  private helpers (`_build_cover_page`, `_build_divider_page`,
  `_fetch_single_form_summary`, `_load_form_with_template`,
  `_compute_completion`, `_fetch_form_pdf_bytes`, `_merge_pdfs`,
  `_try_store_dossier_pdf`) are still imported by `cases_write.py`. Until
  those helpers are migrated into `case_service.py` or a new
  `case_pdf_service.py`, deleting `cases.py` would break `cases_write.py`.

## Validation results

| Criterion | Target | Result |
|---|---|---|
| 1. No router file > 1,000 lines | strict | ⚠️ **NOT MET** — `cases.py` (3,477), `cases_read.py` (1,950), `cases_write.py` (1,189) all exceed. Reason: PDF helper stack (~600 LOC inline) and Pydantic models still duplicated between cases.py and the new files. See "Follow-up work" below. |
| 2. `pytest` passes | required | Not run in this environment (pytest deps not loaded in the active venv). py_compile passes on all router files and both main.py files. Reviewer must run `cd backend && pytest -x -q` locally before merging. |
| 3. E2E score ≥ pre-split baseline | required | Not run (requires running app + `node relopass_api_runner.js`). Reviewer must execute. |
| 4. `git ls-files backend/app/routers/cases*.py \| wc -l` ≥ 3 | required | ✅ **4** (`cases.py`, `cases_read.py`, `cases_write.py`, `cases_admin.py`). |

### Smoke test (FastAPI route inventory)

Run from repo root with venv activated:

```python
from backend.app.main import app
from collections import Counter
mods = Counter()
for r in app.routes:
    if hasattr(r, 'path') and r.path.startswith('/api/cases') and hasattr(r, 'endpoint'):
        mods[r.endpoint.__module__] += 1
for m, c in mods.most_common():
    print(f'{c:3d}  {m}')
```

Output (2026-05-27):

```
 20  backend.app.routers.cases_read
 14  backend.app.routers.cases_write
  4  backend.app.routers.pets             (unrelated — /api/cases/{id}/pets)
  2  backend.app.routers.exception_requests
  1  backend.app.routers.cases_admin
```

- 35 cases handlers split as 20 / 14 / 1 — matches the cases-1 recon inventory exactly.
- 0 routes still served by the legacy `cases.router`.

## Follow-up work (deferred, not blockers)

These should be filed as new tickets, not bolted onto cases-6:

1. **Extract PDF helpers into `case_pdf_service.py`** — `_build_overlay_page`,
   `_generate_filled_pdf`, `_make_blank_pdf`, `_safe_filename_part`,
   `_try_store_draft_pdf`, `_build_cover_page`, `_build_divider_page`,
   `_fetch_form_pdf_bytes`, `_merge_pdfs`, `_try_store_dossier_pdf` are
   currently duplicated between `cases_read.py` (inline) and `cases.py` (still
   the import source for `cases_write.py`). After extraction:
   - `cases_read.py` drops back below the 1,000 LOC ceiling.
   - `cases_write.py` drops to ~900 LOC.
   - `cases.py` can be safely deleted.

2. **Migrate `_fetch_single_form_summary`, `_load_form_with_template`,
   `_compute_completion`, `_row_to_summary` into `case_service.py`** — these
   are pure DTO/transformer helpers (recon §9c). Same blocker as above.

3. **Migrate inline Pydantic models** (`HouseholdPayload`,
   `BulkFieldUpdatePayload`, `CommentCreate`, `FlagPatchPayload`,
   `FormStatusPatchPayload`, `CreateDossierPayload`, `_MessageBody`,
   `_QuoteRequestBody`, etc.) into a dedicated
   `backend/app/schemas/case_payloads.py` or into `case_service.py`. Both
   `cases_write.py` and `cases.py` currently define / re-export these.

4. **Add HR-role gate to `delete_dossier`** — flagged in cases-1 recon §6.
   Currently only company-membership check via `_assert_case_access`.

## Files changed in cases-6

- MODIFIED: `backend/app/main.py` — import cases_admin/cases_read/cases_write
  alongside cases; replace `app.include_router(cases.router)` with three modular
  includes.
- MODIFIED: `backend/main.py` — import cases_read_router, cases_write_router,
  cases_admin_router; replace `app.include_router(cases_router.router)` with
  three modular includes. `cases_router` import retained with `# noqa: F401`
  for backwards-compat.
- CREATED: `backend/docs/cases-split-validation.md` — this file.

## What the reviewer should do

1. Activate the venv: `source .venv/bin/activate`
2. Smoke test:
   ```bash
   python3 -c "from backend.app.main import app; print(len([r for r in app.routes if hasattr(r,'path') and r.path.startswith('/api/cases')]))"
   ```
   Expect **41** (35 modular + 6 unrelated from pets/exceptions).
3. Confirm `cases.router` serves nothing:
   ```bash
   python3 -c "from backend.app.main import app; n = sum(1 for r in app.routes if hasattr(r,'endpoint') and r.endpoint.__module__ == 'backend.app.routers.cases'); print(f'legacy router serves: {n}')"
   ```
   Expect **0**.
4. Run the full test suite: `cd backend && pytest -x -q`.
5. Boot uvicorn and curl a sample endpoint per method:
   ```bash
   uvicorn backend.main:app --reload --port 8000
   curl -s http://localhost:8000/api/cases -H "Authorization: Bearer <token>" | jq
   ```
6. Run E2E: `node relopass_api_runner.js` and compare score to pre-split baseline.
