"""C2-09 — expanded contradiction detection for family fields + nationality.

A 10-case extended fixture exercising the four new comparators added to the
C1-08 detector:

  1. CONTRADICTION_MARRIAGE_DATE  — marriage_cert.marriage_date ≠ application form
  2. CONTRADICTION_CHILD_DOB      — birth_cert.dob ≠ passport.date_of_birth (child)
  3. CONTRADICTION_CHILD_PARENT   — birth-cert parents don't resolve to a case PERSON
  4. CONTRADICTION_NATIONALITY    — ICAO codes diverge across passport / id_card

Built inline on InMemoryContradictionStore, matching test_contradiction_detection.py
(C1-08) rather than external fixture files. The 10 cases:
  - marriage date mismatch ......................... case_marriage_date_mismatch
  - child DOB mismatch ............................. case_child_dob_mismatch
  - child parent unresolvable ...................... case_child_parent_unresolvable
  - foster-care suppression of parent check ........ case_foster_suppresses_parent
  - nationality mismatch passport vs id card ....... case_nationality_mismatch
  - dual nationality legitimate variation .......... case_dual_nationality_ok
  - multiple contradictions on one case ............ case_multiple
  - no contradictions baseline (x3) ................ case_clean_marriage / _child / _nationality
"""

from __future__ import annotations

from uuid import UUID, uuid4

from backend.relopass.agents.contradiction import (
    InMemoryContradictionStore,
    detect_contradictions,
)
from backend.relopass.agents.models import ExtractedField


def _ef(
    *,
    document_id: UUID,
    field_key: str,
    value_raw: str,
    confidence: float = 0.95,
) -> ExtractedField:
    return ExtractedField(
        document_id=document_id,
        field_key=field_key,
        value_raw=value_raw,
        value_canonical=None,
        confidence=confidence,
        agent_run_id=uuid4(),
        resolution_status=None,
        bbox_page=None,
        bbox_x0=None,
        bbox_y0=None,
        bbox_x1=None,
        bbox_y1=None,
    )


def _types(contradictions) -> set:
    return {c.type for c in contradictions}


# ─────────────────────────────────────────────────────────────────────────────
# 1. Marriage date
# ─────────────────────────────────────────────────────────────────────────────


def test_marriage_date_mismatch_fires():
    store = InMemoryContradictionStore()
    case_id, entity = uuid4(), uuid4()
    cert, application = uuid4(), uuid4()
    store.add_field(
        _ef(document_id=cert, field_key="marriage_date", value_raw="2019-06-15"),
        document_type="MARRIAGE_CERT", canonical_entity_id=entity,
    )
    store.add_field(
        _ef(document_id=application, field_key="marriage_date", value_raw="2019-07-15"),
        document_type="APPLICATION_FORM", canonical_entity_id=entity,
    )
    out = detect_contradictions(case_id, store)
    assert "CONTRADICTION_MARRIAGE_DATE" in _types(out)


def test_marriage_date_agreement_clean():
    store = InMemoryContradictionStore()
    case_id, entity = uuid4(), uuid4()
    cert, application = uuid4(), uuid4()
    for doc, dt in ((cert, "MARRIAGE_CERT"), (application, "APPLICATION_FORM")):
        store.add_field(
            _ef(document_id=doc, field_key="marriage_date", value_raw="2019-06-15"),
            document_type=dt, canonical_entity_id=entity,
        )
    out = detect_contradictions(case_id, store)
    assert "CONTRADICTION_MARRIAGE_DATE" not in _types(out)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Child DOB (bridges birth_cert 'dob' ↔ passport 'date_of_birth')
# ─────────────────────────────────────────────────────────────────────────────


def test_child_dob_mismatch_fires():
    store = InMemoryContradictionStore()
    case_id, child = uuid4(), uuid4()
    birth_cert, passport = uuid4(), uuid4()
    store.add_family_member(child, "CHILD")
    store.add_field(
        _ef(document_id=birth_cert, field_key="dob", value_raw="2015-04-02"),
        document_type="BIRTH_CERT", canonical_entity_id=child,
    )
    store.add_field(
        _ef(document_id=passport, field_key="date_of_birth", value_raw="2015-04-20"),
        document_type="PASSPORT_TD3", canonical_entity_id=child,
    )
    out = detect_contradictions(case_id, store)
    assert "CONTRADICTION_CHILD_DOB" in _types(out)


def test_child_dob_agreement_clean():
    store = InMemoryContradictionStore()
    case_id, child = uuid4(), uuid4()
    birth_cert, passport = uuid4(), uuid4()
    store.add_family_member(child, "CHILD")
    store.add_field(
        _ef(document_id=birth_cert, field_key="dob", value_raw="2015-04-02"),
        document_type="BIRTH_CERT", canonical_entity_id=child,
    )
    store.add_field(
        _ef(document_id=passport, field_key="date_of_birth", value_raw="2015-04-02"),
        document_type="PASSPORT_TD3", canonical_entity_id=child,
    )
    out = detect_contradictions(case_id, store)
    assert "CONTRADICTION_CHILD_DOB" not in _types(out)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Child–parent relationship resolution
