"""Document classification — deciding what an uploaded file IS.

Moved here from ``document_extraction_queue`` (AIQ-1764 ruling, 2026-08-04). The
move is behaviour-neutral; only the home changes.

**Why it moved.** Two extraction paths exist, and the ruling made rce the owner
while narrowing ``document_extraction_queue`` to OCR ingest. But the rce path
*imported its classifier from* that module (``rce_ocr_parser.py`` →
``from .document_extraction_queue import classify_document``), so the pipeline
being wound down owned a function the surviving pipeline calls. Classification is
neither path's private business — it decides which agent runs — so it gets its own
module rather than living inside either.

Doing this BEFORE the real classifier lands (AIQ-1768) means that work is written
once, in its final home, instead of being written into a module being retired and
moved afterwards.

**What this is not.** ``policy_document_intake.classify_document(lines, ...)`` is a
different function with a different signature, for policy documents. The two are
unrelated despite the shared name; do not merge them.

**Output vocabulary.** The 4 values below are the MVP heuristic's own, and they do
NOT match ``rce.document_types``. ``document_type_vocabulary`` holds the canonical
mapping and is the thing AIQ-1768 must map onto — measured 2026-08-04, the real
classifier and the runtime registry shared exactly ONE code, so swapping in a
better classifier without that mapping would emit codes no agent can act on.
"""
from __future__ import annotations

from typing import Optional


def classify_document(file_name: Optional[str], mime_type: Optional[str]) -> str:
    """MVP heuristic classifier (the C1-05 classifier isn't on main yet).

    Returns PASSPORT | CONTRACT | PAYSLIP | OTHER from filename keywords.

    Known-weak by design and slated for replacement (AIQ-1768): a payslip named
    ``scan_001.pdf`` returns OTHER and is never extracted, while a holiday photo
    named ``my_contract.pdf`` routes to the contract extractor. It is retained as
    the fail-soft fallback for when the real classifier errors or times out —
    classification sits on an ingest path, so raising there strands uploads.
    """
    name = (file_name or "").lower()
    if "passport" in name:
        return "PASSPORT"
    if "contract" in name:
        return "CONTRACT"
    if "payslip" in name or "pay_slip" in name or "salary" in name:
        return "PAYSLIP"
    return "OTHER"
