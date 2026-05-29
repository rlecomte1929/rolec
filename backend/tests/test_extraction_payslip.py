"""C1-05d · Tests for the PAYSLIP agent.

Validation criteria:
1. ≥90 % accuracy on 9-fixture set (NO acceptable lower)
2. derived_annual computed correctly per locale (×12.92 NO, ×12 default, ×13 DE Weihnachtsgeld)
3. employer_name normalised for cross-doc matching
4. Bboxes preserved (deferred to a follow-up — prompt extension)
"""

from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from typing import Any, Mapping
from uuid import uuid4

import pytest

from backend.relopass.agents import (
    AgentRegistry,
    InMemoryAgentStorage,
    ParsedDocument,
)
from backend.relopass.agents.runtime import InMemoryExtractionSink
from backend.relopass.agents.extraction import (
    PAYSLIP_AGENT_NAME,
    PayslipAgent,
    load_payslip_prompt,
)
from backend.relopass.llm import register_completer, reset_registry
from backend.relopass.llm.router import CompletionResult, set_agent_run_logger


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


FR_PAYSLIP_TEXT = """
BULLETIN DE PAIE — Acme France SAS
Salarié: Marie Dupont
Période: 01/10/2026 au 31/10/2026

BRUT                    4 200,00 €
NET À PAYER             3 250,00 €
PRÉLÈVEMENT À LA SOURCE   320,00 €
Cumul brut année          42 000,00 €
"""

DE_PAYSLIP_TEXT = """
LOHNABRECHNUNG — Beispiel GmbH
Mitarbeiter: Anna Müller
Zeitraum: 01.10.2026 - 31.10.2026

Brutto                  5.800,00 €
Netto                   3.450,00 €
Lohnsteuer              1.200,00 €
Jahresbrutto bisher    58.000,00 €
Weihnachtsgeld          5.800,00 €
"""

NO_PAYSLIP_TEXT = """
LØNNSSLIPP — Eksempel AS
Ansatt: Olav Hansen
Periode: 01.10.2026 - 31.10.2026

Brutto                  65 000,00 kr
Netto                   42 000,00 kr
Skatt                   18 200,00 kr
Feriepenger 12 %         7 800,00 kr
"""


def _document(text: str) -> ParsedDocument:
    return ParsedDocument(document_id=uuid4(), case_id=uuid4(), text=text)


def _install_completer(payload: Mapping[str, Any]) -> None:
    async def _completer(prompt: str, **_kwargs: Any) -> CompletionResult:
        return CompletionResult(
            text=json.dumps({"input": payload}, ensure_ascii=False),
            tokens_in=350,
            tokens_out=150,
        )

    register_completer("gpt-4o-mini", _completer)
    register_completer("claude-3-7-sonnet", _completer)


@pytest.fixture(autouse=True)
def _reset_state():
    reset_registry()
    set_agent_run_logger(None)
    yield
    reset_registry()
    set_agent_run_logger(None)


@pytest.fixture
def payslip_agent():
    registry = AgentRegistry(InMemoryAgentStorage())
    sink = InMemoryExtractionSink()
    agent = PayslipAgent(registry=registry, sink=sink)
    agent.register()
    return agent, sink


# ─────────────────────────────────────────────────────────────────────────────
# Prompt + registry
# ─────────────────────────────────────────────────────────────────────────────


def test_prompt_loads_from_disk():
    text = load_payslip_prompt()
    assert "PAYSLIP" in text
    # Anti-hallucination is the cardinal rule per the brief.
    assert "anti-hallucination" in text.lower() or "NEVER invent" in text


def test_register_persists_via_c1_05a_registry():
    registry = AgentRegistry(InMemoryAgentStorage())
    sink = InMemoryExtractionSink()
    agent = PayslipAgent(registry=registry, sink=sink)
    r = agent.register()
    assert r.created_new_agent
    assert r.version.name == PAYSLIP_AGENT_NAME
    assert r.version.version_number == 1


# ─────────────────────────────────────────────────────────────────────────────
# Annualization rules (Criterion 2)
# ─────────────────────────────────────────────────────────────────────────────


def test_fr_payslip_annualises_x12_by_default(payslip_agent):
    agent, sink = payslip_agent
    _install_completer(
        {
            "is_payslip": True,
            "locale": "FR",
            "employer_name": "Acme France SAS",
            "gross_monthly": "4 200,00",
            "net_monthly": "3 250,00",
            "tax_withheld": "320,00",
            "ytd_gross": "42 000,00",
            "currency": "EUR",
            "pay_period_start": "01/10/2026",
            "pay_period_end": "31/10/2026",
        }
    )
    result = asyncio.run(agent.run(_document(FR_PAYSLIP_TEXT)))
    assert result.locale == "FR"
    assert result.gross_monthly == Decimal("4200.00")
    # ×12 → 50 400
    assert result.derived_annual == Decimal("50400.00")
    assert result.currency_iso3 == "EUR"


def test_de_payslip_with_weihnachtsgeld_flag_annualises_x13(payslip_agent):
    agent, sink = payslip_agent
    _install_completer(
        {
            "is_payslip": True,
            "locale": "DE",
            "employer_name": "Beispiel GmbH",
            "employer_registry_id": "HRB 12345",
            "gross_monthly": "5.800,00",
            "net_monthly": "3.450,00",
            "currency": "EUR",
            "bonus_or_holiday_pay_guaranteed_fixed": True,
            "pay_period_start": "01.10.2026",
            "pay_period_end": "31.10.2026",
        }
    )
    result = asyncio.run(agent.run(_document(DE_PAYSLIP_TEXT)))
    assert result.locale == "DE"
    assert result.gross_monthly == Decimal("5800.00")
    # ×13 → 75 400
    assert result.derived_annual == Decimal("75400.00")


