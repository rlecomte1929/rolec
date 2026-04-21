"""
Policy document intake pipeline (INGEST stage): parse PDF/DOCX, classify, extract metadata.

Pipeline layers (see docs/policy/metadata-vs-decision-layer.md):
- **Layer 1 — document metadata / structure:** Everything in this module (classification,
  extracted_metadata, heuristic flags, mentioned_* terms) is descriptive only. It must not be
  treated as binding coverage for employees.
- **Layer 2 — decision output:** Produced later by normalization + publish + resolution
  (policy_benefit_rules, resolved_assignment_policy_benefits, etc.).

Pipeline stage (3-stage model):
- Ingest (this module): store file in blob storage, extract raw text, classify document type/scope,
  extract metadata (title, version, effective date), and optionally segment into clauses.
  Called from the upload endpoint after the file is stored. Output: policy_documents row + clauses.
- Reprocess: re-run extraction and clause segmentation from the stored file without re-uploading.
  Used when extraction logic or segmentation improves, or to fix failed extraction.
- Normalize: transform clauses into structured policy objects (company_policies, policy_versions,
  benefit_rules, exclusions, etc.). Separate so HR can reprocess without overwriting normalized edits.
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import re
from datetime import datetime
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

log = logging.getLogger(__name__)

# Processing statuses
STATUS_UPLOADED = "uploaded"
STATUS_TEXT_EXTRACTED = "text_extracted"
STATUS_CLASSIFIED = "classified"
STATUS_NORMALIZED = "normalized"
STATUS_REVIEW_REQUIRED = "review_required"
STATUS_APPROVED = "approved"
STATUS_FAILED = "failed"

# Document types
DOC_TYPE_ASSIGNMENT_POLICY = "assignment_policy"
DOC_TYPE_POLICY_SUMMARY = "policy_summary"
DOC_TYPE_SUMMARY_TABLE = "summary_table"
DOC_TYPE_COMPACT_BENEFIT_MATRIX = "compact_benefit_matrix"
DOC_TYPE_TAX_POLICY = "tax_policy"
DOC_TYPE_COUNTRY_ADDENDUM = "country_addendum"
DOC_TYPE_UNKNOWN = "unknown"

# Policy scopes
SCOPE_GLOBAL = "global"
SCOPE_LONG_TERM = "long_term_assignment"
SCOPE_SHORT_TERM = "short_term_assignment"
SCOPE_TAX_EQUALIZATION = "tax_equalization"
SCOPE_MIXED = "mixed"
SCOPE_UNKNOWN = "unknown"

BENEFIT_CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "housing": ["housing", "temporary housing", "rental", "accommodation", "deposit"],
    "movers": ["shipment", "household goods", "movers", "moving", "freight"],
    "schools": ["education", "school", "tuition", "childcare"],
    "immigration": ["visa", "immigration", "work permit", "residence permit"],
    "travel": ["travel", "flight", "airfare", "scouting trip", "home leave"],
    "settling_in": ["settling-in", "settling in", "allowance"],
    "tax": ["tax assistance", "tax equalization", "hypothetical tax", "tax"],
    "spouse": ["spousal support", "spouse", "partner support"],
    "integration": ["language", "cultural", "integration", "training"],
    "repatriation": ["repatriation", "return shipment", "return travel"],
}

ASSIGNMENT_TYPE_PATTERNS = [
    ("long_term", ["long-term assignment", "long term assignment", "lta", "lt assignment", "long-term", "long term"]),
    ("short_term", ["short-term assignment", "short term assignment", "sta", "st assignment", "short-term", "short term"]),
    ("permanent", ["permanent transfer", "permanent relocation", "permanent move"]),
    ("commuter", ["commuter", "commuter assignment"]),
    ("extended_business_trip", ["extended business trip", "ebt"]),
    ("international", ["international assignment", "global assignment"]),
]

FAMILY_STATUS_TERMS = [
    "single", "married", "unmarried", "spouse", "accompanying spouse", "trailing spouse",
    "dependents", "dependent children", "family", "accompanying family",
    "domestic partner", "partner", "household",
]

UNIT_PATTERNS = [
    r"\b(usd|eur|gbp|chf|cad|aud|jpy)\b",
    r"\b(%|percent|percentage)\b",
    r"\b(days?|weeks?|months?|years?)\b",
    r"\b(lbs?|kg)\b",
]

EXCLUSION_SIGNALS = [
    "exclusion", "excluded", "excluding", "not covered", "ineligible",
    "does not apply", "out of scope", "outside policy", "non-covered",
]

APPROVAL_SIGNALS = [
    "approval", "pre-approval", "pre approval", "hr approval", "manager approval",
    "requires approval", "prior approval", "approved by", "sign-off",
]

EVIDENCE_SIGNALS = [
    "evidence", "receipt", "invoice", "documentation required", "proof of",
    "supporting documentation", "submit receipts", "receipts required",
]


def compute_checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_text_from_bytes(data: bytes, mime_type: str) -> Tuple[List[str], Optional[str]]:
    """
    Extract text from PDF or DOCX. Returns (lines, error).
    """
    if mime_type in ("application/pdf", "pdf") or (isinstance(mime_type, str) and "pdf" in mime_type.lower()):
        return _extract_text_from_pdf(data)
    if mime_type in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "docx",
    ) or (isinstance(mime_type, str) and "word" in mime_type.lower() or "docx" in mime_type.lower()):
        return _extract_text_from_docx(data)
    return [], f"Unsupported mime type: {mime_type}"


def _normalize_lines(lines: List[str]) -> List[str]:
    cleaned = []
    for line in lines:
        if not line:
            continue
        s = re.sub(r"\s+", " ", line.strip())
        if s:
            cleaned.append(s)
    return cleaned


def _extract_text_from_docx(data: bytes) -> Tuple[List[str], Optional[str]]:
    try:
        from docx import Document  # type: ignore
    except ImportError as exc:
        return [], f"python-docx required: {exc}"
    try:
        doc = Document(io.BytesIO(data))
        lines: List[str] = []
        for p in doc.paragraphs:
            lines.append(p.text or "")
        for table in doc.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text]
                if cells:
                    lines.append(" | ".join(cells))
        return _normalize_lines(lines), None
    except Exception as e:
        log.warning("docx extraction failed: %s", e, exc_info=True)
        return [], str(e)


def _extract_text_from_pdf(data: bytes) -> Tuple[List[str], Optional[str]]:
    try:
        import pdfplumber  # type: ignore
    except ImportError as exc:
        return [], f"pdfplumber required: {exc}"
    try:
        lines: List[str] = []
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                lines.extend(text.splitlines())
                for table in page.extract_tables() or []:
                    for row in table:
                        cells = [str(c) if c else "" for c in row if c is not None]
                        if cells:
                            lines.append(" | ".join(cells))
        return _normalize_lines(lines), None
    except Exception as e:
        log.warning("pdf extraction failed: %s", e, exc_info=True)
        return [], str(e)


@dataclass(frozen=True)
class DocTypeProfile:
    """
    Keyword profile for a document-type classifier bucket (regex-based).

    - `primary` patterns MUST match in the title block (first ~600 chars +
      the first markdown/ALL-CAPS heading) to make the profile eligible.
      A profile without a primary hit scores 0 for that bucket — no amount
      of body evidence promotes it.
    - `body` patterns match the full lowercased body; each hit adds 1.
    - `negative` patterns match the full body; each hit subtracts 2
      (tunable via _NEGATIVE_WEIGHT).
    - `default_scope` is returned when this profile wins.
    """
    name: str
    primary: Tuple[str, ...]
    body: Tuple[str, ...] = ()
    negative: Tuple[str, ...] = ()
    default_scope: str = SCOPE_UNKNOWN
    min_primary_hits: int = 1


@dataclass
class ClassificationResult:
    """
    Result of classify_by_keywords. The classifier returns this rather than
    a bare tuple so downstream callers can log `reasons` and `scores` for
    audit without having to re-run the match.
    """
    detected_document_type: str
    detected_policy_scope: str
    confidence: float
    review_required: bool
    scores: Dict[str, float]
    reasons: List[str]


# Title block = first N chars + the first heading (markdown or ALL-CAPS).
# The ambiguity markers that Prompt A Dummy 3 carries ("not specified" /
# "not provided" / "support may be provided") land in the body, not the
# title, so this block intentionally doesn't include them.
_TITLE_BLOCK_CHARS = 600
_HEADING_RE = re.compile(r"(?m)^\s{0,3}(#{1,3}\s+.+|[A-Z][A-Z0-9 &/-]{4,}$)")

# Scoring constants (recipe §3).
_PRIMARY_WEIGHT = 3.0
_BODY_WEIGHT = 1.0
_NEGATIVE_WEIGHT = 2.0
# Margin + confidence thresholds for review_required=False.
_MARGIN_THRESHOLD = 1.5
_CONFIDENCE_THRESHOLD = 0.35

# Ambiguity override — if the body is this "missing data"–heavy, the
# classifier returns UNKNOWN even when a profile has a primary hit.
# Preserves Dummy 3's review_required=True + unknown outcome.
_HIGH_AMBIGUITY_MARKERS = (
    r"\bnot\s+specified\b",
    r"\bnot\s+defined\b",
    r"\bnot\s+provided\b",
    r"\bno\s+cost\s+clarity\b",
    r"\bsupport\s+may\s+be\s+provided\b",
    r"\bhandled\s+internally\b",
    r"\bno\s+breakdown\s+of\s+services\b",
    r"\bmissing\s+data\b",
)
_AMBIGUITY_THRESHOLD = 4


# Profile order matters for tie-breaking — the first profile to reach a
# given score wins. assignment_policy is listed first so borderline docs
# interpret as assignments rather than tax policies or summaries.
_DOC_TYPE_PROFILES: Tuple[DocTypeProfile, ...] = (
    DocTypeProfile(
        name=DOC_TYPE_ASSIGNMENT_POLICY,
        primary=(
            r"\bassignment\s+policy\b",
            r"\bassignment\s+type\b",
            r"\blong[- ]term\s+assignment\b",
            r"\bshort[- ]term\s+assignment\b",
            r"\bpermanent\s+transfer\b",
            r"\binternational\s+assignment\b",
            r"\brelocation\s+policy\b",
            r"\bmobility\s+policy\b",
            r"\bglobal\s+mobility\s+policy\b",
        ),
        body=(
            r"\bmobility\s+premium\b",
            r"\bhome\s+leave\b",
            r"\bhousehold\s+goods\b",
            r"\brelocation\s+assistance\b",
            r"\bhousing\s+allowance\b",
            r"\btemporary\s+housing\b",
            r"\bper\s+diem\b",
            r"\bcost\s+of\s+living\b",
            r"\bcola\b",
            r"\bexpat\b",
            r"\btax\s+equalization\b",
            r"\bschooling\b",
            r"\blanguage\s+training\b",
            r"\brepatriation\b",
            r"\bassignee\b",
            r"\bhost\s+country\b",
        ),
        negative=(
            r"\bstandalone\s+tax\s+policy\b",
        ),
        default_scope=SCOPE_GLOBAL,
    ),
    DocTypeProfile(
        name=DOC_TYPE_TAX_POLICY,
        primary=(
            r"\btax\s+policy\b",
            r"\btax\s+equalization\s+policy\b",
            r"\btax\s+protection\s+policy\b",
            r"\bhypothetical\s+tax\s+policy\b",
            r"\bhypothetical\s+social\s+security\s+policy\b",
        ),
        body=(
            r"\bhypothetical\s+tax\b",
            r"\bhypothetical\s+social\s+security\b",
            r"\btax\s+gross[- ]up\b",
            r"\btax\s+return\s+preparation\b",
            r"\btax\s+reimbursement\b",
            r"\btax\s+provider\b",
        ),
        # Appearing alongside these strongly suggests this is a tax SECTION
        # within an assignment policy, not a standalone tax policy.
        negative=(
            r"\bassignment\s+policy\b",
            r"\bassignee\b",
            r"\brelocation\b",
            r"\bmobility\s+premium\b",
            r"\bhousehold\s+goods\b",
            r"\bhome\s+leave\b",
        ),
        default_scope=SCOPE_TAX_EQUALIZATION,
    ),
    DocTypeProfile(
        name=DOC_TYPE_POLICY_SUMMARY,
        primary=(
            r"\blong\s+term\s+assignment\s+policy\s+summary\b",
            r"\blta\s+policy\s+summary\b",
            r"\bpolicy\s+summary\b",
        ),
        body=(r"\bquick\s+reference\b", r"\bat\s+a\s+glance\b"),
        negative=(),
        default_scope=SCOPE_LONG_TERM,
    ),
    DocTypeProfile(
        name=DOC_TYPE_COUNTRY_ADDENDUM,
        primary=(r"\baddendum\b", r"\bannex\b", r"\bappendix\b"),
        body=(r"\bhost\s+country\b", r"\blocal\s+conditions\b"),
        negative=(),
        default_scope=SCOPE_UNKNOWN,
    ),
)


def _title_block(text: str, limit: int = _TITLE_BLOCK_CHARS) -> str:
    """
    Approximate title area: the first H1/H2/ALL-CAPS heading plus the
    first `limit` chars. Lowercased.
    """
    first_heading = _HEADING_RE.search(text)
    head = first_heading.group(0) if first_heading else ""
    return (head + "\n" + text[:limit]).lower()


def _count_matches(patterns: Iterable[str], blob: str) -> int:
    return sum(1 for p in patterns if re.search(p, blob, re.IGNORECASE))


def classify_by_keywords(text: str) -> ClassificationResult:
    """
    Regex + scoring classifier.

    Algorithm:
      1. Ambiguity override — if the body has ≥ _AMBIGUITY_THRESHOLD matches
         of "missing data" markers, return UNKNOWN immediately. This
         preserves Dummy 3's review_required=True outcome even though
         "Permanent transfer" would otherwise match the assignment
         primary keywords.
      2. For each profile, require a primary-keyword hit in the title
         block. No primary hit → score 0 for that profile.
      3. score = (_PRIMARY_WEIGHT × primary_hits) + (_BODY_WEIGHT × body_hits)
                 − (_NEGATIVE_WEIGHT × negative_hits), floored at 0.
      4. Winning profile = highest score. Tie-break: earlier profile
         (list order is assignment → tax → summary → addendum).
      5. review_required = margin between top and runner-up < _MARGIN_THRESHOLD
         or confidence < _CONFIDENCE_THRESHOLD.
    """
    title = _title_block(text)
    body = text.lower()

    reasons: List[str] = []

    ambiguity_hits = _count_matches(_HIGH_AMBIGUITY_MARKERS, body)
    if ambiguity_hits >= _AMBIGUITY_THRESHOLD:
        reasons.append(
            f"ambiguity override: {ambiguity_hits} markers ≥ {_AMBIGUITY_THRESHOLD} threshold"
        )
        return ClassificationResult(
            detected_document_type=DOC_TYPE_UNKNOWN,
            detected_policy_scope=SCOPE_UNKNOWN,
            confidence=0.0,
            review_required=True,
            scores={},
            reasons=reasons,
        )

    scores: Dict[str, float] = {}
    for prof in _DOC_TYPE_PROFILES:
        primary_hits = _count_matches(prof.primary, title)
        if primary_hits < prof.min_primary_hits:
            scores[prof.name] = 0.0
            continue
        body_hits = _count_matches(prof.body, body)
        negative_hits = _count_matches(prof.negative, body)
        score = (
            _PRIMARY_WEIGHT * primary_hits
            + _BODY_WEIGHT * body_hits
            - _NEGATIVE_WEIGHT * negative_hits
        )
        scores[prof.name] = max(score, 0.0)
        reasons.append(
            f"{prof.name}: primary={primary_hits} body={body_hits} "
            f"negative={negative_hits} → {scores[prof.name]:.1f}"
        )

    if not any(scores.values()):
        reasons.append("no document type had a primary keyword hit")
        return ClassificationResult(
            detected_document_type=DOC_TYPE_UNKNOWN,
            detected_policy_scope=SCOPE_UNKNOWN,
            confidence=0.0,
            review_required=True,
            scores=scores,
            reasons=reasons,
        )

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    top_name, top_score = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = top_score - runner_up
    confidence = min(1.0, margin / max(top_score, 1.0))
    review_required = (margin < _MARGIN_THRESHOLD) or (confidence < _CONFIDENCE_THRESHOLD)

    # Resolve scope from the winning profile.
    winner = next(p for p in _DOC_TYPE_PROFILES if p.name == top_name)

    return ClassificationResult(
        detected_document_type=top_name,
        detected_policy_scope=winner.default_scope,
        confidence=confidence,
        review_required=review_required,
        scores=scores,
        reasons=reasons,
    )


def classify_document(lines: List[str], request_id: Optional[str] = None) -> Tuple[str, str, bool]:
    """
    Rule-based document classifier. Returns (document_type, policy_scope, needs_review).

    Public API preserved for backward compatibility — delegates to
    `classify_by_keywords` which returns a richer ClassificationResult.
    Callers that want confidence / scoring trace should use the new API
    directly.

    Audit reference: EXTRACT-BUG-2 (Prompt A).
    """
    text = "\n".join(lines)
    result = classify_by_keywords(text)
    log.info(
        "request_id=%s classify_document: type=%s scope=%s confidence=%.2f review_required=%s",
        request_id or "", result.detected_document_type, result.detected_policy_scope,
        result.confidence, result.review_required,
    )
    return (result.detected_document_type, result.detected_policy_scope, result.review_required)


def _empty_metadata() -> Dict[str, Any]:
    """Canonical empty extracted_metadata schema."""
    return {
        "detected_title": None,
        "detected_version": None,
        "detected_effective_date": None,
        "mentioned_assignment_types": [],
        "mentioned_family_status_terms": [],
        "mentioned_benefit_categories": [],
        "mentioned_units": [],
        "likely_table_heavy": False,
        "likely_country_addendum": False,
        "likely_tax_specific": False,
        "likely_contains_exclusions": False,
        "likely_contains_approval_rules": False,
        "likely_contains_evidence_rules": False,
    }


def normalize_extracted_metadata(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Normalize extracted_metadata to the current schema.
    Backward-compatible with legacy fields (policy_title, version, contains_tables, etc.).
    """
    base = _empty_metadata()
    if not raw or not isinstance(raw, dict):
        return base

    # Map legacy keys to new schema
    base["detected_title"] = raw.get("detected_title") or raw.get("policy_title")
    base["detected_version"] = raw.get("detected_version") or raw.get("version")
    base["detected_effective_date"] = raw.get("detected_effective_date") or raw.get("effective_date")
    base["mentioned_assignment_types"] = raw.get("mentioned_assignment_types")
    if base["mentioned_assignment_types"] is None:
        leg = raw.get("assignment_types_mentioned")
        base["mentioned_assignment_types"] = leg if isinstance(leg, list) else []

    base["mentioned_family_status_terms"] = raw.get("mentioned_family_status_terms")
    if base["mentioned_family_status_terms"] is None:
        base["mentioned_family_status_terms"] = []

    base["mentioned_benefit_categories"] = raw.get("mentioned_benefit_categories")
    if base["mentioned_benefit_categories"] is None:
        leg = raw.get("benefit_categories_mentioned")
        base["mentioned_benefit_categories"] = leg if isinstance(leg, list) else []

    base["mentioned_units"] = raw.get("mentioned_units")
    if base["mentioned_units"] is None:
        base["mentioned_units"] = []

    base["likely_table_heavy"] = bool(
        raw.get("likely_table_heavy")
        if "likely_table_heavy" in raw
        else raw.get("contains_tables", False)
    )
    base["likely_country_addendum"] = bool(raw.get("likely_country_addendum", False))
    base["likely_tax_specific"] = bool(raw.get("likely_tax_specific", False))
    base["likely_contains_exclusions"] = bool(raw.get("likely_contains_exclusions", False))
    base["likely_contains_approval_rules"] = bool(raw.get("likely_contains_approval_rules", False))
    base["likely_contains_evidence_rules"] = bool(raw.get("likely_contains_evidence_rules", False))

    return base


