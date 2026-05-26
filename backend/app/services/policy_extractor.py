import io
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from datetime import datetime

logger = logging.getLogger(__name__)


# Deterministic category mapping per MVP spec
CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "housing": ["temporary housing", "housing", "rental", "deposit", "accommodation"],
    "movers": ["shipment", "household goods", "movers", "moving", "freight", "shipping"],
    "schools": ["education", "school", "tuition", "childcare"],
    "immigration": ["visa", "immigration", "work permit", "residence permit"],
    "travel": ["travel", "flight", "airfare", "scouting trip", "pre-assignment visit"],
    "settling_in": ["settling-in", "settling in", "allowance"],
    "tax": ["tax assistance", "tax equalization", "tax"],
    "spouse": ["spousal support", "spouse", "partner support"],
    "integration": ["language", "cultural", "integration", "training"],
    "repatriation": ["repatriation", "return shipment", "return travel"],
    "home_sale": ["home sale", "home purchase", "property sale", "property purchase"],
}

# benefit_key, label, keywords, category
BENEFIT_KEYS: List[Tuple[str, str, List[str], str]] = [
    ("temporary_housing", "Temporary housing duration", ["temporary housing", "temporary accommodation"], "housing"),
    ("rental_deposit", "Rental deposit support", ["deposit", "rental deposit"], "housing"),
    ("shipment", "Shipment of household goods", ["shipment", "household goods", "moving"], "movers"),
    ("education_support", "Education support", ["education", "school", "tuition"], "schools"),
    ("visa_support", "Visa & immigration support", ["visa", "immigration", "work permit"], "immigration"),
    ("travel_host", "Travel to host location", ["travel", "flight", "airfare"], "travel"),
    ("settling_in_allowance", "Settling-in allowance", ["settling-in", "settling in allowance"], "settling_in"),
    ("tax_assistance", "Tax assistance", ["tax assistance", "tax equalization"], "tax"),
    ("spousal_support", "Spousal support", ["spousal", "partner support"], "spouse"),
    ("language_training", "Language/cultural training", ["language", "cultural", "training"], "integration"),
    ("repatriation", "Repatriation", ["repatriation", "return shipment"], "repatriation"),
    ("scouting_trip", "Scouting trip", ["scouting trip", "pre-assignment visit"], "travel"),
    ("home_sale_purchase", "Home sale/purchase", ["home sale", "home purchase", "property sale", "property purchase"], "home_sale"),
]


def _normalize_text(lines: List[str]) -> List[str]:
    cleaned = []
    for line in lines:
        if not line:
            continue
        s = re.sub(r"\s+", " ", line.strip())
        if s:
            cleaned.append(s)
    return cleaned


def _extract_text_from_docx(data: bytes) -> List[str]:
    try:
        from docx import Document  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("python-docx is required for .docx extraction") from exc
    doc = Document(io.BytesIO(data))
    lines: List[str] = []
    for p in doc.paragraphs:
        lines.append(p.text or "")
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text]
            if cells:
                lines.append(" | ".join(cells))
    return _normalize_text(lines)


def _extract_text_from_pdf(data: bytes) -> List[str]:
    try:
        import pdfplumber  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("pdfplumber is required for .pdf extraction") from exc
    lines: List[str] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines.extend(text.splitlines())
            for table in page.extract_tables() or []:
                for row in table:
                    cells = [c for c in row if c]
                    if cells:
                        lines.append(" | ".join(cells))
    return _normalize_text(lines)


