"""Hermetic tests for promote() national-entity vs global-network collapse.

No database. The session is a fake that answers the two queries promote() issues
(suppliers by name, capabilities by country) and records candidate links.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple
from unittest.mock import patch

from backend.imports.suppliers.executor import promote


class _Rows:
    def __init__(self, rows: Sequence[Any]) -> None:
        self._rows = list(rows)

    def all(self) -> List[Any]:
        return list(self._rows)

    def mappings(self) -> "_Rows":
        return self


class FakeSession:
    """Enough of a SQLAlchemy Session for promote() — no engine, no ORM identity."""

    def __init__(
        self,
        *,
        candidates: Sequence[Dict[str, Any]],
        suppliers: Sequence[Tuple[str, str, Optional[str]]],
        capabilities: Sequence[Tuple[str, Optional[str]]],
    ) -> None:
        self.candidates = [dict(c) for c in candidates]
        self.suppliers = list(suppliers)
        self.capabilities = list(capabilities)
        self.links: List[Tuple[str, Any]] = []
        self.commits = 0

    def execute(self, stmt: Any, params: Optional[Dict[str, Any]] = None) -> _Rows:
        sql = str(stmt).lower()
        if "from public.vendor_candidates" in sql:
            return _Rows(self.candidates)
        if params and "sid" in params and "cid" in params:
            sid, cid = params["sid"], params["cid"]
            self.links.append((sid, cid))
            for row in self.candidates:
                if row["id"] == cid:
                    row["promoted_supplier_id"] = sid
            return _Rows([])
        return _Rows([])

    def query(self, *ents: Any) -> _Rows:
        cls = getattr(ents[0], "class_", ents[0])
        if getattr(cls, "__name__", "") == "SupplierServiceCapability":
            return _Rows(self.capabilities)
        return _Rows(self.suppliers)

    def commit(self) -> None:
        self.commits += 1


def _candidate(**overrides: Any) -> Dict[str, Any]:
    row = {
        "id": "cand-1",
        "name": "Example",
        "website_url": "https://example.test",
        "corridor": "ES-FR",
        "service_category": "banks",
        "country_code": "ES",
        "city": "Madrid",
        "source_url": "https://register.test",
        "source_name": "test-register",
        "accreditation_body": None,
        "accreditation_number": None,
        "accreditation_expiry": None,
        "notes": None,
        "promoted_supplier_id": None,
    }
    row.update(overrides)
    return row


def _run(session: FakeSession) -> Tuple[List[Dict[str, Any]], List[Tuple[str, Dict[str, Any]]]]:
    created: List[Dict[str, Any]] = []
    added: List[Tuple[str, Dict[str, Any]]] = []

    def fake_create(_session: Any, data: Dict[str, Any]) -> Dict[str, Any]:
        created.append(data)
        return {"id": data["id"]}

    def fake_add(_session: Any, supplier_id: str, capability: Dict[str, Any]) -> Dict[str, Any]:
        added.append((supplier_id, capability))
        return {"id": supplier_id}

    with patch("backend.app.services.supplier_registry.create_supplier", fake_create), patch(
        "backend.app.services.supplier_registry.add_capability", fake_add
    ):
        n, skipped, _problems = promote(session, dry_run=False)
    assert skipped == 0
    assert n == 1
    return created, added


def test_santander_es_does_not_collapse_onto_brasil() -> None:
    br_id = "sup-santander-br"
    session = FakeSession(
        candidates=[
            _candidate(
                id="cand-es",
                name="Banco Santander, S.A.",
                country_code="ES",
                service_category="banks",
            )
        ],
        suppliers=[(br_id, "Banco Santander (Brasil) S.A.", None)],
        capabilities=[(br_id, "BR")],
    )
    created, added = _run(session)

    assert created, "ES Santander must become its own supplier"
    new_id = created[0]["id"]
    assert new_id != br_id
    assert not any(sid == br_id for sid, _cap in added)
    assert session.links == [(new_id, "cand-es")]
    assert session.candidates[0]["promoted_supplier_id"] != br_id


def test_crown_norway_collapses_onto_existing_movers_supplier() -> None:
    crown_id = "sup-crown"
    session = FakeSession(
        candidates=[
            _candidate(
                id="cand-crown-no",
                name="Crown Relocations (Norway)",
                country_code="NO",
                service_category="movers",
                corridor="FR-NO",
                city="Oslo",
            )
        ],
        suppliers=[(crown_id, "Crown Relocations", None)],
        capabilities=[(crown_id, "FR")],
    )
    created, added = _run(session)

    assert created == []
    assert added and added[0][0] == crown_id
    assert session.links == [(crown_id, "cand-crown-no")]


def test_same_country_bank_corridor_collapses() -> None:
    banco_id = "sup-bancox"
    session = FakeSession(
        candidates=[
            _candidate(
                id="cand-bancox-es-fr",
                name="Banco X",
                country_code="ES",
                service_category="banks",
                corridor="ES-FR",
            )
        ],
        suppliers=[(banco_id, "Banco X", None)],
        capabilities=[(banco_id, "ES")],
    )
    created, added = _run(session)

    assert created == []
    assert added and added[0][0] == banco_id
    assert session.links == [(banco_id, "cand-bancox-es-fr")]


def test_ags_parenthetical_aside_still_one_movers_supplier() -> None:
    ags_id = "sup-ags-fr"
    session = FakeSession(
        candidates=[
            _candidate(
                id="cand-ags",
                name="AGS France (SOFDI)",
                country_code="FR",
                service_category="movers",
                corridor="FR-DE",
                city="Paris",
            )
        ],
        suppliers=[
            (
                ags_id,
                "AGS France (SOFDI – Société Française de Déménagement International)",
                None,
            )
        ],
        capabilities=[(ags_id, "DE")],
    )
    created, added = _run(session)

    assert created == []
    assert added and added[0][0] == ags_id
    assert session.links == [(ags_id, "cand-ags")]
