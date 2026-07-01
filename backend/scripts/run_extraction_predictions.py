"""AIQ-515 — produce an extraction predictions JSONL for run_extraction_eval.

Plumbing: iterate a per-document corpus (built by build_extraction_corpus) and
apply a `predictor(gt_record) -> [{name, value, bbox}]`, writing one JSONL line
per document keyed by `document_id` — the format `run_extraction_eval --predictions`
consumes.

Predictors:
- ``reference`` (default, offline, $0): returns the ground-truth fields. Validates
  the corpus → producer → JSONL → eval chain end-to-end (scores 1.0). NOT an
  accuracy measure — it's plumbing.
- ``pipeline`` (real, paid, DEFERRED): would run the OCR + extraction agents over
  each dossier PDF. This is the budget-gated seam — see ``pipeline_predictor``.
  It is GUARDED: without OCR keys it raises PredictorUnavailable and the CLI exits
  0 without spending. The live OCR/agent wiring itself is intentionally NOT shipped
  half-tested (tracked in AIQ-515): it requires gold documents + an OCR/LLM budget.

    python -m backend.scripts.run_extraction_predictions --corpus /tmp/ex_corpus --out preds.jsonl
    python -m eval.run_extraction_eval --corpus /tmp/ex_corpus --predictions preds.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List

Predictor = Callable[[Dict[str, Any]], List[Dict[str, Any]]]


class PredictorUnavailable(RuntimeError):
    """Raised when a predictor cannot run in the current environment (e.g. no keys)."""


def reference_predictor(gt: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Offline reference: echo the ground-truth fields (plumbing validation, $0)."""
    return [
        {"name": f.get("name"), "value": f.get("value"), "bbox": f.get("bbox")}
        for f in gt.get("fields", [])
    ]


def pipeline_predictor(gt: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Real OCR + extraction-agent predictor — BUDGET-GATED (deferred, AIQ-515).

    Intended wiring (per the document-extraction pipeline):
      dossier PDF for gt['doc_type']
        → rce_ocr_parser.parse_stored_document(...)            # Mistral / GPT-4o OCR (PAID)
        → rce_extraction_orchestrator.dispatch_and_run(        # extraction agents
              ocr_result=..., document_type_code=...,
              sink=InMemoryExtractionSink(), agent_storage=InMemoryAgentStorage())
        → map each ExtractedField → {name: field_key, value: value_raw, bbox}

    Guarded: requires MISTRAL_API_KEY + OPENAI_API_KEY. The live wiring is NOT
    shipped half-tested — running a meaningful extraction eval also needs real
    gold-labeled documents, not the synthetic pilot stubs. Until then this raises
    so callers fail closed (no silent wrong predictions, no surprise spend).
    """
    if not (os.environ.get("MISTRAL_API_KEY") and os.environ.get("OPENAI_API_KEY")):
        raise PredictorUnavailable(
            "pipeline predictor needs MISTRAL_API_KEY + OPENAI_API_KEY (paid OCR/LLM). "
            "Inject a predictor, or use --predictor reference for offline plumbing."
        )
    raise PredictorUnavailable(
        "Live OCR/agent extraction over real documents is the deferred AIQ-515 step "
        "(needs gold docs + budget). Wire parse_stored_document → dispatch_and_run here."
    )


_PREDICTORS: Dict[str, Predictor] = {
    "reference": reference_predictor,
    "pipeline": pipeline_predictor,
}


def produce_predictions(corpus_dir: Path, out_jsonl: Path, predictor: Predictor) -> int:
    """Apply *predictor* to each per-document ground_truth.json under *corpus_dir*;
    write one JSONL line per document. Returns the number of records written."""
    out_jsonl = Path(out_jsonl)
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(out_jsonl, "w", encoding="utf-8") as fh:
        for gt_path in sorted(Path(corpus_dir).rglob("ground_truth.json")):
            gt = json.loads(gt_path.read_text(encoding="utf-8"))
            doc_id = gt.get("document_id", str(gt_path))
            fields = predictor(gt)
            fh.write(json.dumps({"document_id": doc_id, "fields": fields}, ensure_ascii=False) + "\n")
            n += 1
    return n


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Produce an extraction predictions JSONL for run_extraction_eval")
    ap.add_argument("--corpus", required=True, help="per-document corpus dir (from build_extraction_corpus)")
    ap.add_argument("--out", required=True, help="output predictions JSONL path")
    ap.add_argument("--predictor", choices=sorted(_PREDICTORS), default="reference")
    args = ap.parse_args(argv)
    try:
        n = produce_predictions(Path(args.corpus), Path(args.out), _PREDICTORS[args.predictor])
    except PredictorUnavailable as exc:
        print(f"skipping ({args.predictor}): {exc}")
        return 0
    print(f"wrote {n} predictions to {args.out} (predictor={args.predictor})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