def _guess_meta(lines: List[str]) -> Dict[str, Any]:
    title = ""
    version = ""
    effective_date = None
    for line in lines[:60]:
        if not title and "policy" in line.lower():
            title = line
        if not version:
            m = re.search(r"(version|v\.)\s*([0-9]+(?:\.[0-9]+)?)", line, re.I)
            if m:
                version = m.group(2)
        if not effective_date:
            m = re.search(r"(effective|valid from)\s*[:\-]?\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", line, re.I)
            if m:
                effective_date = m.group(2)
            if not m:
                m = re.search(r"([0-9]{1,2}[/\-][0-9]{1,2}[/\-][0-9]{4})", line)
                if m:
                    d = m.group(1)
                    parts = re.split(r"[/\-]", d)
                    if len(parts) == 3:
                        y, mo, day = (parts[2], parts[0], parts[1]) if len(parts[2]) == 4 else (parts[2], parts[1], parts[0])
                        effective_date = f"{y}-{mo.zfill(2)}-{day.zfill(2)}"
            if not m:
                m = re.search(r"([0-9]{4})-([0-9]{2})-([0-9]{2})", line)
                if m:
                    effective_date = m.group(0)
    return {
        "title": title or "Relocation Policy",
        "version": version or None,
        "effective_date": effective_date,
    }


def _extract_limits(text: str) -> Dict[str, Any]:
    limits: Dict[str, Any] = {}
    day_match = re.search(r"(\d{1,3})\s*(days|day)\b", text, re.I)
    if day_match:
        limits["days"] = int(day_match.group(1))
    percent_match = re.search(r"(\d{1,3})\s*%", text)
    if percent_match:
        limits["percent"] = int(percent_match.group(1))
    amounts: Dict[str, float] = {}
    # Location-specific caps: "Oslo NOK 30,000", "NY USD 6000", "London GBP 4500"
    for m in re.finditer(r"([A-Za-z]+)\s+(NOK|USD|EUR|GBP|SGD)\s+([0-9][0-9,\.]*)", text):
        loc, cur, val_str = m.group(1), m.group(2).upper(), m.group(3)
        key = f"{loc.upper().replace(' ', '_')}_{cur}"
        amounts[key] = float(val_str.replace(",", ""))
    for m in re.finditer(r"([A-Z]{2,3})\s?([0-9][0-9,\.]+)", text):
        cur = m.group(1).upper()
        if cur in ("USD", "EUR", "NOK", "GBP", "SGD"):
            amounts[cur] = float(m.group(2).replace(",", ""))
    for m in re.finditer(r"([0-9][0-9,\.]+)\s?(USD|EUR|NOK|GBP|SGD)", text, re.I):
        cur = m.group(2).upper()
        val = float(m.group(1).replace(",", ""))
        amounts[cur] = val
    if amounts:
        key = "monthly_cap" if re.search(r"month", text, re.I) else "cap"
        limits[key] = amounts
    return limits


def _extract_eligibility(text: str) -> Dict[str, Any]:
    bands = sorted(set(re.findall(r"\bB[1-4]\b", text)))
    assignment_types = []
    for k in ["Permanent", "Long-Term", "Short-Term"]:
        if re.search(k, text, re.I):
            assignment_types.append(k.lower().replace("-", "_"))
    elig: Dict[str, Any] = {}
    if bands:
        elig["bands"] = bands
    if assignment_types:
        elig["assignment_types"] = assignment_types
    return elig


