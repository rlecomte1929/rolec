"""Promote() collapse tests (national-entity vs movers).

The filename matches the brief's pytest invocation. The cases live next to
executor.py so `pytest backend/imports/suppliers` runs the same suite.
"""
from backend.imports.suppliers.test_promote_national_entity import (  # noqa: F401
    test_ags_parenthetical_aside_still_one_movers_supplier,
    test_crown_norway_collapses_onto_existing_movers_supplier,
    test_same_country_bank_corridor_collapses,
    test_santander_es_does_not_collapse_onto_brasil,
)
