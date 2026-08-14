"""[AIQ-1800b] Every write to imm_employee_profiles must bind `field_sources` as jsonb.

WHAT BROKE
----------
`field_sources` is a jsonb column, and all six write paths bound a raw Python dict to it:

    params["field_sources"] = existing_sources        # a dict
    set_clauses.append("field_sources = :field_sources")

psycopg2 cannot adapt a dict, so every INSERT and UPDATE against the table raised
`ProgrammingError: can't adapt type 'dict'` and 500'd. Both the HR path and the employee
path, both branches of each, plus both OCR paths.

Found 2026-08-11 while verifying AIQ-1800: a PUT to
`/api/employee/cases/{id}/profile` returned 500, and the Render log said

    error=ProgrammingError("(psycopg2.ProgrammingError) can't adapt type 'dict'")

It also explains something that had been read the wrong way round. `imm_employee_profiles`
having 0 rows was treated as "nothing stored yet, so this is the cheap moment to set the
encryption key". It was really **"nothing can be stored at all"** — the table has never
accepted a row in production, with or without a key.

WHY THESE ARE INTEGRATION TESTS
-------------------------------
The bug only exists under the Postgres dialect. SQLite accepts a bare bind because the
column is TEXT there, so a unit test on the sqlite lane passes against the broken code and
proves nothing. That is exactly how this survived: `test_jsonb_bind_cast.py` guards the
`:param::type` form at the SQL-string level, and this bug never used that form — it passed
a Python dict.
"""
from __future__ import annotations

import json
import os
import uuid

import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")
from sqlalchemy import create_engine, text  # noqa: E402

DATABASE_URL = os.environ.get("DATABASE_URL", "")
_IS_PG = DATABASE_URL.startswith("postgres")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _IS_PG,
        reason="the dict-bind failure only reproduces on Postgres — sqlite accepts a bare "
        "bind because the column is TEXT there, which is why this shipped",
    ),
]

PROFILES = "public.imm_employee_profiles"


@pytest.fixture()
def conn():
    """Always rolled back — nothing here reaches the table permanently."""
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    with engine.connect() as c:
        tx = c.begin()
        try:
            yield c
        finally:
            tx.rollback()
    engine.dispose()


def _row(**over):
    base = {
        "id": str(uuid.uuid4()),
        "case_id": "aiq1800b-case",
        "employee_id": "aiq1800b-emp",
        "org_id": "aiq1800b-org",
    }
    base.update(over)
    return base


def test_binding_a_raw_dict_still_fails(conn):
    """Pin the actual defect, so this file proves the fix rather than assuming it.

    If a future change made psycopg2 adapt dicts, this test fails and the fix below
    becomes unnecessary — which is worth knowing rather than silently carrying.
    """
    p = _row()
    with pytest.raises(Exception) as exc:
        conn.execute(
            text(
                f"INSERT INTO {PROFILES} (id, case_id, employee_id, org_id, field_sources) "
                "VALUES (:id, :case_id, :employee_id, :org_id, :field_sources)"
            ),
            {**p, "field_sources": {"passport_number": "self_entered"}},
        )
    assert "adapt" in str(exc.value).lower() or "dict" in str(exc.value).lower(), (
        f"expected the raw-dict adaptation failure, got {exc.value!r}"
    )


def test_json_dumps_plus_cast_inserts_and_reads_back_as_jsonb(conn):
    """The fix as shipped: json.dumps() the value, and CAST(:param AS jsonb) in the SQL.

    See the next test for which half is load-bearing — measurement corrected my first
    guess, and the answer is json.dumps().
    """
    p = _row()
    sources = {"passport_number": "self_entered", "nationality": "hr_provided"}
    conn.execute(
        text(
            f"INSERT INTO {PROFILES} (id, case_id, employee_id, org_id, field_sources) "
            "VALUES (:id, :case_id, :employee_id, :org_id, CAST(:field_sources AS jsonb))"
        ),
        {**p, "field_sources": json.dumps(sources)},
    )

    got = conn.execute(
        text(f"SELECT field_sources FROM {PROFILES} WHERE id = :id"), {"id": p["id"]}
    ).scalar()
    assert got == sources, f"round trip changed the value: {got!r}"

    # A jsonb OBJECT, not a JSON string that merely looks right when Python decodes it.
    kind = conn.execute(
        text(f"SELECT jsonb_typeof(field_sources) FROM {PROFILES} WHERE id = :id"),
        {"id": p["id"]},
    ).scalar()
    assert kind == "object", (
        f"field_sources stored as jsonb {kind!r}, not an object — the value was written as "
        "a JSON string rather than parsed"
    )


def test_json_dumps_alone_is_the_load_bearing_half(conn):
    """Measured, and it corrected my first guess — worth recording as a fact.

    I assumed a dumped string bound WITHOUT a cast would land as a jsonb *string*, making
    both halves necessary. It does not: Postgres has a text→jsonb assignment cast, so the
    value is parsed into an object either way.

    So `json.dumps()` is what actually fixes the bug, and `CAST(:p AS jsonb)` is
    explicitness plus the SQLite/Postgres split the codebase already uses elsewhere
    (`_jsonb_expr` in admin_form_templates). Keep the cast — it is the house convention and
    it documents intent at the call site — but do not believe it is load-bearing.

    Contrast with the passport column, where the direction genuinely matters: bytea→text
    has NO registered cast at all (see test_vault_passport_roundtrip).
    """
    p = _row()
    conn.execute(
        text(
            f"INSERT INTO {PROFILES} (id, case_id, employee_id, org_id, field_sources) "
            "VALUES (:id, :case_id, :employee_id, :org_id, :field_sources)"
        ),
        {**p, "field_sources": json.dumps({"a": "b"})},
    )
    kind = conn.execute(
        text(f"SELECT jsonb_typeof(field_sources) FROM {PROFILES} WHERE id = :id"),
        {"id": p["id"]},
    ).scalar()
    assert kind == "object", (
        f"a dumped dict bound without CAST stored as jsonb {kind!r}. If this ever becomes "
        "'string', the CAST becomes load-bearing and every call site needs auditing."
    )


def test_update_path_shape_also_round_trips(conn):
    """The UPDATE branches use the same bind, and were broken the same way."""
    p = _row()
    conn.execute(
        text(
            f"INSERT INTO {PROFILES} (id, case_id, employee_id, org_id, field_sources) "
            "VALUES (:id, :case_id, :employee_id, :org_id, CAST(:field_sources AS jsonb))"
        ),
        {**p, "field_sources": json.dumps({"nationality": "self_entered"})},
    )
    merged = {"nationality": "self_entered", "passport_number": "ocr"}
    conn.execute(
        text(f"UPDATE {PROFILES} SET field_sources = CAST(:fs AS jsonb) WHERE id = :id"),
        {"fs": json.dumps(merged), "id": p["id"]},
    )
    got = conn.execute(
        text(f"SELECT field_sources FROM {PROFILES} WHERE id = :id"), {"id": p["id"]}
    ).scalar()
    assert got == merged
