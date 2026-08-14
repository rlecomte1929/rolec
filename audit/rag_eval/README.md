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

_Last verified 2026-08-12 (AIQ-1821)._

**The dashboard is already `source: "live"`** — the paragraph that used to sit here
("no real report has been committed yet… still shows the honest mock banner") was
stale. Four reports are on disk and three metric families are plotted:

| Metric family | Latest | Threshold | State |
|---|---|---|---|
| `context_precision` | 0.348 (`_baseline_20260615_v2`) | 0.85 | 🔴 below threshold |
| `hr_policy_context_precision` | 0.6 (`20260630`) | 0.50 | 🟢 passing |
| `outcome_accuracy` | 1.0 (`20260630`) | 0.90 | 🟢 passing |

Two behaviours are worth knowing before you read the dashboard:

- **`source` is global, not per-metric.** One valid report anywhere in this
  directory flips the *whole* dashboard to `live`; every metric without a report
  then renders as an empty series with alert reason `no_data` — not as mock.
- **`factual_consistency` has no data and cannot honestly get any yet.** Its
  evaluator needs both a `--generated-steps` sidecar (absent) and an indexed
  immigration corpus — prod `immigration_documents` is empty and
  `immigration_chunks` does not exist. Running it now would emit a vacuous
  zero-entry report. Don't.

Both `context_precision_baseline_20260615*.json` also resolve to the *same* date,
so that metric plots two points on 2026-06-15.

### Non-dashboard reports

`requirement_extraction_20260812.json` is a real run of
`backend/scripts/eval_requirement_extraction.py` (P4-04) committed as a record. It
is **deliberately inert here**: it has no top-level `aggregate` and no matching
`MetricSpec` prefix, so `load_live_reports` skips it. It does not appear on
`/admin/rag-quality` and does not affect any other metric.

That run measured precision **0.125** / recall **0.143** across 5 evaluated golden
entries (1 skipped) — and surfaced that the gate can report a false green: a URL
from which the extractor extracts *zero* facts scores `precision = 1.0` via the
empty-denominator branch, and `--ci` gates on precision only. The FR-NO entry
"passes" at 1.0/1.0 while the extractor never reads the page body. See AIQ-1821.
