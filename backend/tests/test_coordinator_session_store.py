"""AIQ-1414 Phase 2b — unit tests for the coordinator session-state store.

DB-free: a fake connection records the SQL + params so we can assert the row-lock,
the jsonb cast, and get-or-create semantics without a database.
"""

import json

from backend.app.services import coordinator_session_store as store


# ── fakes ─────────────────────────────────────────────────────────────────────


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return self._rows


class _FakeConn:
    def __init__(self, pre_rows=None, post_insert_rows=None):
        self.calls = []  # [(sql, params)]
        self._pre = pre_rows or []
        self._post = post_insert_rows
        self._inserted = False

    def execute(self, clause, params=None):
        sql = str(clause)
        self.calls.append((sql, params or {}))
        upper = sql.strip().upper()
        if upper.startswith("INSERT"):
            self._inserted = True
            return _FakeResult([])
        if upper.startswith("SELECT"):
            rows = self._post if (self._inserted and self._post is not None) else self._pre
            return _FakeResult(rows)
        return _FakeResult([])

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class _FakeEngine:
    def __init__(self, conn):
        self._conn = conn

    def begin(self):
        return self._conn  # _FakeConn is its own context manager


class _FakeDB:
    def __init__(self, conn):
        self.engine = _FakeEngine(conn)


# ── pure helpers ──────────────────────────────────────────────────────────────


def test_append_turn_grows_in_order():
    s = {"recent_turns": [{"user": "a", "assistant": "b"}]}
    store.append_turn(s, "c", "d")
    assert s["recent_turns"] == [{"user": "a", "assistant": "b"}, {"user": "c", "assistant": "d"}]


def test_needs_fold_threshold():
    over = {"recent_turns": [{} for _ in range(store.MAX_RECENT_TURNS + 1)]}
    under = {"recent_turns": [{} for _ in range(store.MAX_RECENT_TURNS)]}
    assert store.needs_fold(over) is True
    assert store.needs_fold(under) is False


def test_row_to_dict_parses_json_turns():
    assert store._row_to_dict({"recent_turns": '[{"user":"x","assistant":"y"}]'})["recent_turns"] == [
        {"user": "x", "assistant": "y"}
    ]
    assert store._row_to_dict({"recent_turns": None})["recent_turns"] == []
    assert store._row_to_dict(None) is None


# ── DB I/O ────────────────────────────────────────────────────────────────────


def test_load_for_update_row_locks():
    conn = _FakeConn(pre_rows=[{"id": "s-1", "case_id": "c-1", "recent_turns": "[]"}])
    out = store.load_for_update(conn, "c-1")
    sql = conn.calls[0][0]
    assert "FOR UPDATE" in sql
    assert out["id"] == "s-1"
    assert out["recent_turns"] == []


def test_save_uses_cast_jsonb_not_bind_cast():
    conn = _FakeConn()
    turns = [{"user": "hi", "assistant": "ok"}]
    store.save(conn, {"id": "s-1", "rolling_summary": "sum", "recent_turns": turns,
                      "model": "claude-sonnet-4-6", "status": "active"})
    sql, params = conn.calls[0]
    assert "CAST(:rt AS jsonb)" in sql
    assert ":rt::jsonb" not in sql  # the PG-only unbound-cast footgun
    assert params["rt"] == json.dumps(turns)
    assert params["id"] == "s-1"


def test_get_or_create_returns_existing_without_insert():
    conn = _FakeConn(pre_rows=[{"id": "s-1", "case_id": "c-1", "recent_turns": "[]"}])
    out = store.get_or_create("c-1", "e-1", "acme", db=_FakeDB(conn))
    assert out["id"] == "s-1"
    assert not any(sql.strip().upper().startswith("INSERT") for sql, _ in conn.calls)


def test_get_or_create_inserts_when_absent():
    conn = _FakeConn(pre_rows=[], post_insert_rows=[{"id": "s-new", "case_id": "c-2", "recent_turns": "[]"}])
    out = store.get_or_create("c-2", None, "acme", db=_FakeDB(conn))
    kinds = [sql.strip().split()[0].upper() for sql, _ in conn.calls]
    assert "INSERT" in kinds
    assert out["id"] == "s-new"
    # the INSERT is conflict-safe
    insert_sql = next(sql for sql, _ in conn.calls if sql.strip().upper().startswith("INSERT"))
    assert "ON CONFLICT (case_id) DO NOTHING" in insert_sql


def test_close_session_sets_closed():
    conn = _FakeConn()
    store.close_session(conn, "c-1")
    sql, params = conn.calls[0]
    assert "status = 'closed'" in sql
    assert params["c"] == "c-1"
