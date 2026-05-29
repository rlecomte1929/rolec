"""C1-04 · Document classification (LangGraph node).

First stage of the document-ingestion pipeline (Architecture Report §3.1).
Routes each uploaded file to the right Extraction Agent by classifying
its document_type_code.

Lifecycle:

1. Caller passes a :class:`ParsedDocument` (from C1-03 OCR).
2. :func:`classify_document` loads the C1-04a prompt, routes via C1-13
   for ``document_classification`` (gpt-4o-mini default), and parses
   the JSON tool-use response.
3. If confidence < 0.80, re-route with the same task class +
   ``current_confidence`` so the C1-13 router escalates to gpt-4o.
4. If post-escalation confidence < 0.50, return ``('UNKNOWN', conf)``.
5. Otherwise return ``(code, conf)``.

Every call writes one ``agent_runs`` row via an injected sink — the
prompt version, model used, token counts, and USD cost are captured for
audit + cost-tracking dashboards.

Per the ``backend/relopass`` package constraint, no module here imports
SQLAlchemy, FastAPI, or any vendor SDK. The LLM completer + DB sink are
both Protocols; tests use in-memory fakes.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Mapping,
    Optional,
    Protocol,
    Tuple,
)
from uuid import UUID, uuid4

from backend.relopass.llm import LLMRoutingError, route_llm

from .models import ParsedDocument

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────


CLASSIFIER_PROMPT_VERSION = "v1"

_PROMPT_PATH = (
    Path(__file__).resolve().parents[3]
    / "prompts"
    / "classifier"
    / "document_classifier_v1.txt"
)

# Controlled vocabulary — must match the rce.document_types catalog seeded
# by C1-01b plus the special 'UNKNOWN' sentinel.
KNOWN_DOCUMENT_CODES: Tuple[str, ...] = (
    "PASSPORT_TD3",
    "EU_NATIONAL_ID",
    "RESIDENCE_PERMIT_EU",
    "EMPLOYMENT_CONTRACT",
    "PAYSLIP",
    "DIPLOMA_BACHELOR",
    "DIPLOMA_MASTER",
    "ANABIN_EVIDENCE",
    "ZAB_STATEMENT_OF_COMPARABILITY",
    "IT_EXPERIENCE_PORTFOLIO",
    "HEALTH_INSURANCE_PROOF",
    "MARRIAGE_CERT",
    "BIRTH_CERT",
    "FOSTER_CARE_ORDER",
    "CRIMINAL_RECORD",
    "TAX_CERT",
    "HOUSING_LEASE",
)

UNKNOWN_CODE = "UNKNOWN"

# Confidence bands per the C1-04a prompt + the Architecture Report §3.1 spec.
ESCALATION_THRESHOLD = 0.80
UNKNOWN_THRESHOLD = 0.50

# Truncate document text fed to the classifier — the classifier doesn't
# need the whole document, only enough to recognise the format. Matches
# the brief's `parsed.raw_text[:8000]` snippet.
MAX_PROMPT_TEXT_CHARS = 8_000


# ─────────────────────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────────────────────


class ClassifierError(Exception):
    """Raised when classification cannot proceed (bad JSON, no completer)."""


class UnknownClassificationCode(ClassifierError):
    """Raised when the LLM emits a code not in :data:`KNOWN_DOCUMENT_CODES`."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(
            f"Classifier emitted unknown code {code!r}; expected one of "
            f"{KNOWN_DOCUMENT_CODES + (UNKNOWN_CODE,)}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Prompt loading
# ─────────────────────────────────────────────────────────────────────────────


_PROMPT_CACHE: Optional[str] = None


def load_classifier_prompt() -> str:
    """Read the C1-04a prompt from disk, caching it after the first load.

    Returns the raw prompt text. The runtime appends the document content
    after a delimiter (see :func:`_build_prompt`).
    """
    global _PROMPT_CACHE
    if _PROMPT_CACHE is None:
        _PROMPT_CACHE = _PROMPT_PATH.read_text(encoding="utf-8")
    return _PROMPT_CACHE


def reset_prompt_cache() -> None:
    """Test hook — drop the in-memory prompt cache."""
    global _PROMPT_CACHE
    _PROMPT_CACHE = None


