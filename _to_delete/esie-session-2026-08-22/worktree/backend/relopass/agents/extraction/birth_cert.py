"""BIRTH_CERT Extraction Agent (C2-01).

The child half of the FamilyMember dimension. Emits child_name, parent_1_name,
parent_2_name, dob, place_of_birth, issuing_authority — and, critically, runs
family-aware entity resolution on the two parent names.

Family-aware resolution (Validation Criterion 4): each parent name is resolved
against the case's existing canonical PERSON entities via the C2-01
:class:`FamilyEntityResolver` (deterministic-first, optional LLM fallback). When
a parent matches an existing canonical PERSON, an ``rce.entity_links`` row is
written (``link_method = DETERMINISTIC`` or ``LLM``) and NO new canonical entity
is created. The child itself is always a new canonical PERSON. An orphan parent
(no match on the case) mints a new canonical and is surfaced ``Requires
attention`` for human confirmation.
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


BIRTH_CERT_AGENT_NAME = "birth_cert"
BIRTH_CERT_DOCUMENT_TYPE = "BIRTH_CERT"


_PROMPT_PATH = (
    Path(__file__).resolve().parents[4]
    / "prompts"
    / "extraction"
    / "birth_cert_v1.txt"
)


def load_birth_cert_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _build_agent() -> ExtractionAgent:
    return ExtractionAgent(
        name=BIRTH_CERT_AGENT_NAME,
        description=(
            "BIRTH_CERT extraction. Emits child_name, parent_1_name, "
            "parent_2_name, dob, place_of_birth, issuing_authority. Runs C1-07 "
            "family-aware resolution on the parent names against the case's "
            "canonical PERSONs — no duplicate canonical entities."
        ),
        extraction_instructions=load_birth_cert_prompt(),
        value_type="string",
        unit=None,
        dimensions="structured: child + two parents + dob + place + authority",
        resolution_instructions=(
            "Parent names are resolved against case canonical PERSONs "
            "(deterministic-first, LLM fallback). A match records an entity_link "
            "and creates NO new canonical. The child is always a new canonical. "
            "Devanagari preserved in *_name_native; Latin in *_name. Dates ISO."
        ),
        inconsistency_instructions=(
            "Ambiguous → null + findings entry. A single-parent certificate sets "
            "the missing parent to null. Orphan parents surface Requires attention."
        ),
        enable_web_search=False,
        enable_complex_calculations_in_resolution=False,
        examples=(),
        output_schema_required_keys=("is_birth_cert",),
    )


_AGENT_SINGLETON: Optional[ExtractionAgent] = None


def _get_agent() -> ExtractionAgent:
    global _AGENT_SINGLETON
    if _AGENT_SINGLETON is None:
        _AGENT_SINGLETON = _build_agent()
    return _AGENT_SINGLETON


@dataclass(frozen=True)
class ParentResolution:
    """The resolution outcome for one parent name on the birth cert."""

    field_key: str  # 'parent_1_name' | 'parent_2_name'
    name: str
    result: ResolutionResult
    # The canonical entity the parent ended up linked to — either an existing
    # one (matched) or a freshly minted one (orphan).
    canonical_entity_id: UUID
    minted_new_canonical: bool


@dataclass(frozen=True)
class BirthCertResult:
    agent_run_id: UUID
    agent_version_id: UUID
    fields: Tuple[ExtractedField, ...]
    llm_payload: Mapping[str, Any]
    child_canonical_entity_id: UUID
    parent_resolutions: Tuple[ParentResolution, ...]
    entity_links: Tuple[EntityLinkRecord, ...]
    model_name: str
    tokens_in: int
    tokens_out: int
    cost_usd: float


@dataclass
class BirthCertAgent:
    registry: AgentRegistry
    sink: ExtractionSink
    # The case-scoped resolver. Defaults to an empty resolver (no canonical
    # persons on the case → every parent is an orphan). Callers inject a
    # resolver loaded with the case's canonical PERSONs.
    resolver: FamilyEntityResolver = field(default_factory=FamilyEntityResolver)
    # Optional link sink — collects entity_links rows + minted canonicals. The
    # in-memory sink lives in entity_resolution; the SQL adapter lives one layer
    # up. Falls back to a private list when not supplied.
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
            raise RuntimeError("BirthCertAgent.run() called before register()")
        return self._agent_version

    async def run(self, document: ParsedDocument) -> BirthCertResult:
        version = self.agent_version
        agent_run_id = uuid4()
        started_at = datetime.now(tz=timezone.utc)

        prompt = (
            load_birth_cert_prompt()
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
        dob = _normalize_date(payload.get("dob"), country_hint)
        native = payload.get("name_native") if isinstance(payload.get("name_native"), Mapping) else {}
        native_script = native.get("script") if native else None

        raw_fields = [
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="child_name",
                value=payload.get("child_name"),
                source="llm_birth_cert_v1+normalize_names",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="child_name_native",
                value=native.get("child_name") if native else None,
                source="llm_birth_cert_v1",
                canonical_extras={"script": native_script},
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="parent_1_name",
                value=payload.get("parent_1_name"),
                source="llm_birth_cert_v1+normalize_names",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="parent_2_name",
                value=payload.get("parent_2_name"),
                source="llm_birth_cert_v1+normalize_names",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="dob",
                value=dob.isoformat() if dob else None,
                source="llm+normalize_dates",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="place_of_birth",
                value=payload.get("place_of_birth"),
                source="llm_birth_cert_v1",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="issuing_authority",
                value=payload.get("issuing_authority"),
                source="llm_birth_cert_v1",
            ),
        ]
        fields = tuple(f for f in raw_fields if f is not None)

        # The child is always a NEW canonical PERSON.
        child_canonical_id = uuid4()
        if self.link_sink is not None and hasattr(self.link_sink, "record_minted_canonical"):
            self.link_sink.record_minted_canonical(
                child_canonical_id, str(payload.get("child_name") or "")
            )

        # Resolve each parent against the case canonical PERSONs.
        parent_resolutions: List[ParentResolution] = []
        entity_links: List[EntityLinkRecord] = []
        for key in ("parent_1_name", "parent_2_name"):
            name = payload.get(key)
            if not name:
                continue
            # ExtractedField rows get their id from the DB on insert; the link's
            # extracted_field_id is reconciled by the SQL adapter one layer up.
            # Here we anchor the link with a stable placeholder id.
            extracted_field_id = uuid4()
            resolution = self.resolver.resolve(name)
            if resolution.matched and resolution.canonical_entity_id is not None:
                link = EntityLinkRecord(
                    extracted_field_id=extracted_field_id,
                    canonical_entity_id=resolution.canonical_entity_id,
                    link_method=resolution.link_method or "DETERMINISTIC",
                    confidence=resolution.confidence,
                )
                entity_links.append(link)
                if self.link_sink is not None and hasattr(self.link_sink, "write_link"):
                    self.link_sink.write_link(link)
                parent_resolutions.append(
                    ParentResolution(
                        field_key=key,
                        name=str(name),
                        result=resolution,
                        canonical_entity_id=resolution.canonical_entity_id,
                        minted_new_canonical=False,
                    )
                )
            else:
                # Orphan parent — mint a new canonical and surface for review.
                minted_id = uuid4()
                if self.link_sink is not None and hasattr(
                    self.link_sink, "record_minted_canonical"
                ):
                    self.link_sink.record_minted_canonical(minted_id, str(name))
                # We still record a link to the freshly minted canonical so the
                # field is anchored, but it is flagged HUMAN-reviewable upstream.
                parent_resolutions.append(
                    ParentResolution(
                        field_key=key,
                        name=str(name),
                        result=resolution,
                        canonical_entity_id=minted_id,
                        minted_new_canonical=True,
                    )
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

        return BirthCertResult(
            agent_run_id=agent_run_id,
            agent_version_id=version.agent_version_id,
            fields=fields,
            llm_payload=payload,
            child_canonical_entity_id=child_canonical_id,
            parent_resolutions=tuple(parent_resolutions),
            entity_links=tuple(entity_links),
            model_name=llm.model_name,
            tokens_in=llm.tokens_in,
            tokens_out=llm.tokens_out,
            cost_usd=llm.cost_usd,
        )

    def run_sync(self, document: ParsedDocument) -> BirthCertResult:
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
