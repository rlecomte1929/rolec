"""
Strict internal contract and validation for policy normalization input.

Built from:
- `policy_documents` row (from `get_policy_document`)
- `policy_document_clauses` rows (from `list_policy_document_clauses`)

Call `validate_and_prepare_normalization_input` before `run_normalization`.
"""
from __future__ import annotations

import copy
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

VALID_CLAUSE_TYPES = frozenset(
    {
        "scope",
        "eligibility",
        "benefit",
        "exclusion",
        "approval_rule",
        "evidence_rule",
        "tax_rule",
        "definition",
        "lifecycle_rule",
        "unknown",
    }
)


@dataclass
class NormalizationIssue:
    """Single validation or repair record."""

    path: str
    code: str
    message: str
    severity: str = "blocking"  # "blocking" | "repair"


class NormalizationInputInvalid(Exception):
    """Input cannot be normalized; no DB writes should be attempted."""

    def __init__(self, issues: List[NormalizationIssue]):
        self.issues = issues
        blocking = [i for i in issues if i.severity == "blocking"]
        super().__init__(blocking[0].message if blocking else "Invalid normalization input")


def _blocking(issues: List[NormalizationIssue]) -> None:
    if any(i.severity == "blocking" for i in issues):
        raise NormalizationInputInvalid(issues)


def _coerce_hints(value: Any, path: str, repairs: List[NormalizationIssue]) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            repairs.append(
                NormalizationIssue(
                    path=path,
                    code="EMPTY_HINT_STRING",
                    message="normalized_hint_json was an empty string; using {}",
                    severity="repair",
                )
            )
            return {}
        try:
            parsed = json.loads(s)
            if isinstance(parsed, dict):
                repairs.append(
                    NormalizationIssue(
                        path=path,
                        code="PARSED_HINT_JSON_STRING",
                        message="normalized_hint_json was a JSON string; parsed to object",
                        severity="repair",
                    )
                )
                return parsed
        except json.JSONDecodeError as e:
            repairs.append(
                NormalizationIssue(
                    path=path,
                    code="INVALID_HINT_JSON",
                    message=f"normalized_hint_json string could not be parsed: {e}; using {{}}",
                    severity="repair",
                )
            )
            return {}
    repairs.append(
        NormalizationIssue(
            path=path,
            code="HINT_COERCED_TO_EMPTY",
            message=f"normalized_hint_json had unexpected type {type(value).__name__}; using {{}}",
            severity="repair",
        )
    )
    return {}


def _coerce_confidence(value: Any, path: str, repairs: List[NormalizationIssue]) -> float:
    if value is None:
        return 0.5
    if isinstance(value, (int, float)):
        try:
            f = float(value)
            if f != f or f in (float("inf"), float("-inf")):  # NaN / inf
                repairs.append(
                    NormalizationIssue(
                        path=path,
                        code="CONFIDENCE_NON_FINITE",
                        message="confidence was NaN or infinite; using 0.5",
                        severity="repair",
                    )
                )
                return 0.5
            return max(0.0, min(1.0, f))
        except (TypeError, ValueError):
            pass
    repairs.append(
        NormalizationIssue(
            path=path,
            code="CONFIDENCE_COERCED",
            message="confidence was not numeric; using 0.5",
            severity="repair",
        )
    )
    return 0.5


def _coerce_clause_type(value: Any, path: str, repairs: List[NormalizationIssue]) -> str:
    s = str(value or "").strip().lower()
    if not s:
        repairs.append(
            NormalizationIssue(
                path=path,
                code="CLAUSE_TYPE_DEFAULTED",
                message="clause_type missing; using unknown",
                severity="repair",
            )
        )
        return "unknown"
    if s not in VALID_CLAUSE_TYPES:
        repairs.append(
            NormalizationIssue(
                path=path,
                code="CLAUSE_TYPE_UNKNOWN_FALLBACK",
                message=f"clause_type {value!r} is not in allowed set; using unknown",
                severity="repair",
            )
        )
        return "unknown"
    return s


