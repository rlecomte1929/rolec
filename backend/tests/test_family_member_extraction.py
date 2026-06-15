"""C2-01 · Tests for the family-member extraction agents + entity resolution.

Covers the Notion validation criteria:

1. A case can carry spouse + 2 children (family_members FK integrity — modelled
   here at the canonical-resolution layer: 3 family canonicals + the employee).
2. MARRIAGE_CERT emits spouse_1_name, spouse_2_name, marriage_date,
   place_of_marriage, registering_authority.
3. BIRTH_CERT emits child_name, parent_1_name, parent_2_name, dob,
   place_of_birth.
4. Parent names on the BIRTH_CERT resolve to existing canonical PERSONs on the
   case (deterministic-first / LLM fallback) — no duplicate canonical PERSON
   rows created.
5. FOSTER_CARE_ORDER recognised as a relationship-establishing document
   equivalent to a birth cert for dependent reunification.
7. Multilingual fixtures: FR / DE / NO / EN / IN (Devanagari via ISO 15919).

Plus the engineered-prompt named tests:
  - test_marriage_cert_extracts_all_fields (FR/DE/NO/EN/IN)
  - test_birth_cert_parent_resolves_to_existing_canonical_on_case
  - test_birth_cert_orphan_parent_creates_new_canonical
  - test_marriage_cert_maiden_name_recorded_as_separate_field
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Mapping
from uuid import uuid4

import pytest

from backend.relopass.agents import (
    AgentRegistry,
    CanonicalPerson,
    FamilyEntityResolver,
    InMemoryAgentStorage,
    InMemoryEntityLinkSink,
    ParsedDocument,
)
from backend.relopass.agents.runtime import InMemoryExtractionSink
from backend.relopass.agents.extraction import (
    BIRTH_CERT_DOCUMENT_TYPE,
    FOSTER_CARE_ORDER_DOCUMENT_TYPE,
    MARRIAGE_CERT_DOCUMENT_TYPE,
    BirthCertAgent,
    EXTRACTION_AGENT_REGISTRY,
    FosterCareOrderAgent,
    MarriageCertAgent,
    get_extraction_agent_class,
    normalize_dependency_type,
)
from backend.relopass.llm import register_completer, reset_registry
from backend.relopass.llm.router import CompletionResult, set_agent_run_logger


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures — multilingual marriage / birth certs
# ─────────────────────────────────────────────────────────────────────────────


FR_MARRIAGE = {
    "is_marriage_cert": True,
    "spouse_1_name": "Marc Dubois",
    "spouse_2_name": "Sophie Dubois",
    "marriage_date": "12/06/2015",
    "place_of_marriage": "Lyon",
    "registering_authority": "Mairie de Lyon",
    "maiden_surname": "Lefevre",
    "country_iso3": "FRA",
}

DE_MARRIAGE = {
    "is_marriage_cert": True,
    "spouse_1_name": "Hans Müller",
    "spouse_2_name": "Anna Müller",
    "marriage_date": "15.07.2018",
    "place_of_marriage": "München",
    "registering_authority": "Standesamt München",
    "maiden_surname": "Schmidt",
    "country_iso3": "DEU",
}

NO_MARRIAGE = {
    "is_marriage_cert": True,
    "spouse_1_name": "Lars Hansen",
    "spouse_2_name": "Ingrid Hansen",
    "marriage_date": "2019-05-20",
    "place_of_marriage": "Oslo",
    "registering_authority": "Folkeregisteret Oslo",
    "country_iso3": "NOR",
}

EN_MARRIAGE = {
    "is_marriage_cert": True,
    "spouse_1_name": "John Smith",
    "spouse_2_name": "Jane Smith",
    "marriage_date": "2017-08-11",
    "place_of_marriage": "London",
    "registering_authority": "General Register Office",
    "country_iso3": "GBR",
}

IN_MARRIAGE = {
    "is_marriage_cert": True,
    "spouse_1_name": "Raj Sharma",
    "spouse_2_name": "Priya Sharma",
    "marriage_date": "2016-11-03",
    "place_of_marriage": "Mumbai",
    "registering_authority": "Marriage Registrar, Mumbai",
    "name_native": {
        "spouse_1_name": "राज शर्मा",
        "spouse_2_name": "प्रिया शर्मा",
        "script": "Devanagari",
    },
    "country_iso3": "IND",
}

ALL_MARRIAGE_FIXTURES = {
    "FR": FR_MARRIAGE,
    "DE": DE_MARRIAGE,
    "NO": NO_MARRIAGE,
    "EN": EN_MARRIAGE,
    "IN": IN_MARRIAGE,
}


# Birth cert listing Marc + Sophie Dubois as parents (match the FR canonical set).
FR_BIRTH = {
    "is_birth_cert": True,
    "child_name": "Léa Dubois",
    "parent_1_name": "Marc Dubois",
    "parent_2_name": "Sophie Dubois",
    "dob": "03/04/2017",
    "place_of_birth": "Lyon",
    "issuing_authority": "Mairie de Lyon",
    "country_iso3": "FRA",
}

# Second child for the "spouse + 2 children" case.
FR_BIRTH_2 = {
    "is_birth_cert": True,
    "child_name": "Hugo Dubois",
    "parent_1_name": "Marc Dubois",
    "parent_2_name": "Sophie Dubois",
    "dob": "09/09/2019",
    "place_of_birth": "Lyon",
    "issuing_authority": "Mairie de Lyon",
    "country_iso3": "FRA",
}

# Orphan birth cert — parents not on the case.
ORPHAN_BIRTH = {
    "is_birth_cert": True,
    "child_name": "Tom Bernard",
    "parent_1_name": "Paul Bernard",
    "parent_2_name": "Claire Bernard",
    "dob": "01/01/2018",
    "place_of_birth": "Paris",
    "issuing_authority": "Mairie de Paris",
    "country_iso3": "FRA",
}

FOSTER_ORDER = {
    "is_foster_care_order": True,
    "dependent_name": "Yusuf Demir",
    "guardian_name": "Marc Dubois",
    "jurisdiction": "Juge des enfants, Lyon",
    "order_date": "10/02/2020",
    "dependency_type": "Guardianship",
    "country_iso3": "FRA",
}


def _document(text: str = "doc") -> ParsedDocument:
    return ParsedDocument(document_id=uuid4(), case_id=uuid4(), text=text)


def _install_completer(payload: Mapping[str, Any]) -> None:
    async def _completer(prompt: str, **_kwargs: Any) -> CompletionResult:
        return CompletionResult(
            text=json.dumps({"input": payload}, ensure_ascii=False),
            tokens_in=300,
            tokens_out=110,
        )

    register_completer("gpt-4o-mini", _completer)
    register_completer("claude-sonnet-4-6", _completer)


@pytest.fixture(autouse=True)
def _reset_state():
    reset_registry()
    set_agent_run_logger(None)
    yield
    reset_registry()
    set_agent_run_logger(None)


def _marriage_agent():
    agent = MarriageCertAgent(
        registry=AgentRegistry(InMemoryAgentStorage()),
        sink=InMemoryExtractionSink(),
    )
    agent.register()
    return agent


def _case_canonical_dubois():
    """The Marc + Sophie Dubois canonical PERSONs already on the case."""
    return [
        CanonicalPerson(canonical_entity_id=uuid4(), display_name="Marc Dubois", issuing_state_iso3="FRA"),
        CanonicalPerson(canonical_entity_id=uuid4(), display_name="Sophie Dubois", issuing_state_iso3="FRA"),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Prompt loading + registry wiring
# ─────────────────────────────────────────────────────────────────────────────


def test_prompts_load_from_disk():
    from backend.relopass.agents.extraction import (
        load_birth_cert_prompt,
        load_foster_care_order_prompt,
        load_marriage_cert_prompt,
    )

    assert "MARRIAGE_CERT" in load_marriage_cert_prompt()
    assert "BIRTH_CERT" in load_birth_cert_prompt()
    assert "FOSTER_CARE_ORDER" in load_foster_care_order_prompt()


def test_registry_wires_all_three_document_types():
    assert get_extraction_agent_class(MARRIAGE_CERT_DOCUMENT_TYPE) is MarriageCertAgent
    assert get_extraction_agent_class(BIRTH_CERT_DOCUMENT_TYPE) is BirthCertAgent
    assert (
        get_extraction_agent_class(FOSTER_CARE_ORDER_DOCUMENT_TYPE)
        is FosterCareOrderAgent
    )
    # The three family doc types must be wired. Other agents (e.g. ID_CARD,
    # C2-02) may also be registered, so this is a subset check, not equality.
    assert {
        MARRIAGE_CERT_DOCUMENT_TYPE,
        BIRTH_CERT_DOCUMENT_TYPE,
        FOSTER_CARE_ORDER_DOCUMENT_TYPE,
    } <= set(EXTRACTION_AGENT_REGISTRY)


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 2 — MARRIAGE_CERT all fields, multilingual
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("locale", list(ALL_MARRIAGE_FIXTURES))
def test_marriage_cert_extracts_all_fields(locale):
    payload = ALL_MARRIAGE_FIXTURES[locale]
    _install_completer(payload)
    agent = _marriage_agent()
    result = asyncio.run(agent.run(_document()))

    by_key = {f.field_key: f for f in result.fields}
    for key in (
        "spouse_1_name",
        "spouse_2_name",
        "marriage_date",
        "place_of_marriage",
        "registering_authority",
    ):
        assert key in by_key, f"{locale}: missing {key}"
        assert by_key[key].value_raw

    # marriage_date normalised to ISO yyyy-mm-dd.
    assert by_key["marriage_date"].value_raw.count("-") == 2
    assert len(by_key["marriage_date"].value_raw) == 10


def test_marriage_cert_devanagari_preserved_in_native_field():
    _install_completer(IN_MARRIAGE)
    agent = _marriage_agent()
    result = asyncio.run(agent.run(_document()))
    by_key = {f.field_key: f for f in result.fields}
    assert "राज" in (by_key["spouse_1_name_native"].value_raw or "")
    assert (by_key["spouse_1_name_native"].value_canonical or {}).get("script") == "Devanagari"
    # Latin form sits in the standard field.
    assert "Raj" in (by_key["spouse_1_name"].value_raw or "")


# ─────────────────────────────────────────────────────────────────────────────
# test_marriage_cert_maiden_name_recorded_as_separate_field
# ─────────────────────────────────────────────────────────────────────────────


def test_marriage_cert_maiden_name_recorded_as_separate_field():
    _install_completer(FR_MARRIAGE)
    agent = _marriage_agent()
    result = asyncio.run(agent.run(_document()))
    by_key = {f.field_key: f for f in result.fields}
    assert "maiden_surname" in by_key
    assert by_key["maiden_surname"].value_raw == "Lefevre"
    # It is a SEPARATE field, never merged into a spouse name.
    assert "Lefevre" not in (by_key["spouse_1_name"].value_raw or "")
    assert "Lefevre" not in (by_key["spouse_2_name"].value_raw or "")
    assert result.maiden_surname == "Lefevre"


def test_marriage_cert_no_maiden_name_emits_no_field():
    _install_completer(NO_MARRIAGE)  # no maiden_surname key
    agent = _marriage_agent()
    result = asyncio.run(agent.run(_document()))
    by_key = {f.field_key: f for f in result.fields}
    assert "maiden_surname" not in by_key
    assert result.maiden_surname is None


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 3 + 4 — BIRTH_CERT fields + parent resolution
# ─────────────────────────────────────────────────────────────────────────────


def test_birth_cert_extracts_all_fields():
    _install_completer(FR_BIRTH)
    agent = BirthCertAgent(
        registry=AgentRegistry(InMemoryAgentStorage()),
        sink=InMemoryExtractionSink(),
    )
    agent.register()
    result = asyncio.run(agent.run(_document()))
    by_key = {f.field_key: f for f in result.fields}
    for key in ("child_name", "parent_1_name", "parent_2_name", "dob", "place_of_birth"):
        assert key in by_key, f"missing {key}"
        assert by_key[key].value_raw


def test_birth_cert_parent_resolves_to_existing_canonical_on_case():
    """Exactly 1 new canonical (the child) + 2 entity_links to existing parents."""
    _install_completer(FR_BIRTH)
    canonical = _case_canonical_dubois()
    marc_id = canonical[0].canonical_entity_id
    sophie_id = canonical[1].canonical_entity_id
    link_sink = InMemoryEntityLinkSink()
    agent = BirthCertAgent(
        registry=AgentRegistry(InMemoryAgentStorage()),
        sink=InMemoryExtractionSink(),
        resolver=FamilyEntityResolver(canonical_persons=canonical),
        link_sink=link_sink,
    )
    agent.register()
    result = asyncio.run(agent.run(_document()))

    # Exactly two parent resolutions, both matched, neither minted a canonical.
    assert len(result.parent_resolutions) == 2
    assert all(r.result.matched for r in result.parent_resolutions)
    assert all(not r.minted_new_canonical for r in result.parent_resolutions)
    assert all(r.result.link_method == "DETERMINISTIC" for r in result.parent_resolutions)

    # Two entity_links pointing at the EXISTING canonical entities.
    assert len(result.entity_links) == 2
    linked_ids = {lnk.canonical_entity_id for lnk in result.entity_links}
    assert linked_ids == {marc_id, sophie_id}

    # Exactly one new canonical minted: the child. No duplicate parents.
    assert len(link_sink.minted_canonical_ids) == 1
    assert link_sink.minted_canonical_ids[0] == result.child_canonical_entity_id
    assert "Léa Dubois" in link_sink.minted_by_name.values()


def test_birth_cert_orphan_parent_creates_new_canonical():
    """No parent matches the case canonical → new canonicals + Requires attention."""
    _install_completer(ORPHAN_BIRTH)
    canonical = _case_canonical_dubois()  # Dubois on case; cert lists Bernard
    link_sink = InMemoryEntityLinkSink()
    agent = BirthCertAgent(
        registry=AgentRegistry(InMemoryAgentStorage()),
        sink=InMemoryExtractionSink(),
        resolver=FamilyEntityResolver(canonical_persons=canonical),
        link_sink=link_sink,
    )
    agent.register()
    result = asyncio.run(agent.run(_document()))

    assert len(result.parent_resolutions) == 2
    assert all(not r.result.matched for r in result.parent_resolutions)
    assert all(r.minted_new_canonical for r in result.parent_resolutions)
    assert all(
        r.result.resolution_status == "Requires attention"
        for r in result.parent_resolutions
    )
    # No entity_links to existing canonicals.
    assert result.entity_links == ()
    # Child + 2 orphan parents = 3 minted canonicals.
    assert len(link_sink.minted_canonical_ids) == 3


def test_birth_cert_llm_fallback_resolves_when_deterministic_inconclusive():
    """Surname differs (deterministic fails) but an LLM adjudicator matches."""
    payload = dict(FR_BIRTH, parent_1_name="Marc Dubois-Lefevre")  # surname diverges

    def _adjudicator(query: str, candidates):
        # The LLM recognises the hyphenated surname is the same Marc.
        for i, c in enumerate(candidates):
            if "Marc" in c and "Marc" in query:
                return i
        return None

    _install_completer(payload)
    canonical = _case_canonical_dubois()
    marc_id = canonical[0].canonical_entity_id
    link_sink = InMemoryEntityLinkSink()
    agent = BirthCertAgent(
        registry=AgentRegistry(InMemoryAgentStorage()),
        sink=InMemoryExtractionSink(),
        resolver=FamilyEntityResolver(
            canonical_persons=canonical, llm_adjudicator=_adjudicator
        ),
        link_sink=link_sink,
    )
    agent.register()
    result = asyncio.run(agent.run(_document()))

    p1 = next(r for r in result.parent_resolutions if r.field_key == "parent_1_name")
    assert p1.result.matched
    assert p1.result.link_method == "LLM"
    assert p1.canonical_entity_id == marc_id


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 1 — spouse + 2 children case carries family canonicals
# ─────────────────────────────────────────────────────────────────────────────


def test_case_carries_spouse_plus_two_children():
    """A marriage cert (spouse) + two birth certs (2 children) resolve without
    minting duplicate parent canonicals — only the 2 children are new."""
    canonical = _case_canonical_dubois()
    link_sink = InMemoryEntityLinkSink()

    # Child 1.
    _install_completer(FR_BIRTH)
    agent1 = BirthCertAgent(
        registry=AgentRegistry(InMemoryAgentStorage()),
        sink=InMemoryExtractionSink(),
        resolver=FamilyEntityResolver(canonical_persons=canonical),
        link_sink=link_sink,
    )
    agent1.register()
    r1 = asyncio.run(agent1.run(_document()))

    # Child 2.
    _install_completer(FR_BIRTH_2)
    agent2 = BirthCertAgent(
        registry=AgentRegistry(InMemoryAgentStorage()),
        sink=InMemoryExtractionSink(),
        resolver=FamilyEntityResolver(canonical_persons=canonical),
        link_sink=link_sink,
    )
    agent2.register()
    r2 = asyncio.run(agent2.run(_document()))

    # Two children minted, parents reused (4 entity_links to the 2 parents).
    assert len(link_sink.minted_canonical_ids) == 2  # only the 2 children
    assert {r1.child_canonical_entity_id, r2.child_canonical_entity_id} == set(
        link_sink.minted_canonical_ids
    )
    assert len(link_sink.links) == 4  # 2 parents x 2 birth certs
    assert all(lnk.link_method == "DETERMINISTIC" for lnk in link_sink.links)


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 5 — FOSTER_CARE_ORDER relationship-establishing
# ─────────────────────────────────────────────────────────────────────────────


def test_foster_care_order_extracts_all_fields_and_resolves_guardian():
    _install_completer(FOSTER_ORDER)
    canonical = _case_canonical_dubois()
    marc_id = canonical[0].canonical_entity_id
    link_sink = InMemoryEntityLinkSink()
    agent = FosterCareOrderAgent(
        registry=AgentRegistry(InMemoryAgentStorage()),
        sink=InMemoryExtractionSink(),
        resolver=FamilyEntityResolver(canonical_persons=canonical),
        link_sink=link_sink,
    )
    agent.register()
    result = asyncio.run(agent.run(_document()))

    by_key = {f.field_key: f for f in result.fields}
    for key in ("dependent_name", "guardian_name", "jurisdiction", "order_date", "dependency_type"):
        assert key in by_key, f"missing {key}"

    # dependency_type mapped to controlled vocab.
    assert result.dependency_type == "GUARDIANSHIP"

    # Guardian (Marc) resolves to the existing canonical; dependent is new.
    assert result.guardian_resolution is not None
    assert result.guardian_resolution.result.matched
    assert result.guardian_resolution.canonical_entity_id == marc_id
    assert not result.guardian_resolution.minted_new_canonical
    assert len(result.entity_links) == 1
    # Only the dependent is a new canonical.
    assert link_sink.minted_canonical_ids == [result.dependent_canonical_entity_id]


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Foster care", "FOSTER_CARE"),
        ("guardianship", "GUARDIANSHIP"),
        ("Kafala", "KAFALA"),
        ("custody", "CUSTODY"),
        ("ward", "GUARDIANSHIP"),
        ("something weird", "OTHER"),
        (None, "OTHER"),
    ],
)
def test_dependency_type_normalization(raw, expected):
    assert normalize_dependency_type(raw) == expected


# ─────────────────────────────────────────────────────────────────────────────
# Auxiliary — runs without an LLM completer
# ─────────────────────────────────────────────────────────────────────────────


def test_birth_cert_runs_when_llm_router_has_no_completer():
    agent = BirthCertAgent(
        registry=AgentRegistry(InMemoryAgentStorage()),
        sink=InMemoryExtractionSink(),
    )
    agent.register()
    result = asyncio.run(agent.run(_document()))
    assert result.model_name == "(none — LLM unrouted)"
