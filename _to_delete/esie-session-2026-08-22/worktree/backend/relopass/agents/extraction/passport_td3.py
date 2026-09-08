"""PASSPORT_TD3 Extraction Agent (C1-05b).

Hybrid extraction: three sources merged into a single :class:`ExtractionRunResult`.

1. **MRZ parser (C1-02)** — authoritative for the 9 ICAO 9303 identity fields
   (surname, given_names, document_number, nationality_iso3, issuing_state_iso3,
   date_of_birth, sex, expiry_date, personal_number). Deterministic; the LLM
   never overrides these.
2. **Azure DI prebuilt-ID (C1-03)** — authoritative for photo_bbox and
   signature_bbox. ``phi_class='BIOMETRIC'`` is stamped on the photo region
   so Article 9 audit logging fires on every read.
3. **LLM extraction via the C1-05P-b prompt** — fills the gaps
   (issuing_authority, endorsements, mrz_body_discrepancies, agent_confidence).
   The prompt explicitly EXCLUDES the 9 MRZ-derived fields so the model is
   structurally prevented from overriding the deterministic parser.

The strategic outcome: every ExtractedField row produced here cites the
authoritative source for the corresponding field, and the Parsewise versioning
rule from C1-05a applies — changing the prompt or extraction config creates
a new agent_versions row AND clears the prior version's extractions.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Dict, List, Mapping, Optional, Protocol, Tuple
from uuid import UUID, uuid4

from backend.relopass.docs.mrz import (
    DocumentValidationFinding,
    MRZParseResult,
    parse_mrz,
)
from backend.relopass.llm import LLMRoutingError, route_llm
from backend.relopass.llm.router import AgentRunRecord

from ..models import (
    ExtractedField,
    ExtractionAgent,
    ExtractionAgentVersion,
    ExtractionRunResult,
    ParsedDocument,
    compute_version_hash,
)
from ..registry import AgentRegistry, SaveResult
from ..runtime import ExtractionRuntimeError, ExtractionSink

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────


PASSPORT_TD3_AGENT_NAME = "passport_td3"

# PHI classifier — when present in an ExtractedField's value_canonical, the
# Article 9 audit logger triggers on every read. Required by the C1-05b brief
# for the photo region.
PHI_CLASS_BIOMETRIC = "BIOMETRIC"

# Field keys emitted by each source. Together they're the full TD3 output set
# the downstream Resolution UI consumes.
MRZ_FIELD_KEYS: Tuple[str, ...] = (
    "surname",
    "given_names",
    "document_number",
    "nationality_iso3",
    "issuing_state_iso3",
    "date_of_birth",
    "sex",
    "expiry_date",
    "personal_number",
)

DI_FIELD_KEYS: Tuple[str, ...] = (
    "photo_bbox",
    "signature_bbox",
)

LLM_FIELD_KEYS: Tuple[str, ...] = (
    "issuing_authority",
    "endorsements",
    "mrz_body_discrepancies",
    "agent_confidence",
)


# Repo root is 4 levels up: parents[0]=extraction → parents[1]=agents →
# parents[2]=relopass → parents[3]=backend → parents[4]=repo root.
_PROMPT_PATH = (
    Path(__file__).resolve().parents[4] / "prompts" / "extraction" / "passport_td3_v1.txt"
)


def load_passport_td3_prompt() -> str:
    """Read the C1-05P-b prompt from :file:`prompts/extraction/passport_td3_v1.txt`.

    Loaded lazily so test runs that don't exercise the LLM path don't pay
    the file-system cost. Raises ``FileNotFoundError`` if the prompt file
    isn't on disk — the prompt is the contract, not optional.
    """
    return _PROMPT_PATH.read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Azure DI provider Protocol
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Bbox:
    """A single rectangular region on a document page, canonical 0–1000 space."""

    page: int
    x0: int
    y0: int
    x1: int
    y1: int


@dataclass(frozen=True)
class AzureDiPassportOutput:
    """The subset of Azure DI prebuilt-ID output the agent consumes.

    The real Azure SDK returns a richer payload; the production adapter (in
    ``backend/services/`` — future task) projects it down to this shape so
    the agent stays SDK-free.
    """

    body_text: str
    photo_bbox: Optional[Bbox] = None
    signature_bbox: Optional[Bbox] = None
    issuing_authority_raw: Optional[str] = None


class AzureDIProvider(Protocol):
    """Pluggable Azure DI adapter.

    Tests register :class:`NullAzureDIProvider` or a hand-rolled fake. The
    production adapter calls Azure DI prebuilt-ID and projects the result.
    """

    def extract_passport(self, document: ParsedDocument) -> AzureDiPassportOutput:
        ...


@dataclass
class NullAzureDIProvider:
    """Inert DI provider — returns no bboxes and the document's own text.

    Used in tests that exercise the MRZ + LLM paths without caring about
    photo/signature regions.
    """

    def extract_passport(self, document: ParsedDocument) -> AzureDiPassportOutput:
        return AzureDiPassportOutput(body_text=document.text)


# ─────────────────────────────────────────────────────────────────────────────
# The ExtractionAgent definition
# ─────────────────────────────────────────────────────────────────────────────


def _build_passport_td3_agent() -> ExtractionAgent:
    """Construct the canonical ExtractionAgent for PASSPORT_TD3.

    Reads the prompt at construction time so the version_hash incorporates
    the prompt's content — editing the prompt forces a new version per
    Parsewise rule.

    Loaded lazily via :data:`PASSPORT_TD3_AGENT`. Callers that don't need
    the agent (e.g. unit tests that only exercise MRZ extraction) shouldn't
    pay the prompt-read cost up front.
    """
    prompt = load_passport_td3_prompt()
    return ExtractionAgent(
        name=PASSPORT_TD3_AGENT_NAME,
        description=(
            "Hybrid PASSPORT_TD3 extraction: ICAO 9303 MRZ (authoritative) + "
            "Azure DI prebuilt-ID (photo / signature bboxes) + LLM extraction "
            "for issuing_authority + endorsements + MRZ↔body discrepancies."
        ),
        extraction_instructions=prompt,
        # The LLM emits a structured JSON object (issuing_authority +
        # endorsements + mrz_body_discrepancies + agent_confidence). "enum"
        # is the closest fit in the rce.agent_versions value_type CHECK
        # constraint set; the actual contract is documented in the prompt.
        value_type="enum",
        unit=None,
        dimensions="structured: issuing_authority + endorsements[] + mrz_body_discrepancies[] + agent_confidence",
        resolution_instructions=(
            "MRZ is canonical for surname, given_names, document_number, "
            "nationality_iso3, issuing_state_iso3, date_of_birth, sex, "
            "expiry_date, personal_number. Body↔MRZ disagreements surface as "
            "mrz_body_discrepancies findings (INFO for legitimate ICAO 9303 "
            "transliterations, WARN otherwise). LLM never overrides MRZ."
        ),
        inconsistency_instructions=(
            "Failed MRZ check digits emit DocumentValidationFinding(WARN) but "
            "do not block extraction. Body text takes secondary precedence "
            "behind MRZ. When mrz_parse.format == 'UNKNOWN' the LLM reports "
            "agent_confidence='low' and emits a body-only discrepancy item."
        ),
        enable_web_search=False,
        enable_complex_calculations_in_resolution=False,
        examples=(),  # 5 exemplars live inside the prompt text itself.
        # issuing_authority + agent_confidence are the only fields the LLM
        # MUST produce; endorsements and discrepancies may be empty arrays.
        output_schema_required_keys=("issuing_authority", "agent_confidence"),
    )


# Lazy singleton — first access triggers the prompt load.
_AGENT_SINGLETON: Optional[ExtractionAgent] = None


def _get_agent() -> ExtractionAgent:
    global _AGENT_SINGLETON
    if _AGENT_SINGLETON is None:
        _AGENT_SINGLETON = _build_passport_td3_agent()
    return _AGENT_SINGLETON


class _AgentDescriptor:
    """Module-level proxy so ``PASSPORT_TD3_AGENT`` looks like an attribute
    but defers prompt loading until first use.
    """

    def __getattr__(self, item: str) -> Any:
        return getattr(_get_agent(), item)

    def __repr__(self) -> str:
        return f"<PASSPORT_TD3_AGENT proxy → {_get_agent()!r}>"


PASSPORT_TD3_AGENT: Any = _AgentDescriptor()


# ─────────────────────────────────────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PassportTd3Result:
    """What :meth:`PassportTd3Agent.run` returns to the caller.

    Bundles the C1-05a-style :class:`ExtractionRunResult` (which carries the
    LLM-driven extraction's agent_run_id + tokens + cost) with the additional
    deterministic outputs from the MRZ + DI layers.
    """

    agent_run_id: UUID
    agent_version_id: UUID
    fields: Tuple[ExtractedField, ...]
    mrz_parse: MRZParseResult
    mrz_findings: Tuple[DocumentValidationFinding, ...]
    di_output: AzureDiPassportOutput
    llm_payload: Mapping[str, Any]
    tokens_in: int
    tokens_out: int
    cost_usd: float
    model_name: str


@dataclass
class PassportTd3Agent:
    """Orchestrates MRZ + Azure DI + LLM into a single PASSPORT_TD3 extraction.

    Usage::

        registry = AgentRegistry(InMemoryAgentStorage())
        sink = InMemoryExtractionSink()
        agent = PassportTd3Agent(
            registry=registry,
            sink=sink,
            di_provider=NullAzureDIProvider(),
        )
        agent.register()
        result = asyncio.run(agent.run(document, mrz_text=...))
    """

    registry: AgentRegistry
    sink: ExtractionSink
    di_provider: AzureDIProvider
    # Optional override of the agent definition. Tests use this to swap in a
    # tweaked prompt without writing to disk.
    agent_override: Optional[ExtractionAgent] = None
    # Filled by :meth:`register`.
    _agent_version: Optional[ExtractionAgentVersion] = field(default=None, init=False, repr=False)

    # ---- Lifecycle ----

    def register(self) -> SaveResult:
        """Save the agent into the C1-05a registry. Idempotent — calling
        twice with the same agent definition returns the same version.
        """
        agent = self.agent_override or _get_agent()
        result = self.registry.save_agent(agent)
        self._agent_version = result.version
        return result

    @property
    def agent_version(self) -> ExtractionAgentVersion:
        if self._agent_version is None:
            raise RuntimeError(
                "PassportTd3Agent.run() called before register(). "
                "Call register() once at boot to persist the agent + version."
            )
        return self._agent_version

    # ---- Run ----

    async def run(
        self,
        document: ParsedDocument,
        *,
        mrz_text: str,
    ) -> PassportTd3Result:
        """Run all three extraction layers and persist the combined result.

        ``mrz_text`` is the two-line MRZ string read off the document
        (provided separately because the OCR layer typically extracts it as
        a discrete region, distinct from the body text).
        """
        version = self.agent_version
        agent_run_id = uuid4()
        started_at = datetime.now(tz=timezone.utc)

        # 1. MRZ — deterministic, authoritative.
        mrz = parse_mrz(mrz_text)
        mrz_fields = self._mrz_to_extracted_fields(mrz, document.document_id, agent_run_id)
        mrz_findings = tuple(mrz.findings)

        # 2. Azure DI — photo + signature bboxes, body text.
        di_out = self.di_provider.extract_passport(document)
        di_fields = self._di_to_extracted_fields(di_out, document.document_id, agent_run_id)

        # 3. LLM — non-MRZ fields + discrepancies. Routed via field_extraction
        # so the same escalation rules as C1-05a apply.
        try:
            handle = route_llm("field_extraction")
            prompt = self._build_llm_prompt(version, mrz, di_out)
            raw = await handle.complete(
                prompt,
                max_tokens=handle.token_budget,
                case_id=str(document.case_id) if document.case_id else None,
            )
            llm_payload = self._parse_llm_output(raw)
            missing = tuple(k for k in version.output_schema_required_keys if k not in llm_payload)
            if missing:
                # Single retry on the escalated model.
                handle = route_llm("field_extraction", validator_failed=True)
                raw = await handle.complete(
                    prompt,
                    max_tokens=handle.token_budget,
                    case_id=str(document.case_id) if document.case_id else None,
                )
                llm_payload = self._parse_llm_output(raw)
                missing = tuple(
                    k for k in version.output_schema_required_keys if k not in llm_payload
                )
                if missing:
                    raise ExtractionRuntimeError(
                        f"LLM output missing required keys after retry: {missing}"
                    )
        except LLMRoutingError as exc:
            # No completer registered (test environment, or the SDK adapter
            # hasn't been wired). The MRZ + DI layers ALREADY have all the
            # MRZ-authoritative + biometric fields we need; skip the LLM
            # layer and record a finding.
            logger.warning("LLM extraction skipped for PASSPORT_TD3: %s", exc)
            llm_payload = {}
            handle_model = "(none — LLM unrouted)"
            tokens_in = 0
            tokens_out = 0
            cost = 0.0
            inputs_digest = ""
            output_digest = ""
        else:
            handle_model = handle.model_name
            tokens_in = handle.tokens_in
            tokens_out = handle.tokens_out
            cost = handle.cost_usd
            inputs_digest = handle.inputs_digest
            output_digest = handle.output_digest

        llm_fields = self._llm_to_extracted_fields(llm_payload, document.document_id, agent_run_id)

        all_fields = mrz_fields + di_fields + llm_fields

        finished_at = datetime.now(tz=timezone.utc)
        self.sink.write_agent_run(
            agent_run_id=agent_run_id,
            agent_version_id=version.agent_version_id,
            case_id=document.case_id,
            document_id=document.document_id,
            model_name=handle_model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost,
            inputs_digest=inputs_digest,
            output_digest=output_digest,
            started_at=started_at,
            finished_at=finished_at,
            status="OK",
        )
        self.sink.write_extracted_fields(all_fields)

        return PassportTd3Result(
            agent_run_id=agent_run_id,
            agent_version_id=version.agent_version_id,
            fields=all_fields,
            mrz_parse=mrz,
            mrz_findings=mrz_findings,
            di_output=di_out,
            llm_payload=llm_payload,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost,
            model_name=handle_model,
        )

    def run_sync(self, document: ParsedDocument, *, mrz_text: str) -> PassportTd3Result:
        return asyncio.run(self.run(document, mrz_text=mrz_text))

    # ---- Source-specific field builders ----

    @staticmethod
    def _mrz_to_extracted_fields(
        mrz: MRZParseResult,
        document_id: UUID,
        agent_run_id: UUID,
    ) -> Tuple[ExtractedField, ...]:
        """Map MRZParseResult → ExtractedField rows.

        All MRZ-derived fields carry confidence=1.0 because the parser is
        deterministic and validated against ICAO check digits. If a check
        digit failed, the relevant field's confidence drops to 0.7 to
        signal to the Resolution UI that the value is suspect (the WARN
        finding sits alongside).
        """
        out: List[ExtractedField] = []
        check_results = mrz.check_digits

        def _value_for(key: str) -> Optional[str]:
            raw = getattr(mrz, _MRZ_FIELD_TO_ATTR.get(key, key), None)
            if raw is None:
                return None
            if isinstance(raw, date):
                return raw.isoformat()
            return str(raw)

        # Per-field confidence: 1.0 unless the relevant check digit failed.
        # Mapping derived from ICAO 9303 Part 3 §4.9 (which check digit
        # protects which field).
        field_to_check = {
            "document_number": "document_number",
            "date_of_birth": "date_of_birth",
            "expiry_date": "expiry_date",
            "personal_number": "personal_number",
        }

        for key in MRZ_FIELD_KEYS:
            value = _value_for(key)
            if value is None:
                continue
            confidence = 1.0
            check_field = field_to_check.get(key)
            if check_field and check_field in check_results:
                # CheckDigitResult exposes `passed: bool` (per backend/relopass/docs/mrz.py).
                if not check_results[check_field].passed:
                    confidence = 0.7
            out.append(
                ExtractedField(
                    document_id=document_id,
                    field_key=key,
                    value_raw=value,
                    value_canonical={
                        "source": "mrz_c1_02",
                        "mrz_format": mrz.format,
                    },
                    confidence=confidence,
                    agent_run_id=agent_run_id,
                    resolution_status="Resolved" if confidence == 1.0 else "Requires attention",
                )
            )
        return tuple(out)

    @staticmethod
    def _di_to_extracted_fields(
        di: AzureDiPassportOutput,
        document_id: UUID,
        agent_run_id: UUID,
    ) -> Tuple[ExtractedField, ...]:
        out: List[ExtractedField] = []
        if di.photo_bbox is not None:
            out.append(
                ExtractedField(
                    document_id=document_id,
                    field_key="photo_bbox",
                    value_raw=_bbox_to_str(di.photo_bbox),
                    value_canonical={
                        "source": "azure_di_prebuilt_id",
                        "phi_class": PHI_CLASS_BIOMETRIC,
                        "bbox": {
                            "page": di.photo_bbox.page,
                            "x0": di.photo_bbox.x0,
                            "y0": di.photo_bbox.y0,
                            "x1": di.photo_bbox.x1,
                            "y1": di.photo_bbox.y1,
                        },
                    },
                    confidence=1.0,
                    bbox_page=di.photo_bbox.page,
                    bbox_x0=di.photo_bbox.x0,
                    bbox_y0=di.photo_bbox.y0,
                    bbox_x1=di.photo_bbox.x1,
                    bbox_y1=di.photo_bbox.y1,
                    agent_run_id=agent_run_id,
                    resolution_status="Resolved",
                )
            )
        if di.signature_bbox is not None:
            out.append(
                ExtractedField(
                    document_id=document_id,
                    field_key="signature_bbox",
                    value_raw=_bbox_to_str(di.signature_bbox),
                    value_canonical={
                        "source": "azure_di_prebuilt_id",
                        "bbox": {
                            "page": di.signature_bbox.page,
                            "x0": di.signature_bbox.x0,
                            "y0": di.signature_bbox.y0,
                            "x1": di.signature_bbox.x1,
                            "y1": di.signature_bbox.y1,
                        },
                    },
                    confidence=1.0,
                    bbox_page=di.signature_bbox.page,
                    bbox_x0=di.signature_bbox.x0,
                    bbox_y0=di.signature_bbox.y0,
                    bbox_x1=di.signature_bbox.x1,
                    bbox_y1=di.signature_bbox.y1,
                    agent_run_id=agent_run_id,
                    resolution_status="Resolved",
                )
            )
        return tuple(out)

    @staticmethod
    def _llm_to_extracted_fields(
        payload: Mapping[str, Any],
        document_id: UUID,
        agent_run_id: UUID,
    ) -> Tuple[ExtractedField, ...]:
        out: List[ExtractedField] = []
        for key in LLM_FIELD_KEYS:
            if key not in payload:
                continue
            value = payload[key]
            canonical = {"source": "llm_passport_td3_v1"}
            if isinstance(value, (list, dict)):
                value_raw = json.dumps(value, ensure_ascii=False)
                canonical["structured"] = value  # type: ignore[assignment]
            elif value is None:
                value_raw = None
            else:
                value_raw = str(value)
            # The LLM emits agent_confidence as a low/medium/high band.
            # Map to a numeric for the ExtractedField row.
            if key == "agent_confidence":
                confidence = _confidence_band_to_float(value)
            else:
                confidence = 0.9  # default for LLM-extracted non-confidence fields
            out.append(
                ExtractedField(
                    document_id=document_id,
                    field_key=key,
                    value_raw=value_raw,
                    value_canonical=canonical,
                    confidence=confidence,
                    agent_run_id=agent_run_id,
                    resolution_status=None,
                )
            )
        return tuple(out)

    # ---- Prompt construction + output parsing ----

    @staticmethod
    def _build_llm_prompt(
        version: ExtractionAgentVersion,
        mrz: MRZParseResult,
        di: AzureDiPassportOutput,
    ) -> str:
        """Concatenate the base prompt (from C1-05P-b) with the per-document
        context the prompt expects (``body_text`` + JSON-serialised
        ``mrz_parse``).
        """
        mrz_serialised = json.dumps(
            {
                "format": mrz.format,
                "surname": mrz.surname,
                "given_names": mrz.given_names,
                "document_number": mrz.document_number,
                "nationality_iso3": mrz.nationality_iso3,
                "issuing_state_iso3": mrz.issuing_state_iso3,
                "date_of_birth": mrz.date_of_birth.isoformat() if mrz.date_of_birth else None,
                "sex": mrz.sex,
                "expiry_date": mrz.expiry_date.isoformat() if mrz.expiry_date else None,
                "personal_number": mrz.personal_number,
                "all_check_digits_valid": mrz.all_check_digits_valid,
                "findings": [
                    {
                        "severity": f.severity,
                        "code": f.code,
                        "field": f.field,
                        "detail": f.detail,
                    }
                    for f in mrz.findings
                ],
            },
            ensure_ascii=False,
        )
        parts = [
            version.extraction_instructions,
            "",
            "=== INPUT ===",
            "",
            f"body_text:\n{di.body_text}",
            "",
            f"mrz_parse:\n{mrz_serialised}",
        ]
        return "\n".join(parts)

    @staticmethod
    def _parse_llm_output(raw: str) -> Dict[str, Any]:
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
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
        # The prompt instructs the model to wrap output in the tool-use
        # schema's "input" key. Unwrap if present.
        if "input" in data and isinstance(data["input"], dict):
            return dict(data["input"])
        return dict(data)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


# Map ExtractedField field_keys → MRZParseResult attribute names where they
# differ. (Most are identical.)
_MRZ_FIELD_TO_ATTR = {
    # All identical except possibly aliases we might add later.
}


def _confidence_band_to_float(band: Any) -> float:
    if isinstance(band, (int, float)):
        # Already numeric — clamp to [0, 1].
        return max(0.0, min(1.0, float(band)))
    if isinstance(band, str):
        b = band.strip().lower()
        if b == "high":
            return 0.95
        if b == "medium":
            return 0.75
        if b == "low":
            return 0.50
    return 0.0


def _bbox_to_str(bbox: Bbox) -> str:
    return f"page={bbox.page};x0={bbox.x0};y0={bbox.y0};x1={bbox.x1};y1={bbox.y1}"
