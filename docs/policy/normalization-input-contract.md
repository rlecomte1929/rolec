# Normalization input contract

This document describes the **internal contract** between the policy document store and `run_normalization`, enforced by `validate_and_prepare_normalization_input` in `backend/services/normalization_input.py`.

---

## 1. Where the payload is built

| Piece | Source | Notes |
|-------|--------|--------|
| **Document** | `Database.get_policy_document(doc_id)` | `extracted_metadata` is normalized via `normalize_extracted_metadata` in the DB layer |
| **Clauses** | `Database.list_policy_document_clauses(doc_id)` | `normalized_hint_json` parsed from JSON string when stored as text |

**HTTP handler:** `POST /api/hr/policy-documents/{doc_id}/normalize` in `backend/main.py` loads both, then validates before calling `run_normalization`.

---

## 2. Expected shape

### 2.1 Document (`document`)

| Field | Type | Required for normalize | Notes |
|-------|------|------------------------|--------|
| `id` | string (uuid) | Yes | Must match `doc_id` in the URL when present |
| `company_id` | string | Yes | Non-empty after trim |
| `raw_text` | string | Yes | Non-empty after trim |
| `extracted_metadata` | object | No | Used for `company_policies` title/version/date |
| Other columns | — | No | Ignored by validation |

### 2.2 Clauses (`clauses[]`)

Each element must be an **object** with:

| Field | Type | Required | Notes |
|-------|------|----------|--------|
| `id` | string | Repaired if missing | Generated UUID for traceability in-memory |
| `policy_document_id` | string | If set, must match document | Blocks on mismatch |
| `clause_type` | string | Repaired if invalid | Must be one of DB allowed types; else coerced to `unknown` |
| `raw_text` | string | Repaired if null | Coerced to `""` |
| `normalized_hint_json` | object | Repaired | Parsed from JSON string if needed; invalid → `{}` |
| `confidence` | number | Repaired | Coerced to float in `[0,1]`; non-finite → `0.5` |
| `section_label`, `source_page_*`, `source_anchor` | optional | No | Passed through |

Allowed `clause_type` values align with `upsert_policy_document_clauses` in `database.py`.

---

## 3. Validation rules

### 3.1 Blocking (HTTP **422**, `error_code: NORMALIZATION_NOT_READY`, `outcome: normalization_not_ready`)

Processing **stops**; **no** `policy_versions` / benefit rows are written.

| Code | Path | Meaning |
|------|------|---------|
| `DOCUMENT_MISSING` | `document` | Null document (should not occur after 404 from access check) |
| `DOCUMENT_ID_EMPTY` | `document_id` | Empty path parameter |
| `DOCUMENT_ID_MISMATCH` | `document.id` | Loaded row id ≠ URL id |
| `DOCUMENT_MISSING_COMPANY_ID` | `document.company_id` | Missing company |
| `DOCUMENT_NO_RAW_TEXT` | `document.raw_text` | No text — user must Reprocess |
| `CLAUSES_NULL` | `clauses` | Not loaded |
| `CLAUSES_EMPTY` | `clauses` | No rows — user must Reprocess |
| `CLAUSE_NOT_OBJECT` | `clauses[i]` | Row is not a dict |
| `CLAUSE_WRONG_DOCUMENT` | `clauses[i].policy_document_id` | Clause attached to another document |

Response body includes `errors: [{ path, code, message, severity: "blocking" }]`.

### 3.2 Repairs (non-blocking, logged + optional `input_repairs` on success)

| Code | Path | Action |
|------|------|--------|
| `CLAUSE_ID_GENERATED` | `clauses[i].id` | Assign UUID |
| `CLAUSE_TYPE_DEFAULTED` / `CLAUSE_TYPE_UNKNOWN_FALLBACK` | `clauses[i].clause_type` | Set to `unknown` |
| `PARSED_HINT_JSON_STRING` / `INVALID_HINT_JSON` / `HINT_COERCED_TO_EMPTY` / `EMPTY_HINT_STRING` | `clauses[i].normalized_hint_json` | `{}` or parsed dict |
| `CONFIDENCE_*` | `clauses[i].confidence` | Numeric in range |
| `RAW_TEXT_DEFAULTED_EMPTY` / `RAW_TEXT_COERCED_TO_STRING` | `clauses[i].raw_text` | Safe string |

---

## 4. Post-structure safeguards (inside `run_normalization`)

After `normalize_clauses_to_objects`:

- **`calc_type`** on each benefit rule must be in the DB CHECK set; unknown values → **`other`** (`policy_normalization.ALLOWED_CALC_TYPES`).
- **`amount_value`**: non-numeric or NaN/inf → **`None`**.
- **`policy_rule_conditions.condition_value_json`** uses keys expected by `policy_resolution._evaluate_condition`:
  - `assignment_type` → `assignment_types` (not `types`)
  - `family_status` → `family_statuses` (not `statuses`)

---

## 5. Known invalid / fragile cases handled

| Case | Handling |
|------|----------|
| `normalized_hint_json` stored as string | Parsed; parse failure → `{}` |
| Missing clause `id` | UUID assigned (links still work for this run) |
| Invalid `clause_type` | `unknown` |
| Non-numeric `confidence` | `0.5` |
| `calc_type` not in DB enum | Coerced to `other` before insert |
| Bad `amount_value` | Cleared |
| Mismatch condition JSON keys vs resolver | Fixed at generation time (see §4) |
| DB rejects boolean/column (legacy driver/schema) | Still possible; **500** with actionable `message` + `hint`; document/clauses **not** deleted |

**Publish / extraction:** Failed validation does **not** update the document. Failed normalize after validation may leave **partial** normalized rows (multi-step inserts); that is unchanged from before—input validation reduces failures **before** any insert. Failed **publish** after a successful normalize is handled separately (`publish_failed_after_normalize`).

---

## 6. Error reporting (normalize endpoint)

| Outcome | HTTP | `error_code` |
|---------|------|----------------|
| Input invalid | 422 | `NORMALIZATION_NOT_READY` (legacy: `normalization_input_invalid`) |
| Business rule (`ValueError`) | 400 | (FastAPI default) |
| DB / logic error | 500 | `normalization_failed` or `publish_failed_after_normalize` |

500 responses include a **`hint`** reminding users that extraction is unchanged and to Reprocess/retry.

---

## 7. Related modules

- `backend/services/normalization_input.py` — validate + repair
- `backend/services/policy_normalization.py` — clause → rules + sanitizers
- `backend/main.py` — `normalize_policy_document`
- `backend/database.py` — `get_policy_document`, `list_policy_document_clauses`, inserts

---

*Contract version aligned with implementation in-repo; bump when required fields or codes change.*
