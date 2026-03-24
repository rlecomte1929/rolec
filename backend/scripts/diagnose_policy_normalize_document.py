#!/usr/bin/env python3
"""
Print normalization readiness + per-clause pipeline diagnostics for one policy_documents.id.

Usage (from repo root, with backend .env loaded):
  PYTHONPATH=. python3 backend/scripts/diagnose_policy_normalize_document.py <document_uuid>
  PYTHONPATH=. python3 backend/scripts/diagnose_policy_normalize_document.py <document_uuid> --json-rows /tmp/rows.json
  PYTHONPATH=. python3 backend/scripts/diagnose_policy_normalize_document.py <document_uuid> --no-table

Also sets RELOPASS_POLICY_PIPELINE_DIAG=1 for the process so policy_normalization emits per-clause
log lines (policy_pipeline_diag ...) if logging is configured to INFO for that logger.

Does not write to the database (except optional --json-rows path). Prints markdown table + duplicate clusters.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import uuid

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from backend.database import Database  # noqa: E402
from backend.services.policy_normalization import (  # noqa: E402
    _sanitize_benefit_rules_for_db,
    normalize_clauses_to_objects,
)
from backend.services.policy_normalization_errors import PolicyNormalizationPayloadInvalid  # noqa: E402
from backend.services.policy_normalization_validate import (  # noqa: E402
    build_version_payload_for_validation,
    evaluate_normalization_readiness,
    json_preview_for_diagnostics,
    log_extraction_and_normalization_shape,
    validate_benefit_rules_payload,
    validate_conditions_payload,
    validate_exclusions_payload,
    validate_policy_version_payload,
)
from backend.services.policy_normalization_draft import build_normalization_draft_model  # noqa: E402
from backend.services.policy_processing_readiness import build_processing_readiness_envelope  # noqa: E402
from backend.services.policy_pipeline_diagnostics import (  # noqa: E402
    build_per_clause_pipeline_table,
    format_pipeline_table_markdown,
    pipeline_fingerprint,
)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("document_id", help="policy_documents.id (UUID)")
    p.add_argument(
        "--no-table",
        action="store_true",
        help="Skip per-clause markdown table and duplicate clusters",
    )
    p.add_argument(
        "--json-rows",
        metavar="PATH",
        help="Write full per-clause rows + summary JSON to PATH",
    )
    args = p.parse_args()
    doc_id = args.document_id.strip()
    try:
        uuid.UUID(doc_id)
    except ValueError:
        print("Invalid UUID", file=sys.stderr)
        return 2

    os.environ["RELOPASS_POLICY_PIPELINE_DIAG"] = "1"
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("backend.services.policy_normalization").setLevel(logging.INFO)

    db = Database()
    doc = db.get_policy_document(doc_id, request_id=None)
    if not doc:
        print("Document not found:", doc_id, file=sys.stderr)
        return 1
    clauses = db.list_policy_document_clauses(doc_id, request_id=None)
    print("=== document ===")
    print("id:", doc.get("id"))
    print("detected_document_type:", doc.get("detected_document_type"))
    print("detected_policy_scope:", doc.get("detected_policy_scope"))
    print("clauses:", len(clauses))

    result = normalize_clauses_to_objects(clauses, doc_id)
    _sanitize_benefit_rules_for_db(result.get("benefit_rules") or [], request_id="diagnostic")

    if not args.no_table:
        rows, psum = build_per_clause_pipeline_table(clauses, result, document_id=doc_id)
        print("\n=== pipeline fingerprint ===")
        print("fingerprint:", pipeline_fingerprint(clauses, result))
        print("\n=== per-clause summary (counts) ===")
        print(
            json.dumps(
                {
                    k: psum[k]
                    for k in psum
                    if k != "duplicate_draft_clusters"
                },
                indent=2,
            )
        )
        print("\n=== duplicate draft clusters (same service_key + excerpt prefix) ===")
        print(json.dumps(psum.get("duplicate_draft_clusters") or [], indent=2))
        print("\n=== per-clause table (markdown) ===")
        print(format_pipeline_table_markdown(rows))
        if args.json_rows:
            out = {"summary": {k: v for k, v in psum.items() if k != "duplicate_draft_clusters"}, "rows": rows}
            out["summary"]["duplicate_draft_clusters"] = psum.get("duplicate_draft_clusters") or []
            with open(args.json_rows, "w", encoding="utf-8") as fh:
                json.dump(out, fh, indent=2)
            print("\nWrote", args.json_rows)
    elif args.json_rows:
        rows, psum = build_per_clause_pipeline_table(clauses, result, document_id=doc_id)
        out = {"summary": {k: v for k, v in psum.items() if k != "duplicate_draft_clusters"}, "rows": rows}
        out["summary"]["duplicate_draft_clusters"] = psum.get("duplicate_draft_clusters") or []
        with open(args.json_rows, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2)
        print("Wrote", args.json_rows)

    log_extraction_and_normalization_shape(
        stage="diagnostic_mapped",
        request_id="diagnostic",
        document_id=doc_id,
        policy_document=doc,
        clauses=clauses,
        normalized=result,
    )

    readiness = evaluate_normalization_readiness(doc, result, request_id="diagnostic", document_id=doc_id)
    print("\n=== readiness ===")
    print("draft_blocked:", readiness.draft_blocked)
    print("publishable:", readiness.publishable)
    print("readiness_status:", readiness.readiness_status)
    for b in readiness.draft_block_details:
        print(f"  [draft_block] {b.field}: {b.issue}")
    for b in readiness.readiness_issues:
        print(f"  [issue] {b.field}: {b.issue}")

    envelope = build_processing_readiness_envelope(doc, clauses, result, readiness)
    print("\n=== policy_readiness (normalization / publish / comparison) ===")
    print(json.dumps(envelope, indent=2))

    policies = db.list_company_policies(str(doc.get("company_id") or ""))
    preview_policy_id = str(policies[0]["id"]) if policies else str(uuid.uuid4())
    draft_preview = build_normalization_draft_model(
        policy_document=doc,
        company_id=str(doc.get("company_id") or ""),
        policy_id=preview_policy_id,
        policy_version_id=str(uuid.uuid4()),
        clauses=clauses,
        mapped=result,
        norm_core=readiness,
    )
    print("\n=== normalization_draft (preview — persist on normalize) ===")
    print(
        json.dumps(
            {
                "schema_version": draft_preview.get("schema_version"),
                "document_metadata": draft_preview.get("document_metadata"),
                "clause_candidates_count": len(draft_preview.get("clause_candidates") or []),
                "rule_candidate_counts": {
                    "benefit_rules": len((draft_preview.get("rule_candidates") or {}).get("benefit_rules") or []),
                    "exclusions": len((draft_preview.get("rule_candidates") or {}).get("exclusions") or []),
                },
            },
            indent=2,
        )
    )

    if policies:
        policy_id = str(policies[0]["id"])
    else:
        policy_id = str(uuid.uuid4())
    existing = db.list_policy_versions(policy_id)
    version_number = max((v.get("version_number") or 1 for v in existing), default=1) + 1 if existing else 1
    version_id = str(uuid.uuid4())
    vp = build_version_payload_for_validation(
        version_id=version_id,
        policy_id=policy_id,
        doc_id=doc_id,
        version_number=version_number,
        status="auto_generated",
        auto_generated=True,
        review_status="pending",
        confidence=0.7,
    )
    print("\n=== policy_versions[0] payload (preview) ===")
    print(json_preview_for_diagnostics({"policy_versions": [vp]}))

    if readiness.draft_blocked:
        print("\n(Skipping pydantic validation because draft is blocked.)")
        return 0

    try:
        validate_policy_version_payload(vp, document_id=doc_id, request_id="diagnostic")
        validate_benefit_rules_payload(result.get("benefit_rules") or [], document_id=doc_id, request_id="diagnostic")
        validate_exclusions_payload(result.get("exclusions") or [], document_id=doc_id, request_id="diagnostic")
        validate_conditions_payload(result.get("conditions") or [], document_id=doc_id, request_id="diagnostic")
        print("\n=== pydantic validation ===\nOK")
    except PolicyNormalizationPayloadInvalid as e:
        print("\n=== pydantic validation ===\nFAILED", e.error_code)
        for d in e.details:
            print(" ", d.to_json())
        return 1

    print("\n=== benefit_rules sample (first 2, internal keys stripped) ===")
    for i, r in enumerate((result.get("benefit_rules") or [])[:2]):
        pub = {k: v for k, v in r.items() if not str(k).startswith("_")}
        print(json_preview_for_diagnostics(pub, max_len=2000))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
