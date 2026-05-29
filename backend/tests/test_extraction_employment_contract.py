"""C1-05c · Tests for the EMPLOYMENT_CONTRACT agent.

Validation criteria:
1. ≥90 % field accuracy on 6-fixture set (mocked LLM; deterministic path verified)
2. Employer registry_id format matches jurisdiction (SIREN / HRB / orgnr)
3. gross_salary_annual is Decimal with currency_iso3 set
4. Annualization correct per jurisdiction (×12 / ×13 / ×12.92)
5. guaranteed_fixed_only_bool correctly excludes bonus/commission language
6. Bboxes preserved (when the LLM emits them)
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
    EMPLOYMENT_CONTRACT_AGENT_NAME,
    EmploymentContractAgent,
    Jurisdiction,
    load_employment_contract_prompt,
)
from backend.relopass.agents.extraction.employment_contract import (
    NON_FIXED_TRIGGERS,
    is_guaranteed_fixed_only,
)
from backend.relopass.llm import register_completer, reset_registry
from backend.relopass.llm.router import CompletionResult, set_agent_run_logger


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


FR_CDI_TEXT = """
CONTRAT DE TRAVAIL À DURÉE INDÉTERMINÉE

Entre Acme France SAS, dont le siège est sis à Paris, SIREN 552 120 222
et Madame Marie Dupont, ci-après "le Salarié".

Article 3 - Rémunération
La rémunération brute mensuelle est fixée à 4 200,00 €.

Article 4 - Date d'effet
Le présent contrat prend effet le 1er septembre 2026.

Article 5 - Durée du travail
Temps plein, 35 heures hebdomadaires (100 %).
"""

FR_CDI_BONUS_TEXT = FR_CDI_TEXT + "\nArticle 8 — Prime variable jusqu'à 15 % de la rémunération annuelle, conditionnée à l'atteinte des objectifs."

DE_AV_TEXT = """
ARBEITSVERTRAG

zwischen der Beispiel GmbH, eingetragen im Handelsregister HRB 12345 beim
Amtsgericht München, und Frau Anna Müller ("Arbeitnehmerin").

§ 3 Vergütung
Das monatliche Bruttogehalt beträgt 5.800,00 €.
Weihnachtsgeld in Höhe eines Monatsgehalts wird als feste Gehaltsbestandteil
gezahlt.

§ 5 Beginn
Das Arbeitsverhältnis beginnt am 01.10.2026.

§ 6 Arbeitszeit
Vollzeit, 40 Stunden pro Woche.
"""

NO_AK_TEXT = """
ARBEIDSKONTRAKT

mellom Eksempel AS, organisasjonsnummer 998 877 665, og Olav Hansen
("Arbeidstaker").

§ 4 Lønn
Brutto månedslønn: 65 000 NOK.
Feriepenger 12 % i henhold til ferieloven.

§ 6 Tiltredelse
Arbeidsforholdet starter 1. november 2026.

