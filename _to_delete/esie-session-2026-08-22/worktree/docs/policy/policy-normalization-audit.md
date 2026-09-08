# HR policy normalization & extraction — technical audit

**Scope:** Codebase as of this document (backend `main.py`, `services/policy_*`, `database.py`, Supabase migrations under `supabase/migrations/`).  
**Out of scope:** Changing runtime behavior (no code changes in this deliverable).

---

## 1. End-to-end pipeline: upload → publish

| Stage | Trigger | What happens | Primary code |
|-------|---------|--------------|--------------|
| **A. Upload (ingest)** | `POST /api/hr/policy-documents/upload` | Validate company, upload bytes to Supabase Storage (`hr-policies`), insert `policy_documents`, run text extraction + rule-based classify + metadata extraction, update row; if text OK, segment into `policy_document_clauses` | `main.py` ~7786–8060; `policy_document_intake.process_uploaded_document`; `policy_document_clauses.segment_document_from_raw_text` |
| **B. Reprocess** | `POST /api/hr/policy-documents/{doc_id}/reprocess` | Download file from storage, re-run extraction/classify/metadata, re-segment clauses | `main.py` ~8198–8264 |
| **C. Normalize** | `POST /api/hr/policy-documents/{doc_id}/normalize` | Requires `raw_text` and at least one clause. Builds canonical objects from clauses, inserts `policy_versions` + related rows under first `company_policies` for that company (or creates one). **Auto-publishes only when** readiness marks the draft `publishable` (Layer-2 bar matches publish gate); otherwise returns 200 with a draft and `publishable: false`. Publish gate failures after an attempted publish return 200 with `publish_blocked`. | `main.py` `normalize_policy_document`; `services/policy_normalization.run_normalization`; `policy_publish_gate`; `_hr_publish_policy_version` |
| **D. HR review / re-publish** | Review workspace UI + `PATCH`/`POST` company-policy version routes | HR can edit rules, change draft/review statuses, or call explicit publish on latest/specific version | `main.py` ~8388–8498 |
| **E. Employee resolution** | `GET /api/employee/me/assignment-package-policy`, `GET /api/employee/assignments/{id}/policy`, etc. | Picks assignment, resolves **published** `policy_versions` for company candidates, runs `resolve_policy_for_assignment` → persists `resolved_assignment_policies` + benefit/exclusion rows | `main.py` `_resolve_published_policy_for_employee`; `services/policy_resolution.py` |
| **F. Services vs policy** | `GET .../policy-service-comparison`, `policy-budget` | Reads **resolved** benefits (or triggers resolve), maps service categories → benefit keys, compares requested amounts vs caps | `services/policy_service_comparison.py` |

**Important:** Employees only consume rows where `policy_versions.status = 'published'`. Normalize may save a **draft** without publishing when Layer-2 is empty or strict readiness blocks auto-publish; HR uses the review workspace to add rules and publish explicitly when needed.

---

## 2. Data model (current)

### 2.1 `policy_documents` (intake)

Defined in `20260329000000_policy_documents.sql` (and echoed in catch-up migrations). Notable columns:

- `company_id`, `filename`, `mime_type`, `storage_path`, `checksum`
- `processing_status`: `uploaded` → `text_extracted` → `classified` / `review_required` → optional downstream `normalized` / `failed`
- `detected_document_type`, `detected_policy_scope` (CHECK-constrained enums)
- `version_label`, `effective_date` (duplicated from metadata for convenience)
- `raw_text`, `extraction_error`
- `extracted_metadata` **jsonb** — canonical schema from `extract_metadata()` / `normalize_extracted_metadata()`

### 2.2 `policy_document_clauses`

- Linked to `policy_document_id`
- Fields used downstream: `raw_text`, `clause_type`, `section_label`, `normalized_hint_json`, page/anchor fields, `confidence`
- Produced by `segment_document_from_raw_text` (PDF/DOCX with page-aware extraction)

### 2.3 `company_policies`

- Company-scoped policy “folder” (title, version string, effective_date, file_url, extraction/template fields)
- Normalization **reuses the first** `company_policies` row for the company or **creates** one using document metadata (`policy_normalization.run_normalization`)

