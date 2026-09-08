"""The B3 city bundles, and the silent failure they are shaped to prevent.

`country_resources` stores provenance as `source_id`, a FK into `resource_sources`. It has no
`source_url` column. The executor resolves that FK by looking a resource's
`source_name`/`source_url` up among rows that ALREADY EXIST, so a bundle naming a source it
never declares links to nothing — and the resource lands with `source_id` NULL rather than
failing.

The first run of this import did exactly that: 13 rows written, zero citations, exit code 0,
no warning. For a batch whose entire claim is that every record is source-cited, an uncited row
is not a partial success; it is the failure. `test_every_resource_declares_its_source` is that
incident.

DB-free by construction: every assertion is about the bundle's internal consistency, which is
precisely the property that makes the import self-sufficient.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
FIXTURES = REPO / "backend" / "imports" / "resources" / "fixtures"
DATA = REPO / "docs" / "imports" / "data" / "B3"

BUNDLES = {
    "bundle_stavanger.json": ("city_stavanger.ndjson", "Stavanger", "NO"),
    "bundle_copenhagen.json": ("city_copenhagen.ndjson", "Copenhagen", "DK"),
}

#: Categories seeded in production, measured 2026-08-19. `schools_childcare` is deliberately
#: absent — the bundles declare it themselves, which is what this list exists to prove.
PROD_CATEGORIES = frozenset({
    "admin_essentials", "housing", "healthcare", "daily_life", "transport", "cost_of_living",
})


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


class TestB3CityBundles(unittest.TestCase):
    def test_every_resource_declares_its_source(self) -> None:
        """The regression test. An undeclared source resolves to NULL, silently."""
        for name in BUNDLES:
            bundle = load(name)
            declared = {s["source_name"] for s in bundle["sources"]}
            for r in bundle["resources"]:
                self.assertIn(
                    r["source_name"], declared,
                    f"{name}: resource {r['title']!r} cites a source the bundle never "
                    "declares — it would land with source_id NULL and no citation",
                )

    def test_every_declared_source_carries_a_url_and_a_retrieval_date(self) -> None:
        for name in BUNDLES:
            for s in load(name)["sources"]:
                self.assertTrue(s.get("url"), f"{name}: {s['source_name']} has no url")
                self.assertTrue(
                    s.get("retrieved_at"),
                    f"{name}: {s['source_name']} has no retrieved_at — a citation nobody "
                    "can date cannot be re-checked for staleness",
                )

    def test_every_category_is_either_in_production_or_declared(self) -> None:
        """A category that is neither fails validation, so the import cannot self-start."""
        for name in BUNDLES:
            bundle = load(name)
            available = PROD_CATEGORIES | {c["key"] for c in bundle["categories"]}
            for r in bundle["resources"]:
                self.assertIn(r["category_key"], available, f"{name}: {r['category_key']}")

    def test_counts_reconcile_with_the_b3_artifacts(self) -> None:
        for name, (ndjson, city, cc) in BUNDLES.items():
            expected = len([
                l for l in (DATA / ndjson).read_text().splitlines() if l.strip()
            ])
            bundle = load(name)
            self.assertEqual(len(bundle["resources"]), expected, name)
            for r in bundle["resources"]:
                self.assertEqual(r["city_name"], city)
                self.assertEqual(r["country_code"], cc)

    def test_nothing_is_published_or_visible(self) -> None:
        """Candidate only. Promotion to published is a separate human step."""
        for name in BUNDLES:
            for r in load(name)["resources"]:
                self.assertEqual(r["status"], "draft", f"{name}: {r['title']}")
                self.assertFalse(r["is_visible_to_end_users"], f"{name}: {r['title']}")

    def test_external_keys_are_unique_so_a_re_run_updates(self) -> None:
        keys = [r["external_key"] for name in BUNDLES for r in load(name)["resources"]]
        self.assertEqual(len(keys), len(set(keys)), "duplicate external_key would double-write")

    def test_the_generator_reproduces_the_committed_bundles(self) -> None:
        """A hand-edited bundle drifts from the artifact it claims to represent."""
        r = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "gen_b3_city_bundles.py"), "--check"],
            capture_output=True, text=True, cwd=str(REPO),
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class TestValidateOnlyReportsFailure(unittest.TestCase):
    """`--validate-only` used to print its errors and then announce "Validation passed".

    Line 106 read `if not args.validate_only: return 1`, so the failure path was skipped in
    exactly the mode whose only job is to report failure. A check that exits 0 while listing
    its own errors is worse than no check: it is cited as evidence.
    """

    def _run(self, bundle: dict) -> subprocess.CompletedProcess:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(bundle, fh)
            path = fh.name
        return subprocess.run(
            [sys.executable, str(REPO / "scripts" / "import_resources.py"),
             "--bundle", path, "--validate-only"],
            capture_output=True, text=True, cwd=str(REPO),
        )

    def test_a_bundle_referencing_an_undeclared_category_exits_nonzero(self) -> None:
        bad = load("bundle_stavanger.json")
        bad["resources"][0]["category_key"] = "does_not_exist_anywhere"
        # Strip the declared category too, so the reference cannot resolve locally either.
        bad["categories"] = []
        r = self._run(bad)
        self.assertNotEqual(r.returncode, 0,
                            "validation errors were printed but the process exited 0")
        self.assertIn("Validation errors", r.stdout)

    def test_a_self_sufficient_bundle_still_validates(self) -> None:
        """The guard must discriminate, not just fail everything."""
        ok = load("bundle_stavanger.json")
        # Declare every category it uses, so the check holds with no DB reachable.
        ok["categories"] = [
            {"key": k, "label": k, "description": "", "icon_name": "x",
             "sort_order": i + 1, "is_active": True}
            for i, k in enumerate(sorted({r["category_key"] for r in ok["resources"]}))
        ]
        r = self._run(ok)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
