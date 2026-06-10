"""ID_CARD Extraction Agent (C2-02 / nationality source for C2-09).

National identity cards carry an ICAO 9303 MRZ — TD1 (3×30) for most modern
cards, occasionally TD2 (2×36). The MRZ is the authoritative, deterministic
source for the identity fields this agent emits; in particular it is the second
``nationality_iso3`` source (alongside PASSPORT_TD3) that C2-09's
``_compare_nationality`` cross-checks for divergence.

Unlike PASSPORT_TD3 this agent is intentionally MRZ-only: no Azure DI / LLM
orchestration. The MRZ alone yields every field C2-09 needs, and keeping the
agent deterministic makes it cheap, offline, and trivially testable. The visual
inspection zone (photo, card-specific text) is out of scope here — a richer
DI+LLM pass can be layered on later the way PASSPORT_TD3 does.

Reuses :func:`backend.relopass.docs.mrz.parse_mrz` (C1-02), which auto-detects
TD1/TD2/TD3. Follows the C1-05a runtime contract (versioned ExtractionAgent
registered in the AgentRegistry; emits ExtractedField rows + an agent_runs row).
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Tuple
from uuid import UUID, uuid4

from backend.relopass.docs.mrz import MRZParseResult, parse_mrz

from ..models import (
    ExtractedField,
    ExtractionAgent,
    ExtractionAgentVersion,
    ParsedDocument,
)
from ..registry import AgentRegistry, SaveResult
from ..runtime import ExtractionSink
from ._common import make_field

logger = logging.getLogger(__name__)


ID_CARD_AGENT_NAME = "id_card"
ID_CARD_DOCUMENT_TYPE = "ID_CARD"

# Fields the MRZ deterministically provides. nationality_iso3 is the load-bearing
# one for C2-09's cross-document nationality check.
MRZ_FIELD_KEYS: Tuple[str, ...] = (
    "surname",
    "given_names",
    "document_number",
    "nationality_iso3",
    "issuing_state_iso3",
    "date_of_birth",
    "sex",
    "expiry_date",
)


def _build_agent() -> ExtractionAgent:
    return ExtractionAgent(
        name=ID_CARD_AGENT_NAME,
        description=(
            "ID_CARD extraction. Parses the ICAO 9303 MRZ (TD1/TD2) off a national "
            "identity card and emits the identity fields — notably nationality_iso3, "
            "the second nationality source C2-09 cross-checks against PASSPORT_TD3."
        ),
        extraction_instructions=(
            "Deterministic MRZ parse (ICAO Doc 9303). No LLM. The MRZ is the "
            "authoritative source; the visual zone is out of scope for this agent."
        ),
        value_type="string",
        unit=None,
        dimensions="structured: ICAO 9303 MRZ identity fields",
        resolution_instructions=(
            "nationality_iso3 / issuing_state_iso3 are ICAO 3-letter codes taken "
            "verbatim from the MRZ. Dates are ISO from the MRZ check-digit-validated "
            "fields. Names are the MRZ transliterated forms."
        ),
        inconsistency_instructions=(
            "If the MRZ does not parse (format=UNKNOWN), emit no fields and record "
            "the parse findings on the agent run."
        ),
        enable_web_search=False,
        enable_complex_calculations_in_resolution=False,
        examples=(),
        output_schema_required_keys=(),
    )


_AGENT_SINGLETON: Optional[ExtractionAgent] = None


def _get_agent() -> ExtractionAgent:
    global _AGENT_SINGLETON
    if _AGENT_SINGLETON is None:
        _AGENT_SINGLETON = _build_agent()
    return _AGENT_SINGLETON


@dataclass(frozen=True)
class IdCardResult:
    agent_run_id: UUID
    agent_version_id: UUID
    fields: Tuple[ExtractedField, ...]
    mrz: MRZParseResult
    mrz_findings: Tuple[object, ...]


@dataclass
class IdCardAgent:
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
            raise RuntimeError("IdCardAgent.run() called before register()")
        return self._agent_version

    def run(self, document: ParsedDocument, *, mrz_text: str) -> IdCardResult:
        """Parse the card MRZ and emit deterministic identity ExtractedFields.

        ``mrz_text`` is the MRZ string (TD1 = 3 lines, TD2 = 2 lines) read off
        the card by the OCR layer — same contract as PassportTd3Agent.run.
        """
        version = self.agent_version
        agent_run_id = uuid4()
        started_at = datetime.now(tz=timezone.utc)

        mrz = parse_mrz(mrz_text)
        fields = self._mrz_to_extracted_fields(mrz, document.document_id, agent_run_id)

        finished_at = datetime.now(tz=timezone.utc)
        inputs_digest = hashlib.sha256(mrz_text.encode("utf-8")).hexdigest()
        output_digest = hashlib.sha256(
            "|".join(f"{f.field_key}={f.value_raw}" for f in fields).encode("utf-8")
        ).hexdigest()
        self.sink.write_agent_run(
            agent_run_id=agent_run_id,
            agent_version_id=version.agent_version_id,
            case_id=document.case_id,
            document_id=document.document_id,
            model_name="deterministic_mrz_icao9303",
            tokens_in=0,
            tokens_out=0,
            cost_usd=0.0,
            inputs_digest=inputs_digest,
            output_digest=output_digest,
            started_at=started_at,
            finished_at=finished_at,
            status="OK" if mrz.is_well_formed else "PARTIAL",
        )
        self.sink.write_extracted_fields(fields)

        return IdCardResult(
            agent_run_id=agent_run_id,
            agent_version_id=version.agent_version_id,
            fields=fields,
            mrz=mrz,
            mrz_findings=tuple(mrz.findings),
        )

    def run_sync(self, document: ParsedDocument, *, mrz_text: str) -> IdCardResult:
        return self.run(document, mrz_text=mrz_text)

    @staticmethod
    def _mrz_to_extracted_fields(
        mrz: MRZParseResult, document_id: UUID, agent_run_id: UUID
    ) -> Tuple[ExtractedField, ...]:
        raw = {
            "surname": mrz.surname,
            "given_names": mrz.given_names,
            "document_number": mrz.document_number,
            "nationality_iso3": mrz.nationality_iso3,
            "issuing_state_iso3": mrz.issuing_state_iso3,
            "date_of_birth": mrz.date_of_birth.isoformat() if mrz.date_of_birth else None,
            "sex": mrz.sex,
            "expiry_date": mrz.expiry_date.isoformat() if mrz.expiry_date else None,
        }
        built = tuple(
            make_field(
                document_id=document_id,
                agent_run_id=agent_run_id,
                key=key,
                value=raw[key],
                source=f"mrz_icao9303_{mrz.format.lower()}",
            )
            for key in MRZ_FIELD_KEYS
        )
        return tuple(f for f in built if f is not None)


def load_id_card_prompt() -> str:
    """No prompt: this agent is MRZ-deterministic. Present for interface parity
    with the LLM-backed agents; returns an empty string."""
    return ""
