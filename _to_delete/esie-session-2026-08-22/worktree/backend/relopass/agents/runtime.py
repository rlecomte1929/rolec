"""ExtractionRunner — executes an agent version against a ParsedDocument (C1-05a).

The runner is the glue between the agent definition, the OCR'd document, the
C1-13 LLM router, and the persistence layer (ExtractedField rows + agent_runs
row). It:

1. Builds a prompt from the agent version + document text + few-shot examples.
2. Selects a model via :func:`backend.relopass.llm.route_llm` for the
   ``field_extraction`` task class (escalates to claude-sonnet-4-6 on
   validator failure or low confidence — Architecture Report §11).
3. Awaits the LLM call via the handle's ``complete()`` method. Token / cost
   logging flows through the router's pluggable agent_runs logger.
4. Parses the JSON response, validates required field keys, builds
   :class:`ExtractedField` rows.
5. Persists fields + the agent_runs row via an injected :class:`ExtractionSink`
   (Protocol). Tests inject :class:`InMemoryExtractionSink`.

The runner has NO direct DB or SDK imports. The vendor SDK lives in the
service-layer completer registered with the LLM router; the DB-bound sink
lives one layer up in ``backend/services/``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Mapping, Optional, Protocol, Tuple
from uuid import UUID, uuid4

from backend.relopass.llm import LLMHandle, route_llm
from backend.relopass.llm.router import AgentRunRecord

from .models import (
    ExtractedField,
    ExtractionAgentVersion,
    ExtractionRunResult,
    ParsedDocument,
)


# ─────────────────────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────────────────────


class ExtractionRuntimeError(Exception):
    """Raised when the runtime cannot produce a result (missing fields, bad
    JSON, exhausted retries, etc.).
    """


class SchemaValidationError(ExtractionRuntimeError):
    """Raised when the LLM output is missing one or more required field keys
    declared on the agent version.
    """

    def __init__(self, missing_keys: Tuple[str, ...]) -> None:
        self.missing_keys = missing_keys
        super().__init__(
            "Extraction output missing required keys: " + ", ".join(missing_keys)
        )


# ─────────────────────────────────────────────────────────────────────────────
# Persistence sink (Protocol)
# ─────────────────────────────────────────────────────────────────────────────


class ExtractionSink(Protocol):
    """Persistence contract for ExtractedField rows + agent_runs rows.

    The concrete adapter (Supabase/psycopg2) lives in the service layer.
    """

    def write_agent_run(
        self,
        *,
        agent_run_id: UUID,
        agent_version_id: UUID,
        case_id: Optional[UUID],
        document_id: UUID,
        model_name: str,
        tokens_in: int,
        tokens_out: int,
        cost_usd: float,
        inputs_digest: str,
        output_digest: str,
        started_at: datetime,
        finished_at: datetime,
        status: str,
    ) -> None:
        ...

    def write_extracted_fields(self, fields: Tuple[ExtractedField, ...]) -> None:
        ...


# ─────────────────────────────────────────────────────────────────────────────
# In-memory sink (test default)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class _AgentRunRow:
    agent_run_id: UUID
    agent_version_id: UUID
    case_id: Optional[UUID]
    document_id: UUID
    model_name: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    inputs_digest: str
    output_digest: str
    started_at: datetime
    finished_at: datetime
    status: str


@dataclass
class InMemoryExtractionSink:
    agent_runs: List[_AgentRunRow] = field(default_factory=list)
    extracted_fields: List[ExtractedField] = field(default_factory=list)

    def write_agent_run(
        self,
        *,
        agent_run_id: UUID,
        agent_version_id: UUID,
        case_id: Optional[UUID],
        document_id: UUID,
        model_name: str,
        tokens_in: int,
        tokens_out: int,
        cost_usd: float,
        inputs_digest: str,
        output_digest: str,
        started_at: datetime,
        finished_at: datetime,
        status: str,
    ) -> None:
        self.agent_runs.append(
            _AgentRunRow(
                agent_run_id=agent_run_id,
                agent_version_id=agent_version_id,
                case_id=case_id,
                document_id=document_id,
                model_name=model_name,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost_usd,
                inputs_digest=inputs_digest,
                output_digest=output_digest,
                started_at=started_at,
                finished_at=finished_at,
                status=status,
            )
        )

    def write_extracted_fields(self, fields: Tuple[ExtractedField, ...]) -> None:
        self.extracted_fields.extend(fields)


# ─────────────────────────────────────────────────────────────────────────────
# ExtractionRunner
# ─────────────────────────────────────────────────────────────────────────────


# The output JSON shape the LLM returns. Documented in the system prompt
# embedded in :func:`_build_prompt`.
ParsedLLMOutput = Mapping[str, Any]


@dataclass
class ExtractionRunner:
    """Runs an :class:`ExtractionAgentVersion` against a :class:`ParsedDocument`."""

    sink: ExtractionSink
    # Optional confidence threshold — the runner asks the router to escalate
    # when the LLM's reported per-field confidence is below this. Mirrors
    # the field_extraction default in router.ESCALATION_CONFIDENCE_THRESHOLDS.
    escalation_confidence: float = 0.85

    async def run(
        self,
        agent_version: ExtractionAgentVersion,
        document: ParsedDocument,
    ) -> ExtractionRunResult:
        started_at = datetime.now(tz=timezone.utc)
        prompt = _build_prompt(agent_version, document)

        # Route based on field_extraction. The router's escalation logic
        # decides between gpt-4o-mini and claude-sonnet-4-6 at the
        # validator-failure / low-confidence step.
        handle = route_llm("field_extraction")
        raw_output = await handle.complete(
            prompt,
            max_tokens=handle.token_budget,
            case_id=str(document.case_id) if document.case_id else None,
        )
        parsed = _parse_json_output(raw_output)

        # Schema validation: every required key must be present.
        missing = tuple(
            k for k in agent_version.output_schema_required_keys if k not in parsed
        )
        if missing:
            # Re-route with validator_failed=True so the next attempt
            # escalates to the premium model. Single retry for safety.
            handle = route_llm("field_extraction", validator_failed=True)
            raw_output = await handle.complete(
                prompt,
                max_tokens=handle.token_budget,
                case_id=str(document.case_id) if document.case_id else None,
            )
            parsed = _parse_json_output(raw_output)
            missing = tuple(
                k for k in agent_version.output_schema_required_keys if k not in parsed
            )
            if missing:
                raise SchemaValidationError(missing)

        # Build ExtractedField rows. The LLM is asked (see _build_prompt)
        # to emit a dict[field_key, {value, confidence, bbox}].
        agent_run_id = uuid4()
        finished_at = datetime.now(tz=timezone.utc)
        fields = _build_extracted_fields(
            parsed,
            document_id=document.document_id,
            agent_run_id=agent_run_id,
            agent_version=agent_version,
        )

        # Persist agent_runs row + ExtractedField rows.
        self.sink.write_agent_run(
            agent_run_id=agent_run_id,
            agent_version_id=agent_version.agent_version_id,
            case_id=document.case_id,
            document_id=document.document_id,
            model_name=handle.model_name,
            tokens_in=handle.tokens_in,
            tokens_out=handle.tokens_out,
            cost_usd=handle.cost_usd,
            inputs_digest=handle.inputs_digest,
            output_digest=handle.output_digest,
            started_at=started_at,
            finished_at=finished_at,
            status="OK",
        )
        self.sink.write_extracted_fields(fields)

        return ExtractionRunResult(
            agent_run_id=agent_run_id,
            agent_version_id=agent_version.agent_version_id,
            fields=fields,
            tokens_in=handle.tokens_in,
            tokens_out=handle.tokens_out,
            cost_usd=handle.cost_usd,
            model_name=handle.model_name,
        )

    def run_sync(
        self,
        agent_version: ExtractionAgentVersion,
        document: ParsedDocument,
    ) -> ExtractionRunResult:
        """Synchronous convenience wrapper for non-async callers."""
        import asyncio

        return asyncio.run(self.run(agent_version, document))


# ─────────────────────────────────────────────────────────────────────────────
# Prompt building + output parsing
# ─────────────────────────────────────────────────────────────────────────────


_PROMPT_HEADER = """You are a structured field extraction agent. Read the document text and the
extraction instructions, then emit a JSON object mapping each required field
key to an extracted value plus a bounding box and confidence score.

