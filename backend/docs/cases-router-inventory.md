# `cases.py` Router Inventory — `backend/app/routers/cases.py`

> **Audit task**: AUDIT-B9-cases-1 (AIQ-449)
> **Parent**: AUDIT-B9-followup · Decompose `cases.py` into services
> **Date**: 2026-05-27
> **Source file**: `backend/app/routers/cases.py` (3,733 lines)
> **Router definition**: `router = APIRouter(prefix="/api/cases", tags=["cases"])` (line 36)
> **Snapshot caveat**: The parent task brief cited 3,328 LOC. The file has grown to **3,733 LOC** since that snapshot was taken — the decomposition target ("no file > 1,000 lines" after split) becomes more aggressive accordingly.

---

## 1. Summary

| Metric | Count |
|---|---|
| Total file LOC | **3,733** |
| `@router.*` route handlers | **35** |
| Private helpers / pure functions (no `@router`) | **24** |
| Imported services (already extracted) | **7** |
| Imported schemas / crud modules | **2** (`schemas`, `crud`) |
| DB layers in use | **2** — `SessionLocal` (SQLAlchemy sync) **and** `main_db` (legacy `database.db`) → dual-DB, flagged ⚠️ in `router-inventory.md` row 3 |

**Domain bucket totals (handlers only):**

| # | Domain bucket | Handlers |
|---|---|---|
| 1 | Employee reads | 1 |
| 2 | HR reads | 1 |
| 3 | Reads (shared: employee + HR) | 18 |
| 4 | HR mutations | 2 |
| 5 | Admin ops | 0 |
| 6 | Wizard / draft mutations | 13 |
| **Total** | **35** | |

> **Note on "Admin ops"** (domain 5 in the task spec): `cases.py` exposes no admin-prefixed routes — admin uses `/api/admin/*` instead. The bucket exists for completeness but is intentionally empty. Operations such as `delete_dossier` and `regenerate_dossier` are HR mutations, not admin ops, because they go through the same `_assert_case_access` HR/employee guard (not an `is_admin` check).

**Validation:** `grep -c '^@router\.' backend/app/routers/cases.py` → **35** (matches handler count).

---

## 2. Imports & shared dependencies

### 2a. Internal modules

| Import | Path | Used for |
|---|---|---|
| `SessionLocal` | `..db` | Sync SQLAlchemy session (used by wizard/draft handlers via `crud`) |
| `crud`, `schemas` | `..` | ORM `crud` helpers + Pydantic DTOs (`CaseDTO`, `CaseDraftDTO`, `CaseRequirementsDTO`) |
| `get_current_user` | `..auth_deps` | Auth dependency on every handler |
| `db as main_db` | `...database` | Legacy raw-SQL helper — used for `engine.connect()` and `list_linked_assignments_for_employee` |
| `invalidate_relocation_plan_cache` | `..services.relocation_plan_view_service` | Cache invalidation on mutations |
| `run_country_research` | `..services.research` | Async research pipeline trigger |
| `compute_case_requirements` | `..services.requirements_builder` | Build country requirements snapshot |
| `derive_roadmap` | `..services.roadmap_builder` | Multi-track roadmap derivation |
| `fire_roadmap_events` | `..services.trigger_engine` | P1-3 trigger engine — auto-create CaseForms |
| `run_prefill_for_dependents` | `..services.prefill_engine` | P2-1 pre-fill engine |
| `insert_audit_log`, `ACTION_*`, `ACTOR_*` | `..services.audit_log_service` | Audit log entries |

### 2b. Stdlib / external

`json`, `logging`, `re`, `uuid`, `datetime`, `io`, `zipfile`, `requests`, `fastapi.{APIRouter, HTTPException, Request, Depends, Response}`, `fastapi.responses.{StreamingResponse, JSONResponse}`, `pydantic.BaseModel`, `sqlalchemy.text`.

> 🚩 **Dual DB pattern** — both `SessionLocal` (ORM) and `main_db.engine.connect()` (raw SQL) are used in the same file. Several handlers use both within a single function body (e.g., `_assert_case_access` uses raw SQL via `main_db`, while `patch_case` uses `SessionLocal`). The `case_service.py` extraction (AUDIT-B9-cases-2) must preserve both call-sites unchanged — do not "harmonize" the DB layer in that step.

---

## 3. Domain 1 — Employee reads (1 handler)

| # | Lines | Method | Path | Handler | Notes |
|---|---|---|---|---|---|
| 1 | 137–174 | GET | `""` (= `/api/cases`) | `list_employee_cases` | Returns the authenticated employee's assigned cases. **HR/admin tokens get an empty list** — role-isolated to `employee` (line 148). Uses `main_db.list_linked_assignments_for_employee`. |

