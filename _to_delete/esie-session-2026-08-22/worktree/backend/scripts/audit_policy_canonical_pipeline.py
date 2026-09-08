"""
Run the canonical policy pipeline over one or more external policy files.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend.database import db
from backend.services.policy_canonical_chunking import chunk_canonical_policy_document
from backend.services.policy_canonical_extraction import extract_canonical_policy_facts
from backend.services.policy_canonical_ingestion import ingest_canonical_policy_document


def _markdown_report(report: Dict[str, Any]) -> str:
    lines = [
        "# Canonical Policy Audit Report",
        "",
    ]
    for document in report["documents"]:
        lines.extend(
            [
                f"## {document['filename']}",
                f"- Canonical document id: `{document['canonical_document_id']}`",
                f"- Chunks: {document['chunks_count']}",
                f"- Facts: {document['facts_count']}",
                f"- Validation errors: {document['validation_error_count']}",
                f"- Validation pass rate: {document['validation_pass_rate']:.2%}",
                f"- Counts by category: `{json.dumps(document['counts_by_category'], sort_keys=True)}`",
                f"- Counts by phase: `{json.dumps(document['counts_by_phase'], sort_keys=True)}`",
                "",
            ]
        )
    return "\n".join(lines)


def run_audit(file_paths: List[str], *, use_fallback: bool) -> Dict[str, Any]:
    docs: List[Dict[str, Any]] = []
    for file_path in file_paths:
        document = ingest_canonical_policy_document(db, file_path=file_path)
        chunk_canonical_policy_document(db, str(document["id"]))
        extract_canonical_policy_facts(db, str(document["id"]), use_fallback=use_fallback)
        summary = db.get_canonical_policy_audit_summary(str(document["id"]))
        docs.append(
            {
                "filename": os.path.basename(file_path),
                "canonical_document_id": document["id"],
                **summary,
            }
        )
    return {"documents": docs}


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit canonical policy extraction pipeline.")
    parser.add_argument("file_paths", nargs="+", help="Absolute or relative paths to policy PDFs/DOCX files")
    parser.add_argument("--output-json", default="audit_report.json")
    parser.add_argument("--output-markdown", default="audit_report.md")
    parser.add_argument(
        "--use-fallback",
        action="store_true",
        help="Use the deterministic fallback extractor instead of the OpenAI-backed extractor.",
    )
    args = parser.parse_args()

    report = run_audit(args.file_paths, use_fallback=args.use_fallback)
    with open(args.output_json, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    with open(args.output_markdown, "w", encoding="utf-8") as fh:
        fh.write(_markdown_report(report))

    for document in report["documents"]:
        print(
            f"{document['filename']}: chunks={document['chunks_count']} "
            f"facts={document['facts_count']} validation_errors={document['validation_error_count']}"
        )
    print(f"Wrote {args.output_json} and {args.output_markdown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