def extract_metadata(lines: List[str]) -> Dict[str, Any]:
    """
    Rule-based, deterministic extraction of structured metadata.
    Returns canonical schema for extracted_metadata.
    """
    meta = _empty_metadata()
    text_lower = "\n".join(lines).lower()
    text_full = "\n".join(lines)

    # detected_title: first substantial line containing "policy"
    for line in lines[:40]:
        s = line.strip()
        if s and "policy" in s.lower() and 5 < len(s) < 150:
            meta["detected_title"] = s
            break

    # detected_version
    for line in lines[:60]:
        m = re.search(r"(?:version|v\.?)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)", line, re.I)
        if m:
            meta["detected_version"] = m.group(1)
            break

    # detected_effective_date
    for line in lines[:80]:
        m = re.search(r"(?:effective|valid from)\s*[:\-]?\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", line, re.I)
        if m:
            meta["detected_effective_date"] = m.group(1)
            break
        if not meta["detected_effective_date"]:
            m = re.search(r"([0-9]{1,2}[/\-][0-9]{1,2}[/\-][0-9]{4})", line)
            if m:
                d = m.group(1)
                parts = re.split(r"[/\-]", d)
                if len(parts) == 3:
                    y, mo, day = (
                        (parts[2], parts[0], parts[1])
                        if len(parts[2]) == 4
                        else (parts[2], parts[1], parts[0])
                    )
                    meta["detected_effective_date"] = f"{y}-{mo.zfill(2)}-{day.zfill(2)}"
                    break
        if not meta["detected_effective_date"]:
            m = re.search(r"([0-9]{4})-([0-9]{2})-([0-9]{2})", line)
            if m:
                meta["detected_effective_date"] = m.group(0)
                break

    # mentioned_assignment_types
    for key, patterns in ASSIGNMENT_TYPE_PATTERNS:
        if any(p in text_lower for p in patterns) and key not in meta["mentioned_assignment_types"]:
            meta["mentioned_assignment_types"].append(key)

    # mentioned_family_status_terms
    for term in FAMILY_STATUS_TERMS:
        if term in text_lower and term not in meta["mentioned_family_status_terms"]:
            meta["mentioned_family_status_terms"].append(term)

    # mentioned_benefit_categories
    for cat, keywords in BENEFIT_CATEGORY_KEYWORDS.items():
        if any(k in text_lower for k in keywords) and cat not in meta["mentioned_benefit_categories"]:
            meta["mentioned_benefit_categories"].append(cat)

    # mentioned_units (currencies, %, time units)
    seen: set = set()
    for pat in UNIT_PATTERNS:
        for m in re.finditer(pat, text_lower, re.I):
            u = m.group(1).lower()
            if u not in seen:
                seen.add(u)
                meta["mentioned_units"].append(u)

    # likely_table_heavy: many pipe-separated lines
    table_like = sum(1 for ln in lines if " | " in ln and len(ln) > 20)
    meta["likely_table_heavy"] = table_like >= 3

    # likely_country_addendum
    addendum_match = re.search(
        r"(addendum|annex|appendix)\s+.*\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b",
        text_full,
        re.I,
    )
    meta["likely_country_addendum"] = bool(
        addendum_match and any(c in text_lower for c in ["country", "local", "host"])
    )

    # likely_tax_specific
    meta["likely_tax_specific"] = any(
        s in text_lower
        for s in [
            "tax equalization",
            "hypothetical tax",
            "hypothetical social security",
            "tax protection",
        ]
    )

    # likely_contains_exclusions
    meta["likely_contains_exclusions"] = any(s in text_lower for s in EXCLUSION_SIGNALS)

    # likely_contains_approval_rules
    meta["likely_contains_approval_rules"] = any(s in text_lower for s in APPROVAL_SIGNALS)

    # likely_contains_evidence_rules
    meta["likely_contains_evidence_rules"] = any(s in text_lower for s in EVIDENCE_SIGNALS)

    return meta