### 2.4 `policy_versions`

- `policy_id` → `company_policies`
- `source_policy_document_id` → `policy_documents`
- `version_number`, `status` (must match DB CHECK; extended by `20260402000000_policy_version_status_extend.sql` to include `review_required`, `reviewed`, `published`, plus original `draft`, `auto_generated`, …)
- `auto_generated`, `review_status`, `confidence`, `created_by`, timestamps

Child tables (all keyed by `policy_version_id`):

- `policy_benefit_rules` — `benefit_key`, `benefit_category`, `calc_type`, amounts, `metadata_json`, etc.
- `policy_exclusions`, `policy_evidence_requirements`
- `policy_rule_conditions` — `object_type` + `object_id` + `condition_type` + `condition_value_json`
- `policy_assignment_type_applicability`, `policy_family_status_applicability`, `policy_tier_overrides`
- `policy_source_links` — traceability to `policy_document_clauses`

### 2.5 `resolved_assignment_policies` (+ benefits / exclusions)

- Per-`assignment_id` snapshot after resolution: `policy_id`, `policy_version_id`, `resolution_context_json`, `resolution_status`, `resolved_at`
- `resolved_assignment_policy_benefits` stores flattened fields used by UI and comparison: `benefit_key`, `included`, min/standard/max, currency, unit, frequency, `approval_required`, JSON for evidence/exclusions/source ids

---

## 3. What normalization expects (payload contract)

The HTTP body for normalize is **empty**; the server loads:

1. **`policy_documents` row** for `doc_id` (must exist; HR access checked).
2. **`raw_text`** must be non-empty (`main.py` returns 400 otherwise).
3. **`policy_document_clauses`** for that document — non-empty list (400 if missing).

Each **clause** row is used by `normalize_clauses_to_objects` as:

- `raw_text`, `clause_type`, `normalized_hint_json` (dict), `section_label`, `confidence`, `id`, optional page/anchor fields.

There is **no separate JSON payload** from the client for normalize. The effective “contract” is:

- Clause segmentation quality + `normalized_hint_json` keys (`candidate_benefit_key`, `candidate_*`, flags).
- Document-level `extracted_metadata` only for **company_policy** title/version/effective_date (not for rule logic).

`run_normalization` **does not** validate a schema beyond Python/runtime DB constraints; failures surface as DB exceptions or rare `ValueError` (e.g. missing `company_id` on document).

---

## 4. Where “invalid policy_versions payload” comes from

**User-facing message:** `main.py` maps some 500s to:

> Normalization failed because of an invalid policy_versions payload.

when the exception string contains **`DatatypeMismatch`**, **`auto_generated`**, or **`boolean`** (`main.py` ~8354–8355).

So the label is **heuristic**, not a dedicated validator. Typical underlying causes:

| Cause | Mechanism |
|-------|-----------|
| **Postgres type mismatch** | INSERT into `policy_versions` / `policy_benefit_rules` / … with a value Postgres rejects (e.g. boolean vs integer binding, or wrong type for a column). The substring `auto_generated` often appears in PG error text. |
| **CHECK / constraint** | e.g. `policy_versions.status` not in allowed set on a DB that has **not** applied `20260402000000_policy_version_status_extend.sql` while app sends `auto_generated` or `published`. |
| **Schema drift** | Missing columns, wrong types vs `database.py` SQL (other branches mention `template_*` / `UndefinedColumn`). |
| **FK / UUID issues** | Less common if ids are coerced to strings; still possible with malformed UUIDs. |

**Not** typically: a malformed JSON body from the HR UI (there is none).

---

## 5. Fields extracted today (ingest + clauses)

### 5.1 Document-level (`extracted_metadata` + columns)

From `policy_document_intake.extract_metadata()` / `classify_document()` / `process_uploaded_document()`:

- **Classification:** `detected_document_type`, `detected_policy_scope`, processing status (`classified` vs `review_required` when classifier is uncertain).
- **Metadata JSON:** `detected_title`, `detected_version`, `detected_effective_date`, `mentioned_assignment_types`, `mentioned_family_status_terms`, `mentioned_benefit_categories`, `mentioned_units`, booleans `likely_table_heavy`, `likely_country_addendum`, `likely_tax_specific`, `likely_contains_exclusions`, `likely_contains_approval_rules`, `likely_contains_evidence_rules`.
- **Top-level duplicates:** `version_label`, `effective_date` from detected version/date when found.

