# Document extraction: which pipeline owns it?

**AIQ-1764 · Subtask 1 of AIQ-1760.** Blocks AIQ-1766 (CONTRACT agent), AIQ-1767 (PAYSLIP agent)
and AIQ-1768 (real classifier) — all three build *into* whichever pipeline wins.

> **Status: RECOMMENDATION, NOT A DECISION.** This document sets out the evidence and proposes an
> answer. The choice is the maintainer's; nothing here has been actioned.

Snapshot: 2026-08-04, against `origin/main` (`82c03aaa`) and prod `nsvefcvpvwwwhuqyuqmp`.

---

## 1. The question is mis-framed

The parent task describes "two parallel pipelines" and asks which to keep. The code does not
support that framing. They are **not** competing implementations at the same layer — they are two
stages that already depend on one another.

`backend/app/routers/immigration_documents.py` — a single upload endpoint — fires both:

```python
:28  from ..services.document_extraction_queue import run_extraction
:30  from ..services.rce_pipeline_worker import process_rce_document
...
:111 background_tasks.add_task(run_extraction, ...)              # ALWAYS
:122 if record.get("rce_document_id"):
:123     background_tasks.add_task(process_rce_document, ...)    # ONLY if bridged into rce.cases
```

And the rce path **imports its classifier from the MVP path**:

```python
backend/app/services/rce_ocr_parser.py:184
    from .document_extraction_queue import classify_document
```

So "deprecate `document_extraction_queue`" is not available as stated: doing so removes the
classifier the rce pipeline itself calls.

## 2. Consumer inventory

### A. `document_extraction_queue` (the MVP / OCR path)

| Consumer | Reference |
|---|---|
| Immigration upload endpoint | `backend/app/routers/immigration_documents.py:28`, called at `:111` — unconditional |
| **The rce pipeline itself** | `backend/app/services/rce_ocr_parser.py:184` imports `classify_document` |
| Contract note | `backend/app/services/rce_pipeline_worker.py:11` — rce explicitly mirrors this module's fail-soft contract |

### B. The rce engine

| Consumer | Reference |
|---|---|
| Immigration upload endpoint | `backend/app/routers/immigration_documents.py:30`, called at `:123` — **gated** on `record["rce_document_id"]` |
| Upload service (the bridge) | `backend/app/services/document_upload_service.py:22` → `bridge_case_document_to_rce` |
| Offline eval harness | `backend/scripts/run_extraction_predictions.py:50` → `dispatch_and_run` |

**Not a consumer:** `backend/app/services/policy_document_intake.py:525` defines its own
`classify_document(lines, request_id)`. Same name, different signature, policy documents — unrelated.
Easy to miscount as a third caller.

## 3. Evidence

**The rce branch has never fired in production.** `rce.documents` is empty (0 rows). The trigger at
`:122` requires `rce_document_id`, set only when an upload is bridged into `rce.cases`
(E-PIPE-1). No upload has been.

This cuts both ways, and the direction matters:

- *For deprecating rce:* nothing to migrate — zero rows, zero users affected.
- *Against:* rce is the path with the real agent architecture. It has 6 reachable extraction agents
  (`_agent_class`, `rce_extraction_orchestrator.py:53`), structured field persistence, entity
  resolution and contradiction detection. The MVP path has a **filename keyword** classifier whose
  own docstring calls itself a placeholder (`document_extraction_queue.py:44`).

Emptiness reflects an unfired *bridge*, not a failed design. Deprecating on that basis would
discard the better architecture because a feature flag never opened.

## 4. Recommendation — keep rce as the owner; demote the MVP path to ingest

**Own extraction in the rce engine.** It is where the agent registry, structured persistence and
downstream consumers (contradictions, entity resolution) already are, and where AIQ-1766/1767/1768
naturally land.

**Do not delete `document_extraction_queue`.** Narrow it to what it uniquely provides — OCR ingest
and *provisional* classification — and move `classify_document` to a neutral module so rce no
longer reaches into a path being wound down. AIQ-1768 replaces that function's body anyway; do that
work **once**, in its new home.

Concretely, in order:

1. Move `classify_document` out of `document_extraction_queue` into a shared classifier module
   (rce already imports it cross-path — the dependency exists, it is just pointed the wrong way).
2. Land AIQ-1768's real classifier there.
3. Build the CONTRACT (AIQ-1766) and PAYSLIP (AIQ-1767) agents as rce agents, registered in
   `EXTRACTION_AGENT_REGISTRY` — and covered by `test_extraction_agent_wiring.py` (AIQ-1765), so
   they cannot ship unreachable the way `DiplomaAgent` did.
4. **Separately**, decide whether the rce bridge should open for real uploads. That is a product
   call, not an architectural one, and it is the reason `rce.documents` is empty. Until it opens,
   agents 3 builds will not run on real documents — worth knowing before investing in them.

**How the empty-table evidence was weighted:** as a fact about the bridge, not about rce's fitness.
Had `rce.documents` held real data with a poor outcome, the recommendation would likely invert.

## 5. What this does not resolve

- **`TAX_CERT` remains unreachable** regardless of this decision. Three country-specific agents sit
  behind one document-type code and the selection point receives no country
  (`dispatch_and_run` gets only `ocr_result`, `document_type_code`, `sink`, `agent_storage`,
  `resolver`). Recorded in `UNREACHABLE_AGENTS` (AIQ-1765); needs its own selector design.
- **Whether to open the rce bridge** — step 4 above; deliberately out of scope here.

## Verification

Every reference re-grepped against `82c03aaa`. To re-check:

```bash
grep -rn "document_extraction_queue\|classify_document" backend | grep -v __pycache__
grep -rn "rce_extraction_orchestrator\|rce_pipeline_worker\|rce_document_ingest" backend | grep -v __pycache__
```

Prod emptiness: `SELECT count(*) FROM rce.documents;` → 0.
