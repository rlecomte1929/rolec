"""Every catalogued country must have an `employment` purpose.

`crud.list_requirements` keys on (country_code, purpose). Post-AIQ-1444 the purpose
resolver maps essentially every real relocation onto `employment` — `work`, `lta`,
`sta`, `permanent`, `transfer`, `Employment` all land there. So a country seeded
WITHOUT an `employment` purpose is a silent hole: the destination resolves, the
lookup runs, and it returns zero rows.

That is exactly what happened to Germany. `long_term_only.yaml` declared
`GERMANY: [other]` — the only country in the file without `employment` — and 372
production cases (the single biggest corridor) got an empty requirements list.
Which the UI then rendered as "No destination requirements apply to your case."

Nothing asserted this. This is that assertion.
"""
from __future__ import annotations

import glob
import os

import pytest

yaml = pytest.importorskip("yaml")

_SEED_DIR = os.path.join(os.path.dirname(__file__), "..", "seeds", "requirements")


def _purposes_by_country():
    """country -> set of purposes, across every seed file."""
    out: dict[str, set[str]] = {}
    for path in sorted(glob.glob(os.path.join(_SEED_DIR, "*.yaml"))):
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        for country, purposes in (data.get("purposes_by_country") or {}).items():
            out.setdefault(country.upper(), set()).update(purposes or [])
    return out


class TestEveryCountryCanServeAnEmploymentRelocation:
    def test_no_country_is_missing_the_employment_purpose(self):
        by_country = _purposes_by_country()
        assert by_country, "no seed files found — the test is not testing anything"

        missing = sorted(c for c, purposes in by_country.items() if "employment" not in purposes)
        assert missing == [], (
            f"{missing} have no `employment` purpose. Nearly every real relocation "
            "resolves to `employment` (work / lta / sta / permanent / transfer all map "
            "there), so those destinations return ZERO requirement rows — an empty list, "
            "which on the employee's screen reads as 'nothing is required of you'."
        )

    def test_every_declared_purpose_is_one_the_resolver_can_produce(self):
        """A seed file declaring a purpose no case can ever resolve to is dead content."""
        from backend.app.services.requirements_purpose_key import CANONICAL_PURPOSES

        for country, purposes in _purposes_by_country().items():
            unreachable = purposes - set(CANONICAL_PURPOSES)
            assert unreachable == set(), (
                f"{country} declares {unreachable}, which `to_purpose` can never return — "
                "no case will ever match those rows"
            )


class TestAnEmptyLookupNeverClaimsNothingIsRequired:
    """The invariant. A (country, purpose) pair with zero rows must return
    covered=False — never covered=True with an empty list, which the client renders
    as "nothing is required of you"."""

    def test_zero_rows_returns_not_covered(self, monkeypatch):
        import json as _json

        from backend.app.services import requirements_builder as rb

        class _Case:
            id = "c1"
            dest_country = "FRANCE"
            purpose = "study"  # FRANCE is catalogued, but not for `study`
            origin_country = "India"
            draft_json = _json.dumps(
                {"relocationBasics": {"destCountry": "France", "originCountry": "India",
                                      "purpose": "study"}}
            )

        class _Session:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        monkeypatch.setattr(rb, "SessionLocal", lambda: _Session())
        monkeypatch.setattr(rb.crud, "get_case", lambda db, cid: _Case())
        monkeypatch.setattr(rb.crud, "list_sources", lambda db, c: [])
        monkeypatch.setattr(rb.crud, "list_requirements", lambda db, c, p: [])  # the gap

        dto = rb.compute_case_requirements("c1")

        assert dto.covered is False, (
            "a catalog gap must be covered=False. covered=True + an empty list is "
            "rendered as 'nothing is required of you' — a claim we cannot support."
        )
        assert dto.requirements == []
