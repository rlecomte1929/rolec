import uuid

from sqlalchemy import create_engine, text

from backend.app.services.service_roadmap_bridge import (
    reconcile_service_milestones, advance_quote_step,
)


class FakeDB:
    """Minimal Database-shaped object backed by in-memory SQLite, exposing only
    the methods the bridge uses."""

    def __init__(self):
        self.engine = create_engine("sqlite:///:memory:")
        with self.engine.begin() as c:
            c.execute(text("""
                CREATE TABLE case_milestones (
                  id TEXT PRIMARY KEY, case_id TEXT NOT NULL, canonical_case_id TEXT,
                  milestone_type TEXT NOT NULL, title TEXT NOT NULL, description TEXT,
                  target_date TEXT, actual_date TEXT, status TEXT NOT NULL DEFAULT 'pending',
                  sort_order INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL, owner TEXT DEFAULT 'joint',
                  criticality TEXT DEFAULT 'normal', notes TEXT, source TEXT, service_key TEXT
                )
            """))

    def coalesce_case_lookup_id(self, case_id):
        return case_id

    def _exec(self, conn, sql, params=None, **kwargs):
        return conn.execute(text(sql), params or {})

    def list_case_milestones(self, case_id, request_id=None):
        with self.engine.connect() as c:
            rows = c.execute(text(
                "SELECT id, milestone_type, title, status, source, service_key "
                "FROM case_milestones WHERE case_id = :cid OR canonical_case_id = :cid"
            ), {"cid": case_id}).mappings().all()
        return [dict(r) for r in rows]

    def upsert_case_milestone(self, case_id, milestone_type, title, *, description=None,
                              status="pending", sort_order=0, source=None, service_key=None,
                              milestone_id=None, request_id=None, **_):
        with self.engine.begin() as c:
            if milestone_id:
                c.execute(text(
                    "UPDATE case_milestones SET title=:t, description=:d, status=:s, "
                    "sort_order=:so, source=:src, service_key=:sk, updated_at='now' WHERE id=:id"
                ), {"t": title, "d": description, "s": status, "so": sort_order,
                    "src": source, "sk": service_key, "id": milestone_id})
                return {"id": milestone_id}
            mid = str(uuid.uuid4())
            c.execute(text(
                "INSERT INTO case_milestones (id, case_id, canonical_case_id, milestone_type, "
                "title, description, status, sort_order, created_at, updated_at, source, service_key) "
                "VALUES (:id,:cid,:cid,:mt,:t,:d,:s,:so,'now','now',:src,:sk)"
            ), {"id": mid, "cid": case_id, "mt": milestone_type, "t": title, "d": description,
                "s": status, "so": sort_order, "src": source, "sk": service_key})
            return {"id": mid}

    def delete_service_milestones_not_in(self, case_id, keep_service_keys, request_id=None):
        keys = list(keep_service_keys)
        with self.engine.begin() as c:
            if keys:
                ph = ",".join(f":k{i}" for i in range(len(keys)))
                params = {"cid": case_id, **{f"k{i}": k for i, k in enumerate(keys)}}
                sql = (f"DELETE FROM case_milestones WHERE (case_id=:cid OR canonical_case_id=:cid) "
                       f"AND source='service' AND service_key NOT IN ({ph})")
            else:
                params = {"cid": case_id}
                sql = ("DELETE FROM case_milestones WHERE (case_id=:cid OR canonical_case_id=:cid) "
                       "AND source='service'")
            c.execute(text(sql), params)


def _svc_rows(db, case_id):
    return [m for m in db.list_case_milestones(case_id) if m["source"] == "service"]


def test_selecting_services_materialises_steps():
    db = FakeDB()
    reconcile_service_milestones(db, "case1", ["immigration", "schools"])
    rows = _svc_rows(db, "case1")
    assert rows, "expected service milestones"
    keys = {r["service_key"] for r in rows}
    assert keys == {"immigration", "schools"}
    titles = " ".join(r["title"].lower() for r in rows)
    assert "embassy" in titles or "consular" in titles


def test_deselecting_a_service_removes_its_steps():
    db = FakeDB()
    reconcile_service_milestones(db, "case1", ["immigration", "schools"])
    reconcile_service_milestones(db, "case1", ["immigration"])  # dropped schools
    keys = {r["service_key"] for r in _svc_rows(db, "case1")}
    assert keys == {"immigration"}


def test_reconcile_is_idempotent():
    db = FakeDB()
    reconcile_service_milestones(db, "case1", ["housing"])
    n1 = len(_svc_rows(db, "case1"))
    reconcile_service_milestones(db, "case1", ["housing"])
    n2 = len(_svc_rows(db, "case1"))
    assert n1 == n2 and n1 > 0


def test_reconcile_never_touches_non_service_rows():
    db = FakeDB()
    db.upsert_case_milestone("case1", "phase_ai_01", "AI step", source="ai")
    db.upsert_case_milestone("case1", "manual_x", "Manual step", source=None)
    reconcile_service_milestones(db, "case1", ["banking"])
    all_rows = db.list_case_milestones("case1")
    assert any(r["source"] == "ai" for r in all_rows)
    assert any(r["source"] is None for r in all_rows)


def test_unknown_service_key_is_skipped():
    db = FakeDB()
    reconcile_service_milestones(db, "case1", ["banking", "not_a_service"])
    keys = {r["service_key"] for r in _svc_rows(db, "case1")}
    assert keys == {"banking"}


def test_advance_quote_step_sets_in_progress():
    db = FakeDB()
    reconcile_service_milestones(db, "case1", ["housing"])
    advance_quote_step(db, "case1", ["Housing search"], quote_request_id="q-123")
    quote_rows = [r for r in _svc_rows(db, "case1") if r["milestone_type"].endswith("_quote")]
    assert quote_rows and quote_rows[0]["status"] == "in_progress"
