"""AIQ-2095 — approving a supplier capability forges the linked catalog master,
with the master's country taken from the CAPABILITY (country_code), never from
suppliers.based_in_country.

These pin the master-creation contract at the approval gate without the app-ORM /
dual-engine plumbing: `service_catalog.upsert_item` is mocked and the calls it
receives are asserted. ADR-002 Option B: one FR-based supplier serving DE and NO
under one name keeps a single master whose country is NULLed on the second
distinct country — not two masters, and not an FR one.
"""
from __future__ import annotations

import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services import supplier_registry, service_catalog  # noqa: E402


def _cap(country_code, *, category="movers", city="Oslo", supplier_id="vc-ags"):
    # Duck-typed SupplierServiceCapability: only the attrs the helper reads.
    return SimpleNamespace(
        service_category=category, country_code=country_code,
        city_name=city, supplier_id=supplier_id,
    )


class ApprovalCreatesMasterTests(unittest.TestCase):
    def test_master_country_comes_from_capability(self):
        cap = _cap("NO")  # supplier is based in FR, but the capability serves NO
        with mock.patch.object(service_catalog, "find_master_by_category_name", return_value=None), \
             mock.patch.object(service_catalog, "upsert_item") as up:
            supplier_registry._ensure_catalog_master_for_capability(cap, "AGS France")
        up.assert_called_once()
        kw = up.call_args.kwargs
        self.assertEqual(kw["category"], "movers")
        self.assertEqual(kw["country"], "NO")          # from the capability, not FR
        self.assertEqual(kw["supplier_id"], "vc-ags")
        self.assertEqual(kw["source"], "registry_promoted")
        self.assertEqual(kw["external_id"], "registry:vc-ags:movers:NO")

    def test_ags_france_second_country_nulls_the_single_master(self):
        """One FR-based supplier, two capabilities (DE then NO) → one master, country NULL."""
        existing = {"id": "master-ags", "supplier_id": "vc-ags", "country": "DE"}
        with mock.patch.object(service_catalog, "find_master_by_category_name", return_value=None), \
             mock.patch.object(service_catalog, "upsert_item") as up, \
             mock.patch.object(service_catalog, "clear_master_country") as clear:
            supplier_registry._ensure_catalog_master_for_capability(_cap("DE"), "AGS France")
        up.assert_called_once()
        self.assertEqual(up.call_args.kwargs["country"], "DE")
        clear.assert_not_called()

        with mock.patch.object(service_catalog, "find_master_by_category_name", return_value=existing), \
             mock.patch.object(service_catalog, "upsert_item") as up, \
             mock.patch.object(service_catalog, "clear_master_country") as clear:
            supplier_registry._ensure_catalog_master_for_capability(_cap("NO"), "AGS France")
        up.assert_not_called()
        clear.assert_called_once_with("master-ags")

    def test_same_country_reapproval_leaves_master_country(self):
        existing = {"id": "master-ags", "supplier_id": "vc-ags", "country": "DE"}
        with mock.patch.object(service_catalog, "find_master_by_category_name", return_value=existing), \
             mock.patch.object(service_catalog, "upsert_item") as up, \
             mock.patch.object(service_catalog, "clear_master_country") as clear:
            supplier_registry._ensure_catalog_master_for_capability(_cap("DE"), "AGS France")
        up.assert_not_called()
        clear.assert_not_called()

    def test_missing_category_creates_no_master(self):
        cap = _cap("NO", category="")
        with mock.patch.object(service_catalog, "upsert_item") as up:
            supplier_registry._ensure_catalog_master_for_capability(cap, "X")
        up.assert_not_called()

    def test_catalog_failure_never_raises(self):
        cap = _cap("NO")
        with mock.patch.object(service_catalog, "find_master_by_category_name", return_value=None), \
             mock.patch.object(
                 service_catalog, "upsert_item", side_effect=RuntimeError("db down")
             ):
            # Best-effort: an approval already committed must not be undone by a
            # catalog failure.
            supplier_registry._ensure_catalog_master_for_capability(cap, "AGS France")


if __name__ == "__main__":
    unittest.main()
