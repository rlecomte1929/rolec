"""Supplier capability `country_code` must be a real ISO-3166-1 alpha-2 code.

Live incident, 2026-08-26. The nightly "Cluster tiering refresh" workflow died with

    psycopg2.errors.StringDataRightTruncation: value too long for type character(2)

because three supplier capabilities in prod carried a country *name* in the
country *code* column — 'Spain' (Madrid to Dublin Movers), 'Norway' (Tine Movers)
and 'Ireland' (Google Dublin Test Housing Finders), all created through the admin
UI on 22/25 Aug. `list_supplier_countries()` returns DISTINCT country_code, so the
refresh job saw phantom cells keyed 'Norway'/'Spain'/'Ireland' alongside the real
NO/ES/IE ones and tried to write them into `supplier_cluster_cache.country_iso2`,
which is `character(2)`.

Two holes let them in, both covered here:

1. `validate_capability` checked ``len(cc) < 2`` — a floor, not an equality — so
   'Norway' (6 chars) passed the country branch, and the *city* branch checked
   only that country_code was non-empty. All three bad rows were scope='city'.

2. `create_supplier` wrote ``c.get("country_code")`` verbatim, while the sibling
   paths `add_capability` / `update_capability` both normalise with
   ``.strip().upper()[:2]``. The bad rows arrived as supplier-with-capabilities in
   one POST, which is the only path that skipped normalisation.

Truncation alone is NOT a fix and must not be relied on: 'Norway'[:2] == 'NO' is
right by luck, but 'Spain'[:2] == 'SP', which is not Spain (ES). Validation has to
reject, not silently trim — hence the reject-first assertions below.
"""
from __future__ import annotations

import os
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.db import Base  # noqa: E402
from backend.app.models import SupplierServiceCapability  # noqa: E402
from backend.app.services import supplier_registry  # noqa: E402
from backend.app.services.supplier_validation import validate_capability  # noqa: E402


@pytest.fixture
def SessionMaker():
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)


# ── validation gate ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("scope", ["country", "city"])
@pytest.mark.parametrize("bad", ["Norway", "Spain", "Ireland", "NOR", "N", "12"])
def test_validate_capability_rejects_non_iso2_country_code(scope, bad):
    """The three prod rows were scope='city'; the city branch had no length check
    at all, and the country branch used ``len(cc) < 2``. Both must reject."""
    ok, err = validate_capability(
        {
            "service_category": "movers",
            "coverage_scope_type": scope,
            "country_code": bad,
            "city_name": "Oslo",
        },
        exclude_id=True,
    )
    assert ok is False, f"{bad!r} was accepted for scope={scope}"
    assert "country_code" in (err or "")


@pytest.mark.parametrize("scope", ["country", "city"])
@pytest.mark.parametrize("good", ["NO", "ES", "ie", " no "])
def test_validate_capability_accepts_iso2_country_code(scope, good):
    ok, err = validate_capability(
        {
            "service_category": "movers",
            "coverage_scope_type": scope,
            "country_code": good,
            "city_name": "Oslo",
        },
        exclude_id=True,
    )
    assert ok is True, f"{good!r} was rejected for scope={scope}: {err}"


# ── write path ───────────────────────────────────────────────────────────────

def test_create_supplier_rejects_country_name_in_capability(SessionMaker):
    """Reproduces the exact payload shape that created 'Tine Movers'."""
    with SessionMaker() as s:
        with pytest.raises(ValueError, match="country_code"):
            supplier_registry.create_supplier(
                s,
                {
                    "name": "Tine Movers",
                    "capabilities": [
                        {
                            "service_category": "movers",
                            "coverage_scope_type": "city",
                            "country_code": "Norway",
                            "city_name": "Oslo",
                        }
                    ],
                },
            )


def test_create_supplier_normalises_country_code(SessionMaker):
    """create_supplier wrote country_code verbatim while add_capability and
    update_capability both normalised — so it alone could store ' no '."""
    with SessionMaker() as s:
        supplier_registry.create_supplier(
            s,
            {
                "name": "Oslo Housing Co",
                "capabilities": [
                    {
                        "service_category": "housing_agencies",
                        "coverage_scope_type": "city",
                        "country_code": " no ",
                        "city_name": "Oslo",
                    }
                ],
            },
        )
        s.commit()
    with SessionMaker() as s:
        cap = s.query(SupplierServiceCapability).one()
        assert cap.country_code == "NO"


def test_no_supplier_capability_can_break_the_char2_cache(SessionMaker):
    """The invariant the nightly refresh depends on: every stored country_code is
    exactly 2 chars, so `supplier_cluster_cache.country_iso2` (character(2)) can
    always hold it."""
    with SessionMaker() as s:
        supplier_registry.create_supplier(
            s,
            {
                "name": "Madrid Movers",
                "capabilities": [
                    {
                        "service_category": "movers",
                        "coverage_scope_type": "city",
                        "country_code": "ES",
                        "city_name": "Madrid",
                    }
                ],
            },
        )
        s.commit()
    with SessionMaker() as s:
        codes = [c.country_code for c in s.query(SupplierServiceCapability).all()]
        assert codes and all(len(c) == 2 for c in codes), codes