Rule-based only — no LLM in this path.

### 5.2 Clause-level (`normalized_hint_json`)

From `policy_document_clauses._extract_normalized_hints()` (non-authoritative hints):

- `candidate_benefit_key`, `candidate_currency`, `candidate_unit`, `candidate_numeric_values`, `candidate_frequency`
- `candidate_assignment_types`, `candidate_family_status_terms`
- Flags: `candidate_exclusion_flag`, `candidate_approval_flag`, `candidate_evidence_items`
- Plus `clause_type` from keyword segmentation (`benefit`, `exclusion`, `evidence_rule`, …)

---

## 6. Which extracted fields are used downstream?

| Source | Used where | How |
|--------|------------|-----|
| `extracted_metadata` title/version/date | `run_normalization` when **creating** `company_policies` | Title, version label, effective date for the policy row |
| `extracted_metadata` lists & “likely_*” | **HR UI / admin display** | Surfaced as “detected metadata”; **not** driving `resolve_policy_for_assignment` |
| Clause `raw_text` + `clause_type` + hints | `normalize_clauses_to_objects` | Drives `policy_benefit_rules`, exclusions, evidence, conditions, applicability, source links |
| Published `policy_benefit_rules` + children | `resolve_policy_for_assignment` | Filter by assignment/family applicability, evaluate conditions, apply exclusions, compute resolved benefits |
| `resolved_assignment_policy_benefits` | Employee policy UI, `policy_service_comparison`, policy-budget | Flat list keyed by `benefit_key` |

---

## 7. Metadata-only vs decision-usable

| Artifact | Role |
|----------|------|
| Document `extracted_metadata` “mentioned_*” / `likely_*` | **Discovery / UX** — shows what the doc talks about; **not** used as enforcement in resolution |
| Clause hints | **Heuristic inputs** to normalization; quality varies with text and segmentation |
| `policy_benefit_rules` (+ applicability + conditions + exclusions) | **Decision-usable** once published and resolved |
| `resolved_assignment_policy_*` | **Decision-usable snapshot** per assignment (what employees and comparison read) |

---

## 8. Gaps for employee-side cost / service comparison

### 8.1 Service ↔ policy mapping

`policy_service_comparison.SERVICE_TO_BENEFIT` maps only a **small** set of case service categories (e.g. `housing` → `temporary_housing`, `movers` → `shipment`). Many normalized `benefit_key` values from `BENEFIT_TAXONOMY` have **no** mapping → comparison returns **“No policy rule for {category}”** / `out_of_scope`.

### 8.2 Numeric sufficiency

- Normalization infers `calc_type` and `amount_value` from text/hints; many rules end up as **`other`** with **null** amounts.
- Comparison uses `max_value` or `standard_value` from **resolved** benefits; if both missing, cap checks are skipped and explanations degrade to generic “included” / approval strings.

### 8.3 Conditions bug (contract mismatch)

Normalization writes `policy_rule_conditions.condition_value_json` as:

- `assignment_type`: `{"types": [...]}`  
- `family_status`: `{"statuses": [...]}`  

But `_evaluate_condition` in `policy_resolution.py` reads **`assignment_types`** / **`family_statuses`** (or `values`). If those keys are absent it treats **allowed list as empty** and returns **True** (“no restriction”). So auto-generated conditions **do not narrow** rules today; **applicability tables** (`policy_assignment_type_applicability` / `policy_family_status_applicability`) are the real filters when populated.

### 8.4 “Which services may the employee consider?”

There is **no** explicit “allowed service catalog” table. “Allowed” is inferred indirectly:

- If a **benefit_key** appears in resolved benefits with `included: true` and passes comparison logic, the mapped service category can show as covered/capped.
- Categories without a rule or mapping appear out-of-scope.

### 8.5 Assignment selection for “me” policy

`get_assignment_for_employee` returns the **first** linked assignment (`ORDER BY created_at DESC`). Multi-assignment employees may not get the case you expect for policy/comparison.

