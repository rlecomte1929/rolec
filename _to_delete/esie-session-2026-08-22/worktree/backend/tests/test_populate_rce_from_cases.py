"""AIQ-941 — tests for the public.cases → rce.* populator.

Pure/mocked (no DB, no FS): they pin the unification contract (rce case_id ==
public case id), the status mapping, and skip-when-uncovered behaviour.
"""
from __future__ import annotations

import uuid
from datetime import date

import backend.scripts.populate_rce_from_cases as pop


def test_map_status_vocabulary():
    assert pop.map_status("active") == "ACTIVE"
    assert pop.map_status("on_hold") == "BLOCKED"
    assert pop.map_status("draft") == "DRAFT"
    assert pop.map_status("completed") == "COMPLETED"
    assert pop.map_status("cancelled") == "CANCELLED"
    assert pop.map_status("ACTIVE") == "ACTIVE"  # case-insensitive
    assert pop.map_status(None) == "ACTIVE"      # unknown → ACTIVE default
    assert pop.map_status("weird") == "ACTIVE"


def test_to_iso_country_name_and_passthrough():
    assert pop.to_iso_country("INDIA") == "IN"
    assert pop.to_iso_country("Germany") == "DE"   # case-insensitive
    assert pop.to_iso_country(" france ") == "FR"  # trims
    assert pop.to_iso_country("UAE") == "AE"
    assert pop.to_iso_country("IN") == "IN"        # already ISO-2 → passthrough
    assert pop.to_iso_country("ZZ") == "ZZ"        # unknown → passthrough
    assert pop.to_iso_country(None) is None


def test_resolve_pathway_normalizes_country_names(monkeypatch):
    """A name-spelled corridor (INDIA_GERMANY) resolves to the ISO pathway (IN_DE)."""
    class _PW:
        id = "BLUECARD_2026"
    seen = {}
    def _get_pathways(cid):
        seen["cid"] = cid
        return (_PW(),)
    monkeypatch.setattr(pop.corridor_registry, "get_pathways", _get_pathways)
    monkeypatch.setattr(pop.corridor_registry, "get_pathway_file", lambda cid, pid: f"/fake/{cid}/{pid}/v1.yaml")
    path, cid, pid = pop.resolve_pathway_file("INDIA", "GERMANY")
    assert cid == "IN_DE" and pid == "BLUECARD_2026"
    assert path == "/fake/IN_DE/BLUECARD_2026/v1.yaml"
    assert seen["cid"] == "IN_DE"  # name→ISO happened before the registry lookup


def test_resolve_pathway_missing_country_codes():
    assert pop.resolve_pathway_file(None, "DE") == (None, None, None)
    assert pop.resolve_pathway_file("IN", None) == (None, None, None)


def test_resolve_pathway_uncovered_corridor(monkeypatch):
    monkeypatch.setattr(pop.corridor_registry, "get_pathways", lambda cid: ())
    path, cid, pid = pop.resolve_pathway_file("US", "JP")
    assert path is None and cid == "US_JP" and pid is None


def test_resolve_pathway_covered_corridor(monkeypatch):
    class _PW:  # minimal CorridorPathway stand-in
        id = "BLUECARD_2026"
    monkeypatch.setattr(pop.corridor_registry, "get_pathways", lambda cid: (_PW(),))
    monkeypatch.setattr(pop.corridor_registry, "get_pathway_file", lambda cid, pid: "/fake/IN_DE/BLUECARD_2026/v1.yaml")
    path, cid, pid = pop.resolve_pathway_file("IN", "DE")
    assert path == "/fake/IN_DE/BLUECARD_2026/v1.yaml" and cid == "IN_DE" and pid == "BLUECARD_2026"


def test_populate_keys_rce_case_to_public_id(monkeypatch):
    """The unification contract: persist is called with case_id == public.cases.id."""
    captured = {}
    monkeypatch.setattr(pop.corridor_registry, "get_pathways", lambda cid: (type("P", (), {"id": "BLUECARD_2026"})(),))
    monkeypatch.setattr(pop.corridor_registry, "get_pathway_file", lambda cid, pid: "/fake/path.yaml")
    monkeypatch.setattr(pop, "load_corridor", lambda path: object())
    def _fake_persist(corridor, *, case_id, target_arrival_date, status):
        captured.update(case_id=case_id, target_arrival_date=target_arrival_date, status=status)
        return {"cases": 1, "rule_citations": 3}
    monkeypatch.setattr(pop, "persist_corridor_case", _fake_persist)

    public_id = uuid.uuid4()
    summary = pop.populate_rce_for_public_case({
        "id": public_id, "origin_country_code": "IN", "dest_country_code": "DE",
        "target_move_date": date(2026, 9, 1), "status": "on_hold",
    })
    assert summary == {"cases": 1, "rule_citations": 3}
    assert captured["case_id"] == public_id          # ← rce.cases.case_id == public.cases.id
    assert captured["status"] == "BLOCKED"           # on_hold → BLOCKED
    assert captured["target_arrival_date"] == date(2026, 9, 1)


def test_populate_accepts_string_uuid_and_defaults_date(monkeypatch):
    captured = {}
    monkeypatch.setattr(pop.corridor_registry, "get_pathways", lambda cid: (type("P", (), {"id": "P"})(),))
    monkeypatch.setattr(pop.corridor_registry, "get_pathway_file", lambda cid, pid: "/fake/path.yaml")
    monkeypatch.setattr(pop, "load_corridor", lambda path: object())
    monkeypatch.setattr(pop, "persist_corridor_case", lambda corridor, *, case_id, target_arrival_date, status: captured.update(case_id=case_id, target_arrival_date=target_arrival_date) or {})
    sid = str(uuid.uuid4())
    pop.populate_rce_for_public_case({"id": sid, "origin_country_code": "IN", "dest_country_code": "DE", "target_move_date": None, "status": "active"})
    assert captured["case_id"] == uuid.UUID(sid)     # string id coerced to UUID
    assert isinstance(captured["target_arrival_date"], date)  # null move date → fallback date


def test_populate_skips_uncovered_corridor(monkeypatch):
    monkeypatch.setattr(pop.corridor_registry, "get_pathways", lambda cid: ())
    called = {"persist": False}
    monkeypatch.setattr(pop, "persist_corridor_case", lambda *a, **k: called.update(persist=True))
    out = pop.populate_rce_for_public_case({"id": uuid.uuid4(), "origin_country_code": "US", "dest_country_code": "JP", "status": "active"})
    assert out is None and called["persist"] is False
