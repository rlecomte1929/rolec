"""
AIQ-1690 — a registry item and its legacy static twin must not both enter the dataset.

The supplier registry keys a candidate by ``item_id = supplier.id`` (a UUID); the legacy
static JSON dataset keys the *same* supplier ``item_id = 'm-N'``. They never collide on
item_id, so ``_load_dataset_with_registry`` used to merge both — one real supplier could
then occupy two of the ``top_n`` slots and push a different distinct approved supplier
below the cut. ``apply_hr_curation`` dedups by master id, but only *after* the cut.

The link between the two representations is ``service_catalog_items.supplier_id``
(external_id='m-1', supplier_id=<that supplier UUID>) — the same link AIQ-1688 used.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app import db as app_db  # noqa: E402
from backend.app.recommendations import engine  # noqa: E402
from backend.app.recommendations.registry import get_plugin  # noqa: E402
from backend.app.services import service_catalog, supplier_registry  # noqa: E402

_SUPPLIER_UUID = "6ad6f9ee-4506-4a06-a867-1d0cf357b1f6"  # Asian Tigers, prod shape
_CRITERIA = {"destination_city": "Singapore", "destination_country": "SG"}


def _registry_item(item_id: str, name: str) -> dict:
    return {
        "item_id": item_id,
        "name": name,
        "city": "Singapore",
        "rating": 4.5,
        "rating_count": 10,
        "_source": "supplier_registry",
    }


def _static_item(item_id: str, name: str) -> dict:
    return {
        "item_id": item_id,
        "name": name,
        "service_areas": ["Singapore"],
        "international_capable": True,
        "max_volume_m3": 40,
        "rating": 4.7,
        "rating_count": 89,
    }


@pytest.fixture
def wired(monkeypatch):
    """Stub the two DB-backed inputs of _load_dataset_with_registry.

    Returns a setter so each test declares (registry_items, static_dataset, masters)
    without touching Postgres.
    """
    monkeypatch.setattr(app_db, "SessionLocal", MagicMock(), raising=False)

    def _wire(registry_items, static_dataset, twin_external_ids, *, lookup_raises=False):
        monkeypatch.setattr(
            supplier_registry,
            "search_by_service_destination",
            lambda *a, **k: list(registry_items),
            raising=False,
        )
        monkeypatch.setattr(
            get_plugin("movers"),
            "load_dataset",
            lambda: list(static_dataset),
            raising=False,
        )

        def _fake_lookup(category, supplier_ids):
            if lookup_raises:
                raise RuntimeError("service_catalog_items unavailable")
            return set(twin_external_ids)

        monkeypatch.setattr(
            service_catalog,
            "external_ids_for_supplier_ids",
            _fake_lookup,
            raising=False,
        )

    return _wire


def test_static_twin_dropped_registry_representation_kept(wired):
    """Criterion 2: registry item + its static twin → ONE candidate, the registry one."""
    wired(
        registry_items=[_registry_item(_SUPPLIER_UUID, "Asian Tigers")],
        static_dataset=[_static_item("m-1", "Asian Tigers")],
        twin_external_ids={"m-1"},
    )

    dataset = engine._load_dataset_with_registry("movers", _CRITERIA)

    assert [d["item_id"] for d in dataset] == [_SUPPLIER_UUID]
    assert dataset[0]["_source"] == "supplier_registry"


def test_static_item_without_registry_twin_still_merged(wired):
    """A static item that is NOT a registry supplier must survive — no over-dedup."""
    wired(
        registry_items=[_registry_item(_SUPPLIER_UUID, "Asian Tigers")],
        static_dataset=[_static_item("m-1", "Asian Tigers"), _static_item("m-5", "Leo's Moving")],
        twin_external_ids={"m-1"},
    )

    dataset = engine._load_dataset_with_registry("movers", _CRITERIA)

    assert [d["item_id"] for d in dataset] == [_SUPPLIER_UUID, "m-5"]


def test_no_distinct_supplier_crowded_out_of_top_n(wired):
    """Criterion 1 (unit form): with twins removed, top_n holds top_n DISTINCT suppliers.

    Twelve registry suppliers, ten of which also have a static twin. Before the fix the
    22-row dataset let twins eat top-10 slots; after it the dataset is 12 distinct rows.
    """
    registry = [_registry_item(f"uuid-{i}", f"Mover {i}") for i in range(1, 13)]
    static = [_static_item(f"m-{i}", f"Mover {i}") for i in range(1, 11)]
    wired(
        registry_items=registry,
        static_dataset=static,
        twin_external_ids={f"m-{i}" for i in range(1, 11)},
    )

    dataset = engine._load_dataset_with_registry("movers", _CRITERIA)

    assert len(dataset) == 12
    assert len({d["item_id"] for d in dataset}) == 12
    assert all(d["_source"] == "supplier_registry" for d in dataset)


def test_twin_lookup_failure_falls_back_to_legacy_merge(wired):
    """The dedup is best-effort: a lookup error must not blank the category."""
    wired(
        registry_items=[_registry_item(_SUPPLIER_UUID, "Asian Tigers")],
        static_dataset=[_static_item("m-1", "Asian Tigers")],
        twin_external_ids={"m-1"},
        lookup_raises=True,
    )

    dataset = engine._load_dataset_with_registry("movers", _CRITERIA)

    assert [d["item_id"] for d in dataset] == [_SUPPLIER_UUID, "m-1"]


def test_registry_empty_uses_static_only(wired):
    """Regression: with no registry hits the static dataset is still the fallback."""
    wired(
        registry_items=[],
        static_dataset=[_static_item("m-1", "Asian Tigers")],
        twin_external_ids=set(),
    )

    dataset = engine._load_dataset_with_registry("movers", _CRITERIA)

    assert [d["item_id"] for d in dataset] == ["m-1"]
