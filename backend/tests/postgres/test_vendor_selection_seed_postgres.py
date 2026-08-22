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
from backend.app.services.vendor_proposal import _SEED_SQL  # noqa: E402

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
        # Genuinely global: country IS NULL. This is the shape of the real SIRVA /
        # Déménagements Delahaye rows, and the only shape that should follow a global
        # capability onto any destination.
        conn.execute(
            text("INSERT INTO service_catalog_items "
                 "(category, country, name, attributes_json, source, active, external_id, supplier_id) "
                 "VALUES ('movers', NULL, 'SIRVA Worldwide', '{}'::jsonb, 'seed', true, 'gl-1', :s)"),
            {"s": supplier_id},
        )
        # [AIQ-1903] The Santa Fe case, modelled: a row tagged for ANOTHER country whose
        # supplier capability is global. In production this is `Santa Fe Relocation`
        # (country='AU', city='Sydney'), which seeded onto Irish moves beside the existing
        # `Santa Fe Relocation Dublin` — a near-duplicate from the wrong hemisphere.
        conn.execute(
            text("INSERT INTO service_catalog_items "
                 "(category, country, city, name, attributes_json, source, active, external_id, supplier_id) "
                 "VALUES ('movers', 'AU', 'Sydney', 'Santa Fe Relocation', '{}'::jsonb, 'seed', true, 'au-1', :s)"),
            {"s": supplier_id},
        )
        # [AIQ-1903] An untagged row with NO supplier link: the `Supplier Test` /
        # `testsupplier` shape. Must never reach a real customer's list.
        conn.execute(
            text("INSERT INTO service_catalog_items "
                 "(category, country, name, attributes_json, source, active, external_id) "
                 "VALUES ('movers', NULL, 'testsupplier', '{}'::jsonb, 'seed', true, 'junk-1')")
        )
        # [AIQ-1903] A SCRAPER-verified solicitor. attributes_json says verified=true, but the
        # research pipeline wrote it — 876 of 877 scraper rows claim to be verified. Must be
        # proposed, never auto-approved.
        conn.execute(
            text("INSERT INTO service_catalog_items "
                 "(category, country, name, attributes_json, source, active, external_id) "
                 "VALUES ('legal_admin', 'IE', 'Otto Scraped Solicitors', "
                 "'{\"verified\": true, \"provenance\": \"otto_research\"}'::jsonb, "
                 "'scraper', true, 'ie-scraped')")
        )
    return engine, company_id


