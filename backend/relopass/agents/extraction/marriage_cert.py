"""MARRIAGE_CERT Extraction Agent (C2-01).

The spouse half of the FamilyMember dimension. Emits the five load-bearing
fields the Cohort-2 family rules consume — spouse_1_name, spouse_2_name,
marriage_date, place_of_marriage, registering_authority — plus an OPTIONAL
``maiden_surname`` carve-out that feeds the C1-08 surname-contradiction
comparator so a post-marriage surname change is not flagged as a contradiction.

Native (non-Latin) name forms are preserved in ``*_name_native`` fields with
the Latin transliteration sitting in the standard ``spouse_N_name`` fields,
matching the DIPLOMA agent's institution_name / institution_name_native split.
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


MARRIAGE_CERT_AGENT_NAME = "marriage_cert"
MARRIAGE_CERT_DOCUMENT_TYPE = "MARRIAGE_CERT"


_PROMPT_PATH = (
    Path(__file__).resolve().parents[4]
    / "prompts"
    / "extraction"
    / "marriage_cert_v1.txt"
)


def load_marriage_cert_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _build_agent() -> ExtractionAgent:
    return ExtractionAgent(
        name=MARRIAGE_CERT_AGENT_NAME,
        description=(
            "MARRIAGE_CERT extraction. Emits spouse_1_name, spouse_2_name, "
            "marriage_date, place_of_marriage, registering_authority, and an "
            "optional maiden_surname carve-out for the C1-08 surname comparator."
        ),
        extraction_instructions=load_marriage_cert_prompt(),
        value_type="string",
        unit=None,
        dimensions="structured: two spouses + date + place + authority + maiden carve-out",
        resolution_instructions=(
            "Names normalised via C1-06 normalize_name (ICAO fold + particle "
            "handling). Devanagari preserved in *_name_native; Latin form in "
            "spouse_N_name. maiden_surname is a SEPARATE field — never merged "
            "into a spouse name. Dates normalised to ISO with a locale hint."
        ),
        inconsistency_instructions=(
            "Ambiguous → null + findings entry. A recorded maiden name is NOT a "
            "contradiction; it is the carve-out the C1-08 comparator consumes."
        ),
        enable_web_search=False,
        enable_complex_calculations_in_resolution=False,
        examples=(),
        output_schema_required_keys=("is_marriage_cert",),
    )


_AGENT_SINGLETON: Optional[ExtractionAgent] = None


def _get_agent() -> ExtractionAgent:
    global _AGENT_SINGLETON
    if _AGENT_SINGLETON is None:
        _AGENT_SINGLETON = _build_agent()
    return _AGENT_SINGLETON


@dataclass(frozen=True)
class MarriageCertResult:
    agent_run_id: UUID
    agent_version_id: UUID
    fields: Tuple[ExtractedField, ...]
    llm_payload: Mapping[str, Any]
    maiden_surname: Optional[str]
    model_name: str
    tokens_in: int
    tokens_out: int
    cost_usd: float


@dataclass
class MarriageCertAgent:
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
            raise RuntimeError("MarriageCertAgent.run() called before register()")
        return self._agent_version

    async def run(self, document: ParsedDocument) -> MarriageCertResult:
        version = self.agent_version
        agent_run_id = uuid4()
        started_at = datetime.now(tz=timezone.utc)

        prompt = (
            load_marriage_cert_prompt()
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
        marriage_date = _normalize_date(payload.get("marriage_date"), country_hint)
        native = payload.get("name_native") if isinstance(payload.get("name_native"), Mapping) else {}
        native_script = native.get("script") if native else None
        maiden_surname = payload.get("maiden_surname")

        raw_fields = (
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="spouse_1_name",
                value=payload.get("spouse_1_name"),
                source="llm_marriage_cert_v1+normalize_names",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="spouse_1_name_native",
                value=native.get("spouse_1_name") if native else None,
                source="llm_marriage_cert_v1",
                canonical_extras={"script": native_script},
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="spouse_2_name",
                value=payload.get("spouse_2_name"),
                source="llm_marriage_cert_v1+normalize_names",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="spouse_2_name_native",
                value=native.get("spouse_2_name") if native else None,
                source="llm_marriage_cert_v1",
                canonical_extras={"script": native_script},
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="marriage_date",
                value=marriage_date.isoformat() if marriage_date else None,
                source="llm+normalize_dates",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="place_of_marriage",
                value=payload.get("place_of_marriage"),
                source="llm_marriage_cert_v1",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="registering_authority",
                value=payload.get("registering_authority"),
                source="llm_marriage_cert_v1",
            ),
            # maiden_surname is the C1-08 carve-out. Recorded as its own field so
            # the surname-contradiction comparator can suppress the post-marriage
            # name-change false positive.
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="maiden_surname",
                value=maiden_surname,
                source="llm_marriage_cert_v1",
                canonical_extras={"carve_out": "C1-08_maiden_name"},
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

        return MarriageCertResult(
            agent_run_id=agent_run_id,
            agent_version_id=version.agent_version_id,
            fields=fields,
            llm_payload=payload,
            maiden_surname=maiden_surname,
            model_name=llm.model_name,
            tokens_in=llm.tokens_in,
            tokens_out=llm.tokens_out,
            cost_usd=llm.cost_usd,
        )

    def run_sync(self, document: ParsedDocument) -> MarriageCertResult:
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