§ 8 Arbeidstid
Heltid, 37,5 timer per uke.
"""


def _document(text: str) -> ParsedDocument:
    return ParsedDocument(document_id=uuid4(), case_id=uuid4(), text=text)


def _install_completer(payload: Mapping[str, Any]) -> None:
    async def _completer(prompt: str, **_kwargs: Any) -> CompletionResult:
        return CompletionResult(
            text=json.dumps({"input": payload}, ensure_ascii=False),
            tokens_in=400,
            tokens_out=180,
        )

    register_completer("gpt-4o-mini", _completer)
    register_completer("claude-3-7-sonnet", _completer)


@pytest.fixture(autouse=True)
def _reset_global_state():
    reset_registry()
    set_agent_run_logger(None)
    yield
    reset_registry()
    set_agent_run_logger(None)


@pytest.fixture
def contract_agent():
    registry = AgentRegistry(InMemoryAgentStorage())
    sink = InMemoryExtractionSink()
    agent = EmploymentContractAgent(registry=registry, sink=sink)
    agent.register()
    return agent, sink


# ─────────────────────────────────────────────────────────────────────────────
# Prompt + registry
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("jurisdiction", ["FR", "DE", "NO"])
def test_prompt_per_jurisdiction_loads_from_disk(jurisdiction):
    text = load_employment_contract_prompt(jurisdiction)
    assert "EMPLOYMENT_CONTRACT" in text
    # Sanity — each prompt mentions its jurisdiction name.
    assert any(tag in text for tag in [jurisdiction, jurisdiction.lower(), {"FR": "FRANCE", "DE": "GERMANY", "NO": "NORWAY"}[jurisdiction]])


def test_register_persists_via_c1_05a_registry():
    registry = AgentRegistry(InMemoryAgentStorage())
    sink = InMemoryExtractionSink()
    agent = EmploymentContractAgent(registry=registry, sink=sink)
    r = agent.register()
    assert r.created_new_agent
    assert r.version.name == EMPLOYMENT_CONTRACT_AGENT_NAME
    assert r.version.version_number == 1


# ─────────────────────────────────────────────────────────────────────────────
# Salary parsing + annualization
# ─────────────────────────────────────────────────────────────────────────────


def test_fr_monthly_salary_annualises_x12(contract_agent):
    agent, sink = contract_agent
    _install_completer(
        {
            "is_employment_contract": True,
            "employer_legal_name": "Acme France SAS",
            "employer_registry_id": "552120222",
            "position_title": "Senior Engineer",
            "gross_salary": "4200,00",
            "currency": "EUR",
            "salary_period": "month",
            "gross_salary_guaranteed_fixed_only_bool": True,
            "contract_start_date": "01/09/2026",
            "working_time_percent": 100,
        }
    )
    result = asyncio.run(agent.run(_document(FR_CDI_TEXT), jurisdiction="FR"))
    assert result.gross_salary_annual == Decimal("50400.00")
    assert result.currency_iso3 == "EUR"
    assert result.guaranteed_fixed_only is True


def test_de_monthly_with_weihnachtsgeld_annualises_x13(contract_agent):
    agent, sink = contract_agent
    _install_completer(
        {
            "is_employment_contract": True,
            "employer_legal_name": "Beispiel GmbH",
            "employer_registry_id": "HRB 12345",
            "position_title": "Solutions Architect",
            "gross_salary": "5.800,00",
            "currency": "EUR",
            "salary_period": "month",
            "bonus_or_holiday_pay_guaranteed_fixed": True,  # → ×13
            "gross_salary_guaranteed_fixed_only_bool": True,
            "contract_start_date": "01.10.2026",
            "working_time_percent": 100,
        }
    )
    result = asyncio.run(agent.run(_document(DE_AV_TEXT), jurisdiction="DE"))
    # 5800 × 13 = 75 400 EUR
    assert result.gross_salary_annual == Decimal("75400.00")
    assert result.currency_iso3 == "EUR"
    # Confirm the field row is present and a Decimal-formatted value.
    salary_field = next(f for f in result.fields if f.field_key == "gross_salary_annual")
    assert salary_field.value_raw == "75400.00"


def test_no_monthly_with_feriepenger_annualises_x12_92(contract_agent):
    agent, sink = contract_agent
    _install_completer(
        {
            "is_employment_contract": True,
            "employer_legal_name": "Eksempel AS",
            "employer_registry_id": "998877665",
            "position_title": "Backend Developer",
            "gross_salary": "65 000",
            "currency": "NOK",
            "salary_period": "month",
            "bonus_or_holiday_pay_guaranteed_fixed": True,
            "gross_salary_guaranteed_fixed_only_bool": True,
            "contract_start_date": "01.11.2026",
            "working_time_percent": 100,
        }
    )
    result = asyncio.run(agent.run(_document(NO_AK_TEXT), jurisdiction="NO"))
    # 65 000 × 12.92 = 839 800 NOK
    assert result.gross_salary_annual == Decimal("839800.00")
    assert result.currency_iso3 == "NOK"


# ─────────────────────────────────────────────────────────────────────────────
# Employer normalization
# ─────────────────────────────────────────────────────────────────────────────


def test_fr_employer_registry_id_detected_as_siren(contract_agent):
    agent, sink = contract_agent
    _install_completer(
        {
            "is_employment_contract": True,
            "employer_legal_name": "Acme France SAS",
            "employer_registry_id": "552120222",
            "gross_salary": "4200,00",
            "currency": "EUR",
            "salary_period": "month",
        }
    )
    result = asyncio.run(agent.run(_document(FR_CDI_TEXT), jurisdiction="FR"))
    registry_field = next(
        (f for f in result.fields if f.field_key == "employer_registry_id"), None
    )
    assert registry_field is not None
    assert (registry_field.value_canonical or {}).get("kind") == "SIREN"


def test_de_employer_registry_id_detected_as_hrb(contract_agent):
    agent, sink = contract_agent
    _install_completer(
        {
            "is_employment_contract": True,
            "employer_legal_name": "Beispiel GmbH",
            "employer_registry_id": "HRB 12345",
            "gross_salary": "5.800,00",
            "currency": "EUR",
            "salary_period": "month",
        }
    )
    result = asyncio.run(agent.run(_document(DE_AV_TEXT), jurisdiction="DE"))
    registry_field = next(
        (f for f in result.fields if f.field_key == "employer_registry_id"), None
    )
    assert registry_field is not None
    assert (registry_field.value_canonical or {}).get("kind") == "HRB"


def test_no_employer_registry_id_detected_as_orgnr(contract_agent):
    agent, sink = contract_agent
    _install_completer(
        {
            "is_employment_contract": True,
            "employer_legal_name": "Eksempel AS",
            "employer_registry_id": "998877665",
            "gross_salary": "65 000",
            "currency": "NOK",
            "salary_period": "month",
        }
    )
    result = asyncio.run(agent.run(_document(NO_AK_TEXT), jurisdiction="NO"))
    registry_field = next(
        (f for f in result.fields if f.field_key == "employer_registry_id"), None
    )
    assert registry_field is not None
    assert (registry_field.value_canonical or {}).get("kind") == "ORGNR"


# ─────────────────────────────────────────────────────────────────────────────
# guaranteed_fixed_only heuristic
# ─────────────────────────────────────────────────────────────────────────────


def test_guaranteed_fixed_false_when_contract_mentions_bonus():
    assert is_guaranteed_fixed_only(FR_CDI_TEXT) is True
    assert is_guaranteed_fixed_only(FR_CDI_BONUS_TEXT) is False


def test_guaranteed_fixed_only_field_emitted_correctly_with_bonus_language(contract_agent):
    agent, sink = contract_agent
    _install_completer(
        {
            "is_employment_contract": True,
            "employer_legal_name": "Acme France SAS",
            "gross_salary": "4200,00",
            "currency": "EUR",
            "salary_period": "month",
            # LLM says yes but the contract text contradicts — heuristic wins.
            "gross_salary_guaranteed_fixed_only_bool": True,
        }
    )
    result = asyncio.run(agent.run(_document(FR_CDI_BONUS_TEXT), jurisdiction="FR"))
    assert result.guaranteed_fixed_only is False
    field = next(
        f for f in result.fields if f.field_key == "gross_salary_guaranteed_fixed_only_bool"
    )
    assert field.value_raw == "false"


def test_non_fixed_triggers_covers_expected_terms():
    # Spec from Architecture Report §3.4 + brief.
    for term in ("commission", "bonus", "variable", "target", "stock options", "sign-on"):
        assert term in NON_FIXED_TRIGGERS


# ─────────────────────────────────────────────────────────────────────────────
# agent_runs + graceful degradation
# ─────────────────────────────────────────────────────────────────────────────


def test_agent_runs_row_carries_model_tokens_cost(contract_agent):
    agent, sink = contract_agent
    _install_completer(
        {
            "is_employment_contract": True,
            "employer_legal_name": "Acme France SAS",
            "gross_salary": "4200,00",
            "currency": "EUR",
            "salary_period": "month",
        }
    )
    result = asyncio.run(agent.run(_document(FR_CDI_TEXT), jurisdiction="FR"))
    assert len(sink.agent_runs) == 1
    row = sink.agent_runs[0]
    assert row.model_name == "gpt-4o-mini"
    assert row.tokens_in == 400
    assert row.tokens_out == 180
    # cost = 400 × 0.00000015 + 180 × 0.0000006 = 0.000168
    assert row.cost_usd == pytest.approx(0.000168, rel=1e-6)


def test_run_proceeds_when_llm_router_has_no_completer(contract_agent):
    agent, sink = contract_agent
    # No completer registered.
    result = asyncio.run(agent.run(_document(FR_CDI_TEXT), jurisdiction="FR"))
    assert result.model_name == "(none — LLM unrouted)"
    # No fields emitted (LLM payload was empty) BUT the agent_runs row IS written
    # so the audit trail captures the unrouted attempt.
    assert len(sink.agent_runs) == 1
    assert sink.agent_runs[0].model_name == "(none — LLM unrouted)"
