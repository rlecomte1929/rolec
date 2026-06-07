# RAG-quality evaluation reports (`audit/rag_eval/`)

This directory holds the **committed JSON eval reports** that power the admin
RAG-quality dashboard at `/admin/rag-quality`
(`GET /api/admin/rag-eval/metrics` → `backend/app/services/rag_eval_reports.py`).

**The dashboard reads this directory directly.** The moment one real report per
metric lands here, the same endpoint serves `source: "live"` instead of the
deterministic, clearly-labelled `source: "mock"` series — **no code change**.
Until then the dashboard renders the mock series under a "Showing mock data"
banner (honest by design).

> Do **not** hand-write or commit fabricated numbers here. A file in this
> directory is presented to admins as a real measurement. Only commit JSON that
> a real evaluator run produced (see below).

---

## How a report is consumed

`rag_eval_reports.load_live_reports()` globs `*.json` here and groups files by
**filename prefix** (the canonical metric family the dashboard plots):

| Metric family (filename prefix) | Threshold | Evaluator | Status |
|---|---|---|---|
| `context_precision_*.json`   | ≥ 0.85 | `backend/scripts/eval_rag_context_precision.py` | ✅ wired to `immigration_retriever` |
| `factual_consistency_*.json` | ≥ 0.95 | `backend/scripts/eval_factual_consistency.py`   | ✅ wired to the P1-01c verifier (`factual_verifier.verify_step`) |
| `outcome_accuracy_*.json`    | ≥ 0.90 | _not implemented yet_ | ⏳ needs P1-07 case-outcomes table |

Each report file must:
- be named `<metric_prefix>_<date>.json`, where `<date>` is `YYYYMMDD` or
  `YYYY-MM-DD` (e.g. `context_precision_20260607.json`) — the dashboard derives
  the time-series point's date from the report's `generated_at` field if present,
  otherwise from this filename date;
- contain a top-level numeric `aggregate` field (the harness'
  `aggregate_report()` already emits this, plus `by_corridor` / `by_intent` /
  `lowest_queries` breakdowns).

Malformed or undated `*.json` files are skipped with a warning rather than
breaking the dashboard. Non-JSON files (like this README) are ignored.

---

## Generate + commit a real report (the runnable step)

### Prerequisites
- **`DATABASE_URL`** pointing at an environment whose corpus is **indexed**
  (e.g. the FR→NO corridor; see `.github/workflows/immigration-indexer.yml`).
  The local default SQLite DB has no corpus index, so the evaluators must run
  against the Supabase-backed DB.
- **`OPENAI_API_KEY`** — the retriever embeds each golden query; the
  factual-consistency verifier also calls the model.
- The golden query set already exists:
  `backend/tests/fixtures/rag_eval/queries.jsonl` (50 FR→NO queries with
  `expected_chunk_ids`).

### Context precision
```bash
python backend/scripts/eval_rag_context_precision.py \
  --queries backend/tests/fixtures/rag_eval/queries.jsonl \
  --out audit/rag_eval/context_precision_$(date +%Y%m%d).json \
  --k 5
```

### Factual consistency
```bash
python backend/scripts/eval_factual_consistency.py \
  --queries backend/tests/fixtures/rag_eval/queries.jsonl \
  --out audit/rag_eval/factual_consistency_$(date +%Y%m%d).json
```

Each evaluator exits non-zero if its aggregate falls below the threshold above,
so the same command is usable as a CI gate.

### Commit + go live
```bash
git add audit/rag_eval/context_precision_*.json
git commit -m "chore(rag-eval): commit <date> context-precision report"
```
On the next deploy the dashboard reads the committed report and flips that
metric to `source: "live"` automatically.

---

## Current status

No real report has been committed yet, because the evaluators must run against an
environment with the corpus index built and an `OPENAI_API_KEY` available — which
is why `/admin/rag-quality` still shows the honest mock banner. Everything else is
in place: the golden set, the two wired evaluators, the report→dashboard wiring,
and this runbook. `outcome_accuracy` additionally needs its evaluator built once
the P1-07 case-outcomes table ships.
