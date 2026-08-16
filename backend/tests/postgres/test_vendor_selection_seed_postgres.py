"""The test-drive vendor seed must propose the destination's catalog, not just linked suppliers.

THE DEFECT THIS PINS
--------------------
`_SEED_VENDOR_SELECTIONS_SQL` INNER JOINed `suppliers` + `supplier_service_capabilities`, which
silently required every catalog row to carry a `supplier_id` pointing at an approved supplier.
Measured against production on 2026-08-16:

    service_catalog_items, country='IE', active            -> 29 rows, all 6 categories
    ...of those, supplier_id IS NOT NULL                   ->  0 rows
    rows surviving the seed's JOIN                         ->  3 rows

The 3 survivors were SIRVA, Santa Fe and Déménagements Delahaye — global-coverage movers that
match *every* destination. It read as a hardcoded three-mover default; it was the join. Every
Ireland vendor we catalogued was unreachable, and no per-company seeding could fix it because
the seed itself was the thing dropping them.

WHY THE POSTGRES LANE
---------------------
The sqlite suite cannot express any of the three things under test:
  1. `attributes_json ->> 'verified'` — needs a real `jsonb` column;
  2. `row_number() OVER (PARTITION BY ...)` — the display-order window;
  3. LEFT JOIN semantics against a `varchar` FK that is NULL for every catalog row.

`service_catalog_items` and `company_vendor_selections` have no ORM model (they are raw-SQL
tables owned by `service_catalog.py` / `vendor_curation.py`), so `create_all` does not build
them. They are created here from the DDL in their own migrations —
`20260427120000_service_catalog_items.sql`, `20260427130000_company_vendor_selections.sql`, plus
the `supplier_id` column added by `20260918000000_rfq_supplier_identity.sql:42`. `suppliers` and
`supplier_service_capabilities` DO have models, so the session fixture's `create_all` supplies
them.
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import text

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

pytestmark = pytest.mark.postgres

# Import the full model registry BEFORE the session fixture runs `create_all`. Importing only
# the router under test leaves `Base.metadata` partially populated, so tables other migrations
# in the lane reference (e.g. `requirement_items`) are never created and the replay aborts with
# `relation "public.requirement_items" does not exist` — a fixture failure that looks like a
# failure of this test.
from backend.app import models  # noqa: E402,F401
from backend.app.routers.test_drive import _SEED_VENDOR_SELECTIONS_SQL  # noqa: E402

_RAW_SQL_TABLES = """
CREATE TABLE IF NOT EXISTS public.service_catalog_items (
  id uuid primary key default gen_random_uuid(),
  category text not null,
  city text,
  country text,
  name text not null,
  attributes_json jsonb not null default '{}'::jsonb,
  source text not null default 'manual',
  active boolean not null default true,
  external_id text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by_user_id uuid,
  supplier_id varchar
);
CREATE TABLE IF NOT EXISTS public.company_vendor_selections (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null,
  category text not null,
  destination_city text,
  country text,
  master_item_id uuid references public.service_catalog_items (id) on delete set null,
  custom_item_json jsonb,
  selected boolean not null default true,
  display_order integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by_user_id uuid,
  constraint cvs_one_source check (
    (master_item_id is not null and custom_item_json is null)
    or (master_item_id is null and custom_item_json is not null)
  ),
  unique (company_id, category, destination_city, master_item_id)
);
"""


@pytest.fixture()
def seeded(pg_schema):
    """A destination catalog shaped like production's Ireland: no supplier links, plus one
    globally-covering approved mover that the old INNER JOIN did let through."""
    engine = pg_schema
    company_id = str(uuid.uuid4())
    with engine.begin() as conn:
        for stmt in _RAW_SQL_TABLES.split(";"):
            if stmt.strip():
                conn.execute(text(stmt))
        conn.execute(text("DELETE FROM company_vendor_selections"))
        conn.execute(text("DELETE FROM service_catalog_items"))
        conn.execute(text("DELETE FROM supplier_service_capabilities"))
        conn.execute(text("DELETE FROM suppliers"))

        # 1) Ireland catalog rows with NO supplier linkage — production's actual shape.
        for name, category, verified in (
            ("Dublin Immigration Solicitors", "legal_admin", True),
            ("Unaccredited Legal Co", "legal_admin", False),
            ("Dublin Tax Partners", "tax_finance", True),
            ("Grafton Lettings", "housing_agencies", False),
            ("Bank of Ireland", "banks", False),
        ):
            conn.execute(
                text(
                    "INSERT INTO service_catalog_items "
                    "(category, country, name, attributes_json, source, active, external_id) "
                    "VALUES (:c, 'IE', :n, CAST(:a AS jsonb), 'seed', true, :e)"
                ),
                {
                    "c": category,
                    "n": name,
                    "a": '{"verified": true}' if verified else '{"verified": false}',
                    "e": f"ie-{name.lower().replace(' ', '-')}",
                },
            )

        # 2) A global-coverage approved mover, linked to a supplier — the pre-existing path
        #    that must keep working (this is what the 3 survivors were).
        supplier_id = "sup-global-mover"
        conn.execute(
            text("INSERT INTO suppliers (id, name, status, verified, source) "
                 "VALUES (:i, 'SIRVA Worldwide', 'active', false, 'admin_manual')"),
            {"i": supplier_id},
        )
        conn.execute(
            text("INSERT INTO supplier_service_capabilities "
                 "(id, supplier_id, service_category, coverage_scope_type, country_code, "
                 " platform_vetting_status, family_support, corporate_clients, remote_support) "
                 "VALUES (:id, :s, 'movers', 'global', NULL, 'approved', false, false, false)"),
            {"id": str(uuid.uuid4()), "s": supplier_id},
        )
        conn.execute(
            text("INSERT INTO service_catalog_items "
                 "(category, country, name, attributes_json, source, active, external_id, supplier_id) "
                 "VALUES ('movers', 'SG', 'SIRVA Worldwide', '{}'::jsonb, 'seed', true, 'gl-1', :s)"),
            {"s": supplier_id},
        )
    return engine, company_id


def _seed(engine, company_id, dest="IE"):
    with engine.begin() as conn:
        return conn.execute(
            text(_SEED_VENDOR_SELECTIONS_SQL),
            {"company_id": company_id, "dest_country": dest, "created_by": None},
        ).rowcount


def _rows(engine, company_id):
    with engine.begin() as conn:
        return {
            r.name: r
            for r in conn.execute(
                text(
                    "SELECT sci.name, sci.category, cvs.selected, cvs.display_order "
                    "FROM company_vendor_selections cvs "
                    "JOIN service_catalog_items sci ON sci.id = cvs.master_item_id "
                    "WHERE cvs.company_id = CAST(:c AS uuid)"
                ),
                {"c": company_id},
            ).mappings()
        }


def test_unlinked_destination_catalog_rows_are_seeded(seeded):
    """The regression: 5 IE rows with supplier_id NULL must all become selectable."""
    engine, company_id = seeded
    _seed(engine, company_id)
    rows = _rows(engine, company_id)
    assert "Dublin Immigration Solicitors" in rows
    assert "Grafton Lettings" in rows
    assert "Bank of Ireland" in rows
    # All 6 seeded items: 5 Ireland catalog rows + the global mover.
    assert len(rows) == 6
    # ...spanning real categories, not movers-only.
    assert {r["category"] for r in rows.values()} == {
        "legal_admin", "tax_finance", "housing_agencies", "banks", "movers",
    }


def test_global_coverage_supplier_still_seeded(seeded):
    """The pre-existing path must not regress: a global approved mover still qualifies even
    though its catalog row's own country is SG, not the destination."""
    engine, company_id = seeded
    _seed(engine, company_id)
    assert "SIRVA Worldwide" in _rows(engine, company_id)