### 8.6 Publish / resolve freshness

- Employees need **published** version + successful **resolve** into `resolved_assignment_policies`.
- Cached resolved row must match current published `policy_version_id` or resolution re-runs (see `_resolve_published_policy_for_employee`).

---

## 9. What is published today, and in what shape?

- **Canonical published store:** `policy_versions` with `status = 'published'` (plus archived history).
- **After normalize (current app):** New version is set to **published** immediately after insert (unless publish step fails with `publish_failed_after_normalize`).
- **API shape for HR normalized view:** `GET /api/company-policies/{policy_id}/normalized` returns policy row, **latest** version (may differ from published if HR moves draft — implementation uses `get_latest_policy_version`), benefit_rules, exclusions, evidence, conditions, applicability, source_links.
- **Employee-facing shape:** `GET /api/employee/me/assignment-package-policy` returns status (`found` | `no_policy_found` | `no_assignment` | `error`), plus when `found`: policy summary, **benefits** and **exclusions** lists from resolution (same conceptual shape as resolved benefit rows: keys, included, amounts, approval, evidence, condition summary).

---

## 10. Failure points (concise)

| Point | Symptom | Notes |
|-------|---------|--------|
| Storage / bucket / service role | Upload 5xx, structured error codes | Before DB insert |
| Text extraction (pdfplumber / python-docx) | `processing_status=failed`, `extraction_error` | No clauses → normalize 400 |
| Segmentation | 0 clauses | Normalize 400 |
| Normalize DB insert / publish | 500, often “invalid policy_versions payload” heuristic | See §4 |
| No published version | Employee `no_policy_found` | Or publish failed after normalize |
| No company on document | `ValueError` → 400 | Wrong upload scope |
| Comparison | Empty comparisons / “No published policy” | Resolved policy missing or mapping gap |

---

## 11. Recommendation — minimum normalized policy package (target shape)

For **machine-usable** downstream (employee UI + service comparison), aim for a **single logical document** (versioned) that always includes:

1. **`service_allowlist` or `benefit_catalog`**  
   Explicit list of service categories (aligned with `case_services` / wizard) the employee may plan for, each with `eligible: bool` and optional `reason`.

2. **`coverage_by_benefit`** (normalized keys stable across pipeline)  
   For each benefit: `included`, `calc_type`, `min` / `standard` / `max`, `currency`, `unit`, `frequency`, `approval_required`, `evidence_required[]`, `exclusion_reason` if any.

3. **`applicability`**  
   Assignment type, family profile, duration, tier — **same JSON keys** as the evaluator (fix `types` → `assignment_types` / `statuses` → `family_statuses` or teach evaluator to accept both).

4. **`comparison_readiness`**  
   Flags: `has_numeric_caps_for_mapped_services`, `unmapped_benefit_keys[]`, `unmapped_service_categories[]`, `resolution_warnings[]`.

5. **Provenance**  
   Keep `policy_source_links` (or equivalent) so HR can audit machine output vs PDF.

This package can be **materialized** as:

- Published `policy_versions` + normalized tables (current), **plus** a generated JSON blob on the version or a dedicated `policy_package_json` column; or
- Only resolved rows, if you guarantee resolve runs on every publish and stores enough structure for comparison (today resolved rows are close but mapping + caps remain the weak points).

---

## 12. File index (quick navigation)

| Area | Files |
|------|--------|
| Upload / reprocess / normalize routes | `backend/main.py` |
| Intake classify + metadata | `backend/services/policy_document_intake.py` |
| Clause segmentation + hints | `backend/services/policy_document_clauses.py` |
| Clause → canonical objects | `backend/services/policy_normalization.py` |
| Benefit taxonomy | `backend/services/policy_taxonomy.py` |
| Employee resolve | `backend/services/policy_resolution.py` |
| Service comparison | `backend/services/policy_service_comparison.py` |
| DB access | `backend/database.py` (policy_* / resolved_* methods) |
| DDL | `supabase/migrations/20260329000000_policy_documents.sql`, `20260331000000_policy_normalization.sql`, `20260402000000_policy_version_status_extend.sql`, catch-up migrations |

---

*End of audit.*