# ─────────────────────────────────────────────────────────────────────────────


def test_child_parent_unresolvable_fires():
    store = InMemoryContradictionStore()
    case_id, child = uuid4(), uuid4()
    emp, spouse = uuid4(), uuid4()
    birth_cert = uuid4()
    # The case's canonical PERSONs.
    store.add_canonical_person(emp, "Marc DUPONT", "FRA")
    store.add_canonical_person(spouse, "Sophie DUPONT", "FRA")
    # Birth cert names parents who are NOT on the case.
    store.add_birth_cert_claim(
        birth_cert, parent_names=["Pierre MARTIN", "Claire BERNARD"], child_entity_id=child
    )
    out = detect_contradictions(case_id, store)
    assert "CONTRADICTION_CHILD_PARENT" in _types(out)


def test_child_parent_resolves_clean():
    store = InMemoryContradictionStore()
    case_id, child = uuid4(), uuid4()
    emp, spouse = uuid4(), uuid4()
    birth_cert = uuid4()
    store.add_canonical_person(emp, "Marc DUPONT", "FRA")
    store.add_canonical_person(spouse, "Sophie DUPONT", "FRA")
    # Both parents ARE on the case → resolves, no contradiction.
    store.add_birth_cert_claim(
        birth_cert, parent_names=["Marc DUPONT", "Sophie DUPONT"], child_entity_id=child
    )
    out = detect_contradictions(case_id, store)
    assert "CONTRADICTION_CHILD_PARENT" not in _types(out)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Foster-care suppression of the parent check
# ─────────────────────────────────────────────────────────────────────────────


def test_foster_care_suppresses_parent_check():
    store = InMemoryContradictionStore()
    case_id, child = uuid4(), uuid4()
    emp = uuid4()
    birth_cert = uuid4()
    store.add_canonical_person(emp, "Marc DUPONT", "FRA")
    # Parents don't resolve, BUT a foster order covers this child → suppressed.
    store.add_birth_cert_claim(
        birth_cert, parent_names=["Unknown BIRTHPARENT"], child_entity_id=child
    )
    store.suppress_foster_child(child)
    out = detect_contradictions(case_id, store)
    assert "CONTRADICTION_CHILD_PARENT" not in _types(out)


# ─────────────────────────────────────────────────────────────────────────────
# 5 & 6. Nationality
# ─────────────────────────────────────────────────────────────────────────────


def test_nationality_mismatch_passport_vs_id_card_fires():
    store = InMemoryContradictionStore()
    case_id, entity = uuid4(), uuid4()
    passport, id_card = uuid4(), uuid4()
    store.add_field(
        _ef(document_id=passport, field_key="nationality_iso3", value_raw="DEU"),
        document_type="PASSPORT_TD3", canonical_entity_id=entity,
    )
    store.add_field(
        _ef(document_id=id_card, field_key="nationality_iso3", value_raw="FRA"),
        document_type="ID_CARD", canonical_entity_id=entity,
    )
    out = detect_contradictions(case_id, store)
    assert "CONTRADICTION_NATIONALITY" in _types(out)


def test_dual_nationality_legitimate_variation_clean():
    store = InMemoryContradictionStore()
    case_id, entity = uuid4(), uuid4()
    passport, id_card = uuid4(), uuid4()
    # Passport declares dual {FRA, GBR}; id card declares FRA → overlap, no clash.
    store.add_field(
        _ef(document_id=passport, field_key="nationality_iso3", value_raw="FRA,GBR"),
        document_type="PASSPORT_TD3", canonical_entity_id=entity,
    )
    store.add_field(
        _ef(document_id=id_card, field_key="nationality_iso3", value_raw="FRA"),
        document_type="ID_CARD", canonical_entity_id=entity,
    )
    out = detect_contradictions(case_id, store)
    assert "CONTRADICTION_NATIONALITY" not in _types(out)


# ─────────────────────────────────────────────────────────────────────────────
# 7. Multiple contradictions on one case
# ─────────────────────────────────────────────────────────────────────────────