def _build_prompt(document: ParsedDocument) -> str:
    base = load_classifier_prompt()
    text = document.text or ""
    if len(text) > MAX_PROMPT_TEXT_CHARS:
        text = text[:MAX_PROMPT_TEXT_CHARS]
    return f"{base}\n\n=== INPUT DOCUMENT ===\n\n{text}"


# ─────────────────────────────────────────────────────────────────────────────
# agent_runs sink Protocol (write-only)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ClassifierAgentRun:
    """The shape we write per classification call.

    Mirrors the C1-01 ``rce.agent_runs`` columns plus the prompt version
    + tier used. The production sink (future task in `backend/services/`)
    INSERTs into ``rce.agent_runs``; tests use the in-memory fake.
    """

    agent_run_id: UUID
    document_id: UUID
    case_id: Optional[UUID]
    agent_id: str
    prompt_version: str
    model_name: str
    tier: str  # "default" | "escalated" | "unrouted"
    tokens_in: int
    tokens_out: int
    cost_usd: float
    inputs_digest: str
    output_digest: str
    started_at: datetime
    finished_at: datetime
    status: str  # "OK" | "FAILED"
    final_code: str
    final_confidence: float


class ClassifierAgentRunSink(Protocol):
    """Persistence contract."""

    def write_classifier_run(self, run: ClassifierAgentRun) -> None:
        ...


@dataclass
class InMemoryClassifierAgentRunSink:
    runs: List[ClassifierAgentRun] = field(default_factory=list)

    def write_classifier_run(self, run: ClassifierAgentRun) -> None:
        self.runs.append(run)


# ─────────────────────────────────────────────────────────────────────────────
# Output parsing
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ClassifierResult:
    """What :func:`classify_document` returns."""

    code: str
    confidence: float
    evidence: str
    tier: str
    model_name: str
    agent_run_id: UUID


