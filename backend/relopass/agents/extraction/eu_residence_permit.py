"""EU_RESIDENCE_PERMIT Extraction Agent (C1-05f).

Uniform Regulation (EC) 1030/2002 format. Every EU/EEA Member State
issues the same physical credit-card-sized polycarbonate credential
with a TD1 (3×30 char) MRZ on the back. The visual side carries the
residence-purpose text in the issuing state's language plus validity dates.

Hybrid extraction (mirrors C1-05b PASSPORT_TD3):

1. **C1-02 TD1 parser** — authoritative for: surname, given_names,
   document_number, nationality_iso3, issuing_state_iso3,
   date_of_birth, sex, expiry_date.
2. **C1-05P-f prompt** — LLM extracts validity_start, residence_purpose_code
   (controlled vocabulary mapped from the on-card text), permit_type,
   restrictions, work_authorization, plus any MRZ↔body discrepancies.

A "validity expired" Finding is emitted whenever expiry_date < current_date.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, List, Mapping, Optional, Tuple
from uuid import UUID, uuid4

from backend.relopass.docs.mrz import (
    DocumentValidationFinding,
    MRZParseResult,
    parse_mrz,
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


EU_RESIDENCE_PERMIT_AGENT_NAME = "eu_residence_permit"


# Controlled vocabulary the LLM must map the on-card residence-purpose text to.
# Mirror of the residence_purpose_code list in the C1-05P-f prompt.
RESIDENCE_PURPOSE_VOCABULARY: Tuple[str, ...] = (
    "BLUE_CARD",
    "FAMILY_MEMBER",
    "RESEARCHER",
    "ICT",
    "STUDENT",
    "WORK",
    "LONG_TERM_RESIDENT",
    "REFUGEE",
    "SUBSIDIARY_PROTECTION",
    "TEMPORARY_PROTECTION",
    "OTHER",
)


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


_PROMPT_PATH = (
    Path(__file__).resolve().parents[4]
    / "prompts"
    / "extraction"
    / "eu_residence_permit_v1.txt"
)


def load_eu_residence_permit_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# ExtractionAgent definition (lazy singleton)
# ─────────────────────────────────────────────────────────────────────────────


def _build_agent() -> ExtractionAgent:
    return ExtractionAgent(
        name=EU_RESIDENCE_PERMIT_AGENT_NAME,
        description=(
            "EU/EEA residence permit extraction (Reg. (EC) 1030/2002 uniform "
            "format). C1-02 TD1 MRZ parser is authoritative for the 9 MRZ "
            "identity fields; the LLM picks up validity_start, "
            "residence_purpose_code (controlled vocabulary), permit_type, "
            "restrictions, work_authorization."
        ),
        extraction_instructions=load_eu_residence_permit_prompt(),
        value_type="enum",
        unit=None,
        dimensions="structured: validity + residence_purpose + restrictions",
        resolution_instructions=(
            "MRZ is canonical for the 9 identity fields. residence_purpose_code "
            "must be one of: " + ", ".join(RESIDENCE_PURPOSE_VOCABULARY) + ". "
            "When the on-card text doesn't match any vocabulary entry, return "
            "OTHER + permit_type carrying the raw text."
        ),
        inconsistency_instructions=(
            "Failed TD1 check digit emits DocumentValidationFinding(WARN); "
            "extraction proceeds. expiry_date < current_date emits "
            "PERMIT_EXPIRED finding."
        ),
        enable_web_search=False,
        enable_complex_calculations_in_resolution=False,
        examples=(),
        output_schema_required_keys=("residence_purpose_code",),
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
class EuResidencePermitResult:
    agent_run_id: UUID
    agent_version_id: UUID
    fields: Tuple[ExtractedField, ...]
    mrz_parse: MRZParseResult
    mrz_findings: Tuple[DocumentValidationFinding, ...]
    llm_payload: Mapping[str, Any]
    residence_purpose_code: Optional[str]
    is_expired: bool
    model_name: str
    tokens_in: int
    tokens_out: int
    cost_usd: float


# ─────────────────────────────────────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class EuResidencePermitAgent:
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
            raise RuntimeError("EuResidencePermitAgent.run() called before register()")
        return self._agent_version

    async def run(
        self,
        document: ParsedDocument,
        *,
        mrz_text: str,
        current_date: Optional[date] = None,
    ) -> EuResidencePermitResult:
        if current_date is None:
            current_date = datetime.now(tz=timezone.utc).date()
        version = self.agent_version
        agent_run_id = uuid4()
        started_at = datetime.now(tz=timezone.utc)

        # 1. MRZ — TD1 deterministic.
        mrz = parse_mrz(mrz_text)
        mrz_fields = self._mrz_to_extracted_fields(mrz, document.document_id, agent_run_id)

        # 2. LLM via C1-13 router.
        prompt = self._build_llm_prompt(version, mrz, document, current_date)
        llm = await call_llm_with_retry(
            prompt,
            required_keys=version.output_schema_required_keys,
            case_id=str(document.case_id) if document.case_id else None,
        )
        payload = llm.payload

        purpose = self._coerce_residence_purpose(payload.get("residence_purpose_code"))
        is_expired = mrz.expiry_date is not None and mrz.expiry_date < current_date

        # 3. Build ExtractedField rows for the LLM-sourced fields.
        llm_fields = self._llm_to_extracted_fields(
            payload, purpose, document.document_id, agent_run_id
        )

        # 4. Validity / expiry finding (separate from the LLM payload).
        expiry_fields: List[ExtractedField] = []
        if is_expired:
            expiry_finding = {
                "field": "expiry_date",
                "code": "PERMIT_EXPIRED",
                "severity": "WARN",
                "detail": (
                    f"Permit expiry {mrz.expiry_date} < current date {current_date}."
                ),
                "expiry_date": mrz.expiry_date.isoformat() if mrz.expiry_date else None,
                "current_date": current_date.isoformat(),
            }
            f = make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="permit_expired_finding",
                value=expiry_finding,
                source="agent_eu_residence_permit",
                resolution_status="Requires attention",
            )
            if f:
                expiry_fields.append(f)

        all_fields = mrz_fields + llm_fields + tuple(expiry_fields)

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
        self.sink.write_extracted_fields(all_fields)

        return EuResidencePermitResult(
            agent_run_id=agent_run_id,
            agent_version_id=version.agent_version_id,
            fields=all_fields,
            mrz_parse=mrz,
            mrz_findings=tuple(mrz.findings),
            llm_payload=payload,
            residence_purpose_code=purpose,
            is_expired=is_expired,
            model_name=llm.model_name,
            tokens_in=llm.tokens_in,
            tokens_out=llm.tokens_out,
            cost_usd=llm.cost_usd,
        )

    def run_sync(
        self,
        document: ParsedDocument,
        *,
        mrz_text: str,
        current_date: Optional[date] = None,
    ) -> EuResidencePermitResult:
        import asyncio

        return asyncio.run(self.run(document, mrz_text=mrz_text, current_date=current_date))

    # ---- Helpers ----

    @staticmethod
    def _mrz_to_extracted_fields(
        mrz: MRZParseResult, document_id: UUID, agent_run_id: UUID
    ) -> Tuple[ExtractedField, ...]:
        out: List[ExtractedField] = []
        check_results = mrz.check_digits

        check_field_map = {
            "document_number": "document_number",
            "date_of_birth": "date_of_birth",
            "expiry_date": "expiry_date",
        }

        for key in MRZ_FIELD_KEYS:
            value = getattr(mrz, key, None)
            if value is None:
                continue
            display = value.isoformat() if hasattr(value, "isoformat") else str(value)
            confidence = 1.0
            check_field = check_field_map.get(key)
            if check_field and check_field in check_results:
                if not check_results[check_field].passed:
                    confidence = 0.7
            f = make_field(
                document_id=document_id,
                agent_run_id=agent_run_id,
                key=key,
                value=display,
                source="mrz_c1_02_td1",
                confidence=confidence,
                canonical_extras={
                    "source": "mrz_c1_02_td1",
                    "mrz_format": mrz.format,
                },
                resolution_status="Resolved" if confidence == 1.0 else "Requires attention",
            )
            if f:
                out.append(f)
        return tuple(out)

    @staticmethod
    def _llm_to_extracted_fields(
        payload: Mapping[str, Any],
        purpose: Optional[str],
        document_id: UUID,
        agent_run_id: UUID,
    ) -> Tuple[ExtractedField, ...]:
        keys = (
            "validity_start",
            "residence_purpose_code",
            "permit_type",
            "restrictions",
            "work_authorization",
        )
        out: List[ExtractedField] = []
        for key in keys:
            raw_value = purpose if key == "residence_purpose_code" else payload.get(key)
            if raw_value is None or raw_value == "":
                continue
            f = make_field(
                document_id=document_id,
                agent_run_id=agent_run_id,
                key=key,
                value=raw_value,
                source="llm_eu_residence_permit_v1",
                canonical_extras={
                    "controlled_vocabulary": list(RESIDENCE_PURPOSE_VOCABULARY)
                    if key == "residence_purpose_code"
                    else None,
                },
            )
            if f:
                out.append(f)
        return tuple(out)

    @staticmethod
    def _coerce_residence_purpose(raw: Any) -> Optional[str]:
        if raw is None:
            return None
        s = str(raw).strip().upper()
        if s in RESIDENCE_PURPOSE_VOCABULARY:
            return s
        # Unknown vocab entry → fall back to OTHER but keep the original via permit_type.
        return "OTHER"

    @staticmethod
    def _build_llm_prompt(
        version: ExtractionAgentVersion,
        mrz: MRZParseResult,
        document: ParsedDocument,
        current_date: date,
    ) -> str:
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
        return "\n".join(
            [
                version.extraction_instructions,
                "",
                "=== INPUT ===",
                "",
                f"current_date: {current_date.isoformat()}",
                "",
                f"body_text:\n{document.text}",
                "",
                f"mrz_parse:\n{mrz_serialised}",
            ]
        )
