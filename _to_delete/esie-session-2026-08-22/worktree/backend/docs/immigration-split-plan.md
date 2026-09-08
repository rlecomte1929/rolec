# `immigration.py` Split Plan — `backend/app/routers/immigration.py`

> **Audit task**: AUDIT-B9-imm-1 (AIQ-442)
> **Date**: 2026-05-27
> **Source file**: `backend/app/routers/immigration.py` (1,732 lines)
> **Router definition**: `router = APIRouter(prefix="/api", tags=["immigration"])` (line 72)
> **Snapshot caveat**: The parent task brief cited 1,544 LOC. The file has grown to **1,732 LOC**. Sub-1,000-LOC target after split still feels achievable.

---

## 1. Summary

| Metric | Count |
|---|---|
| Total file LOC | **1,732** |
| `@router.*` route handlers | **20** |
| Private helpers / pure functions | **14** |
| Imported services (already extracted) | **1** — `immigration_interview_engine` (10 symbols imported) |

**Validation:** `grep -c '^@router\.' backend/app/routers/immigration.py` → **20** (matches handler count).

**Persona scoping is URL-based** (clean — much easier than `cases.py`):
- `/api/hr/*` → HR endpoints (gated by `get_org_id_for_hr_user` / `require_admin_or_hr`)
- `/api/employee/*` → Employee endpoints (gated by `get_current_user`)
- `/api/hr/immigration/*` → HR immigration-case CRUD (separate URL family)

**Target-file totals:**

| # | Target file | Handlers | Est. LOC (handlers only) |
|---|---|---|---|
| 1 | `immigration_intake.py` | 10 | ~845 |
| 2 | `immigration_status.py` | 8 | ~365 |
| 3 | `immigration_documents.py` | 0 | n/a — **empty bucket** |
| 4 | `immigration_gdpr.py` *(new — proposed)* | 2 | ~29 |
| 5 | `immigration_service.py` (helpers) | n/a | ~339 (14 helpers) |
| **Total** | | **20** | ~1,578 (matches file LOC minus imports/Pydantic models) |

> **Note on "documents" bucket** (in task brief): `immigration.py` has zero document-review-queue endpoints — those live in `prescreening.py` and `hr_coordination.py`. Recommend dropping `immigration_documents.py` from the split.

> **New bucket: GDPR** — The task brief listed 3 target files (intake/status/documents) but reality has a 4th category: GDPR subject-rights endpoints (`/my-data/export`, `/my-data/erasure-request`). Both are stubs (IMM-17, IMM-18). Proposed file: `immigration_gdpr.py`. Alternative: park them in `immigration_status.py` until they're filled out.

---

## 2. Imports & shared dependencies

### 2a. Internal modules

| Import | Path | Used for |
|---|---|---|
| `get_current_user`, `get_org_id_for_hr_user`, `require_admin_or_hr` | `..auth_deps` | Auth dependencies — distinguishes HR vs employee |
| `db` | `...database` | Legacy raw-SQL helper (`db.engine.connect()`) |
| `immigration_interview_engine` | `..services.immigration_interview_engine` | 10 symbols: `AddressGap`, `QuestionNode`, `compute_completion_pct`, `compute_section_progress`, `detect_address_gaps`, `get_next_question`, `get_section_summary`, `get_vault_updates`, `load_questions`, …  |

### 2b. Stdlib / external

`hashlib`, `logging`, `uuid`, `datetime.{date, datetime, timezone}`, `typing`, `fastapi.{APIRouter, Depends, File, HTTPException, UploadFile, status}`, `pydantic.BaseModel`, `sqlalchemy.text`.

### 2c. DB pattern — **single-DB ✅**

Unlike `cases.py` (which uses both `SessionLocal` ORM and `main_db` raw SQL), `immigration.py` uses **only** the raw-SQL helper `db.engine.connect()` with `sqlalchemy.text`. Migration of helpers into `immigration_service.py` should be mechanical.

### 2d. Module docstring is stale

The file-top docstring (lines 1–27) does **not** list these endpoints that exist in the file:
- `POST /employee/cases/{case_id}/consent` (line 530)
- `GET  /hr/cases/{case_id}/immigration/interview-status` (line 871)
- `POST /hr/immigration/cases` (line 1335)
- `GET  /hr/immigration/cases/{immigration_case_id}` (line 1408)
- `GET  /employee/cases/{case_id}/immigration` (line 1431)

These were added after the docstring was written. Worth refreshing the docstring (or removing it entirely) as part of the split.

---

## 3. `immigration_intake.py` — 10 handlers (~845 LOC)

Consent recording, profile read/write, OCR passport extraction, interview Q&A driver.