---

## 4. Domain 2 — HR reads (1 handler)

| # | Lines | Method | Path | Handler | Notes |
|---|---|---|---|---|---|
| 2 | 416–526 | GET | `/{case_id}/roadmap/tracks` | `get_case_roadmap_tracks` | Multi-track roadmap (GAP 2 / GAP 5). Used by HR Command Center; the `RoadmapTracksResponse` model is HR-specific. (Employees access the simpler `/roadmap` endpoint at line 345.) |

---

## 5. Domain 3 — Reads, shared employee + HR (18 handlers)

All gated by `_assert_case_access` (line 864) which permits an employee that owns the assignment **or** any HR/admin in the same company.

| # | Lines | Method | Path | Handler | Notes |
|---|---|---|---|---|---|
| 3 | 175–185 | GET | `/{case_id}` | `get_case` | Returns `CaseDTO` |
| 4 | 272–280 | GET | `/{case_id}/requirements` | `get_case_requirements` | Returns `CaseRequirementsDTO` (snapshot of country research) |
| 5 | 345–370 | GET | `/{case_id}/roadmap` | `get_case_roadmap` | Single-track legacy roadmap |
| 6 | 527–586 | GET | `/{case_id}/research/status` | `get_research_status` | Polled by frontend during async research |
| 7 | 986–1142 | GET | `/{case_id}/forms` | `list_case_forms` | Returns `List[CaseFormSummary]` |
| 8 | 1196–1264 | GET | `/{case_id}/forms/{form_id}/fields` | `get_form_fields` | Returns `List[FieldValueItem]` |
| 9 | 1805–1857 | GET | `/{case_id}/forms/{form_id}/comments` | `list_form_comments` | |
| 10 | 1944–1999 | GET | `/{case_id}/forms/{form_id}/events` | `list_form_events` | Form audit/event log |
| 11 | 2302–2363 | GET | `/{case_id}/forms/{form_id}/original` | `get_form_original` | StreamingResponse of original PDF |
| 12 | 2364–2520 | GET | `/{case_id}/forms/{form_id}/pdf` | `get_form_pdf` | StreamingResponse of filled PDF |
| 13 | 2864–2937 | GET | `/{case_id}/dossiers/{dossier_id}/zip` | `get_dossier_zip` | ZIP of dossier forms |
| 14 | 2983–3032 | GET | `/{case_id}/dossiers` | `list_dossiers` | List dossier packages for case |
| 15 | 3033–3080 | GET | `/{case_id}/dossiers/{dossier_id}` | `get_dossier` | Dossier detail |
| 16 | 3112–3203 | GET | `/{case_id}/dossiers/{dossier_id}/pdf` | `get_dossier_pdf` | StreamingResponse merged dossier PDF |
| 17 | 3319–3404 | GET | `/{case_id}/budget-summary` | `get_budget_summary` | Roll-up of budget allocations |
| 18 | 3590–3637 | GET | `/{case_id}/messages` | `list_case_messages` | Case message thread |
| 19 | 3638–3691 | GET | `/{case_id}/vendors` | `list_case_vendors` | Vendors linked to case |
| 20 | 3693–3733 | GET | `/{case_id}/budget-lines` | `list_case_budget_lines` | Per-line budget items |

---

## 6. Domain 4 — HR mutations (2 handlers)

Routes where the body of the handler enforces HR-only behavior (employee callers are rejected or the action is conceptually HR-only).

| # | Lines | Method | Path | Handler | Notes |
|---|---|---|---|---|---|
| 21 | 2000–2135 | PATCH | `/{case_id}/forms/{form_id}/flag` | `patch_form_flag` | HR flagging of forms for follow-up |
| 22 | 3081–3111 | DELETE | `/{case_id}/dossiers/{dossier_id}` | `delete_dossier` | Destructive — HR-only by convention (no explicit role gate beyond `_assert_case_access` company membership) |

> ⚠️ `delete_dossier` does **not** explicitly check role beyond the company-membership gate. An employee with case access would also satisfy it. Decomposition opportunity: add a hard HR-only role check during the `cases_write.py` extraction (AUDIT-B9-cases-4) — flag this for the reviewer.

---

## 7. Domain 5 — Admin ops (0 handlers)

**Empty by design.** `cases.py` does not expose any admin-prefixed endpoints. Admin operations on cases live in `backend/main.py` under `/api/admin/*` and in `backend/app/routers/admin.py`. The `cases_admin.py` file proposed by the parent task (AUDIT-B9-followup) is best-named `cases_write.py` or merged into HR mutations — there is no work to do for this bucket.