def _seed(engine, company_id, dest="IE", default_selected=True):
    """`default_selected` is the caller POLICY: True for test-drive (a demo must arrive
    populated), False for a real company (propose, let HR approve)."""
    with engine.begin() as conn:
        return conn.execute(
            text(_SEED_SQL),
            {"company_id": company_id, "dest_country": dest, "created_by": None,
             "default_selected": default_selected},
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
    # 7 seeded: 5 Ireland catalog rows + the genuinely-global mover + the scraper-verified
    # solicitor (proposed, not approved). The AU-tagged Santa Fe row and the supplier-less
    # `testsupplier` are excluded — each has its own test below.
    assert len(rows) == 7
    # ...spanning real categories, not movers-only.
    assert {r["category"] for r in rows.values()} == {
        "legal_admin", "tax_finance", "housing_agencies", "banks", "movers",
    }


def test_genuinely_global_supplier_still_seeded(seeded):
    """The pre-existing path must not regress: an untagged (country IS NULL) approved mover
    still follows its global capability onto any destination."""
    engine, company_id = seeded
    _seed(engine, company_id)
    assert "SIRVA Worldwide" in _rows(engine, company_id)


def test_a_row_tagged_for_another_country_is_never_seeded(seeded):
    """[AIQ-1903] A global CAPABILITY does not license a foreign catalog row.

    This test previously asserted the opposite — it accepted an 'SG'-tagged row onto an Irish
    move because its supplier coverage was global. In production that rule seeded
    `Santa Fe Relocation` (country='AU', city='Sydney') alongside the existing
    `Santa Fe Relocation Dublin`: a near-duplicate, from the wrong country, on every Irish
    move. Coverage says where a supplier CAN work; the catalog row's own country says which
    destination this listing is FOR, and the second one wins.
    """
    engine, company_id = seeded
    _seed(engine, company_id)
    assert "Santa Fe Relocation" not in _rows(engine, company_id)


def test_untagged_rows_without_a_supplier_are_never_seeded(seeded):
    """[AIQ-1903] `country IS NULL` alone must not qualify, or the fixtures leak.

    Production carries active, country-less catalog rows literally named `Supplier Test` and
    `testsupplier`. Admitting every untagged row — which an earlier draft of this fix did —
    proposes them as vendors to real customers. An untagged row must earn its place through
    an approved supplier capability.
    """
    engine, company_id = seeded
    _seed(engine, company_id)
    assert "testsupplier" not in _rows(engine, company_id)


def test_a_scraper_verified_solicitor_is_proposed_but_not_auto_approved(seeded):
    """[AIQ-1903] `attributes_json.verified` is not, by itself, evidence of accreditation.

    Measured 2026-08-17: the research pipeline sets verified=true on essentially everything it
    writes — otto_research_backfill 338/338, otto_research_thin 293/293, otto_research 245/245;
    876 of 877 scraper rows. Gating on the flag alone auto-approved 4 of 5 Irish solicitors and
    all 11 French legal/tax firms. A regulated professional must be human-verified before
    ReloPass pre-ticks them on HR's behalf, so the flag must be paired with a non-scraper
    source.

    The row is still SEEDED — HR can see and approve it. Only the auto-approval is withheld.
    """
    engine, company_id = seeded
    _seed(engine, company_id)
    rows = _rows(engine, company_id)
    assert "Otto Scraped Solicitors" in rows, "must be proposed, not hidden"
    assert rows["Otto Scraped Solicitors"]["selected"] is False


def test_real_company_policy_proposes_everything_unselected(seeded):
    """[AIQ-1903] The real-company caller seeds the same list, approved by nobody.

    `hr_catalog.get_curation_view` treats an untouched master as selected=False and the
    employee filter shows an empty curation as "HR is finalizing providers". Seeding a real
    company's rows as approved would overturn that authority model, so the case-finalisation
    caller passes default_selected=False: HR gets a full pre-filled list to tick, the employee
    sees no change until they do.
    """
    engine, _ = seeded
    company = str(uuid.uuid4())
    inserted = _seed(engine, company, default_selected=False)
    rows = _rows(engine, company)
    assert inserted == len(rows) > 0
    assert all(r["selected"] is False for r in rows.values()), (
        "a real company must have nothing approved on its behalf"
    )


def test_compliance_categories_are_not_auto_selected_while_unverified(seeded):
    engine, company_id = seeded
    _seed(engine, company_id)
    rows = _rows(engine, company_id)
    # legal_admin / tax_finance: selected only when HUMAN-verified (source <> 'scraper').
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
    assert first == 7
    assert second == 0, "re-running the seed must insert nothing"
    assert len(_rows(engine, company_id)) == 7


def test_other_destination_does_not_pull_ireland(seeded):
    """Tenant/destination hygiene: seeding a NO company must not hand it Ireland's catalog."""
    engine, _ = seeded
    other_company = str(uuid.uuid4())
    _seed(engine, other_company, dest="NO")
    rows = _rows(engine, other_company)
    assert "Dublin Immigration Solicitors" not in rows
    # Only the globally-covering mover qualifies for a destination with no catalog of its own.
    assert set(rows) == {"SIRVA Worldwide"}


# ─────────────────────────────────────────────────────────────────────────────
# [AIQ-1903 re-land] Norway — the shape that got the first attempt reverted.
#
# #1870 measured IE (29 rows, 0 supplier-linked) and FR (46, 0). Those are the two
# destinations where the vetting gate has nothing to bite on, because no row carries
# a supplier link. Norway is the opposite and was never measured:
#
#     production 2026-08-19        FR  46 rows,  0 supplier-linked
#                                  IE  29 rows,  0 supplier-linked
#                                  NO  17 rows, 17 supplier-linked, 3 verified
#
# E2E Sentinel [R4X-B] runs on FR_NO and needs at least 2 provider cards; the FR_NO
# fixture rendered 1, and #1870 was reverted in #1907. The revert asked for exactly
# one thing before re-landing: "re-land with Norway measured alongside IE and FR".
#
# These tests are that measurement, expressed as fixtures rather than as a snapshot of
# production — so they keep holding when the vetting data moves again (all 17 Norwegian
# capabilities are 'approved' as of 2026-08-22, which is why the original symptom no
# longer reproduces; that is data, and data changes back).
# ─────────────────────────────────────────────────────────────────────────────

_NO_CATEGORIES = (
    ("banks", 3),
    ("housing_agencies", 4),
    ("movers", 4),
    ("schools", 3),
    ("legal_admin", 3),     # compliance — held back unless human-verified
    ("tax_finance", 2),     # compliance — held back unless human-verified
)


@pytest.fixture()
def norway(pg_schema):
    """A destination catalog shaped like production's Norway: EVERY row supplier-linked
    with an approved, country-scoped capability, and no compliance row human-verified."""
    engine = pg_schema
    company_id = str(uuid.uuid4())
    with engine.begin() as conn:
        for stmt in _RAW_SQL_TABLES.split(";"):
            if stmt.strip():
                conn.execute(text(stmt))
        for table in ("company_vendor_selections", "service_catalog_items",
                      "supplier_service_capabilities", "suppliers"):
            conn.execute(text(f"DELETE FROM {table}"))

        for category, count in _NO_CATEGORIES:
            for n in range(count):
                supplier_id = f"sup-no-{category}-{n}"
                conn.execute(
                    text("INSERT INTO suppliers (id, name, status, verified, source) "
                         "VALUES (:i, :nm, 'active', false, 'admin_manual')"),
                    {"i": supplier_id, "nm": f"NO {category} {n}"},
                )
                conn.execute(
                    text("INSERT INTO supplier_service_capabilities "
                         "(id, supplier_id, service_category, coverage_scope_type, country_code, "
                         " platform_vetting_status, family_support, corporate_clients, remote_support) "
                         "VALUES (:id, :s, :c, 'country', 'NO', 'approved', false, false, false)"),
                    {"id": str(uuid.uuid4()), "s": supplier_id, "c": category},
                )
                conn.execute(
                    text("INSERT INTO service_catalog_items "
                         "(category, country, name, attributes_json, source, active, external_id, supplier_id) "
                         "VALUES (:c, 'NO', :nm, '{}'::jsonb, 'seed', true, :e, :s)"),
                    {"c": category, "nm": f"NO {category} {n}",
                     "e": f"no-{category}-{n}", "s": supplier_id},
                )
    return engine, company_id


def test_norway_shaped_catalog_seeds_every_row(norway):
    """The country guard must not drop rows that ARE tagged for the destination.

    This is the half of #1870 the revert blamed: "a catalog row tagged for a different
    country no longer qualifies". Norwegian rows are tagged 'NO', so for dest='NO' they
    all qualify — the guard only excludes OTHER countries.
    """
    engine, company_id = norway
    assert _seed(engine, company_id, dest="NO") == sum(c for _, c in _NO_CATEGORIES)


def test_norway_still_offers_enough_providers_for_the_r4x_b_fixture(norway):
    """[R4X-B] on FR_NO renders provider cards from `selected=true` rows and asserts >= 2.

    The compliance hold-back (legal_admin / tax_finance unverified -> selected=false) is
    correct and deliberate, but it must not starve the page. Assert the floor the E2E
    fixture actually needs, so a future change to the hold-back rule fails HERE — in a
    deterministic Postgres test — rather than as a red Sentinel run on main.
    """
    engine, company_id = norway
    _seed(engine, company_id, dest="NO", default_selected=True)
    rows = _rows(engine, company_id)
    selected = [r for r in rows.values() if r["selected"]]
    assert len(selected) >= 2, (
        f"only {len(selected)} selected rows for a Norway-shaped catalog; [R4X-B] needs 2. "
        "This is the regression that reverted #1870 in #1907."
    )
    # And specifically: the non-compliance categories carry it.
    non_compliance = {r["category"] for r in selected}
    assert non_compliance == {"banks", "housing_agencies", "movers", "schools"}


def test_norway_compliance_categories_are_seeded_but_not_auto_approved(norway):
    """Unverified solicitors/tax advisers are PROPOSED to HR, never endorsed for them.

    Held back even though their supplier capability is 'approved': platform vetting is not
    professional accreditation, and a demo is not a reason to endorse a regulated adviser.
    """
    engine, company_id = norway
    _seed(engine, company_id, dest="NO", default_selected=True)
    rows = _rows(engine, company_id)
    compliance = [r for r in rows.values() if r["category"] in ("legal_admin", "tax_finance")]
    assert len(compliance) == 5, "compliance rows must still be proposed"
    assert all(r["selected"] is False for r in compliance)
