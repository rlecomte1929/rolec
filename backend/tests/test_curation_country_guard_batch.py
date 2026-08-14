"""[F-2] One bad toggle must not discard HR's whole save.

`bulk_select` loops over toggles with no error handling, so a guard that raises would abort
the entire batch — a worse bug than the one it fixes. HR saves ~19 selections at a time
(the audit measured avg 19.4 per company), so a single Sydney mover in the list would have
silently discarded eighteen good rows.

The guard therefore rejects per toggle and returns the rejections, which is what these tests
pin. If someone later "simplifies" the try/except away, the batch test fails.
"""
from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

_qc = MagicMock()
_qc.install_query_counter = lambda *a, **k: None
sys.modules.setdefault("backend.app.services.query_counter", _qc)

from backend.app.routers import hr_catalog  # noqa: E402
from backend.app.services.vendor_curation import CountryMismatch  # noqa: E402

_USER = {"id": "hr-1"}


def _body(*toggles):
    return hr_catalog.BulkSelectBody(
        category="movers",
        destination_city="Oslo",
        country="NO",
        toggles=[hr_catalog.SelectToggle(master_item_id=m, selected=s) for m, s in toggles],
    )


class BatchRejectionTests(unittest.TestCase):
    def _run(self, body, side_effect):
        with patch.object(hr_catalog, "_caller_company_id", return_value="co-1"), \
             patch.object(hr_catalog, "_audit_catalog"), \
             patch.object(hr_catalog.vendor_curation, "upsert_master_selection",
                          side_effect=side_effect) as up:
            return hr_catalog.bulk_select(body, user=_USER), up

    def test_the_good_toggles_in_a_batch_still_save(self) -> None:
        def side_effect(*, master_item_id, **kw):
            if master_item_id == "bad":
                raise CountryMismatch("Santa Fe Relocation is in AU; this selection is for NO.")
            return {"id": f"row-{master_item_id}", "selected": True}

        out, up = self._run(_body(("ok-1", True), ("bad", True), ("ok-2", True)), side_effect)

        self.assertEqual(out["updated"], 2, "the two valid toggles must persist")
        self.assertEqual(len(out["rejected"]), 1)
        self.assertEqual(up.call_count, 3, "every toggle is attempted, not short-circuited")

    def test_the_rejection_names_the_row_and_the_reason(self) -> None:
        def side_effect(*, master_item_id, **kw):
            raise CountryMismatch("Santa Fe Relocation is in AU; this selection is for NO.")

        out, _ = self._run(_body(("bad", True)), side_effect)
        rej = out["rejected"][0]
        self.assertEqual(rej["master_item_id"], "bad")
        self.assertIn("AU", rej["reason"])
        self.assertIn("NO", rej["reason"])

    def test_a_clean_batch_reports_no_rejections(self) -> None:
        out, _ = self._run(
            _body(("ok-1", True), ("ok-2", False)),
            lambda **kw: {"id": "row", "selected": True},
        )
        self.assertEqual(out["updated"], 2)
        self.assertEqual(out["rejected"], [])

    def test_the_response_keeps_its_existing_shape(self) -> None:
        """`rejected` is additive — the shipped client reads `updated` and `rows`."""
        out, _ = self._run(_body(("ok-1", True)), lambda **kw: {"id": "r", "selected": True})
        self.assertIn("updated", out)
        self.assertIn("rows", out)
        self.assertEqual(len(out["rows"]), out["updated"])

    def test_an_all_rejected_batch_does_not_raise(self) -> None:
        """HR gets a 200 listing what was refused, not a 500."""
        def side_effect(**kw):
            raise CountryMismatch("wrong country")

        out, _ = self._run(_body(("bad-1", True), ("bad-2", True)), side_effect)
        self.assertEqual(out["updated"], 0)
        self.assertEqual(len(out["rejected"]), 2)

    def test_an_unrelated_error_still_propagates(self) -> None:
        """Only CountryMismatch is absorbed. A DB failure must not be swallowed as a
        'rejected toggle' — that would hide an outage behind a validation message."""
        def side_effect(**kw):
            raise RuntimeError("db down")

        with self.assertRaises(RuntimeError):
            self._run(_body(("x", True)), side_effect)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