| # | Lines | Est. LOC | Method | Path | Handler | Persona |
|---|---|---|---|---|---|---|
| 1 | 239–333 | 95 | GET | `/hr/cases/{case_id}/immigration-requirements` | `get_immigration_requirements` | HR |
| 2 | 334–402 | 69 | POST | `/hr/cases/{case_id}/immigration-consent` | `record_consent` | HR |
| 3 | 403–443 | 41 | GET | `/hr/cases/{case_id}/profile` | `get_profile_hr` | HR |
| 4 | 444–529 | 86 | PATCH | `/hr/cases/{case_id}/profile/hr-fields` | `update_profile_hr_fields` | HR |
| 5 | 530–604 | 75 | POST | `/employee/cases/{case_id}/consent` | `record_consent_employee` | Employee |
| 6 | 605–654 | 50 | GET | `/employee/cases/{case_id}/profile` | `get_profile_employee` | Employee |
| 7 | 655–767 | 113 | PUT | `/employee/cases/{case_id}/profile` | `upsert_profile_employee` | Employee |
| 8 | 918–1051 | 134 | POST | `/employee/cases/{case_id}/profile/ocr-passport` | `ocr_passport` **(async)** | Employee |
| 9 | 1052–1097 | 46 | GET | `/employee/cases/{case_id}/interview/next` | `interview_next` | Employee |
| 10 | 1098–1233 | 136 | POST | `/employee/cases/{case_id}/interview/answer` | `interview_answer` | Employee |

> ⚠️ `ocr_passport` is the only `async def` in the file — uses `UploadFile`. Pattern-watch when extracting.

---

## 4. `immigration_status.py` — 8 handlers (~365 LOC)

Milestones, interview status reads, immigration-case CRUD shells.

| # | Lines | Est. LOC | Method | Path | Handler | Persona |
|---|---|---|---|---|---|---|
| 11 | 768–796 | 29 | GET | `/hr/cases/{case_id}/immigration/milestones` | `list_milestones` | HR |
| 12 | 797–829 | 33 | POST | `/hr/cases/{case_id}/immigration/milestones` | `create_milestone` | HR |
| 13 | 830–870 | 41 | PATCH | `/hr/cases/{case_id}/immigration/milestones/{milestone_id}` | `update_milestone` | HR |
| 14 | 871–917 | 47 | GET | `/hr/cases/{case_id}/immigration/interview-status` | `get_interview_status_hr` | HR |
| 15 | 1234–1290 | 57 | GET | `/employee/cases/{case_id}/interview/status` | `interview_status` | Employee |
| 16 | 1335–1407 | 73 | POST | `/hr/immigration/cases` | `create_immigration_case` | HR |
| 17 | 1408–1430 | 23 | GET | `/hr/immigration/cases/{immigration_case_id}` | `get_immigration_case_hr` | HR |
| 18 | 1431–1492 | 62 | GET | `/employee/cases/{case_id}/immigration` | `get_immigration_case_employee` | Employee |

> The four `/hr/immigration/cases*` and `/employee/cases/.../immigration` handlers (rows 16-18) were added by MVG-6 — they're the immigration-case shell CRUD. Cohesive enough to live with the milestones/status family.

---

## 5. `immigration_documents.py` — 0 handlers

**Empty bucket.** `immigration.py` exposes no document-review-queue endpoints. Document handling lives in:
- `backend/app/routers/prescreening.py` (document upload + pre-screening AI)
- `backend/app/routers/hr_coordination.py` (HR document review workflows)

**Recommendation:** Drop `immigration_documents.py` from the split. Do not create an empty router file.

---

## 6. `immigration_gdpr.py` *(proposed)* — 2 handlers (~29 LOC)

Both are stubs (mentioned IMM-17 and IMM-18 in the source docstring) — currently return placeholder responses.

| # | Lines | Est. LOC | Method | Path | Handler | Notes |
|---|---|---|---|---|---|---|
| 19 | 1291–1295 | 5 | GET | `/employee/cases/{case_id}/my-data/export` | `data_export_stub` | GDPR Art. 15 — stub |
| 20 | 1296–1319 | 24 | POST | `/employee/cases/{case_id}/my-data/erasure-request` | `erasure_request_stub` | GDPR Art. 17 — stub, creates an erasure-request record |

> **Alternative**: park these in `immigration_status.py` until they're meaningfully implemented (IMM-17 / IMM-18). Only ~29 LOC combined — a standalone file feels premature.

---

## 7. `immigration_service.py` — 14 helpers (~339 LOC)

Target file: `backend/app/services/immigration_service.py` (canonical tree per `backend/CLAUDE.md`).

### 7a. Tenant / access primitives

| # | Lines | Est. LOC | Function | Notes |
|---|---|---|---|---|
| H1 | 159–177 | 19 | `_check_consent(case_id, employee_id)` | Consent gate used before any PII read |
| H2 | 178–212 | 35 | `_log_access(...)` | Append-only audit log writer (`data_access_log` table) |
| H3 | 213–238 | 26 | `_get_case_details(case_id, org_id)` | Resolves case + asserts org match |

