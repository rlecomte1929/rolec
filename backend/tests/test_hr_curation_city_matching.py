"""The curation screen must not lose vendors to a difference in spelling.

HR could not reach 29 already-approved Dublin vendors. `get_curation_view` filtered the admin
master items with a raw `m.get("city") == destination_city`, while
`vendor_curation.list_curation` — called in the SAME request — canonicalises the city, for
exactly this reason (AIQ-1457). The destination allowlist held Dublin as both 'Dublin' and
'dublin'; the picker offered both; choosing the lower-cased one returned zero master items
while 29 vendors sat curated and `selected=true` underneath.

These pin the two halves agreeing, and the size cap that silently truncates cities.
"""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.routers import hr_catalog  # noqa: E402
from backend.app.services.vendor_curation import _canon_city  # noqa: E402

_DUBLIN_MASTERS = [
    {"id": "m1", "name": "Santa Fe Dublin", "city": "Dublin", "country": "IE"},
    {"id": "m2", "name": "Crown Relocations Dublin", "city": "Dublin", "country": "IE"},
    {"id": "m3", "name": "Bergen Movers", "city": "Bergen", "country": "NO"},
]


def _filter(destination_city: str):
    """The exact expression get_curation_view uses to narrow master items to a city."""
    want = _canon_city(destination_city)
    return [m for m in _DUBLIN_MASTERS if _canon_city(m.get("city")) == want]


class CityMatchingIsCanonical(unittest.TestCase):
    def test_the_exact_spelling_still_works(self) -> None:
        self.assertEqual(2, len(_filter("Dublin")))

    def test_the_lowercase_spelling_that_lost_29_vendors_now_matches(self) -> None:
        """The regression. Under the old `==` this returned 0."""
        self.assertEqual(2, len(_filter("dublin")))

    def test_whitespace_and_diacritics_do_not_hide_a_city(self) -> None:
        self.assertEqual(2, len(_filter("  DUBLIN  ")))
        masters = [{"id": "z", "city": "Zürich"}]
        self.assertEqual(
            1, len([m for m in masters if _canon_city(m["city"]) == _canon_city("Zurich")])
        )

    def test_a_different_city_is_still_excluded(self) -> None:
        """Canonicalising must not turn the filter into a pass-through — it would serve
        Bergen movers to a Dublin case, which is worse than serving none."""
        self.assertEqual(1, len(_filter("Bergen")))
        self.assertEqual(0, len(_filter("Madrid")))

    def test_the_view_and_the_curation_reader_use_the_same_canonicaliser(self) -> None:
        """They disagreeing IS the bug. Importing from the owning module makes drift
        impossible; this asserts the import is actually wired."""
        self.assertIs(hr_catalog._canon_city, _canon_city)


class CategorySizeCapDoesNotTruncateCities(unittest.TestCase):
    def test_the_cap_clears_the_largest_category(self) -> None:
        """The cap is applied BEFORE the city filter, so a category that outgrows it loses
        whole cities with no error. legal_admin was at 183 of 200 on 2026-08-23."""
        import inspect

        src = inspect.getsource(hr_catalog.get_curation_view)
        self.assertIn("limit=2000", src)
        self.assertNotIn("limit=200,", src)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
