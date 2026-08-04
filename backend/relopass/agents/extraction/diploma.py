"""DIPLOMA Extraction Agent (C1-05e).

The qualification component of the Blue Card §18g eligibility predicate.
ISCED level and German anabin recognition are the two load-bearing
downstream consumers — C1-09 (corridor agent) gates on isced_level ≥ 6
and an H+ anabin status.

This agent emits:

* ``institution_name`` (Latin) + ``institution_name_native`` (Devanagari
  preserved when present, via normalize.names ISO 15919 transliteration)
* ``qualification_title``
* ``isced_level`` (one of 5/6/7/8 inferred from the qualification title)
* ``award_date``
* ``field_of_study``
* ``country_iso3`` of the issuing institution
* ``recognized_in_anabin`` — always emitted as null with
  ``status: 'pending_external_lookup'`` per the brief (anabin is a
  Cohort-2 EXTERNAL_LOOKUP pattern, not an LLM call)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Mapping, Optional, Tuple
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


DIPLOMA_AGENT_NAME = "diploma"

# Keyed to rce.document_types.code. Its absence is why this agent shipped
# unreachable: EXTRACTION_AGENT_REGISTRY is keyed by document-type code, and
# every registered agent declares one — this module did not, so there was
# nothing to register it under. See test_extraction_agent_wiring.py.
DIPLOMA_DOCUMENT_TYPE = "DIPLOMA"


# ─────────────────────────────────────────────────────────────────────────────
# ISCED inference fallback
# ─────────────────────────────────────────────────────────────────────────────
#
# The prompt does the heavy lifting (the LLM should emit isced_level); this
# fallback runs only when the LLM omits the value. Title-based heuristics
# inferred from common qualification labels.

ISCED_LEVEL = Literal[5, 6, 7, 8]


_TITLE_TO_ISCED: Tuple[Tuple[str, ISCED_LEVEL], ...] = (
    # Order matters: longer / more specific patterns first.
    ("doctorat", 8),
    ("doctorate", 8),
    ("doktorat", 8),
    ("doctor of philosophy", 8),
    ("ph.d", 8),
    ("ph d", 8),
    ("phd", 8),
    ("master of science", 7),
    ("master of arts", 7),
    ("master of business administration", 7),
    ("mba", 7),
    ("master", 7),
    ("magister", 7),
    ("diplom-ingenieur", 7),
    ("diplom ingenieur", 7),
    ("bachelor of science", 6),
    ("bachelor of arts", 6),
    ("bachelor of engineering", 6),
    ("bachelor of technology", 6),
    ("bachelor", 6),
    ("licence", 6),
    ("license", 6),
    ("b.tech", 6),
    ("b.sc", 6),
    ("b.a.", 6),
    ("bsc", 6),
    ("ba ", 6),
    ("be ", 6),
    ("be,", 6),
    ("diplôme universitaire de technologie", 5),
    ("dut", 5),
    ("brevet de technicien supérieur", 5),
    ("bts", 5),
    ("foundation degree", 5),
)


def infer_isced_level_from_title(qualification_title: Optional[str]) -> Optional[ISCED_LEVEL]:
    """Fallback ISCED inference from a qualification title string.

    Used only when the LLM omits ``isced_level``. Returns ``None`` when
    no pattern matches — the agent never invents a level.
    """
    if not qualification_title:
        return None
    lower = qualification_title.lower()
    for pattern, level in _TITLE_TO_ISCED:
        if pattern in lower:
            return level
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Prompt loading
# ─────────────────────────────────────────────────────────────────────────────


_PROMPT_PATH = (
    Path(__file__).resolve().parents[4] / "prompts" / "extraction" / "diploma_v1.txt"
)


def load_diploma_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# ExtractionAgent definition
# ─────────────────────────────────────────────────────────────────────────────


def _build_agent() -> ExtractionAgent:
    return ExtractionAgent(
        name=DIPLOMA_AGENT_NAME,
        description=(
            "DIPLOMA extraction. Emits institution_name (Latin + native), "
            "qualification_title, isced_level (5/6/7/8), award_date, "
            "field_of_study, country_iso3. anabin status is emitted as null "
            "+ pending_external_lookup (the lookup is a Cohort-2 EXTERNAL_LOOKUP)."
        ),
        extraction_instructions=load_diploma_prompt(),
        value_type="enum",
        unit=None,
        dimensions="structured: institution + qualification + isced + date + field",
        resolution_instructions=(
            "ISCED level: 5 short-cycle tertiary, 6 Bachelor, 7 Master, "
            "8 Doctorate. Infer from the qualification title rather than guess. "
            "Devanagari names preserved in name_native; ISO 15919 reverse "
            "transliteration in institution_name. Anti-hallucination rule: "
            "ambiguous → null + findings entry."
        ),
        inconsistency_instructions=(
            "anabin recognition is a Cohort-2 EXTERNAL_LOOKUP (PF-1 pattern). "
            "Emit recognized_in_anabin=null with status='pending_external_lookup'."
        ),
        enable_web_search=False,
        enable_complex_calculations_in_resolution=False,
        examples=(),
        output_schema_required_keys=("is_diploma", "qualification_title"),
    )


_AGENT_SINGLETON: Optional[ExtractionAgent] = None


def _get_agent() -> ExtractionAgent:
    global _AGENT_SINGLETON
    if _AGENT_SINGLETON is None:
        _AGENT_SINGLETON = _build_agent()
    return _AGENT_SINGLETON


# ─────────────────────────────────────────────────────────────────────────────
# Result type
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DiplomaResult:
    agent_run_id: UUID
    agent_version_id: UUID
    fields: Tuple[ExtractedField, ...]
    llm_payload: Mapping[str, Any]
    isced_level: Optional[ISCED_LEVEL]
    isced_inference_source: Literal["llm", "title_fallback", "absent"]
    model_name: str
    tokens_in: int
    tokens_out: int
    cost_usd: float


# ─────────────────────────────────────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class DiplomaAgent:
    registry: AgentRegistry
    sink: ExtractionSink
    agent_override: Optional[ExtractionAgent] = None
    _agent_version: Optional[ExtractionAgentVersion] = field(default=None, init=False, repr=False)

    def register(self) -> SaveResult:
        agent = self.agent_override or _get_agent()
        result = self.registry.save_agent(agent)
        self._agent_version = result.version
        return result

    @property
    def agent_version(self) -> ExtractionAgentVersion:
        if self._agent_version is None:
            raise RuntimeError("DiplomaAgent.run() called before register()")
        return self._agent_version

    async def run(self, document: ParsedDocument) -> DiplomaResult:
        version = self.agent_version
        agent_run_id = uuid4()
        started_at = datetime.now(tz=timezone.utc)

        prompt = (
            load_diploma_prompt()
            + "\n\n=== DOCUMENT TEXT ===\n\n"
            + document.text
        )
        llm = await call_llm_with_retry(
            prompt,
            required_keys=version.output_schema_required_keys,
            case_id=str(document.case_id) if document.case_id else None,
        )
        payload = llm.payload

        isced_level, isced_source = self._resolve_isced(payload)
        award_date = self._normalize_date(payload.get("award_date"), payload.get("country_iso3"))

        raw_fields = (
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="institution_name",
                value=payload.get("institution_name"),
                source="llm_diploma_v1",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="institution_name_native",
                value=payload.get("institution_name_native"),
                source="llm_diploma_v1+normalize_names",
                canonical_extras={"script": payload.get("native_script")},
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="qualification_title",
                value=payload.get("qualification_title"),
                source="llm_diploma_v1",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="isced_level",
                value=isced_level,
                source="llm_diploma_v1" if isced_source == "llm" else "title_inference_fallback",
                canonical_extras={"inference_source": isced_source},
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="award_date",
                value=award_date.isoformat() if award_date else None,
                source="llm+normalize_dates",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="field_of_study",
                value=payload.get("field_of_study"),
                source="llm_diploma_v1",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="country_iso3",
                value=payload.get("country_iso3"),
                source="llm_diploma_v1",
            ),
            # anabin: always null + pending_external_lookup (Cohort-2 work).
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="recognized_in_anabin",
                value="null",
                source="pending_external_lookup",
                canonical_extras={
                    "status": "pending_external_lookup",
                    "lookup_provider": "anabin.de",
                    "pattern": "EXTERNAL_LOOKUP",
                },
                confidence=0.0,
                resolution_status="Not resolved",
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

        return DiplomaResult(
            agent_run_id=agent_run_id,
            agent_version_id=version.agent_version_id,
            fields=fields,
            llm_payload=payload,
            isced_level=isced_level,
            isced_inference_source=isced_source,
            model_name=llm.model_name,
            tokens_in=llm.tokens_in,
            tokens_out=llm.tokens_out,
            cost_usd=llm.cost_usd,
        )

    def run_sync(self, document: ParsedDocument) -> DiplomaResult:
        import asyncio

        return asyncio.run(self.run(document))

    @staticmethod
    def _resolve_isced(
        payload: Mapping[str, Any],
    ) -> Tuple[Optional[ISCED_LEVEL], Literal["llm", "title_fallback", "absent"]]:
        raw = payload.get("isced_level")
        if raw in (5, 6, 7, 8):
            return raw, "llm"  # type: ignore[return-value]
        if isinstance(raw, str) and raw.isdigit():
            v = int(raw)
            if v in (5, 6, 7, 8):
                return v, "llm"  # type: ignore[return-value]
        fallback = infer_isced_level_from_title(payload.get("qualification_title"))
        if fallback is not None:
            return fallback, "title_fallback"
        return None, "absent"

    @staticmethod
    def _normalize_date(raw: Any, country_iso3: Any):
        if not raw:
            return None
        from datetime import date

        hint = {"FRA": "fr", "DEU": "de", "NOR": "no"}.get(country_iso3, None)
        parsed = parse_date(str(raw), locale_hint=hint)
        if parsed.iso is None:
            return None
        return date.fromisoformat(parsed.iso)
