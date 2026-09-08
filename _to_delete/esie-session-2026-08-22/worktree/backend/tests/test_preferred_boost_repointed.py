"""[AIQ-1530] The +15 'preferred' boost reads HR curation, not the retired table.

Validation criterion 2: "Nothing reads company_preferred_suppliers any more" — in the
RECOMMENDATION + MARKETPLACE path. (The /hr/preferred-suppliers page endpoint still reads it;
that page is retired by S4/AIQ-1532, out of scope here.) These are source-guards so a future
edit can't silently repoint the boost back at the dead table.
"""
from __future__ import annotations

import inspect

from backend.app.recommendations import criteria_builder
from backend.app.routers import marketplace
from backend.db.companies import CompaniesMixin


def test_criteria_builder_no_longer_reads_the_retired_table():
    src = inspect.getsource(criteria_builder)
    assert "list_company_preferred_suppliers" not in src, (
        "the boost source must be HR curation, not the retired company_preferred_suppliers"
    )
    assert "list_company_curated_supplier_ids" in src, "must read curation instead"


def test_marketplace_company_branch_reads_curation_and_keeps_the_global_flag():
    src = inspect.getsource(marketplace._get_preferred_supplier_ids)
    # Company branch repointed off the retired table...
    assert 'table("company_preferred_suppliers")' not in src
    assert "list_company_curated_supplier_ids" in src
    # ...but the GLOBAL preferred_partner branch is preserved.
    assert "preferred_partner" in src, "the global partner flag must still surface"


def test_the_new_reader_joins_curation_to_supplier_id_by_display_order():
    """The reader resolves CVS -> service_catalog_items.supplier_id, gated on selected, in
    HR's display_order. Pin the shape so the join can't silently drift."""
    src = inspect.getsource(CompaniesMixin.list_company_curated_supplier_ids)
    assert "company_vendor_selections" in src
    assert "service_catalog_items" in src and "supplier_id" in src
    assert "cvs.selected = true" in src, "selected is the hard gate"
    assert "display_order" in src, "HR's ranking intent"