def _parse_classifier_output(raw: str) -> Mapping[str, Any]:
    """Parse the JSON tool-use response. Tolerates markdown fences and
    the Anthropic-style ``{"input": {...}}`` wrapper.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text[:4].lower() == "json":
            text = text[4:]
        text = text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ClassifierError(f"LLM output was not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ClassifierError(
            f"LLM output JSON must be an object, got {type(data).__name__}"
        )
    if "input" in data and isinstance(data["input"], dict):
        data = data["input"]
    return data


def _validate_classifier_output(payload: Mapping[str, Any]) -> Tuple[str, float, str]:
    code = payload.get("code")
    if not isinstance(code, str):
        raise ClassifierError(f"missing or non-string code in payload: {payload!r}")
    code_norm = code.strip().upper()
    if code_norm not in KNOWN_DOCUMENT_CODES and code_norm != UNKNOWN_CODE:
        raise UnknownClassificationCode(code_norm)

    confidence = payload.get("confidence")
    if not isinstance(confidence, (int, float)):
        raise ClassifierError(f"missing or non-numeric confidence: {payload!r}")
    conf_norm = max(0.0, min(1.0, float(confidence)))

    evidence = payload.get("evidence", "")
    if not isinstance(evidence, str):
        raise ClassifierError(f"evidence must be a string, got {type(evidence).__name__}")

    return code_norm, conf_norm, evidence


# ─────────────────────────────────────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────────────────────────────────────


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


async def classify_document(
    document: ParsedDocument,
    *,
    sink: ClassifierAgentRunSink,
    agent_id: str = "document_classifier_v1",
) -> ClassifierResult:
    """Classify ``document`` into one of the 17 doc-type codes (or UNKNOWN).

    Args:
        document: ParsedDocument from C1-03 OCR (text + case_id +
            document_id).
        sink: where to write the agent_runs row for this call.
        agent_id: identifier stored alongside agent_runs. Defaults to
            ``document_classifier_v1``.

    Returns a :class:`ClassifierResult` carrying the chosen code,
    confidence (the final value AFTER any escalation), evidence string,
    which tier produced it ('default' / 'escalated' / 'unrouted'), and
    the agent_run_id.

    Raises :class:`ClassifierError` on malformed LLM output or when the
    LLM router has no completer registered (no graceful degradation —
    the classifier is the entry point of the pipeline; a silent failure
    would break every downstream agent).
    """
    started_at = datetime.now(tz=timezone.utc)
    agent_run_id = uuid4()
    prompt = _build_prompt(document)
    inputs_digest = _digest(prompt)

    # First pass — gpt-4o-mini default for document_classification.
    try:
        handle = route_llm("document_classification")
    except LLMRoutingError as exc:
        raise ClassifierError(f"LLM routing failed: {exc}") from exc

    try:
        raw = await handle.complete(
            prompt,
            max_tokens=handle.token_budget,
            case_id=str(document.case_id) if document.case_id else None,
        )
    except LLMRoutingError as exc:
        raise ClassifierError(
            f"No completer registered for {handle.model_name!r} — "
            "classifier cannot proceed; this is the pipeline entry point."
        ) from exc

    payload = _parse_classifier_output(raw)
    code, confidence, evidence = _validate_classifier_output(payload)
    output_digest = _digest(raw)
    tier = "default"
    model_name = handle.model_name
    tokens_in = handle.tokens_in
    tokens_out = handle.tokens_out
    cost = handle.cost_usd

    # Escalation: gpt-4o handle for the second pass when confidence is below
    # the §11 threshold. The router supplies the escalated handle when we
    # pass current_confidence.
    if confidence < ESCALATION_THRESHOLD:
        try:
            handle2 = route_llm(
                "document_classification",
                current_confidence=confidence,
            )
        except LLMRoutingError as exc:
            raise ClassifierError(f"escalation routing failed: {exc}") from exc

        # Only call again if the router actually picked a different model.
        if handle2.model_name != handle.model_name:
            try:
                raw2 = await handle2.complete(
                    prompt,
                    max_tokens=handle2.token_budget,
                    case_id=str(document.case_id) if document.case_id else None,
                )
            except LLMRoutingError as exc:
                raise ClassifierError(
                    f"No completer registered for {handle2.model_name!r} "
                    "on escalation."
                ) from exc
            payload2 = _parse_classifier_output(raw2)
            code, confidence, evidence = _validate_classifier_output(payload2)
            output_digest = _digest(raw2)
            tier = "escalated"
            model_name = handle2.model_name
            tokens_in += handle2.tokens_in
            tokens_out += handle2.tokens_out
            cost += handle2.cost_usd

    # Below-floor confidence → UNKNOWN (route to human-review queue).
    if confidence < UNKNOWN_THRESHOLD and code != UNKNOWN_CODE:
        code = UNKNOWN_CODE

    finished_at = datetime.now(tz=timezone.utc)
    sink.write_classifier_run(
        ClassifierAgentRun(
            agent_run_id=agent_run_id,
            document_id=document.document_id,
            case_id=document.case_id,
            agent_id=agent_id,
            prompt_version=CLASSIFIER_PROMPT_VERSION,
            model_name=model_name,
            tier=tier,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost,
            inputs_digest=inputs_digest,
            output_digest=output_digest,
            started_at=started_at,
            finished_at=finished_at,
            status="OK",
            final_code=code,
            final_confidence=confidence,
        )
    )

    return ClassifierResult(
        code=code,
        confidence=confidence,
        evidence=evidence,
        tier=tier,
        model_name=model_name,
        agent_run_id=agent_run_id,
    )


def classify_document_sync(
    document: ParsedDocument,
    *,
    sink: ClassifierAgentRunSink,
    agent_id: str = "document_classifier_v1",
) -> ClassifierResult:
    """Synchronous convenience wrapper for non-async callers."""
    import asyncio

    return asyncio.run(classify_document(document, sink=sink, agent_id=agent_id))


# ─────────────────────────────────────────────────────────────────────────────
# Public surface
# ─────────────────────────────────────────────────────────────────────────────


__all__ = [
    "CLASSIFIER_PROMPT_VERSION",
    "ESCALATION_THRESHOLD",
    "KNOWN_DOCUMENT_CODES",
    "UNKNOWN_CODE",
    "UNKNOWN_THRESHOLD",
    "ClassifierAgentRun",
    "ClassifierAgentRunSink",
    "ClassifierError",
    "ClassifierResult",
    "InMemoryClassifierAgentRunSink",
    "UnknownClassificationCode",
    "classify_document",
    "classify_document_sync",
    "load_classifier_prompt",
    "reset_prompt_cache",
]
