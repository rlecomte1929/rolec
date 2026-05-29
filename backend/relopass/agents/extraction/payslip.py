"""PAYSLIP Extraction Agent (C1-05d).

Locale-aware money parsing is the load-bearing primitive here. Layouts
differ radically per jurisdiction:

* **FR** — bulletin de paie. Right-justified columns, abbreviations
  ("BRUT", "NET À PAYER"), `1 234,56 €` money format.
* **DE** — Lohnabrechnung. Dense tabular layout, "Brutto" / "Netto",
  `1.234,56 €` format.
* **NO** — lønnsslipp. Densest of the three; OCR often misaligns cells.
  `1 234,56 kr` or `NOK 1 234,56`.

The agent is intentionally conservative: when a field is ambiguous,
the prompt (C1-05P-d) instructs the model to return null + a `findings[]`
entry rather than invent a value. The annualisation logic mirrors C1-05c's
employment contract: ×12 default, ×13 for DE Weihnachtsgeld, ×12.92 for
NO feriepenger when the LLM flags either as explicitly present on the
slip.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, Mapping, Optional, Tuple
from uuid import UUID, uuid4

from backend.relopass.normalize import normalize_employer, parse_date, parse_money
from backend.relopass.normalize.money import annualize as money_annualize

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


PAYSLIP_AGENT_NAME = "payslip"
Locale = Literal["FR", "DE", "NO"]


_PROMPTS_DIR = Path(__file__).resolve().parents[4] / "prompts" / "extraction"
_PROMPT_PATH = _PROMPTS_DIR / "payslip_v1.txt"


def load_payslip_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# ExtractionAgent definition (lazy singleton)
# ─────────────────────────────────────────────────────────────────────────────


def _build_agent() -> ExtractionAgent:
    return ExtractionAgent(
        name=PAYSLIP_AGENT_NAME,
        description=(
            "Locale-aware PAYSLIP extraction (FR bulletin / DE Lohnabrechnung / "
            "NO lønnsslipp). LLM emits a single canonical JSON; normalize.money "
            "parses the Decimal + ISO 4217 currency; derived_annual is computed "
            "via locale rules (×12 default, ×13 DE Weihnachtsgeld, ×12.92 NO feriepenger)."
        ),
        extraction_instructions=load_payslip_prompt(),
        value_type="enum",
        unit=None,
        dimensions="structured: gross + net + period + employer + findings",
        resolution_instructions=(
            "Anti-hallucination rule from C1-05P-d: when ambiguous, return null + "
            "add a findings entry. NEVER pick a number from the document just to "
            "fill a slot. Resolution UI shows findings; ambiguous-but-flagged is "
            "recoverable, invented values are not."
        ),
        inconsistency_instructions=(
            "If locale cannot be determined, return mostly null + a single "
            "LOCALE_UNDETERMINED finding. NO lønnsslipp accepted to fall short "
            "of FR/DE accuracy — Reducto fallback in Cohort 3 closes the gap."
        ),
        enable_web_search=False,
        enable_complex_calculations_in_resolution=False,
        examples=(),
        output_schema_required_keys=("locale", "is_payslip"),
    )


_AGENT_SINGLETON: Optional[ExtractionAgent] = None


def _get_agent() -> ExtractionAgent:
    global _AGENT_SINGLETON
    if _AGENT_SINGLETON is None:
        _AGENT_SINGLETON = _build_agent()
    return _AGENT_SINGLETON


# ─────────────────────────────────────────────────────────────────────────────
# Annualization factors (mirror C1-05c)
# ─────────────────────────────────────────────────────────────────────────────


JURISDICTION_BONUS_MULTIPLIERS: Mapping[Locale, Decimal] = {
    "FR": Decimal("13"),
    "DE": Decimal("13"),
    "NO": Decimal("12.92"),
}


# ─────────────────────────────────────────────────────────────────────────────
# Result type
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PayslipResult:
    agent_run_id: UUID
    agent_version_id: UUID
    locale: Optional[Locale]
    fields: Tuple[ExtractedField, ...]
    llm_payload: Mapping[str, Any]
    gross_monthly: Optional[Decimal]
    derived_annual: Optional[Decimal]
    currency_iso3: Optional[str]
    findings_count: int
    model_name: str
    tokens_in: int
    tokens_out: int
    cost_usd: float


# ─────────────────────────────────────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class PayslipAgent:
    """Drives the PAYSLIP extraction.

    Usage::

        agent = PayslipAgent(registry, sink)
        agent.register()
        result = asyncio.run(agent.run(document))

    Unlike :class:`EmploymentContractAgent`, locale is detected by the LLM
    from the document text rather than passed as a kwarg — payslips don't
    declare their jurisdiction explicitly.
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
            raise RuntimeError("PayslipAgent.run() called before register()")
        return self._agent_version

    async def run(self, document: ParsedDocument) -> PayslipResult:
        version = self.agent_version
        agent_run_id = uuid4()
        started_at = datetime.now(tz=timezone.utc)

        prompt = (
            load_payslip_prompt()
            + "\n\n=== DOCUMENT TEXT ===\n\n"
            + document.text
        )
        llm = await call_llm_with_retry(
            prompt,
            required_keys=version.output_schema_required_keys,
            case_id=str(document.case_id) if document.case_id else None,
        )
        payload = llm.payload

        locale: Optional[Locale] = (
            payload.get("locale") if payload.get("locale") in {"FR", "DE", "NO"} else None
        )

        gross_monthly, currency = self._parse_amount(payload, "gross_monthly", locale)
        net_monthly, _ = self._parse_amount(payload, "net_monthly", locale)
        tax_withheld, _ = self._parse_amount(payload, "tax_withheld", locale)
        ytd_gross, _ = self._parse_amount(payload, "ytd_gross", locale)

        derived_annual = self._compute_annual(gross_monthly, payload, locale)

        period_start = self._normalize_date(payload.get("pay_period_start"), locale)
        period_end = self._normalize_date(payload.get("pay_period_end"), locale)

        employer = self._normalize_employer(payload, locale)
        findings = payload.get("findings") or []

        raw_fields = (
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="locale",
                value=locale,
                source="llm_payslip_v1",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="employer_name",
                value=(employer or {}).get("legal_name_display")
                or payload.get("employer_name"),
                source="llm+normalize_employers",
                canonical_extras=employer or {},
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="employer_address",
                value=payload.get("employer_address"),
                source="llm_payslip_v1",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="gross_monthly",
                value=str(gross_monthly) if gross_monthly is not None else None,
                source="llm+normalize_money",
                canonical_extras={"currency_iso3": currency, "locale": locale},
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="net_monthly",
                value=str(net_monthly) if net_monthly is not None else None,
                source="llm+normalize_money",
                canonical_extras={"currency_iso3": currency, "locale": locale},
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="tax_withheld",
                value=str(tax_withheld) if tax_withheld is not None else None,
                source="llm+normalize_money",
                canonical_extras={"currency_iso3": currency, "locale": locale},
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="ytd_gross",
                value=str(ytd_gross) if ytd_gross is not None else None,
                source="llm+normalize_money",
                canonical_extras={"currency_iso3": currency, "locale": locale},
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="derived_annual",
                value=str(derived_annual) if derived_annual is not None else None,
                source="derived_from_gross_monthly",
                canonical_extras={
                    "currency_iso3": currency,
                    "locale": locale,
                    "multiplier_rule": self._multiplier_rule_label(payload, locale),
                },
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="pay_period_start",
                value=period_start.isoformat() if period_start else None,
                source="llm+normalize_dates",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="pay_period_end",
                value=period_end.isoformat() if period_end else None,
                source="llm+normalize_dates",
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="findings",
                value=findings if findings else None,
                source="llm_payslip_v1",
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

        return PayslipResult(
            agent_run_id=agent_run_id,
            agent_version_id=version.agent_version_id,
            locale=locale,
            fields=fields,
            llm_payload=payload,
            gross_monthly=gross_monthly,
            derived_annual=derived_annual,
            currency_iso3=currency,
            findings_count=len(findings),
            model_name=llm.model_name,
            tokens_in=llm.tokens_in,
            tokens_out=llm.tokens_out,
            cost_usd=llm.cost_usd,
        )

    def run_sync(self, document: ParsedDocument) -> PayslipResult:
        import asyncio

        return asyncio.run(self.run(document))

    # ---- Helpers ----

    @staticmethod
    def _parse_amount(
        payload: Mapping[str, Any], key: str, locale: Optional[Locale]
    ) -> Tuple[Optional[Decimal], Optional[str]]:
        raw = payload.get(key)
        if raw is None or raw == "":
            return None, None
        currency_hint = payload.get("currency")
        text = f"{raw} {currency_hint or ''}".strip()
        parsed = parse_money(text, locale_hint=(locale.lower() if locale else None))
        return parsed.amount, parsed.currency_iso3 or currency_hint

    @staticmethod
    def _compute_annual(
        gross_monthly: Optional[Decimal],
        payload: Mapping[str, Any],
        locale: Optional[Locale],
    ) -> Optional[Decimal]:
        if gross_monthly is None:
            return None
        if locale and payload.get("bonus_or_holiday_pay_guaranteed_fixed") is True:
            multiplier = JURISDICTION_BONUS_MULTIPLIERS[locale]
            return (gross_monthly * multiplier).quantize(Decimal("0.01"))
        return money_annualize(gross_monthly, "month")

    @staticmethod
    def _multiplier_rule_label(payload: Mapping[str, Any], locale: Optional[Locale]) -> str:
        if locale and payload.get("bonus_or_holiday_pay_guaranteed_fixed") is True:
            return {
                "FR": "x13 (13e mois guaranteed)",
                "DE": "x13 (Weihnachtsgeld guaranteed)",
                "NO": "x12.92 (feriepenger explicit)",
            }[locale]
        return "x12 (default)"

    @staticmethod
    def _normalize_employer(
        payload: Mapping[str, Any], locale: Optional[Locale]
    ) -> Optional[Mapping[str, Any]]:
        name = payload.get("employer_name")
        if not name:
            return None
        country = None
        if locale is not None:
            country = {"FR": "FRA", "DE": "DEU", "NO": "NOR"}[locale]
        registry_hint = payload.get("employer_registry_id")
        norm = normalize_employer(
            str(name),
            country_iso3=country,
            registry_id=str(registry_hint) if registry_hint else None,
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
    def _normalize_date(raw: Any, locale: Optional[Locale]):
        if not raw:
            return None
        from datetime import date

        hint = locale.lower() if locale else None
        parsed = parse_date(str(raw), locale_hint=hint)
        if parsed.iso is None:
            return None
        return date.fromisoformat(parsed.iso)