def extract_policy_from_bytes(file_bytes: bytes, file_type: str) -> Dict[str, Any]:
    if file_type == "docx":
        lines = _extract_text_from_docx(file_bytes)
    elif file_type == "pdf":
        lines = _extract_text_from_pdf(file_bytes)
    else:
        raise ValueError("Unsupported file type")

    meta = _guess_meta(lines)
    benefits: List[Dict[str, Any]] = []
    seen_keys: set = set()
    current_section = ""

    for i, line in enumerate(lines):
        lower = line.lower()
        # Detect section headings (short lines, often numbered like "6.3 Temporary Housing")
        if len(line) < 80 and re.match(r"^[\d.]+\s+\w+", line):
            current_section = line.strip()

        for key, label, keywords, category in BENEFIT_KEYS:
            if key in seen_keys:
                continue
            if any(k in lower for k in keywords):
                context = " ".join(lines[max(0, i - 1) : i + 2])
                elig = _extract_eligibility(context)
                limits = _extract_limits(context)
                benefits.append(
                    {
                        "service_category": category,
                        "benefit_key": key,
                        "benefit_label": label,
                        "eligibility": elig or None,
                        "limits": limits or None,
                        "notes": None,
                        "source_section": current_section or None,
                        "source_quote": (line[:200] if len(line) > 30 else context[:200]),
                        "confidence": 0.6 if limits or elig else 0.4,
                    }
                )
                seen_keys.add(key)

    # Add fallback entries for critical categories if found in document body
    if not benefits:
        for line in lines[:80]:
            for category, keywords in CATEGORY_KEYWORDS.items():
                if any(k in line.lower() for k in keywords):
                    benefit_key = f"{category}_support"
                    if benefit_key in seen_keys:
                        continue
                    benefits.append(
                        {
                            "service_category": category,
                            "benefit_key": benefit_key,
                            "benefit_label": f"{category.replace('_', ' ').title()} support",
                            "eligibility": None,
                            "limits": _extract_limits(line) or None,
                            "notes": None,
                            "source_section": None,
                            "source_quote": line[:200],
                            "confidence": 0.3,
                        }
                    )
                    seen_keys.add(benefit_key)

    return {
        "policy_meta": meta,
        "benefits": benefits,
        "extracted_at": datetime.utcnow().isoformat(),
        "extracted_by": "regex",
    }


# ─────────────────────────────────────────────────────────────────────────────
# AIQ-285 — LLM-augmented extraction with 3-way diff
#
# Adds an LLM extraction path alongside the deterministic regex one and
# exposes a single orchestrator that returns both results plus a merged
# preview. The merge prefers LLM values when present and falls back to regex
# for fields the LLM didn't return — concretely, the merged benefits[] list
# is the union of both, keyed by benefit_key, with LLM rows overwriting regex
# rows when both exist.
#
# The orchestrator is the surface used by the new /extract-preview endpoint.
# The original `extract_policy_from_bytes` is unchanged so the legacy auto-
# saving /extract endpoint keeps working for any caller that depends on it.
# ─────────────────────────────────────────────────────────────────────────────


def _parse_lines_from_bytes(file_bytes: bytes, file_type: str) -> List[str]:
    """Shared parsing step — used by both the regex path and the LLM path."""
    if file_type == "docx":
        return _extract_text_from_docx(file_bytes)
    if file_type == "pdf":
        return _extract_text_from_pdf(file_bytes)
    raise ValueError("Unsupported file type")


def _build_regex_extraction(lines: List[str]) -> Dict[str, Any]:
    """Re-run the existing regex extractor over pre-parsed lines.

    Mirrors `extract_policy_from_bytes` but skips the docx/pdf parse step so
    the orchestrator can hand both the regex and LLM paths the same input.
    """
    meta = _guess_meta(lines)
    benefits: List[Dict[str, Any]] = []
    seen_keys: set = set()
    current_section = ""

    for i, line in enumerate(lines):
        lower = line.lower()
        if len(line) < 80 and re.match(r"^[\d.]+\s+\w+", line):
            current_section = line.strip()
        for key, label, keywords, category in BENEFIT_KEYS:
            if key in seen_keys:
                continue
            if any(k in lower for k in keywords):
                context = " ".join(lines[max(0, i - 1) : i + 2])
                elig = _extract_eligibility(context)
                limits = _extract_limits(context)
                benefits.append(
                    {
                        "service_category": category,
                        "benefit_key": key,
                        "benefit_label": label,
                        "eligibility": elig or None,
                        "limits": limits or None,
                        "notes": None,
                        "source_section": current_section or None,
                        "source_quote": (line[:200] if len(line) > 30 else context[:200]),
                        "confidence": 0.6 if limits or elig else 0.4,
                    }
                )
                seen_keys.add(key)

    return {
        "policy_meta": meta,
        "benefits": benefits,
        "extracted_at": datetime.utcnow().isoformat(),
        "extracted_by": "regex",
    }