def process_uploaded_document(
    data: bytes,
    mime_type: str,
    filename: str,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Full intake pipeline: validate bytes, extract text, classify, extract metadata.

    Rejection ordering (important — cheaper checks first):
      1. Size check (DocumentSizeError)
      2. Magic-byte sniff (UnsupportedFileTypeError)
      3. PDF encryption check (EncryptedDocumentError)
      4. Text extraction (MalformedDocumentError on parser failure)

    Rejections from steps 1–4 re-raise as PolicyIntakeError subclasses so
    callers can map them to typed HTTP responses. Legacy callers that expect
    only a dict result still work — the result dict contains the same
    processing_status='failed' + extraction_error fields as before.

    Audit reference: Prompt 0 GAPs 003/004/009/010; Prompt A §9 R1–R4.
    """
    from .policy_filetype import validate_upload_bytes
    from .policy_intake_errors import MalformedDocumentError, PolicyIntakeError

    result: Dict[str, Any] = {
        "raw_text": None,
        "detected_document_type": DOC_TYPE_UNKNOWN,
        "detected_policy_scope": SCOPE_UNKNOWN,
        "extracted_metadata": {},
        "processing_status": STATUS_UPLOADED,
        "extraction_error": None,
        "version_label": None,
        "effective_date": None,
    }

    try:
        # Steps 1–3: size + magic-byte sniff + encryption gate. Any failure
        # re-raises as the specific PolicyIntakeError subclass.
        sniff = validate_upload_bytes(data)

        # Step 4: extract text using the sniffed kind (claimed mime_type is
        # ignored — sniff is authoritative). A parser failure becomes
        # MalformedDocumentError.
        if sniff.kind == "pdf":
            lines, err = _extract_text_from_pdf(data)
        else:
            lines, err = _extract_text_from_docx(data)
        if err:
            raise MalformedDocumentError(f"Could not read document: {err}")
        if not lines:
            raise MalformedDocumentError("No readable text extracted from document.")

        raw_text = "\n".join(lines)
        result["raw_text"] = raw_text
        result["processing_status"] = STATUS_TEXT_EXTRACTED

        doc_type, scope, needs_review = classify_document(lines, request_id=request_id)
        result["detected_document_type"] = doc_type
        result["detected_policy_scope"] = scope
        result["processing_status"] = STATUS_CLASSIFIED if not needs_review else STATUS_REVIEW_REQUIRED

        meta = extract_metadata(lines)
        result["extracted_metadata"] = meta
        result["version_label"] = meta.get("detected_version")
        result["effective_date"] = meta.get("detected_effective_date")

    except PolicyIntakeError as e:
        # Typed rejection — record on the result dict so legacy callers see
        # it, then re-raise so the API layer can map to the right HTTP code.
        result["processing_status"] = STATUS_FAILED
        result["extraction_error"] = str(e)
        log.info(
            "request_id=%s process_uploaded_document rejected: %s (%s)",
            request_id, e.code, e,
        )
        raise
    except Exception as e:
        # Keep the catch-all for genuinely unexpected errors. Never let a
        # stray exception crash a background task.
        result["processing_status"] = STATUS_FAILED
        result["extraction_error"] = str(e)
        log.warning(
            "request_id=%s process_uploaded_document failed: %s",
            request_id,
            e,
            exc_info=True,
        )

    return result
