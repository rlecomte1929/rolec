# When the pipeline uses row-based (summary table) parsing

## Default path

`segment_document_from_raw_text` (upload + reprocess) first calls `try_build_clauses_via_summary_rows`. If it returns **clause dicts**, those replace legacy `segment_into_clauses` for that document. If it returns **`None`**, behavior is unchanged: line/buffer/table-per-row segmentation as before.

## Activation gates

Row-based parsing runs only when **all** of the following hold:

1. **Document typing** — `detected_document_type` is one of:
   - `policy_summary` (`DOC_TYPE_POLICY_SUMMARY`)
   - `summary_table` (`DOC_TYPE_SUMMARY_TABLE`)
   - `compact_benefit_matrix` (`DOC_TYPE_COMPACT_BENEFIT_MATRIX`)  
   **Or** `extracted_metadata.subformat` is `summary_table` / `compact_benefit_matrix`.

2. **Overrides** (optional, for QA / fixtures):
   - `extracted_metadata.force_summary_row_parser == true`
   - `extracted_metadata.parser_profile == "summary_rows"`

3. **Table signal** — at least **two** pipe/table-like lines **or** (`likely_table_heavy` from `extract_metadata` and at least **one** table-like line). This avoids switching on narrative-only `policy_summary` PDFs.

## When to keep legacy segmentation

- `assignment_policy`, `tax_policy`, `unknown`, etc. → **legacy** (unless metadata override above).
- Gated type but **no** table-like lines → parser yields **no rows** → **`None`** → **legacy**.
- Long-form policies with few accidental `|` characters: usually below the table threshold; if not, tighten gates or set `force_summary_row_parser` off.

## Output shape

Each **logical row** becomes **one** `policy_document_clauses` row:

- `raw_text` = **summary description** (component column excluded; section reference stripped from text).
- `normalized_hint_json.summary_row_candidate` = provenance: `row_id`, `section_reference`, `component_label`, `section_context`, `parser_strategy`, `page_number`, `raw_cells`.
- **Headings** (“Family Support”, numbered titles) update `section_context` only; they **do not** create clauses unless row grouping fails (then the whole document falls back to legacy).

## Classifier follow-up

To route more files into this path without metadata hacks, teach `classify_document` to emit `summary_table` / `compact_benefit_matrix` when appropriate, or set `extracted_metadata.subformat` from filename/title heuristics.
