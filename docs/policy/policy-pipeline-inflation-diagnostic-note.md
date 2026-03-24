# Policy pipeline inflation — diagnostic note (LTA policy summary)

This note summarizes **where row inflation and “section ref as value” symptoms are introduced** in the ReloPass policy pipeline for short summary documents (e.g. *Long Term Assignment Policy Summary*). It accompanies **read-only** tooling: `RELOPASS_POLICY_PIPELINE_DIAG`, `backend/services/policy_pipeline_diagnostics.py`, and `backend/scripts/diagnose_policy_normalize_document.py`.

## End-to-end path

| Stage | Module / artifact | Role |
|--------|-------------------|------|
| Ingest | `policy_document_intake.py` | PDF/DOCX → lines, metadata |
| Segmentation | `policy_document_clauses.py` → `policy_document_clauses` rows | Lines / table cells → **one DB clause per table row** and **one clause per numbered heading flush**; section headings flush a short clause |
| Layer-1 hints | `_extract_normalized_hints` in `policy_document_clauses.py` | Regex hints (`candidate_benefit_key`, `candidate_numeric_values`, …) |
| Clause → objects | `policy_normalization.normalize_clauses_to_objects` | **1 `draft_rule_candidate` per clause** when `wants_draft`; 0–1 benefit / exclusion / evidence per clause; **multiple `conditions` per clause** when a benefit row is emitted (one per assignment type + one per family hint + optional duration) |
| Draft blob | `policy_normalization_draft.build_normalization_draft_model` | `clause_candidates`, `rule_candidates`, persisted `normalization_draft_json` |
| HR review payload | `policy_hr_review_service.py` | Merges live `draft_rule_candidates` with stored Layer-2 when a version exists |
| Publish | `run_normalization` + publish gate | Relational `policy_benefit_rules`, exclusions, conditions, … |

## Where duplication / inflation is introduced

1. **Segmentation (primary multiplier)**  
   - Each **PDF/DOCX table row** becomes its **own clause** (`segment_into_clauses`, `is_table_row`).  
   - Each **numbered heading** line (`2.1 …`) flushes a buffer and often becomes its **own short clause**.  
   - **Section name** lines matching `SECTION_HEADINGS` flush **twice** (buffer + `flush_buffer(title=…)`), producing **very small clauses** that still may get drafts if hints or length thresholds fire.

2. **One draft per clause**  
   - `wants_draft` is true for almost any clause with hints, caps, assignment/family fragments, or `len(raw) >= 24`. So **draft count ≈ clause count** for typical summaries → **inflated draft list** vs. human “rows”.

3. **Conditions fan-out (publish layer)**  
   - For each published **benefit** clause, the mapper emits **one condition row per assignment type** and **one per family-status hint** (`normalize_clauses_to_objects`). A single semantic row with three assignment types becomes **three** `assignment_type` conditions.

4. **Section references treated as numeric hints**  
   - `_extract_normalized_hints` uses `NUMERIC_PATTERN` on the full clause text. Dotted section numbers (**2.1**, **6.5**) can yield **`candidate_numeric_values`**, which flow into `amount_fragments` / `has_structured_monetary_cap` heuristics and the draft UI as if they were amounts.

5. **Section refs in `section_label` / text drive `resolve_benefit_key`**  
   - `resolve_benefit_key` (`policy_taxonomy.py`) matches **keywords in `section_label` and raw text** in taxonomy iteration order. Headings like “Housing” or narrative that mentions multiple domains can map a **single fragment** to the **first matching** benefit (over-broad or wrong), and **separate clauses** for the same topic each get their **own** draft.

6. **Repeated mapping from adjacent fragments**  
   - There is **no merge** of clauses before mapping: neighboring lines (heading + table + bullet) each map independently → **duplicate clusters** (same `candidate_service_key` + similar excerpt) visible in the diagnostic **duplicate_draft_clusters** output.

## Which stage should become “row-based”

**Segmentation + mapping should treat one logical policy row (e.g. one table row or one heading + following paragraph) as a single unit** before emitting `draft_rule_candidates` and publish rows. Today the **atomic unit is the stored clause** (often a **fragment**). Normalization is **clause-at-a-time**, not **document-row-at-a-time**.

## How to run diagnostics

```bash
# Per-clause markdown table + duplicate clusters (DB-backed document id)
PYTHONPATH=. python3 backend/scripts/diagnose_policy_normalize_document.py <policy_documents.uuid>

# Full rows JSON
PYTHONPATH=. python3 backend/scripts/diagnose_policy_normalize_document.py <uuid> --json-rows /tmp/pipeline_rows.json
```

Optional runtime logs (per clause) when normalizing via API or tests:

```bash
export RELOPASS_POLICY_PIPELINE_DIAG=1
```

Look for log lines prefixed with `policy_pipeline_diag` from `backend.services.policy_normalization`.
