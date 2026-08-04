"""TAX_CERT extraction agent — NORWAY (C2-02b).

Handles both NO tax-document subtypes via the prompt's discriminator:
* SKATTEMELDING — annual tax return draft/filing (Skatteetaten).
* SKATTEOPPGJOR — final tax settlement notice.

The holder identifier is an 11-digit fødselsnummer (FNR). The agent extracts
it into ``tax_id``; the runtime independently re-checks the Skatteetaten
Mod-11 algorithm via ``tax_id_format_finding`` and signals redaction with
``holder_national_id_redacted``.

Downstream consumers:
* FR→NO corridor residency proof (NO cert + employee.current_residence=FRA
  → CONTRADICTION_RESIDENCE).
* Salary cross-check (annualised lønnsinntekt vs the employment contract).
* C1-08 name comparator against the passport MRZ.

Mirrors ``diploma.py``; runtime findings via the shared
``_tax_cert_findings`` helper.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Tuple
from uuid import UUID, uuid4

from ..models import (
    ExtractedField,
    ExtractionAgent,
    ExtractionAgentVersion,
    ParsedDocument,
)
from ..registry import AgentRegistry, SaveResult
from ..runtime import ExtractionSink
from ._common import call_llm_with_retry, make_field
from ._tax_cert_findings import all_findings
from ._validators_freshness import Finding

logger = logging.getLogger(__name__)


TAX_CERT_NO_AGENT_NAME = "tax_cert_no"
# One 'TAX_CERT' code, three locale agents — the issuing country discriminates.
# See TAX_CERT_AGENTS_BY_ISSUING_COUNTRY in extraction/__init__.py.
TAX_CERT_NO_DOCUMENT_TYPE = "TAX_CERT"
TAX_CERT_NO_ISSUING_COUNTRY = "NOR"  # ISO-3166-1 alpha-3
_COUNTRY_ISO3 = "NOR"


# ─────────────────────────────────────────────────────────────────────────────
# Prompt loading
# ─────────────────────────────────────────────────────────────────────────────


_PROMPT_PATH = (
    Path(__file__).resolve().parents[4] / "prompts" / "extraction" / "tax_cert_no_v1.txt"
)


def load_tax_cert_no_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# ExtractionAgent definition
# ─────────────────────────────────────────────────────────────────────────────


def _build_agent() -> ExtractionAgent:
    return ExtractionAgent(
        name=TAX_CERT_NO_AGENT_NAME,
        description=(
            "TAX_CERT extraction — NO skattemelding or skatteoppgjør "
            "(Skatteetaten). Emits document_subtype, issuing authority, "
            "tax_year, 11-digit FNR tax_id (redaction-flagged), holder name "
            "+ dob, residence_country_iso3, gross/business/net income, total "
            "tax. Runtime layers freshness + Mod-11 FNR + residence "
            "cross-checks."
        ),
        extraction_instructions=load_tax_cert_no_prompt(),
        value_type="enum",
        unit=None,
        dimensions="structured: subtype + issuer + tax_year + fnr + names + income",
        resolution_instructions=(
            "Issuing country is always NOR. document_subtype is SKATTEMELDING "
            "(draft) or SKATTEOPPGJOR (settled). The FNR is extracted "
            "faithfully; Mod-11 verification is the runtime's job. Always set "
            "holder_national_id_redacted=true."
        ),
        inconsistency_instructions=(
            "TAX_CERT_RESIDENCE_MISMATCH and TAX_ID_FORMAT_INVALID_NO (Mod-11) "
            "are runtime findings computed against case context."
        ),
        enable_web_search=False,
        enable_complex_calculations_in_resolution=False,
        examples=(),
        output_schema_required_keys=(
            "is_tax_document",
            "document_subtype",
            "issuing_country_iso3",
            "issuing_authority",
            "tax_year",
            "tax_id",
            "holder_national_id_redacted",
            "holder_name",
            "residence_country_iso3",
            "currency_iso3",
            "findings",
            "agent_confidence",
        ),
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
class TaxCertResult:
    agent_run_id: UUID
    agent_version_id: UUID
    fields: Tuple[ExtractedField, ...]
    findings: Tuple[Finding, ...]
    llm_payload: Mapping[str, Any]
    model_name: str
    tokens_in: int
    tokens_out: int
    cost_usd: float


# ─────────────────────────────────────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class TaxCertNoAgent:
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
            raise RuntimeError("TaxCertNoAgent.run() called before register()")
        return self._agent_version

    async def run(
        self,
        document: ParsedDocument,
        *,
        case_employee_country_iso3: Optional[str] = None,
        reference_date: Optional[date] = None,
    ) -> TaxCertResult:
        version = self.agent_version
        agent_run_id = uuid4()
        started_at = datetime.now(tz=timezone.utc)
        ref_date = reference_date or date.today()

        prompt = (
            load_tax_cert_no_prompt()
            + "\n\n=== DOCUMENT TEXT ===\n\n"
            + document.text
        )
        llm = await call_llm_with_retry(
            prompt,
            required_keys=version.output_schema_required_keys,
            case_id=str(document.case_id) if document.case_id else None,
        )
        payload = llm.payload

        findings = all_findings(
            country=_COUNTRY_ISO3,
            payload=payload,
            case_employee_country_iso3=case_employee_country_iso3,
            reference_date=ref_date,
        )

        # FNR is PII — flag for downstream redaction; never widen its exposure.
        redact = bool(payload.get("holder_national_id_redacted", True))

        raw_fields = (
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="document_subtype",
                value=payload.get("document_subtype"),
                source="llm_tax_cert_no_v1",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="issuing_authority",
                value=payload.get("issuing_authority"),
                source="llm_tax_cert_no_v1",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="issuing_authority_normalized",
                value=payload.get("issuing_authority_normalized"),
                source="llm_tax_cert_no_v1",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="tax_year",
                value=payload.get("tax_year"),
                source="llm_tax_cert_no_v1",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="tax_id",
                value=payload.get("tax_id"),
                source="llm_tax_cert_no_v1",
                canonical_extras={"pii": True, "redact": redact},
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="holder_name",
                value=payload.get("holder_name"),
                source="llm_tax_cert_no_v1",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="holder_dob",
                value=payload.get("holder_dob"),
                source="llm_tax_cert_no_v1",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="residence_country_iso3",
                value=payload.get("residence_country_iso3"),
                source="llm_tax_cert_no_v1",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="gross_income_annual",
                value=payload.get("gross_income_annual"),
                source="llm_tax_cert_no_v1",
                canonical_extras={"currency": payload.get("currency_iso3")},
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="business_income_annual",
                value=payload.get("business_income_annual"),
                source="llm_tax_cert_no_v1",
                canonical_extras={"currency": payload.get("currency_iso3")},
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="net_taxable_income_annual",
                value=payload.get("net_taxable_income_annual"),
                source="llm_tax_cert_no_v1",
                canonical_extras={"currency": payload.get("currency_iso3")},
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="total_tax_annual",
                value=payload.get("total_tax_annual"),
                source="llm_tax_cert_no_v1",
                canonical_extras={"currency": payload.get("currency_iso3")},
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="findings",
                value=[f.code for f in findings] or None,
                source="tax_cert_no_runtime+llm",
                canonical_extras={
                    "findings": [
                        {"severity": f.severity, "code": f.code, "message": f.message}
                        for f in findings
                    ]
                },
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

        return TaxCertResult(
            agent_run_id=agent_run_id,
            agent_version_id=version.agent_version_id,
            fields=fields,
            findings=findings,
            llm_payload=payload,
            model_name=llm.model_name,
            tokens_in=llm.tokens_in,
            tokens_out=llm.tokens_out,
            cost_usd=llm.cost_usd,
        )

    def run_sync(
        self,
        document: ParsedDocument,
        *,
        case_employee_country_iso3: Optional[str] = None,
        reference_date: Optional[date] = None,
    ) -> TaxCertResult:
        import asyncio

        return asyncio.run(
            self.run(
                document,
                case_employee_country_iso3=case_employee_country_iso3,
                reference_date=reference_date,
            )
        )
