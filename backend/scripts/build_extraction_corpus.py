"""AIQ-515 — build a per-DOCUMENT extraction-eval corpus from the pilot dossiers.

Materialises the 20 pilot dossiers, splits each into per-document ground-truth
records (backend/eval/extraction_corpus_adapter), and writes one
``<out>/<dossier_id>__<doc_type>/ground_truth.json`` per document in the layout
``backend/eval/run_extraction_eval.py`` expects (it rglobs ground_truth.json,
one document each).

    python -m backend.scripts.build_extraction_corpus --out /tmp/extraction_corpus
    python -m eval.run_extraction_eval --corpus /tmp/extraction_corpus          # mock → 1.0 (plumbing)
    python -m eval.run_extraction_eval --corpus /tmp/extraction_corpus --predictions preds.jsonl

This is structural plumbing (it makes the extraction eval RUNNABLE on the corpus);
a meaningful accuracy score needs real gold documents + a real predictions JSONL
(see backend/scripts/run_extraction_predictions.py). NOT a deploy artifact.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import List

from ..eval.extraction_corpus_adapter import dossier_to_document_records

# backend/ dir — the pilot materializer imports via the top-level `tests.*`
# namespace, so backend/ must be on sys.path (mirrors test_schema.py's pattern).
_BACKEND_DIR = str(Path(__file__).resolve().parents[1])


def build_corpus(out_dir: Path, work_dir: Path | None = None) -> List[Path]:
    """Materialise dossiers + write per-document ground_truth.json files. Returns paths."""
    if _BACKEND_DIR not in sys.path:
        sys.path.insert(0, _BACKEND_DIR)
    from tests.fixtures.pilot.materialize import materialize  # noqa: E402  (top-level tests.*)

    src = Path(work_dir or tempfile.mkdtemp(prefix="pilot_dossiers_"))
    materialize(str(src))

    out_dir = Path(out_dir)
    written: List[Path] = []
    for gt_path in sorted(src.rglob("ground_truth.json")):
        dossier_gt = json.loads(gt_path.read_text(encoding="utf-8"))
        for rec in dossier_to_document_records(dossier_gt):
            doc_dir = out_dir / f"{rec['dossier_id']}__{rec['doc_type']}"
            doc_dir.mkdir(parents=True, exist_ok=True)
            dest = doc_dir / "ground_truth.json"
            with open(dest, "w", encoding="utf-8") as fh:
                json.dump(rec, fh, indent=2, ensure_ascii=False)
            written.append(dest)
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build the per-document extraction-eval corpus from pilot dossiers")
    ap.add_argument("--out", required=True, help="output directory for the per-document corpus")
    args = ap.parse_args(argv)
    written = build_corpus(Path(args.out))
    doc_types = sorted({p.parent.name.split("__", 1)[1] for p in written})
    print(f"wrote {len(written)} per-document ground_truth.json files to {args.out}")
    print(f"doc_types: {doc_types}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