### 7b. Pure utility

| # | Lines | Est. LOC | Function | Notes |
|---|---|---|---|---|
| H4 | 155–158 | 4 | `_now_iso()` | ISO timestamp helper |
| H5 | 1536–1548 | 13 | `_ts(v)` | DB timestamp normalizer |
| H6 | 1724–1732 | 9 | `_get_encryption_key()` | pgcrypto key resolver (reads env var) |

### 7c. Profile loaders

| # | Lines | Est. LOC | Function | Notes |
|---|---|---|---|---|
| H7 | 1493–1514 | 22 | `_load_profile_for_case(case_id)` | HR-facing profile fetch |
| H8 | 1515–1535 | 21 | `_load_profile_for_case_employee(case_id, employee_id)` | Employee-facing profile fetch (ownership guard) |

### 7d. Interview session lifecycle

| # | Lines | Est. LOC | Function | Notes |
|---|---|---|---|---|
| H9 | 1549–1566 | 18 | `_load_session(case_id, employee_id)` | Read-only session loader |
| H10 | 1567–1585 | 19 | `_load_session_for_update(case_id, employee_id)` | Row-locked variant for safe upsert |
| H11 | 1586–1616 | 31 | `_load_or_create_session(case_id, employee_id, org_id)` | First-touch handler |
| H12 | 1617–1660 | 44 | `_save_session(...)` | Session writer (interview state persistence) |
| H13 | 1661–1723 | 63 | `_apply_vault_updates(...)` | Encrypted vault writer — calls pgcrypto |

### 7e. Serialization

| # | Lines | Est. LOC | Function | Notes |
|---|---|---|---|---|
| H14 | 1320–1334 | 15 | `_serialize_imm_case(row)` | Immigration-case row → API DTO |

> All 14 helpers are pure-Python (no `Request` or response objects). Mechanical extraction.

---

## 8. Line-count projections after split

| Target file | Handlers | Helpers | Imports/Pydantic | LOC estimate | Under 1,000-line target? |
|---|---|---|---|---|---|
| `immigration_intake.py` | 10 (845) | 0 | ~80 | **~925** | ✅ Just under |
| `immigration_status.py` | 8 (365) | 0 | ~70 | **~435** | ✅ |
| `immigration_gdpr.py` *(proposed)* | 2 (29) | 0 | ~40 | **~70** | ✅ — but tiny, see §6 alt |
| `immigration_service.py` | 0 | 14 (339) | ~50 | **~390** | ✅ |

**Headline:** A 3-way handler split (intake / status / gdpr) plus the service-layer extraction lands every file comfortably under 1,000 LOC. `immigration_intake.py` is the largest at ~925 — close to the ceiling but inside it. If the file grows further before this split lands, consider sub-splitting intake into `immigration_intake_consent.py` (handlers 1, 2, 5) + `immigration_intake_profile.py` (3, 4, 6, 7, 8) + `immigration_intake_interview.py` (9, 10).

---

## 9. Migration steps (recommended order)

1. **Extract `immigration_service.py` first** (14 helpers, mechanical). All routers downstream will import from it.
2. **Move intake handlers** to `immigration_intake.py`. Update imports.
3. **Move status handlers** to `immigration_status.py`. Update imports.
4. **Decide GDPR fate**: standalone file vs park in status. If standalone, create `immigration_gdpr.py`.
5. **Wire the new routers into `backend/app/main.py`** (preserving `prefix="/api"` and `tags=["immigration"]`). Delete the legacy `immigration.py` aggregator or keep it as a thin re-exporter for one PR cycle.
6. **Refresh the file-top docstring** — current one (lines 1–27) is stale (§2d).

> Suggested ordering of follow-up Notion subtasks: `AUDIT-B9-imm-2` (extract service) → `AUDIT-B9-imm-3` (intake) → `AUDIT-B9-imm-4` (status) → `AUDIT-B9-imm-5` (gdpr decision + wire-in).

---

## 10. Validation

| Criterion | Evidence |
|---|---|
| File exists at `backend/docs/immigration-split-plan.md` | This file. |
| Every handler is assigned to exactly one target file | 20 / 20 — intake (10) + status (8) + gdpr (2) + documents (0). Sum matches. |
| Row count in the handler tables matches `grep -c '^@router\.' backend/app/routers/immigration.py` | grep → **20**; tables in §3 + §4 + §6 → 10 + 8 + 2 = 20. Match. |
| All `def _helpers` listed | `grep -c '^def _' backend/app/routers/immigration.py` → **14**; §7 enumerates H1–H14. Match. |
| Shared deps (auth, db helpers) documented | §2a–§2c. |
| LOC projections per output file present | §8. |
