"""AIQ-515 — adapt the pilot dossier corpus into per-DOCUMENT extraction records.

`run_extraction_eval` scores per-document records:
    {document_id, doc_type, fields: [{name, value, bbox, is_money}]}
treating each ground_truth.json as ONE document. The pilot corpus
(tests/fixtures/pilot) is per-DOSSIER: one ground_truth.json per case with a flat
`extracted_fields: [{field_key, value, bbox, confidence}]` mixing fields from
several source documents. This adapter splits a dossier into one record per
source document so the extraction eval can run over the corpus.

The field→doc_type map is derived from the corpus's known, deterministic field
set (see backend/tests/fixtures/pilot/generators). It is a grouping label only —
`run_extraction_eval` uses it for per-doc-type gating, not for routing.
"""
from __future__ import annotations

from typing import Any, Dict, List

# Which source document each corpus field_key belongs to. Grouping label for the
# extraction eval (NOT the pipeline's own doc-type codes).
_FIELD_TO_DOCTYPE: Dict[str, str] = {
    "surname": "identity_document",
    "given_name": "identity_document",
    "dob": "identity_document",
    "address": "identity_document",
    "employer_name": "employment_contract",
    "monthly_salary_eur": "employment_contract",
    "diploma_field": "diploma",
}

# Fields graded with money tolerance (run_extraction_eval money_accuracy).
_MONEY_FIELDS = {"monthly_salary_eur"}

# Stable doc-type ordering for deterministic output.
_DOCTYPE_ORDER = ("identity_document", "employment_contract", "diploma")


def dossier_to_document_records(dossier_gt: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Split one dossier ground_truth dict into per-document extraction records.

    Returns a list of ``{document_id, doc_type, fields:[{name,value,bbox,is_money}]}``
    — one record per source document present in the dossier. document_id is
    ``f"{dossier_id}:{doc_type}"`` so predictions can key to the same id.
    Fields whose key is not in the doc-type map are skipped (forward-compatible).
    """
    dossier_id = dossier_gt.get("dossier_id", "UNKNOWN")
    by_doctype: Dict[str, List[Dict[str, Any]]] = {}

    for field in dossier_gt.get("extracted_fields", []):
        fk = field.get("field_key")
        doc_type = _FIELD_TO_DOCTYPE.get(fk)
        if doc_type is None:
            continue
        by_doctype.setdefault(doc_type, []).append({
            "name": fk,
            "value": field.get("value"),
            "bbox": field.get("bbox"),
            "is_money": fk in _MONEY_FIELDS,
        })

    records: List[Dict[str, Any]] = []
    for doc_type in _DOCTYPE_ORDER:
        fields = by_doctype.get(doc_type)
        if not fields:
            continue
        records.append({
            "document_id": f"{dossier_id}:{doc_type}",
            "doc_type": doc_type,
            "dossier_id": dossier_id,
            "fields": fields,
        })
    return records