def _merge_extractions(
    regex_result: Dict[str, Any],
    llm_result: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Produce a merged extraction.

    Rules:
    - When the LLM result is None, the merged result is the regex result with
      `extracted_by="regex"`.
    - When both exist, prefer LLM-extracted benefits (by benefit_key); fall
      back to regex for keys the LLM missed.
    - Policy meta prefers LLM when present, else regex.
    """
    if not llm_result:
        return {**regex_result, "extracted_by": "regex"}

    regex_benefits = {b.get("benefit_key"): b for b in regex_result.get("benefits", []) if isinstance(b, dict)}
    llm_benefits = {b.get("benefit_key"): b for b in llm_result.get("benefits", []) if isinstance(b, dict)}
    merged_keys = list(llm_benefits.keys()) + [k for k in regex_benefits if k not in llm_benefits]
    merged_benefits: List[Dict[str, Any]] = []
    for key in merged_keys:
        if key in llm_benefits:
            row = dict(llm_benefits[key])
            row["extracted_by"] = "ai"
            merged_benefits.append(row)
        else:
            row = dict(regex_benefits[key])
            row["extracted_by"] = "regex"
            merged_benefits.append(row)

    regex_meta = regex_result.get("policy_meta") or {}
    llm_meta = llm_result.get("policy_meta") or {}
    merged_meta = {
        "title": llm_meta.get("title") or regex_meta.get("title"),
        "version": llm_meta.get("version") or regex_meta.get("version"),
        "effective_date": llm_meta.get("effective_date") or regex_meta.get("effective_date"),
    }
    return {
        "policy_meta": merged_meta,
        "benefits": merged_benefits,
        "extracted_at": datetime.utcnow().isoformat(),
        "extracted_by": "merged",
    }


def extract_policy_with_diff(file_bytes: bytes, file_type: str) -> Dict[str, Any]:
    """Run regex + LLM extraction over a policy document and return a 3-way diff.

    The shape is::

        {
            "regex_extracted": { policy_meta, benefits, extracted_at, extracted_by="regex" },
            "llm_extracted":   { ... } | None,
            "merged":          { policy_meta, benefits, extracted_at, extracted_by="ai"|"regex"|"merged" },
            "llm_used":        bool,
            "llm_unavailable_reason": "no_api_key" | "sdk_missing" | "call_failed" | "parse_failed" | None,
        }

    The caller is responsible for deciding what to do with the result — the
    new ``/extract-preview`` endpoint returns it verbatim to the Policy Builder
    UI; the legacy ``/extract`` endpoint does not call this orchestrator.
    """
    lines = _parse_lines_from_bytes(file_bytes, file_type)

    regex_result = _build_regex_extraction(lines)

    llm_result: Optional[Dict[str, Any]] = None
    llm_unavailable_reason: Optional[str] = None
    try:
        # Import locally so the regex-only path doesn't pay the cost / risk
        # of pulling the LLM module into modules that never need it.
        from .llm_policy_extractor import extract_policy_with_llm

        llm_result = extract_policy_with_llm(lines)
        if llm_result is None:
            # The LLM module logs the specific reason; here we just record
            # that it was unavailable so the UI can decide whether to warn.
            import os as _os
            if not _os.environ.get("ANTHROPIC_API_KEY"):
                llm_unavailable_reason = "no_api_key"
            else:
                llm_unavailable_reason = "call_failed"
    except ImportError:
        llm_unavailable_reason = "sdk_missing"
    except Exception as exc:  # noqa: BLE001 — never block the upload flow
        logger.warning(
            "extract_policy_with_diff: LLM layer raised unexpectedly (%s); using regex only.",
            exc.__class__.__name__,
        )
        llm_unavailable_reason = "call_failed"

    merged = _merge_extractions(regex_result, llm_result)
    return {
        "regex_extracted": regex_result,
        "llm_extracted": llm_result,
        "merged": merged,
        "llm_used": llm_result is not None,
        "llm_unavailable_reason": llm_unavailable_reason,
    }