**Recommendation to parent task:** Re-scope AUDIT-B9-cases-5 (`cases_admin.py`) — either drop it as a separate target file or repurpose it to host high-privilege operations such as `delete_dossier` after adding a real HR-role gate.

---

## 8. Domain 6 — Wizard / draft mutations (13 handlers)

State-changing endpoints that drive the case creation wizard (PATCH endpoints that merge fragments into the `case.draft_json`) plus the form/dossier/message lifecycle.

| # | Lines | Method | Path | Handler | Wizard step / lifecycle |
|---|---|---|---|---|---|
| 23 | 186–227 | PATCH | `/{case_id}` | `patch_case` | Generic draft merge (wizard backbone) |
| 24 | 228–241 | PATCH | `/{case_id}/relocationBasics` | `patch_case_relocation_basics` | Wizard step 1 |
| 25 | 242–254 | PATCH | `/{case_id}/serviceSelections` | `patch_case_service_selections` | Wizard step 2 |
| 26 | 255–271 | POST | `/{case_id}/research/start` | `start_research` | Async kickoff of country research |
| 27 | 281–344 | POST | `/{case_id}/create` | `create_case` | Wizard final step — snapshots requirements, sets `status=CREATED`, fires analytics event |
| 28 | 587–677 | POST | `/{case_id}/household` | `update_household` | Household composition update |
| 29 | 1265–1432 | PUT | `/{case_id}/forms/{form_id}/fields` | `bulk_update_form_fields` | Bulk field-value upsert with provenance |
| 30 | 1433–1706 | PATCH | `/{case_id}/forms/{form_id}` | `patch_form_status` | Form status transitions (`ready`, `submitted`) — fires `trigger_engine` |
| 31 | 1858–1943 | POST | `/{case_id}/forms/{form_id}/comments` | `create_form_comment` | Add a comment to a form |
| 32 | 2705–2863 | POST | `/{case_id}/dossiers` | `create_dossier` | Create dossier package |
| 33 | 3204–3318 | POST | `/{case_id}/dossiers/{dossier_id}/regenerate` | `regenerate_dossier` | Re-build dossier PDFs (staleness-driven) |
| 34 | 3405–3516 | POST | `/{case_id}/quote-request` | `create_case_quote_request` | Trigger RFQ flow for case |
| 35 | 3524–3589 | POST | `/{case_id}/messages` | `post_case_message` | Add message to case thread |

---

## 9. Helpers / utilities (24 functions to extract into `case_service.py`)

These are the candidates for AUDIT-B9-cases-2 (extract `case_service.py`).
Target file: `backend/app/services/case_service.py` (canonical tree — see `backend/CLAUDE.md`).

### 9a. Tenant isolation & audit (highest-priority extraction)

| # | Lines | Function | Why it must move first |
|---|---|---|---|
| H1 | 864–985 | `_assert_case_access(user, case_id)` | **Used by virtually every handler in this file.** Moving it to `case_service.py` is the linchpin of the decomposition — cases_read/write/admin all need to import it. Inspect callers before any rename. |
| H2 | 71–125 | `_audit_case(entity_type, entity_id, action_type, ...)` | Audit-log helper invoked from all mutations. Pure function, safe to extract. |
| H3 | 126–136 | `_deep_merge_case_drafts(base, update)` | Deep dict merge for draft JSON. Pure. |

### 9b. DB dialect helpers

| # | Lines | Function | Notes |
|---|---|---|---|
| H4 | 45–52 | `_pg_table(name)` | Schema-prefix toggle (`public.X` on Postgres, bare on SQLite). |
| H5 | 53–61 | `_sql_now()` | `NOW()` vs `CURRENT_TIMESTAMP`. |
| H6 | 62–70 | `_sql_uuid_gen()` | `gen_random_uuid()` vs SQLite fallback. |
| H7 | 371–415 | `_pg_conn()` | psycopg-style connection helper. |

> These four belong together — extract as a single `_dialect.py` sub-module or keep grouped in `case_service.py`.

### 9c. DTO transformers

| # | Lines | Function | Notes |
|---|---|---|---|
| H8 | 678–757 | `_case_dto(case, draft)` | Build `schemas.CaseDTO` from ORM row + draft JSON. |
| H9 | 758–863 | `_row_to_summary(row)` | Build `CaseFormSummary` from raw row. |
| H10 | 1143–1176 | `_load_form_with_template(...)` | Loader for form + its template. |
| H11 | 1177–1195 | `_compute_completion(...)` | % completion calc for a form. |
| H12 | 1707–1804 | `_fetch_single_form_summary(case_id, form_id)` | Re-fetch + re-summarize a form after mutation. |

### 9d. PDF generation helpers

These are large (~600 LOC total) and could form their own `case_pdf_service.py`.