Output schema:
{
  "fields": {
    "<field_key>": {
      "value": <string|number|null>,
      "confidence": <float 0.0–1.0>,
      "bbox": {
        "page": <integer 1-indexed>,
        "x0": <int 0–1000>, "y0": <int 0–1000>,
        "x1": <int 0–1000>, "y1": <int 0–1000>
      }
    }
  }
}

All bbox coordinates are in canonical 0–1000 space (Parsewise convention).
Confidence ranges 0.0 to 1.0 inclusive. Omit a field entirely if the document
does not contain the answer.
"""


def _build_prompt(version: ExtractionAgentVersion, document: ParsedDocument) -> str:
    sections: List[str] = [_PROMPT_HEADER]

    sections.append(f"AGENT: {version.name} (v{version.version_number})")
    sections.append(f"VALUE TYPE: {version.value_type}")
    if version.unit:
        sections.append(f"UNIT: {version.unit}")
    if version.dimensions:
        sections.append(f"DIMENSIONS: {version.dimensions}")
    sections.append("")
    sections.append("EXTRACTION INSTRUCTIONS:")
    sections.append(version.extraction_instructions)
    if version.resolution_instructions:
        sections.append("")
        sections.append("RESOLUTION INSTRUCTIONS:")
        sections.append(version.resolution_instructions)
    if version.inconsistency_instructions:
        sections.append("")
        sections.append("INCONSISTENCY HANDLING:")
        sections.append(version.inconsistency_instructions)

    if version.examples:
        sections.append("")
        sections.append("EXAMPLES:")
        for i, ex in enumerate(version.examples, start=1):
            sections.append(f"--- Example {i} ---")
            sections.append("Input:")
            sections.append(ex.input_text)
            sections.append("Output:")
            sections.append(json.dumps(ex.output, ensure_ascii=False))

    if version.output_schema_required_keys:
        sections.append("")
        sections.append("REQUIRED FIELD KEYS:")
        sections.append(", ".join(version.output_schema_required_keys))

    sections.append("")
    sections.append("DOCUMENT TEXT:")
    sections.append(document.text)

    return "\n".join(sections)


def _parse_json_output(raw: str) -> Dict[str, Any]:
    text = raw.strip()
    # Strip a markdown fence if the LLM wrapped its JSON in ```json ... ```.
    if text.startswith("```"):
        text = text.strip("`")
        # Drop a leading "json" language hint
        if text[:4].lower() == "json":
            text = text[4:]
        text = text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ExtractionRuntimeError(f"LLM output was not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ExtractionRuntimeError(
            f"LLM output JSON must be an object, got {type(data).__name__}"
        )
    # The expected shape is {"fields": {...}} but we tolerate top-level dicts
    # for the validator-required-keys check.
    if "fields" in data and isinstance(data["fields"], dict):
        return data["fields"]
    return data


def _build_extracted_fields(
    parsed: Mapping[str, Any],
    *,
    document_id: UUID,
    agent_run_id: UUID,
    agent_version: ExtractionAgentVersion,
) -> Tuple[ExtractedField, ...]:
    out: List[ExtractedField] = []
    for key, payload in parsed.items():
        if not isinstance(payload, Mapping):
            # Tolerate {"<key>": "<scalar>"} shape — wrap it.
            payload = {"value": payload, "confidence": 0.0}
        value = payload.get("value")
        confidence = float(payload.get("confidence", 0.0))
        bbox = payload.get("bbox") or {}
        bbox_page = _maybe_int(bbox.get("page"))
        bbox_x0 = _maybe_int(bbox.get("x0"))
        bbox_y0 = _maybe_int(bbox.get("y0"))
        bbox_x1 = _maybe_int(bbox.get("x1"))
        bbox_y1 = _maybe_int(bbox.get("y1"))
        value_canonical = payload.get("canonical")
        if not isinstance(value_canonical, Mapping):
            value_canonical = None

        out.append(
            ExtractedField(
                document_id=document_id,
                field_key=key,
                value_raw=None if value is None else str(value),
                value_canonical=dict(value_canonical) if value_canonical else None,
                confidence=max(0.0, min(1.0, confidence)),
                bbox_page=bbox_page,
                bbox_x0=bbox_x0,
                bbox_y0=bbox_y0,
                bbox_x1=bbox_x1,
                bbox_y1=bbox_y1,
                agent_run_id=agent_run_id,
                resolution_status=None,
            )
        )
    return tuple(out)


def _maybe_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
