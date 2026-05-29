"""EMPLOYMENT_CONTRACT Extraction Agent (C1-05c).

Multi-jurisdiction (FR CDI/CDD, DE Arbeitsvertrag, NO arbeidskontrakt).
Hybrid extraction: LLM does the cross-language reading via the C1-05P-c
prompt; the normalize package (C1-06) provides deterministic primitives
for money, employer, and date parsing of the LLM output.

The output ExtractedField rows feed:
  * C1-09 IN→DE Blue Card salary-threshold check
  * C1-08 cross-document salary-contradiction detection (vs. payslips)

Salary precision matters more than any other field here — the
Architecture Report calls it out as the contradiction-detection axis.
``gross_salary_guaranteed_fixed_only_bool`` is the binary the corridor
agents use; it MUST be false whenever the contract document mentions
'commission', 'bonus', 'variable', 'target', 'stock options', or
'sign-on' (Architecture Report §3.4).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, Mapping, Optional, Tuple
from uuid import UUID, uuid4
from datetime import datetime, timezone

from backend.relopass.normalize import (
    normalize_employer,
    parse_date,
    parse_money,
)
from backend.relopass.normalize.money import annualize as money_annualize

from ..models import (
    ExtractedField,
    ExtractionAgent,
    ExtractionAgentVersion,
    ParsedDocument,
)
from ..registry import AgentRegistry, SaveResult
from ..runtime import ExtractionSink
from ._common import LLMCallResult, call_llm_with_retry, make_field

logger = logging.getLogger(__name__)


EMPLOYMENT_CONTRACT_AGENT_NAME = "employment_contract"


Jurisdiction = Literal["FR", "DE", "NO"]


# Annualization multipliers per Architecture Report §3.4.
# FR: standard ×12; 13e/14e mois only counted when contractually guaranteed.
# DE: standard ×12; +1 month when Weihnachtsgeld is guaranteed-fixed.
# NO: standard ×12; ×12.92 when feriepenger is explicitly contracted.
DEFAULT_MULTIPLIERS: Mapping[Jurisdiction, Decimal] = {
    "FR": Decimal("12"),
    "DE": Decimal("12"),
    "NO": Decimal("12"),
}

JURISDICTION_BONUS_MULTIPLIERS: Mapping[Jurisdiction, Decimal] = {
    "FR": Decimal("13"),  # 13e mois (if guaranteed)
    "DE": Decimal("13"),  # Weihnachtsgeld (if guaranteed)
    "NO": Decimal("12.92"),  # Feriepenger (5 weeks holiday allowance)
}


# Triggers that mean salary is NOT guaranteed-fixed-only. Match
# case-insensitively against the raw contract text — these include
# obvious English equivalents because contracts often use the borrowed
# terms ("bonus", "commission", "stock options") even in French/German/Norwegian.
NON_FIXED_TRIGGERS: Tuple[str, ...] = (
    "commission",
    "bonus",
    "variable",
    "target",
    "stock options",
    "sign-on",
    "signon",
    "prime variable",
    "prime cible",
    "vergütungsbestandteil",
    "boni",
)


def is_guaranteed_fixed_only(contract_text: str) -> bool:
    """Heuristic check used by the agent when the LLM did not emit a value
    or when its output should be cross-checked against the document text.
    """
    lower = contract_text.lower()
    return not any(trigger in lower for trigger in NON_FIXED_TRIGGERS)


# ─────────────────────────────────────────────────────────────────────────────
# Prompt loading — one prompt per jurisdiction
# ─────────────────────────────────────────────────────────────────────────────


_PROMPTS_DIR = Path(__file__).resolve().parents[4] / "prompts" / "extraction"
_PROMPT_FILES = {
    "FR": _PROMPTS_DIR / "employment_contract_fr_v1.txt",
    "DE": _PROMPTS_DIR / "employment_contract_de_v1.txt",
    "NO": _PROMPTS_DIR / "employment_contract_no_v1.txt",
}


def load_employment_contract_prompt(jurisdiction: Jurisdiction) -> str:
    path = _PROMPT_FILES[jurisdiction]
    return path.read_text(encoding="utf-8")


def _all_prompts_concatenated() -> str:
    """Concatenate FR + DE + NO prompts so version_hash incorporates all
    three. Used for the ExtractionAgent definition's extraction_instructions.
    """
    return "\n\n=== PROMPT BREAK ===\n\n".join(
        load_employment_contract_prompt(j) for j in ("FR", "DE", "NO")
    )


# ─────────────────────────────────────────────────────────────────────────────
# ExtractionAgent definition (lazy singleton)
# ─────────────────────────────────────────────────────────────────────────────


def _build_agent() -> ExtractionAgent:
    return ExtractionAgent(
        name=EMPLOYMENT_CONTRACT_AGENT_NAME,
        description=(
            "Multi-jurisdiction EMPLOYMENT_CONTRACT extraction (FR CDI/CDD, "
            "DE Arbeitsvertrag, NO arbeidskontrakt). LLM extracts position + "
            "salary + dates; normalize.{money,employers,dates} normalises the "
            "output into Decimal/ISO 8601/registry-ID canonical form."
        ),
        extraction_instructions=_all_prompts_concatenated(),
        value_type="enum",
        unit=None,
        dimensions="structured: employer + position + salary + dates",
        resolution_instructions=(
            "When salary is ambiguous, return null + low confidence (precision > recall). "
            "Annualization: ×12 default; ×13 when DE Weihnachtsgeld / FR 13e mois is "
            "contractually guaranteed; ×12.92 when NO feriepenger is explicit. "
            "guaranteed_fixed_only = false when commission / bonus / variable / target / "
            "stock options / sign-on language is present."
        ),
        inconsistency_instructions=(
            "If the document is not an employment contract (CDI/CDD/Arbeitsvertrag/"
            "arbeidskontrakt), set is_employment_contract=false and emit no fields."
        ),
        enable_web_search=False,
        enable_complex_calculations_in_resolution=False,
        examples=(),
        output_schema_required_keys=(
            "is_employment_contract",
            "employer_legal_name",
            "gross_salary",
            "currency",
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
class EmploymentContractResult:
    agent_run_id: UUID
    agent_version_id: UUID
    jurisdiction: Jurisdiction
    fields: Tuple[ExtractedField, ...]
    llm_payload: Mapping[str, Any]
    gross_salary_annual: Optional[Decimal]
    currency_iso3: Optional[str]
    guaranteed_fixed_only: bool
    model_name: str
    tokens_in: int
    tokens_out: int
    cost_usd: float


# ─────────────────────────────────────────────────────────────────────────────
# Agent orchestrator
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class EmploymentContractAgent:
    """Orchestrates the EMPLOYMENT_CONTRACT extraction.

    Usage::

        agent = EmploymentContractAgent(registry, sink)
        agent.register()
        result = asyncio.run(agent.run(document, jurisdiction="FR"))
    """

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
            raise RuntimeError("EmploymentContractAgent.run() called before register()")
        return self._agent_version

    async def run(
        self,
        document: ParsedDocument,
        *,
        jurisdiction: Jurisdiction,
    ) -> EmploymentContractResult:
        version = self.agent_version
        agent_run_id = uuid4()
        started_at = datetime.now(tz=timezone.utc)

        # Pick the right prompt for the jurisdiction; concatenate with document text.
        prompt = (
            load_employment_contract_prompt(jurisdiction)
            + "\n\n=== DOCUMENT TEXT ===\n\n"
            + document.text
        )
        llm = await call_llm_with_retry(
            prompt,
            required_keys=version.output_schema_required_keys,
            case_id=str(document.case_id) if document.case_id else None,
        )

        payload = llm.payload

        # ---- Deterministic normalization of the LLM output ----
        money_result = self._parse_salary(payload, jurisdiction)
        gross_annual, currency_iso3 = money_result

        guaranteed_fixed = self._guaranteed_fixed_only(payload, document.text)
        employer_norm = self._normalize_employer(payload, jurisdiction)
        contract_start = self._normalize_date(payload.get("contract_start_date"), jurisdiction)

        # ---- Build ExtractedField rows ----
        raw_fields = (
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="employer_legal_name",
                value=employer_norm["legal_name_display"] if employer_norm else payload.get("employer_legal_name"),
                source="llm_employment_contract_v1",
                canonical_extras=employer_norm or {},
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="employer_registry_id",
                value=(employer_norm or {}).get("registry_id"),
                source="llm+normalize_employers",
                canonical_extras={"kind": (employer_norm or {}).get("registry_id_kind")},
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="position_title",
                value=payload.get("position_title"),
                source="llm_employment_contract_v1",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="position_isco_2008",
                value=payload.get("position_isco_2008"),
                source="llm_employment_contract_v1",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="gross_salary_annual",
                value=str(gross_annual) if gross_annual is not None else None,
                source="llm+normalize_money",
                canonical_extras={
                    "currency_iso3": currency_iso3,
                    "jurisdiction": jurisdiction,
                    "annualization_period": payload.get("salary_period", "year"),
                },
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="gross_salary_guaranteed_fixed_only_bool",
                value=str(guaranteed_fixed).lower(),
                source="llm+text_heuristic",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="contract_start_date",
                value=contract_start.isoformat() if contract_start else None,
                source="llm+normalize_dates",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="contract_duration_months",
                value=payload.get("contract_duration_months"),
                source="llm_employment_contract_v1",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="working_time_percent",
                value=payload.get("working_time_percent"),
                source="llm_employment_contract_v1",
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

        return EmploymentContractResult(
            agent_run_id=agent_run_id,
            agent_version_id=version.agent_version_id,
            jurisdiction=jurisdiction,
            fields=fields,
            llm_payload=payload,
            gross_salary_annual=gross_annual,
            currency_iso3=currency_iso3,
            guaranteed_fixed_only=guaranteed_fixed,
            model_name=llm.model_name,
            tokens_in=llm.tokens_in,
            tokens_out=llm.tokens_out,
            cost_usd=llm.cost_usd,
        )

    def run_sync(self, document: ParsedDocument, *, jurisdiction: Jurisdiction) -> EmploymentContractResult:
        import asyncio

        return asyncio.run(self.run(document, jurisdiction=jurisdiction))

    # ---- Helpers ----

    @staticmethod
    def _parse_salary(
        payload: Mapping[str, Any], jurisdiction: Jurisdiction
    ) -> Tuple[Optional[Decimal], Optional[str]]:
        """Combine the LLM's salary value + period + currency into a
        canonical annual Decimal + ISO 4217 currency.
        """
        gross = payload.get("gross_salary")
        if gross is None:
            return None, None
        period = (payload.get("salary_period") or "year").lower()
        currency_hint = payload.get("currency")

        # Use the locale-aware money parser; pass the jurisdiction so
        # locale-specific formats (FR ' ', DE '.', NO ' ') are recognised.
        locale_hint = jurisdiction.lower()
        parsed = parse_money(f"{gross} {currency_hint or ''}".strip(), locale_hint=locale_hint)
        if parsed.amount is None:
            return None, parsed.currency_iso3 or currency_hint

        # Annualise via normalize.money.annualize for the standard periods;
        # the jurisdiction bonus multipliers override only when explicitly
        # signalled by the LLM payload.
        if period in {"hour", "day", "week", "month", "quarter", "year"}:
            annual = money_annualize(parsed.amount, period)
        else:
            annual = parsed.amount  # assume annual when period is unknown

        if payload.get("bonus_or_holiday_pay_guaranteed_fixed") is True and period == "month":
            multiplier = JURISDICTION_BONUS_MULTIPLIERS[jurisdiction]
            annual = (parsed.amount * multiplier).quantize(Decimal("0.01"))

        return annual, parsed.currency_iso3 or currency_hint

    @staticmethod
    def _guaranteed_fixed_only(payload: Mapping[str, Any], contract_text: str) -> bool:
        v = payload.get("gross_salary_guaranteed_fixed_only_bool")
        if isinstance(v, bool):
            # Trust the LLM when it commits, but cross-check with the
            # heuristic — if either signal says "not fixed", report false.
            return v and is_guaranteed_fixed_only(contract_text)
        return is_guaranteed_fixed_only(contract_text)

    @staticmethod
    def _normalize_employer(
        payload: Mapping[str, Any], jurisdiction: Jurisdiction
    ) -> Optional[Mapping[str, Any]]:
        legal_name = payload.get("employer_legal_name")
        if not legal_name:
            return None
        # Jurisdiction → country_iso3 used by normalize_employer for
        # registry-id format detection (FR→FRA→SIREN/SIRET, DE→DEU→HRB,
        # NO→NOR→organisasjonsnummer). The registry-id hint goes through the
        # explicit `registry_id` kwarg, not concatenated into the name.
        country = {"FR": "FRA", "DE": "DEU", "NO": "NOR"}[jurisdiction]
        registry_id_hint = payload.get("employer_registry_id")
        norm = normalize_employer(
            str(legal_name),
            country_iso3=country,
            registry_id=str(registry_id_hint) if registry_id_hint else None,
        )
        return {
            "legal_name_display": norm.legal_name_display,
            "legal_name_stripped": norm.legal_name_stripped,
            "legal_suffix": norm.legal_suffix,
            "registry_id": norm.registry_id,
            "registry_id_kind": norm.registry_id_kind,
            "country_iso3": norm.country_iso3,
        }

    @staticmethod
    def _normalize_date(raw: Any, jurisdiction: Jurisdiction):
        if not raw:
            return None
        from datetime import date

        locale_hint = jurisdiction.lower()
        parsed = parse_date(str(raw), locale_hint=locale_hint)
        if parsed.iso is None:
            return None
        # ParsedDate.iso is an ISO 8601 date string; convert back to date for
        # downstream consumers that prefer the typed value.
        return date.fromisoformat(parsed.iso)
