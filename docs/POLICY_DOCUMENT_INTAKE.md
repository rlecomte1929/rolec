# Policy Document Intake Pipeline

First layer for HR policy ingestion: accept uploaded PDF/DOCX, classify, extract metadata before benefit extraction.

## Extracted Metadata Schema

The `extracted_metadata` JSONB field uses this canonical schema (rule-based, deterministic):

| Field | Type | Description |
|-------|------|-------------|
| detected_title | string \| null | Policy title from document |
| detected_version | string \| null | Version label |
| detected_effective_date | string \| null | Effective date (YYYY-MM-DD) |
| mentioned_assignment_types | string[] | long_term, short_term, permanent, commuter, international, etc. |
| mentioned_family_status_terms | string[] | single, married, spouse, dependents, etc. |
| mentioned_benefit_categories | string[] | housing, movers, schools, tax, travel, etc. |
| mentioned_units | string[] | usd, eur, %, days, months, etc. |
| likely_table_heavy | boolean | Many tables detected |
| likely_country_addendum | boolean | Country-specific addendum signals |
| likely_tax_specific | boolean | Tax equalization, hypothetical tax, etc. |
| likely_contains_exclusions | boolean | Exclusion-related phrases |
| likely_contains_approval_rules | boolean | Approval, pre-approval, HR approval |
| likely_contains_evidence_rules | boolean | Receipts, documentation required |

Legacy fields (policy_title, version, contains_tables, etc.) are normalized to this schema on read.

## Schema: policy_documents

| Column | Type | Description |
|--------|------|-------------|
| id | uuid/text | Primary key |
| company_id | text | Company |
| uploaded_by_user_id | text | Uploader |
| filename | text | Original filename |
| mime_type | text | application/pdf or docx |
| storage_path | text | Supabase storage path |
| checksum | text | SHA-256 of file |
| uploaded_at | timestamptz | Upload time |
| processing_status | text | uploaded, text_extracted, classified, normalized, review_required, approved, failed |
| detected_document_type | text | assignment_policy, policy_summary, tax_policy, country_addendum, unknown |
| detected_policy_scope | text | global, long_term_assignment, short_term_assignment, tax_equalization, mixed, unknown |
| version_label | text | Extracted version |
| effective_date | date | Extracted effective date |
| raw_text | text | Extracted text |
| extraction_error | text | Error if failed |
| extracted_metadata | jsonb | Structured metadata |
| created_at, updated_at | timestamptz | Audit |

## Classifier Rules

| Document type | Signals |
|---------------|---------|
| tax_policy | "Tax Equalization", "Hypothetical Tax", "Hypothetical Social Security" |
| policy_summary | "Long Term Assignment Policy Summary", "LTA Policy Summary" |
| assignment_policy | "International Assignment Management" + 2+ of: mobility premium, home leave, moving services, household goods, relocation allowance, housing allowance |
| country_addendum | "addendum"/"annex"/"appendix" + country name + "country"/"local"/"host" |
| unknown | Fallback when no rules match |

## API Routes

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/hr/policy-documents/upload | Upload PDF/DOCX, extract text, classify, extract metadata |
| GET | /api/hr/policy-documents | List documents for company |
| GET | /api/hr/policy-documents/{id} | Get document detail |
| POST | /api/hr/policy-documents/{id}/reprocess | Re-run extraction and classification |

## Clause Segmentation

After text extraction, documents are segmented into `policy_document_clauses`:

| Column | Description |
|--------|-------------|
| section_label | Detected section (scope, moving services, etc.) |
| section_path | Hierarchy path (e.g. "1 > 2") |
| clause_type | scope, eligibility, benefit, exclusion, approval_rule, evidence_rule, tax_rule, definition, lifecycle_rule, unknown |
| raw_text | Original text (preserved for traceability) |
| normalized_hint_json | First-pass hints for normalization (all optional) |
| source_page_start / source_page_end | Page numbers |
| confidence | 0–1 classification confidence |

### normalized_hint_json fields (all optional, non-authoritative)

| Field | Description |
|-------|-------------|
| candidate_benefit_key | housing, household_goods, tuition, home_leave, mobility_premium, etc. |
| candidate_currency | USD, EUR, GBP, CHF, … |
| candidate_unit | %, days, weeks, months, years, weight |
| candidate_numeric_values | Extracted numbers |
| candidate_frequency | per_year, per_assignment, monthly, one_time |
| candidate_assignment_types | long_term, short_term, permanent, commuter |
| candidate_family_status_terms | single, married, spouse, dependents, … |
| candidate_exclusion_flag | true if exclusion signals |
| candidate_approval_flag | true if approval signals |
| candidate_evidence_items | receipt, invoice, documentation, … |

Segmentation uses: section headings, numbering (1.1, 2.3), table rows, bullets. Table rows are emitted as separate clause candidates. Reprocess re-runs segmentation.

### API

- `GET /api/hr/policy-documents/{id}/clauses?clause_type=benefit` – list clauses
- `PATCH /api/hr/policy-documents/{id}/clauses/{clause_id}` – HR override (clause_type, title, hr_override_notes)

## Verification Steps

1. **Upload**: HR → Policy tab → Upload PDF or DOCX → "Upload & classify"
2. **List**: Documents appear with status, type, scope, uploaded date
3. **Expand**: Click row → tabs "Metadata" | "Document structure"
4. **Document structure**: Clauses grouped by section, filter by type, re-tag
5. **Reprocess**: Re-runs extraction + segmentation
6. **Bad file**: Corrupt/invalid file → status=failed, extraction_error set, no crash
