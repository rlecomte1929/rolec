from sqlalchemy import create_engine, text


class FakeCasesDB:
    """Exercises the real roadmap-validation method bodies against in-memory
    SQLite. Mirrors the Database raw-SQL helpers the methods rely on."""

    def __init__(self):
        self.engine = create_engine("sqlite:///:memory:")

    def coalesce_case_lookup_id(self, case_id):
        return case_id

    def _exec(self, conn, sql, params=None, op_name=None, request_id=None):
        return conn.execute(text(sql), params or {})

    # bind the real methods under test
    from backend.db.cases import CasesMixin as _M  # type: ignore
    _ensure_case_roadmap_validations_table = _M.__dict__["_ensure_case_roadmap_validations_table"]
    upsert_roadmap_validation = _M.__dict__["upsert_roadmap_validation"]
    get_roadmap_validation = _M.__dict__["get_roadmap_validation"]


def test_get_returns_none_before_validation():
    db = FakeCasesDB()
    assert db.get_roadmap_validation("case-1") is None


def test_upsert_then_get_roundtrip_and_idempotent():
    db = FakeCasesDB()
    db.upsert_roadmap_validation("case-1", "emp-9")
    row = db.get_roadmap_validation("case-1")
    assert row is not None
    assert row["canonical_case_id"] == "case-1"
    assert row["validated_by_user_id"] == "emp-9"
    assert row["validated_at"]
    # idempotent — second call updates, does not duplicate
    db.upsert_roadmap_validation("case-1", "emp-9")
    again = db.get_roadmap_validation("case-1")
    assert again["canonical_case_id"] == "case-1"


class _Summary:
    def __init__(self, completed=0, in_progress=0):
        self.completed_tasks = completed
        self.in_progress_tasks = in_progress


def test_resolver_explicit_validation_wins():
    from backend.app.services.relocation_plan_view_service import _resolve_roadmap_validation

    class DB:
        def get_roadmap_validation(self, cid):
            return {"validated_at": "2026-06-15T00:00:00", "validated_by_user_id": "emp"}
    v, at, by = _resolve_roadmap_validation(DB(), "c", _Summary())
    assert v is True and at == "2026-06-15T00:00:00" and by == "emp"


def test_resolver_grandfathers_in_execution_case():
    from backend.app.services.relocation_plan_view_service import _resolve_roadmap_validation

    class DB:
        def get_roadmap_validation(self, cid):
            return None
    v, at, by = _resolve_roadmap_validation(DB(), "c", _Summary(in_progress=2))
    assert v is True and at is None


def test_resolver_unvalidated_fresh_case():
    from backend.app.services.relocation_plan_view_service import _resolve_roadmap_validation

    class DB:
        def get_roadmap_validation(self, cid):
            return None
    v, at, by = _resolve_roadmap_validation(DB(), "c", _Summary())
    assert v is False and at is None
