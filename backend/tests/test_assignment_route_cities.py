"""AIQ-1336 follow-up — assignment-detail city comes from wizard_cases.

The HR case summary corridor read city from relocation_cases / the draft, which are
often empty (the city lives in wizard_cases, the intake source of truth — same place
the command-center reads). get_assignment_route_cities joins case_assignments→wizard_cases
the same way, so the corridor renders city-level instead of falling back to country.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from backend.db.cases import CasesMixin  # noqa: E402
from backend.db.misc import MiscMixin  # noqa: E402


class _Host(MiscMixin, CasesMixin):
    def __init__(self, engine) -> None:
        self.engine = engine
        self._initialized = True


def _engine():
    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with e.begin() as c:
        c.execute(text("CREATE TABLE case_assignments (id TEXT, canonical_case_id TEXT, case_id TEXT)"))
        c.execute(text("CREATE TABLE wizard_cases (id TEXT, origin_city TEXT, dest_city TEXT)"))
        # assignment 'a1' points at wizard case 'w1' via case_id (canonical null)
        c.execute(text("INSERT INTO case_assignments (id, canonical_case_id, case_id) VALUES ('a1', NULL, 'w1')"))
        # assignment 'a2' points via canonical_case_id (takes precedence)
        c.execute(text("INSERT INTO case_assignments (id, canonical_case_id, case_id) VALUES ('a2', 'w1', 'other')"))
        c.execute(text("INSERT INTO wizard_cases (id, origin_city, dest_city) VALUES ('w1', 'Paris', 'Dubai')"))
    return e


def test_route_cities_resolved_from_wizard_via_case_id():
    h = _Host(_engine())
    assert h.get_assignment_route_cities("a1") == ("Paris", "Dubai")


def test_route_cities_resolved_via_canonical_case_id():
    h = _Host(_engine())
    assert h.get_assignment_route_cities("a2") == ("Paris", "Dubai")


def test_route_cities_missing_returns_none_pair():
    h = _Host(_engine())
    assert h.get_assignment_route_cities("nope") == (None, None)
    assert h.get_assignment_route_cities("") == (None, None)