| # | Lines | Function | Notes |
|---|---|---|---|
| H13 | 2136–2187 | `_build_overlay_page(...)` | ReportLab overlay for form fields |
| H14 | 2188–2237 | `_generate_filled_pdf(...)` | Compose original + overlay |
| H15 | 2238–2257 | `_make_blank_pdf(title, message)` | Fallback PDF |
| H16 | 2258–2264 | `_safe_filename_part(s)` | Pure string sanitizer |
| H17 | 2265–2301 | `_try_store_draft_pdf(...)` | Storage best-effort |
| H18 | 2521–2576 | `_build_cover_page(...)` | Dossier cover PDF |
| H19 | 2577–2610 | `_build_divider_page(...)` | Dossier divider PDF |
| H20 | 2611–2654 | `_fetch_form_pdf_bytes(...)` | Fetch form PDF for merge |
| H21 | 2655–2671 | `_merge_pdfs(...)` | pypdf merge wrapper |
| H22 | 2672–2704 | `_try_store_dossier_pdf(...)` | Storage best-effort |

> ⚠️ `case_form_pdf.py` is already a separate router (`router-inventory.md` row 4). Some of these helpers may belong there rather than in `case_service.py`. Confirm during AUDIT-B9-cases-2.

### 9e. Misc

| # | Lines | Function | Notes |
|---|---|---|---|
| H23 | 2938–2982 | `_dossier_is_stale(conn, form_ids, generated_at)` | Staleness check for dossier regeneration. |
| H24 | 3517–3523 | `_detect_sender_role(user)` | Role detection for message-thread sender attribution. Tiny — could inline. |

---

## 10. Line-count projections after split

Estimates based on this inventory (each bucket = sum of handler line ranges; helpers move out).

| Target file | Sources | LOC estimate | Under 1,000-line target? |
|---|---|---|---|
| `cases_read.py` | Domain 3 (18 shared reads) + Domain 1 + Domain 2 | ~900–1,050 | **Borderline** — may need a sub-split (`cases_read_forms.py` for the 8 form/dossier GETs at lines 1196–3203, vs. `cases_read.py` for the rest) |
| `cases_write.py` | Domain 4 + Domain 6 (15 handlers) | ~1,400–1,600 | ❌ **Likely > 1,000** — the wizard mutations + `bulk_update_form_fields` (168 LOC alone) + `patch_form_status` (274 LOC) + `regenerate_dossier` (115 LOC) are large. Recommend splitting into `cases_write_wizard.py` (steps 1-2 + create), `cases_write_forms.py` (form mutations), and `cases_write_dossiers.py` (dossier mutations + quote request + messages). |
| `cases_admin.py` | (empty) | 0 | ✅ — **drop the file** or repurpose for hardened HR operations |
| `case_service.py` | Helpers 9a–9c + 9e (~14 helpers) | ~500–600 | ✅ |
| `case_pdf_service.py` (proposed) | Helpers 9d (10 PDF helpers) | ~500 | ✅ — recommended additional split to keep `case_service.py` lean |

**Headline projection:** A naïve 3-way split (read/write/admin) leaves `cases_write.py` over 1,400 LOC, which violates the parent task's "no file > 1,000 lines" success criterion. Recommend a **5-way split** (read × 1, write × 3 sub-domains, service × 2) as a follow-up note on AUDIT-B9-cases-4 (HR + employee mutation endpoints).

---

## 11. Cross-references

- **Parent task**: AUDIT-B9-followup · Decompose `cases.py` (3,328 LOC) into services
- **Pattern reference**: `backend/docs/router-inventory.md` (AUDIT-C2.1)
- **Service-tree rule**: `backend/CLAUDE.md` → all extracted services go to `backend/app/services/`, never `backend/services/`
- **Audit doc**: `audit/02-expert-fullstack.md` P1-3
- **Already migrated**: `cases.py` is **double-mounted** — both `backend/main.py` (legacy) and `backend/app/main.py` (canonical) include this router. The decomposition split must preserve both mounts until the parent `backend/main.py` decomposition lands.

---

## 12. Validation

| Criterion | Evidence |
|---|---|
| File exists at `backend/docs/cases-router-inventory.md` | This file. |
| All `def` functions in `cases.py` appear in the inventory | `grep -cE '^(@router\.\|def \|async def )' backend/app/routers/cases.py` → **94** = 35 router-decorator lines + 35 handler `def` lines + 24 helper `def` lines ✅ |
| Every `@router.*` handler appears in exactly one domain bucket | 35 / 35 — see sections 3–8. |
| Every private helper appears in section 9 | 24 / 24 — see section 9a–9e. |
| Line ranges sum approximately to file LOC | Handlers + helpers + inter-block gaps cover lines 36–3,733. |
