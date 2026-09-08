"""VISA_PERMIT Extraction Agent (AIQ-1309 follow-up).

Turns entry-visa / work-permit / residence-permit documents from OCR-text-only
into structured fields. These documents already flow through the live immigration
/ rce pipeline as the generic ``OTHER`` type (Mistral OCR → text) but, unlike the
family-document types, had no structured extractor — this closes that gap.

Emits the load-bearing fields the roadmap consumes — ``visa_type``,
``expiry_date`` (drives renewal deadlines), ``issue_date``, ``issuing_country``,
``document_number``, ``visa_holder_name`` — plus an optional ``entry_conditions``
carry-through. Mirrors the MARRIAGE_CERT agent's registry+sink contract exactly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Tuple
from uuid import UUID, uuid4

from backend.relopass.normalize import parse_date

from ..models import (
    ExtractedField,
    ExtractionAgent,
    ExtractionAgentVersion,
    ParsedDocument,
)
from ..registry import AgentRegistry, SaveResult
from ..runtime import ExtractionSink
from ._common import call_llm_with_retry, make_field

logger = logging.getLogger(__name__)


VISA_PERMIT_AGENT_NAME = "visa_permit"
VISA_PERMIT_DOCUMENT_TYPE = "VISA_PERMIT"


_PROMPT_PATH = (
    Path(__file__).resolve().parents[4]
    / "prompts"
    / "extraction"
    / "visa_permit_v1.txt"
)


def load_visa_permit_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _build_agent() -> ExtractionAgent:
    return ExtractionAgent(
        name=VISA_PERMIT_AGENT_NAME,
        description=(
            "VISA_PERMIT extraction. Emits visa_type, document_number, "
            "visa_holder_name, issue_date, expiry_date, issuing_country, and an "
            "optional entry_conditions carry-through. expiry_date feeds roadmap "
            "renewal deadlines."
        ),
        extraction_instructions=load_visa_permit_prompt(),
        value_type="string",
        unit=None,
        dimensions="structured: visa type + number + holder + issue/expiry dates + country",
        resolution_instructions=(
            "Dates normalised to ISO via the C1-06 date library with a country "
            "locale hint. issuing_country maps to the AUTHORITY/COUNTRY canonical "
            "entity. visa_type is verbatim; downstream routing maps it to a class."
        ),
        inconsistency_instructions=(
            "Ambiguous → null + findings entry. A plain passport is NOT a "
            "visa_permit (is_visa_permit=false); the PASSPORT agent handles those."
        ),
        enable_web_search=False,
        enable_complex_calculations_in_resolution=False,
        examples=(),
        output_schema_required_keys=("is_visa_permit",),
    )


_AGENT_SINGLETON: Optional[ExtractionAgent] = None


def _get_agent() -> ExtractionAgent:
    global _AGENT_SINGLETON
    if _AGENT_SINGLETON is None:
        _AGENT_SINGLETON = _build_agent()
    return _AGENT_SINGLETON


@dataclass(frozen=True)
class VisaPermitResult:
    agent_run_id: UUID
    agent_version_id: UUID
    fields: Tuple[ExtractedField, ...]
    llm_payload: Mapping[str, Any]
    model_name: str
    tokens_in: int
    tokens_out: int
    cost_usd: float


@dataclass
class VisaPermitAgent:
    registry: AgentRegistry
    sink: ExtractionSink
    agent_override: Optional[ExtractionAgent] = None
    _agent_version: Optional[ExtractionAgentVersion] = field(
        default=None, init=False, repr=False
    )

    def register(self) -> SaveResult:
        agent = self.agent_override or _get_agent()
        result = self.registry.save_agent(agent)
        self._agent_version = result.version
        return result

    @property
    def agent_version(self) -> ExtractionAgentVersion:
        if self._agent_version is None:
            raise RuntimeError("VisaPermitAgent.run() called before register()")
        return self._agent_version

    async def run(self, document: ParsedDocument) -> VisaPermitResult:
        version = self.agent_version
        agent_run_id = uuid4()
        started_at = datetime.now(tz=timezone.utc)

        prompt = (
            load_visa_permit_prompt()
            + "\n\n=== DOCUMENT TEXT ===\n\n"
            + document.text
        )
        llm = await call_llm_with_retry(
            prompt,
            required_keys=version.output_schema_required_keys,
            case_id=str(document.case_id) if document.case_id else None,
        )
        payload = llm.payload

        country_hint = payload.get("country_iso3")
        issue_date = _normalize_date(payload.get("issue_date"), country_hint)
        expiry_date = _normalize_date(payload.get("expiry_date"), country_hint)

        raw_fields = (
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="visa_type",
                value=payload.get("visa_type"),
                source="llm_visa_permit_v1",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="document_number",
                value=payload.get("document_number"),
                source="llm_visa_permit_v1",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="visa_holder_name",
                value=payload.get("visa_holder_name"),
                source="llm_visa_permit_v1",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="issue_date",
                value=issue_date.isoformat() if issue_date else None,
                source="llm+normalize_dates",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="expiry_date",
                value=expiry_date.isoformat() if expiry_date else None,
                source="llm+normalize_dates",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="issuing_country",
                value=payload.get("issuing_country"),
                source="llm_visa_permit_v1",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="entry_conditions",
                value=payload.get("entry_conditions"),
                source="llm_visa_permit_v1",
            ),
        )
        fields = tuple(f for f in raw_fields if f is not None)

        finished_at = datetime.now(tz=timezone.utc)
        self.sink.write_agent_run(
            agent_run_id=agent_run_id,
            agent_version_id=version.agent_version_id,
            case_id=document.case_id,
            document_id=document.document_id,
            model_name=llm.model_name,
            tokens_in=llm.tokens_in,
            tokens_out=llm.tokens_out,
            cost_usd=llm.cost_usd,
            inputs_digest=llm.inputs_digest,
            output_digest=llm.output_digest,
            started_at=started_at,
            finished_at=finished_at,
            status="OK",
        )
        self.sink.write_extracted_fields(fields)

        return VisaPermitResult(
            agent_run_id=agent_run_id,
            agent_version_id=version.agent_version_id,
            fields=fields,
            llm_payload=payload,
            model_name=llm.model_name,
            tokens_in=llm.tokens_in,
            tokens_out=llm.tokens_out,
            cost_usd=llm.cost_usd,
        )

    def run_sync(self, document: ParsedDocument) -> VisaPermitResult:
        import asyncio

        return asyncio.run(self.run(document))


def _normalize_date(raw: Any, country_iso3: Any) -> Optional[date]:
    if not raw:
        return None
    hint = {"FRA": "fr", "DEU": "de", "NOR": "no"}.get(country_iso3, None)
    parsed = parse_date(str(raw), locale_hint=hint)
    if parsed.iso is None:
        return None
    return date.fromisoformat(parsed.iso)