def validate_and_prepare_normalization_input(
    document: Optional[Dict[str, Any]],
    clauses: Optional[List[Dict[str, Any]]],
    doc_id: str,
    request_id: Optional[str] = None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[NormalizationIssue]]:
    """
    Validate and return deep-copied, repaired document + clauses.

    Raises NormalizationInputInvalid if blocking issues exist.
    Always returns (doc_out, clauses_out, all_issues) when not raising;
    `all_issues` includes repairs (severity=repair) for logging / API hints.
    """
    issues: List[NormalizationIssue] = []

    if not document:
        issues.append(
            NormalizationIssue(
                path="document",
                code="DOCUMENT_MISSING",
                message="Policy document was not found or could not be loaded.",
                severity="blocking",
            )
        )
        _blocking(issues)

    doc = copy.deepcopy(document)
    rid = (doc_id or "").strip()
    if not rid:
        issues.append(
            NormalizationIssue(
                path="document_id",
                code="DOCUMENT_ID_EMPTY",
                message="Document id in request path is empty.",
                severity="blocking",
            )
        )
        _blocking(issues)

    did = str(doc.get("id") or "").strip()
    if did and did != rid:
        issues.append(
            NormalizationIssue(
                path="document.id",
                code="DOCUMENT_ID_MISMATCH",
                message=f"Loaded document id {did!r} does not match path id {rid!r}.",
                severity="blocking",
            )
        )
        _blocking(issues)

    cid = str(doc.get("company_id") or "").strip()
    if not cid:
        issues.append(
            NormalizationIssue(
                path="document.company_id",
                code="DOCUMENT_MISSING_COMPANY_ID",
                message="Document has no company_id. Re-upload from the company HR policy workspace.",
                severity="blocking",
            )
        )
        _blocking(issues)

    rt = doc.get("raw_text")
    if rt is None or (isinstance(rt, str) and not str(rt).strip()):
        issues.append(
            NormalizationIssue(
                path="document.raw_text",
                code="DOCUMENT_NO_RAW_TEXT",
                message="No extracted text. Run Reprocess after upload.",
                severity="blocking",
            )
        )
        _blocking(issues)

    if clauses is None:
        issues.append(
            NormalizationIssue(
                path="clauses",
                code="CLAUSES_NULL",
                message="Clause list was not loaded.",
                severity="blocking",
            )
        )
        _blocking(issues)

    if len(clauses) == 0:
        issues.append(
            NormalizationIssue(
                path="clauses",
                code="CLAUSES_EMPTY",
                message="No clauses to normalize. Run Reprocess to segment the document.",
                severity="blocking",
            )
        )
        _blocking(issues)

    out_clauses: List[Dict[str, Any]] = []
    for idx, c in enumerate(clauses):
        if not isinstance(c, dict):
            issues.append(
                NormalizationIssue(
                    path=f"clauses[{idx}]",
                    code="CLAUSE_NOT_OBJECT",
                    message=f"Clause at index {idx} is not an object.",
                    severity="blocking",
                )
            )
            _blocking(issues)
        base = f"clauses[{idx}]"
        row = copy.deepcopy(c)

        pdoc = str(row.get("policy_document_id") or "").strip()
        if pdoc and pdoc != rid:
            issues.append(
                NormalizationIssue(
                    path=f"{base}.policy_document_id",
                    code="CLAUSE_WRONG_DOCUMENT",
                    message="Clause belongs to a different policy document.",
                    severity="blocking",
                )
            )
            _blocking(issues)

        cid_clause = row.get("id")
        if cid_clause is None or str(cid_clause).strip() == "":
            new_id = str(uuid.uuid4())
            row["id"] = new_id
            issues.append(
                NormalizationIssue(
                    path=f"{base}.id",
                    code="CLAUSE_ID_GENERATED",
                    message=f"Missing clause id; assigned temporary id for normalization traceability.",
                    severity="repair",
                )
            )
        else:
            row["id"] = str(cid_clause).strip()

        row["clause_type"] = _coerce_clause_type(row.get("clause_type"), f"{base}.clause_type", issues)
        row["normalized_hint_json"] = _coerce_hints(
            row.get("normalized_hint_json"), f"{base}.normalized_hint_json", issues
        )
        row["confidence"] = _coerce_confidence(row.get("confidence"), f"{base}.confidence", issues)

        raw = row.get("raw_text")
        if raw is None:
            row["raw_text"] = ""
            issues.append(
                NormalizationIssue(
                    path=f"{base}.raw_text",
                    code="RAW_TEXT_DEFAULTED_EMPTY",
                    message="raw_text was null; coerced to empty string",
                    severity="repair",
                )
            )
        elif not isinstance(raw, str):
            row["raw_text"] = str(raw)
            issues.append(
                NormalizationIssue(
                    path=f"{base}.raw_text",
                    code="RAW_TEXT_COERCED_TO_STRING",
                    message="raw_text was not a string; coerced",
                    severity="repair",
                )
            )

        out_clauses.append(row)

    repairs_and_blocking = issues
    if request_id:
        for i in repairs_and_blocking:
            if i.severity == "blocking":
                log.warning(
                    "request_id=%s normalization_input blocking path=%s code=%s message=%s",
                    request_id,
                    i.path,
                    i.code,
                    i.message,
                )
            else:
                log.info(
                    "request_id=%s normalization_input repair path=%s code=%s message=%s",
                    request_id,
                    i.path,
                    i.code,
                    i.message,
                )

    return doc, out_clauses, repairs_and_blocking


def issues_to_jsonable(issues: List[NormalizationIssue]) -> List[Dict[str, str]]:
    return [{"path": i.path, "code": i.code, "message": i.message, "severity": i.severity} for i in issues]
