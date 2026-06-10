"""FOSTER_CARE_ORDER Extraction Agent (C2-01).

A relationship-establishing document for NON-biological dependent reunification
(FR→NO non-EEA dependent, IN→DE §27/§30 AufenthG). Treated as equivalent to a
birth certificate for the purpose of establishing a guardian↔dependent link,
so it runs the same C2-01 family-aware resolution on the guardian name against
the case's canonical PERSONs.

Emits dependent_name, guardian_name, jurisdiction, order_date, dependency_type.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, List, Mapping, Optional, Tuple
from uuid import UUID, uuid4

from backend.relopass.normalize import parse_date

from ..family_entity_resolution import (
    EntityLinkRecord,
    FamilyEntityResolver,
    ResolutionResult,
)
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


FOSTER_CARE_ORDER_AGENT_NAME = "foster_care_order"
FOSTER_CARE_ORDER_DOCUMENT_TYPE = "FOSTER_CARE_ORDER"

# Controlled vocabulary for dependency_type. OTHER is the safe fallback.
DEPENDENCY_TYPES: Tuple[str, ...] = (
    "FOSTER_CARE",
    "GUARDIANSHIP",
    "KAFALA",
    "CUSTODY",
    "OTHER",
)


_PROMPT_PATH = (
    Path(__file__).resolve().parents[4]
    / "prompts"
    / "extraction"
    / "foster_care_order_v1.txt"
)


def load_foster_care_order_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def normalize_dependency_type(raw: Optional[str]) -> str:
    """Map a raw dependency-type string to the controlled vocabulary.

    Returns ``OTHER`` for anything unrecognised — the agent never invents a
    relationship category.
    """
    if not raw:
        return "OTHER"
    upper = str(raw).strip().upper().replace(" ", "_").replace("-", "_")
    if upper in DEPENDENCY_TYPES:
        return upper
    # A few common surface forms.
    aliases = {
        "FOSTER": "FOSTER_CARE",
        "FOSTERCARE": "FOSTER_CARE",
        "GUARDIAN": "GUARDIANSHIP",
        "WARD": "GUARDIANSHIP",
        "KAFALAH": "KAFALA",
        "CUSTODIAL": "CUSTODY",
    }
    return aliases.get(upper, "OTHER")


def _build_agent() -> ExtractionAgent:
    return ExtractionAgent(
        name=FOSTER_CARE_ORDER_AGENT_NAME,
        description=(
            "FOSTER_CARE_ORDER extraction. Emits dependent_name, guardian_name, "
            "jurisdiction, order_date, dependency_type. Relationship-establishing "
            "document equivalent to a birth cert for dependent reunification; "
            "runs C1-07 resolution on the guardian name."
        ),
        extraction_instructions=load_foster_care_order_prompt(),
        value_type="string",
        unit=None,
        dimensions="structured: dependent + guardian + jurisdiction + date + type",
        resolution_instructions=(
            "dependency_type mapped to controlled vocab "
            "(FOSTER_CARE/GUARDIANSHIP/KAFALA/CUSTODY/OTHER). Guardian name "
            "resolved against case canonical PERSONs (deterministic-first, LLM "
            "fallback); a match records an entity_link and creates no new "
            "canonical. Dates normalised to ISO."
        ),
        inconsistency_instructions=(
            "Ambiguous → null + findings entry. Unknown order type → OTHER + "
            "findings. Orphan guardian surfaces Requires attention."
        ),
        enable_web_search=False,
        enable_complex_calculations_in_resolution=False,
        examples=(),
        output_schema_required_keys=("is_foster_care_order",),
    )


_AGENT_SINGLETON: Optional[ExtractionAgent] = None


def _get_agent() -> ExtractionAgent:
    global _AGENT_SINGLETON
    if _AGENT_SINGLETON is None:
        _AGENT_SINGLETON = _build_agent()
    return _AGENT_SINGLETON


@dataclass(frozen=True)
class GuardianResolution:
    name: str
    result: ResolutionResult
    canonical_entity_id: UUID
    minted_new_canonical: bool


@dataclass(frozen=True)
class FosterCareOrderResult:
    agent_run_id: UUID
    agent_version_id: UUID
    fields: Tuple[ExtractedField, ...]
    llm_payload: Mapping[str, Any]
    dependency_type: str
    dependent_canonical_entity_id: UUID
    guardian_resolution: Optional[GuardianResolution]
    entity_links: Tuple[EntityLinkRecord, ...]
    model_name: str
    tokens_in: int
    tokens_out: int
    cost_usd: float


@dataclass
class FosterCareOrderAgent:
    registry: AgentRegistry
    sink: ExtractionSink
    resolver: FamilyEntityResolver = field(default_factory=FamilyEntityResolver)
    link_sink: Optional[Any] = None
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
            raise RuntimeError("FosterCareOrderAgent.run() called before register()")
        return self._agent_version

    async def run(self, document: ParsedDocument) -> FosterCareOrderResult:
        version = self.agent_version
        agent_run_id = uuid4()
        started_at = datetime.now(tz=timezone.utc)

        prompt = (
            load_foster_care_order_prompt()
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
        order_date = _normalize_date(payload.get("order_date"), country_hint)
        dependency_type = normalize_dependency_type(payload.get("dependency_type"))
        native = payload.get("name_native") if isinstance(payload.get("name_native"), Mapping) else {}
        native_script = native.get("script") if native else None

        raw_fields = [
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="dependent_name",
                value=payload.get("dependent_name"),
                source="llm_foster_care_order_v1+normalize_names",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="dependent_name_native",
                value=native.get("dependent_name") if native else None,
                source="llm_foster_care_order_v1",
                canonical_extras={"script": native_script},
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="guardian_name",
                value=payload.get("guardian_name"),
                source="llm_foster_care_order_v1+normalize_names",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="jurisdiction",
                value=payload.get("jurisdiction"),
                source="llm_foster_care_order_v1",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="order_date",
                value=order_date.isoformat() if order_date else None,
                source="llm+normalize_dates",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="dependency_type",
                value=dependency_type,
                source="llm_foster_care_order_v1",
                canonical_extras={"controlled_vocab": list(DEPENDENCY_TYPES)},
            ),
        ]
        fields = tuple(f for f in raw_fields if f is not None)

        # The dependent is always a NEW canonical PERSON (mirrors the child on a
        # birth cert). The guardian is resolved against the case canonical set.
        dependent_canonical_id = uuid4()
        if self.link_sink is not None and hasattr(self.link_sink, "record_minted_canonical"):
            self.link_sink.record_minted_canonical(
                dependent_canonical_id, str(payload.get("dependent_name") or "")
            )

        entity_links: List[EntityLinkRecord] = []
        guardian_resolution: Optional[GuardianResolution] = None
        guardian_name = payload.get("guardian_name")
        if guardian_name:
            resolution = self.resolver.resolve(guardian_name)
            if resolution.matched and resolution.canonical_entity_id is not None:
                link = EntityLinkRecord(
                    extracted_field_id=uuid4(),
                    canonical_entity_id=resolution.canonical_entity_id,
                    link_method=resolution.link_method or "DETERMINISTIC",
                    confidence=resolution.confidence,
                )
                entity_links.append(link)
                if self.link_sink is not None and hasattr(self.link_sink, "write_link"):
                    self.link_sink.write_link(link)
                guardian_resolution = GuardianResolution(
                    name=str(guardian_name),
                    result=resolution,
                    canonical_entity_id=resolution.canonical_entity_id,
                    minted_new_canonical=False,
                )
            else:
                minted_id = uuid4()
                if self.link_sink is not None and hasattr(
                    self.link_sink, "record_minted_canonical"
                ):
                    self.link_sink.record_minted_canonical(minted_id, str(guardian_name))
                guardian_resolution = GuardianResolution(
                    name=str(guardian_name),
                    result=resolution,
                    canonical_entity_id=minted_id,
                    minted_new_canonical=True,
                )

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

        return FosterCareOrderResult(
            agent_run_id=agent_run_id,
            agent_version_id=version.agent_version_id,
            fields=fields,
            llm_payload=payload,
            dependency_type=dependency_type,
            dependent_canonical_entity_id=dependent_canonical_id,
            guardian_resolution=guardian_resolution,
            entity_links=tuple(entity_links),
            model_name=llm.model_name,
            tokens_in=llm.tokens_in,
            tokens_out=llm.tokens_out,
            cost_usd=llm.cost_usd,
        )

    def run_sync(self, document: ParsedDocument) -> FosterCareOrderResult:
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