def test_compliance_categories_are_not_auto_selected_while_unverified(seeded):
    engine, company_id = seeded
    _seed(engine, company_id)
    rows = _rows(engine, company_id)
    # legal_admin / tax_finance: selected only when verified.
    assert rows["Dublin Immigration Solicitors"]["selected"] is True
    assert rows["Dublin Tax Partners"]["selected"] is True
    assert rows["Unaccredited Legal Co"]["selected"] is False
    # Non-compliance categories keep the pre-existing selected=true default.
    assert rows["Grafton Lettings"]["selected"] is True
    assert rows["Bank of Ireland"]["selected"] is True


def test_seed_is_idempotent(seeded):
    engine, company_id = seeded
    first = _seed(engine, company_id)
    second = _seed(engine, company_id)
    assert first == 6
    assert second == 0, "re-running the seed must insert nothing"
    assert len(_rows(engine, company_id)) == 6


def test_other_destination_does_not_pull_ireland(seeded):
    """Tenant/destination hygiene: seeding a NO company must not hand it Ireland's catalog."""
    engine, _ = seeded
    other_company = str(uuid.uuid4())
    _seed(engine, other_company, dest="NO")
    rows = _rows(engine, other_company)
    assert "Dublin Immigration Solicitors" not in rows
    # Only the globally-covering mover qualifies for a destination with no catalog of its own.
    assert set(rows) == {"SIRVA Worldwide"}
