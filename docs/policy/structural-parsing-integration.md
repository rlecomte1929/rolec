# Structural parsing integration (tables, rows, provenance)

This note evaluates **optional** external libraries (e.g. **Docling**, **Unstructured**) for **document → structured elements** only. ReloPass **domain mapping, canonical LTA keys, normalization, and grouping stay proprietary and deterministic** in existing services (`policy_row_to_template_mapper`, `policy_normalization`, `policy_grouped_policy_model`, etc.).

## Current state

- **PDF**: `pdfplumber` — page text lines + `extract_tables()` per page; table rows joined as `" | "` and marked `is_table_row=True` in `policy_document_clauses.extract_lines_with_pages`.
- **DOCX**: `python-docx` — paragraphs + table rows (same pipe convention); page is stubbed as `1`.
- **Downstream**: `segment_document_from_raw_text` → `try_build_clauses_via_summary_rows` / `segment_into_clauses` consumes `List[{"text", "page", "is_table_row"}]`.

Known limits (see `policy-pipeline-inflation-diagnostic-note.md`): table vs body ordering, weak geometric table detection on some PDFs, section numbers leaking into numeric hints when segmentation is noisy.

## Where an external parser would sit

```
[bytes + mime_type]
       │
       ▼
┌──────────────────────────────────────┐
│  policy_structural_parse             │  ← **only** structural extraction
│  parse_policy_document_to_elements() │
└──────────────────────────────────────┘
       │
       │  List[PolicyStructuralElement-like dicts]
       ▼
┌──────────────────────────────────────┐
│  policy_document_clauses             │  segmentation (unchanged semantics)
│  policy_summary_row_parser           │  row candidates (unchanged)
└──────────────────────────────────────┘
       ▼
  existing mapper / normalization / HR review
```

**Do not** pass external parser output directly into benefit mapping. Always normalize to the **ReloPass element contract** first.

## Input / output contract

**Input**

- `data: bytes` — file payload.
- `mime_type: str` — same MIME conventions as today (`application/pdf`, DOCX, etc.).
- `backend: StructuralParseBackend` — `native` | `docling` | `unstructured` (extensible).
- `fallback_on_error: bool` — if an optional backend fails or is unavailable, retry with `native`.

**Output**

- `elements: List[Dict[str, Any]]` — each item **must** include at minimum:
  - `text: str` — line or row text (table rows: pipe-separated cells as today).
  - `page: int` — 1-based page index (best effort for DOCX).
  - `is_table_row: bool` — whether the row should be treated as table-shaped for summary-row gating.

**Optional** (forward-compatible; downstream must ignore unknown keys):

- `element_kind`: `"paragraph"` | `"table_row"` | `"heading"` | `"list_item"`.
- `structural_source`: `"native"` | `"docling"` | `"unstructured"`.
- `table_id`, `row_index`, `col_count` — for deduplication and debugging.
- `bbox` — normalized box if the backend provides layout (for future UI highlights only).

## Fallback path

1. **Default**: `StructuralParseBackend.NATIVE` — current `extract_lines_with_pages` behavior.
2. **Optional backend**: If import fails, timeout, or parser returns empty with error → when `fallback_on_error=True`, log and call native.
3. **Configuration**: `RELOPASS_STRUCTURAL_PARSE_BACKEND` env var (`native` | `docling` | `unstructured`); invalid values map to `native`.

No change to mapping behavior when falling back — only element ordering / table fidelity may differ.

## Risks of Docling / Unstructured

| Risk | Mitigation |
|------|------------|
| **Dependency weight** (Torch, CUDA, large wheels) | Run as optional **worker** or feature-flagged extra; keep API container on `native` only. |
| **Non-determinism** | Pin versions; snapshot tests on fixture PDFs; compare element hashes in CI. |
| **Latency / memory** | Async job for ingest; cap page count / file size. |
| **License / compliance** | Review each library’s license and model weights terms for customer deployments. |
| **Different table topology** | Adapter must map to ReloPass `text` + `is_table_row`; add integration tests on real LTA summaries. |
| **Security** | Sandbox parsing of untrusted uploads; same as today for file handling. |

## Recommendation

- **Short term**: Keep **native** (`pdfplumber` + `python-docx`) as default; invest in **targeted native improvements** (table/body ordering, stricter `is_table_row`, section-ref scrubbing) where regressions appear — lowest operational risk.
- **Adopt Docling or Unstructured** when you have **repeatable PDFs** where `pdfplumber.extract_tables()` systematically misses or splits rows, and the team can absorb **extra deploy surface** (image, deps, or sidecar service).
- **Prefer Unstructured** if you want **partitioning + structure** without full document AI pipelines; **Docling** if you need **richer layout + reading order** and can justify the stack.

The `policy_structural_parse` module provides the **seam** to add an adapter later without touching the domain mapper.
