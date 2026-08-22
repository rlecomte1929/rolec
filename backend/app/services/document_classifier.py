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

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .document_type_vocabulary import (
    CLASSIFIER_PENDING_RUNTIME,
    CLASSIFIER_TO_RUNTIME,
    runtime_code_for,
)
from .pii_masker import mask_pii

log = logging.getLogger(__name__)


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


# ─────────────────────────────────────────────────────────────────────────────
# [AIQ-1854] Content-based classification
# ─────────────────────────────────────────────────────────────────────────────

_PROMPT_PATH = (
    Path(__file__).resolve().parents[3] / "prompts" / "docs" / "classifier" / "v1.txt"
)

#: The codes the C1-04a prompt is allowed to emit. Anything else from the model is
#: treated as a refusal, not as a new code — the prompt states its own closed set and
#: an unrecognised string is far more likely to be a hallucination than a discovery.
_PROMPT_CODES: frozenset = frozenset(
    set(CLASSIFIER_TO_RUNTIME) | set(CLASSIFIER_PENDING_RUNTIME) | {"UNKNOWN"}
)

#: Below this the prompt itself says to return UNKNOWN, so a code arriving under it is
#: a contradiction of the prompt's own contract and is not acted on.
_MIN_CONFIDENCE = 0.5

METHOD_CONTENT = "content"
METHOD_FILENAME_FALLBACK = "filename_fallback"


@dataclass(frozen=True)
class Classification:
    """What an upload was judged to be, and how that judgement was reached.

    ``runtime_code`` is the only field the orchestrator should route on. It is None
    whenever nothing downstream can act on the result — an UNKNOWN, a Cohort-1 code
    with no agent yet (see ``CLASSIFIER_PENDING_RUNTIME``), or any fallback. None means
    "do not extract", never "try the nearest agent".

    ``method`` records whether the content classifier or the filename heuristic
    produced this, and ``fallback_reason`` says why the fallback ran. A silent
    downgrade to filename matching is indistinguishable from a working classifier,
    which is exactly the failure this module already had once.
    """

    code: str
    runtime_code: Optional[str]
    confidence: Optional[float]
    method: str
    signals: tuple = ()
    fallback_reason: Optional[str] = None


def _heuristic_classification(
    file_name: Optional[str], mime_type: Optional[str], reason: str
) -> "Classification":
    """The MVP heuristic, wrapped as a Classification and honestly labelled.

    ``runtime_code`` is deliberately None. The heuristic's four values
    (PASSPORT / CONTRACT / PAYSLIP / OTHER) are not runtime codes and never were —
    measured 2026-08-22, ``runtime_code_for`` returns None for all four, so the
    fallback has never been able to route anything. Pretending otherwise by
    nearest-matching PASSPORT onto PASSPORT_TD3 would send an unverified filename
    guess to a real extractor.
    """
    return Classification(
        code=classify_document(file_name, mime_type),
        runtime_code=None,
        confidence=None,
        method=METHOD_FILENAME_FALLBACK,
        fallback_reason=reason,
    )


def classify_document_content(
    text: Optional[str],
    *,
    file_name: Optional[str] = None,
    mime_type: Optional[str] = None,
    complete_fn=None,
) -> "Classification":
    """Classify an uploaded document from its TEXT, falling back to the filename.

    This is the real C1-04a classifier the module docstring promised. It reads the
    document's content, so a payslip named ``scan_001.pdf`` is a payslip and a holiday
    photo named ``my_contract.pdf`` is not a contract.

    **Never raises.** Classification sits on an ingest path; raising there strands the
    upload. Every failure — no text, no prompt, LLM error, timeout, unparseable or
    out-of-vocabulary response, confidence below the prompt's own floor — degrades to
    the filename heuristic and RECORDS that it did, via ``method`` and
    ``fallback_reason``.

    **PII is masked before the call.** The document text is the most PII-dense payload
    in the product; ``mask_pii`` runs on it before it reaches an LLM sub-processor
    (CLAUDE.md, GDPR Art. 28/44).

    ``complete_fn`` is injected for tests so the unit suite never needs a key or a
    network; production leaves it None and the real client is imported lazily.
    """
    if not (text or "").strip():
        return _heuristic_classification(
            file_name, mime_type, "no extracted text to classify"
        )

    try:
        prompt_template = _PROMPT_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        log.warning("document_classifier: prompt unreadable (%s) — using filename", exc)
        return _heuristic_classification(
            file_name, mime_type, f"classifier prompt unreadable: {exc}"
        )

    # GDPR Art. 28/44 — mask before the sub-processor sees it, not after.
    masked = mask_pii(text)
    user_prompt = prompt_template.replace("{{ document_text }}", masked)

    try:
        if complete_fn is None:
            from .llm_client import complete_text_sync as complete_fn  # type: ignore
        raw = complete_fn(
            system="You are a document classifier. Reply with JSON only.",
            user=user_prompt,
            json_object=True,
            temperature=0.0,
        )
        payload = json.loads(raw)
        code = str(payload["code"]).strip().upper()
        confidence = float(payload.get("confidence") or 0.0)
        signals = tuple(str(s) for s in (payload.get("signals") or ()))
    except Exception as exc:  # noqa: BLE001 — an ingest path must not raise
        log.warning(
            "document_classifier: content classification failed (%s: %s) — using filename",
            type(exc).__name__, exc,
        )
        return _heuristic_classification(
            file_name, mime_type, f"{type(exc).__name__}: {exc}"
        )

    if code not in _PROMPT_CODES:
        return _heuristic_classification(
            file_name, mime_type, f"model returned out-of-vocabulary code {code!r}"
        )
    if confidence < _MIN_CONFIDENCE:
        return _heuristic_classification(
            file_name,
            mime_type,
            f"confidence {confidence:.2f} below the prompt's own {_MIN_CONFIDENCE} floor",
        )

    # runtime_code_for returns None for UNKNOWN and for classified-but-unsupported
    # codes. That is a fail-soft skip, and it must stay None — see its docstring.
    return Classification(
        code=code,
        runtime_code=runtime_code_for(code),
        confidence=confidence,
        method=METHOD_CONTENT,
        signals=signals,
    )
