"""DB-free unit tests for the ES->IE immigration milestone seeder (DOC-4)."""
from datetime import date, datetime

from backend.app.services.immigration_milestone_seed import (
    build_milestone_rows,
    get_template,
)

FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)


def test_es_ie_template_present_and_ordered():
    tmpl = get_template("ES", "IE")
    assert tmpl, "ES->IE template must exist"
    leads = [m["lead_time_days"] for m in tmpl]
    assert leads == sorted(leads), "lead times must be non-decreasing in intended order"
    # case-insensitive corridor lookup
    assert get_template("es", "ie") == tmpl


def test_build_rows_count_sort_order_and_determinism():
    rows = build_milestone_rows("case-1", "org-1", "ES", "IE", None, FIXED_NOW)
    assert len(rows) == len(get_template("ES", "IE")) == 11
    assert [r["sort_order"] for r in rows] == list(range(1, len(rows) + 1))
    assert all(r["case_id"] == "case-1" for r in rows)
    assert all(r["status"] == "pending" for r in rows)
    ids = [r["id"] for r in rows]
    assert len(set(ids)) == len(ids)
    again = build_milestone_rows("case-1", "org-1", "ES", "IE", None, FIXED_NOW)
    assert [r["id"] for r in again] == ids  # deterministic


def test_target_date_from_move_date_else_null():
    assert all(r["target_date"] is None
               for r in build_milestone_rows("c", "o", "ES", "IE", None, FIXED_NOW))
    move = date(2026, 10, 1)
    rows = build_milestone_rows("c", "o", "ES", "IE", move, FIXED_NOW)
    by = {r["milestone_type"]: r for r in rows}
    assert by["travel_to_ireland"]["target_date"] == move.isoformat()
    assert by["employment_permit_granted"]["target_date"] < move.isoformat()
    assert by["irp_stamp1_registration"]["target_date"] > move.isoformat()


def test_unknown_corridor_seeds_nothing():
    assert get_template("XX", "YY") == []
    assert build_milestone_rows("c", "o", "XX", "YY", None, FIXED_NOW) == []
