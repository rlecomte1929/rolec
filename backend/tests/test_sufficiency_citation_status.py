"""[AIQ-2132] The sufficiency payload must say whether a citation was actually verified.

`list_approved_requirement_facts` serves two evidence states side by side (PR #1851 excludes
only `evidence_verified = FALSE`):

    TRUE  — the stored `evidence_quote` was found verbatim in the archived source
    NULL  — nobody has ever checked

Measured on production 2026-08-22: of 315 approved facts, 205 serve — **121 TRUE and 84 NULL**.
The dossier rendered all 205 with the same "Source: host" anchor, so a mover could not tell a
citation we verified from one we have never opened. This test pins the distinction at the
payload boundary; `RequirementsSufficiencyPanel.test.tsx` pins it at the render.

Written to fail against the pre-fix payload: drop `citation_status` and every assertion below
goes red. The bug fails *safe* — the payload stays valid JSON and the panel still renders — so a
test that only checked the endpoint's shape would have passed either way.
"""
from __future__ import annotations

import contextlib

import pytest

from backend.app.services import requirements_sufficiency as mod


class _Case:
    dest_country = "NO"
    draft_json = None


def _fact(fact_id: str, evidence_verified) -> dict:
    return {
        "id": fact_id,
        "fact_text": f"fact {fact_id}",
        "source_url": "https://www.skatteetaten.no/en/person/foreign/",
        "required_fields": [],
        "applies_to": {},
        "evidence_verified": evidence_verified,
    }


@pytest.fixture
def payload_for(monkeypatch):
    """Run the real service over a caller-supplied fact list, with no DB and no network."""

    def _run(facts):
        monkeypatch.setattr(mod, "SessionLocal", lambda: contextlib.nullcontext(object()))
        monkeypatch.setattr(mod.crud, "get_case", lambda _s, _cid: _Case())
        monkeypatch.setattr(mod.db, "list_dossier_questions", lambda _d: [])
        monkeypatch.setattr(mod.db, "list_dossier_answers", lambda _c, _u: [])
        monkeypatch.setattr(mod.db, "list_approved_requirement_facts", lambda _d: facts)
        out = mod.compute_requirements_sufficiency("case-1", "user-1")
        return {r["fact_id"]: r for r in out["supporting_requirements"]}

    return _run


def test_verified_and_unchecked_facts_are_distinguishable(payload_for):
    """The 121-vs-84 production split must survive into the payload."""
    got = payload_for([_fact("checked", True), _fact("never_checked", None)])
    assert got["checked"]["citation_status"] == "verified"
    assert got["never_checked"]["citation_status"] == "unverified"


@pytest.mark.parametrize("raw", [1, True])
def test_truthy_boolean_encodings_read_as_verified(payload_for, raw):
    """Postgres hands back `True`; SQLite — which CI runs against — hands back `1`.

    An `is True` check would silently downgrade every verified fact to 'unverified' on the
    engine the test suite actually uses, which is exactly the kind of drift this pins.
    """
    assert payload_for([_fact("f", raw)])["f"]["citation_status"] == "verified"


@pytest.mark.parametrize("raw", [None, False, 0])
def test_unchecked_and_disproved_encodings_read_as_unverified(payload_for, raw):
    """FALSE cannot reach here (PR #1851 excludes it) but must never read as verified if it did."""
    assert payload_for([_fact("f", raw)])["f"]["citation_status"] == "unverified"


def test_a_fact_missing_the_column_is_not_claimed_as_verified(payload_for):
    """Absent evidence is not evidence: default to the weaker claim, never the stronger one."""
    bare = {"id": "f", "fact_text": "t", "source_url": "https://x.test/", "required_fields": []}
    assert payload_for([bare])["f"]["citation_status"] == "unverified"


def test_citation_status_is_the_only_addition_and_serving_is_unchanged(payload_for):
    """AIQ-2132 is additive: no fact may be dropped and no existing key may change meaning."""
    facts = [_fact("a", True), _fact("b", None), _fact("c", True)]
    got = payload_for(facts)
    assert set(got) == {"a", "b", "c"}
    assert got["a"]["fact_text"] == "fact a"
    assert got["a"]["source_url"] == "https://www.skatteetaten.no/en/person/foreign/"