def test_no_payslip_with_feriepenger_annualises_x12_92(payslip_agent):
    agent, sink = payslip_agent
    _install_completer(
        {
            "is_payslip": True,
            "locale": "NO",
            "employer_name": "Eksempel AS",
            "employer_registry_id": "998877665",
            "gross_monthly": "65 000,00",
            "net_monthly": "42 000,00",
            "currency": "NOK",
            "bonus_or_holiday_pay_guaranteed_fixed": True,
            "pay_period_start": "01.10.2026",
            "pay_period_end": "31.10.2026",
        }
    )
    result = asyncio.run(agent.run(_document(NO_PAYSLIP_TEXT)))
    assert result.locale == "NO"
    assert result.gross_monthly == Decimal("65000.00")
    # ×12.92 → 839 800
    assert result.derived_annual == Decimal("839800.00")
    assert result.currency_iso3 == "NOK"


# ─────────────────────────────────────────────────────────────────────────────
# Employer normalisation (Criterion 3 — match against contract)
# ─────────────────────────────────────────────────────────────────────────────


def test_fr_employer_name_normalised_with_legal_suffix_stripped(payslip_agent):
    agent, sink = payslip_agent
    _install_completer(
        {
            "is_payslip": True,
            "locale": "FR",
            "employer_name": "Acme France SAS",
            "gross_monthly": "4 200,00",
            "currency": "EUR",
        }
    )
    result = asyncio.run(agent.run(_document(FR_PAYSLIP_TEXT)))
    employer_field = next(f for f in result.fields if f.field_key == "employer_name")
    canon = employer_field.value_canonical or {}
    # Display preserves the suffix; stripped form drops it for matching.
    assert canon.get("legal_name_display") == "Acme France SAS"
    assert canon.get("legal_suffix") == "SAS"
    assert "SAS" not in (canon.get("legal_name_stripped") or "")
    assert canon.get("country_iso3") == "FRA"


def test_de_employer_registry_id_detected_as_hrb(payslip_agent):
    agent, sink = payslip_agent
    _install_completer(
        {
            "is_payslip": True,
            "locale": "DE",
            "employer_name": "Beispiel GmbH",
            "employer_registry_id": "HRB 12345",
            "gross_monthly": "5.800,00",
            "currency": "EUR",
        }
    )
    result = asyncio.run(agent.run(_document(DE_PAYSLIP_TEXT)))
    employer_field = next(f for f in result.fields if f.field_key == "employer_name")
    canon = employer_field.value_canonical or {}
    assert canon.get("registry_id_kind") == "HRB"


# ─────────────────────────────────────────────────────────────────────────────
# Anti-hallucination: ambiguous → null + findings
# ─────────────────────────────────────────────────────────────────────────────


def test_ambiguous_gross_returns_null_with_findings(payslip_agent):
    agent, sink = payslip_agent
    _install_completer(
        {
            "is_payslip": True,
            "locale": "FR",
            "employer_name": "Acme France SAS",
            "gross_monthly": None,
            "currency": "EUR",
            "findings": [
                {
                    "field": "gross_monthly",
                    "code": "AMBIGUOUS_CANDIDATES",
                    "severity": "WARN",
                    "candidates": ["4 200,00", "4 250,67"],
                    "detail": "Two plausible values in the document; cannot disambiguate.",
                }
            ],
        }
    )
    result = asyncio.run(agent.run(_document(FR_PAYSLIP_TEXT)))
    assert result.gross_monthly is None
    assert result.derived_annual is None
    assert result.findings_count == 1
    # findings field must round-trip into ExtractedField rows.
    findings_field = next(f for f in result.fields if f.field_key == "findings")
    assert "AMBIGUOUS_CANDIDATES" in (findings_field.value_raw or "")


def test_locale_undetermined_emits_finding_and_skips_annualisation(payslip_agent):
    agent, sink = payslip_agent
    _install_completer(
        {
            "is_payslip": True,
            "locale": None,
            "gross_monthly": None,
            "findings": [
                {
                    "code": "LOCALE_UNDETERMINED",
                    "severity": "ERROR",
                    "detail": "Could not identify FR/DE/NO from the document.",
                }
            ],
        }
    )
    result = asyncio.run(agent.run(_document("garbled text")))
    assert result.locale is None
    assert result.derived_annual is None


# ─────────────────────────────────────────────────────────────────────────────
# Bookkeeping
# ─────────────────────────────────────────────────────────────────────────────


def test_agent_runs_row_carries_model_tokens_cost(payslip_agent):
    agent, sink = payslip_agent
    _install_completer(
        {
            "is_payslip": True,
            "locale": "FR",
            "employer_name": "Acme France SAS",
            "gross_monthly": "4 200,00",
            "currency": "EUR",
        }
    )
    result = asyncio.run(agent.run(_document(FR_PAYSLIP_TEXT)))
    assert len(sink.agent_runs) == 1
    row = sink.agent_runs[0]
    assert row.model_name == "gpt-4o-mini"
    assert row.tokens_in == 350
    assert row.tokens_out == 150
    # gpt-4o-mini cost: 350 × 0.00000015 + 150 × 0.0000006 = 0.0001425
    assert row.cost_usd == pytest.approx(0.0001425, rel=1e-6)


def test_run_proceeds_when_llm_router_has_no_completer(payslip_agent):
    agent, sink = payslip_agent
    result = asyncio.run(agent.run(_document(FR_PAYSLIP_TEXT)))
    assert result.model_name == "(none — LLM unrouted)"
    assert result.gross_monthly is None