def test_multiple_contradictions_on_one_case():
    store = InMemoryContradictionStore()
    case_id = uuid4()
    emp, child = uuid4(), uuid4()
    cert, application = uuid4(), uuid4()
    birth_cert, passport, id_card = uuid4(), uuid4(), uuid4()

    store.add_family_member(child, "CHILD")
    store.add_canonical_person(emp, "Marc DUPONT", "FRA")

    # marriage date clash
    store.add_field(_ef(document_id=cert, field_key="marriage_date", value_raw="2019-06-15"),
                    document_type="MARRIAGE_CERT", canonical_entity_id=emp)
    store.add_field(_ef(document_id=application, field_key="marriage_date", value_raw="2020-01-01"),
                    document_type="APPLICATION_FORM", canonical_entity_id=emp)
    # child dob clash
    store.add_field(_ef(document_id=birth_cert, field_key="dob", value_raw="2015-04-02"),
                    document_type="BIRTH_CERT", canonical_entity_id=child)
    store.add_field(_ef(document_id=passport, field_key="date_of_birth", value_raw="2015-09-09"),
                    document_type="PASSPORT_TD3", canonical_entity_id=child)
    # nationality clash on the employee
    store.add_field(_ef(document_id=passport, field_key="nationality_iso3", value_raw="FRA"),
                    document_type="PASSPORT_TD3", canonical_entity_id=emp)
    store.add_field(_ef(document_id=id_card, field_key="nationality_iso3", value_raw="ITA"),
                    document_type="ID_CARD", canonical_entity_id=emp)
    # child-parent unresolvable
    store.add_birth_cert_claim(birth_cert, parent_names=["Ghost PARENT"], child_entity_id=child)

    out = detect_contradictions(case_id, store)
    found = _types(out)
    assert {
        "CONTRADICTION_MARRIAGE_DATE",
        "CONTRADICTION_CHILD_DOB",
        "CONTRADICTION_NATIONALITY",
        "CONTRADICTION_CHILD_PARENT",
    } <= found


# ─────────────────────────────────────────────────────────────────────────────
# 8. No-contradiction baseline (third clean case: nothing family-related)
# ─────────────────────────────────────────────────────────────────────────────


def test_clean_case_no_family_no_contradictions():
    store = InMemoryContradictionStore()
    case_id, entity = uuid4(), uuid4()
    passport, id_card = uuid4(), uuid4()
    store.add_field(_ef(document_id=passport, field_key="nationality_iso3", value_raw="FRA"),
                    document_type="PASSPORT_TD3", canonical_entity_id=entity)
    store.add_field(_ef(document_id=id_card, field_key="nationality_iso3", value_raw="FRA"),
                    document_type="ID_CARD", canonical_entity_id=entity)
    out = detect_contradictions(case_id, store)
    assert out == ()


# ─────────────────────────────────────────────────────────────────────────────
# 5 (criterion): idempotency contract — re-runs produce no duplicates
# ─────────────────────────────────────────────────────────────────────────────


def test_family_contradictions_are_idempotent():
    store = InMemoryContradictionStore()
    case_id, entity = uuid4(), uuid4()
    cert, application = uuid4(), uuid4()
    store.add_field(_ef(document_id=cert, field_key="marriage_date", value_raw="2019-06-15"),
                    document_type="MARRIAGE_CERT", canonical_entity_id=entity)
    store.add_field(_ef(document_id=application, field_key="marriage_date", value_raw="2019-07-15"),
                    document_type="APPLICATION_FORM", canonical_entity_id=entity)

    # First run inserts one contradiction; the store stays at one row on re-run
    # because the content_hash dedup key already contains it (C1-08 contract:
    # the detector returns attempted contradictions; the store skips duplicates).
    first = detect_contradictions(case_id, store)
    assert len(first) == 1
    assert len(store.contradictions) == 1
    detect_contradictions(case_id, store)
    assert len(store.contradictions) == 1  # no duplicate inserted via content_hash


# ─────────────────────────────────────────────────────────────────────────────
# 7 (criterion): JSON/contract shape matches §3.6 (same as C1-08)
# ─────────────────────────────────────────────────────────────────────────────


def test_contradiction_shape_matches_parsewise_contract():
    store = InMemoryContradictionStore()
    case_id, entity = uuid4(), uuid4()
    passport, id_card = uuid4(), uuid4()
    store.add_field(_ef(document_id=passport, field_key="nationality_iso3", value_raw="DEU"),
                    document_type="PASSPORT_TD3", canonical_entity_id=entity)
    store.add_field(_ef(document_id=id_card, field_key="nationality_iso3", value_raw="FRA"),
                    document_type="ID_CARD", canonical_entity_id=entity)
    (c,) = detect_contradictions(case_id, store)
    payload = c.model_dump()
    for key in (
        "contradiction_id", "case_id", "canonical_entity_id", "field_key",
        "type", "candidates", "resolution_status", "suggested_winner",
        "content_hash", "detected_at", "detected_by",
    ):
        assert key in payload, f"missing §3.6 key: {key}"
    assert payload["type"] == "CONTRADICTION_NATIONALITY"
    assert payload["resolution_status"] == "Requires attention"
    assert payload["suggested_winner"] is None
