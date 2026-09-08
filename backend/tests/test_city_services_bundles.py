"""City-services harvest → resources bundle.

Same silent-NULL trap as B3: `country_resources.source_id` is an FK. A resource
that names a source the bundle never declares lands uncited. This file is
DB-free; it only checks the bundle's internal consistency.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
FIXTURE = REPO / "backend" / "imports" / "resources" / "fixtures" / "bundle_city_services_2026_08_31.json"
HARVEST = REPO / "docs" / "imports" / "relopass-city-services-2026-08-31"
GEN = REPO / "scripts" / "gen_city_services_bundles.py"

PROD_OR_DECLARED_OK = frozenset({
    "admin_essentials", "housing", "healthcare", "daily_life", "transport",
    "cost_of_living", "schools_childcare",
})


def load() -> dict:
    return json.loads(FIXTURE.read_text())


class TestCityServicesBundle(unittest.TestCase):
    def test_every_resource_declares_its_source(self) -> None:
        bundle = load()
        declared = {s["source_name"] for s in bundle["sources"]}
        for r in bundle["resources"]:
            self.assertIn(
                r["source_name"], declared,
                f"{r['title']!r} cites a source the bundle never declares",
            )

    def test_every_declared_source_carries_a_url_and_a_retrieval_date(self) -> None:
        for s in load()["sources"]:
            self.assertTrue(s.get("url"), f"{s['source_name']} has no url")
            self.assertTrue(
                s.get("retrieved_at"),
                f"{s['source_name']} has no retrieved_at",
            )

    def test_every_category_is_declared_in_the_bundle(self) -> None:
        bundle = load()
        available = {c["key"] for c in bundle["categories"]}
        for r in bundle["resources"]:
            self.assertIn(r["category_key"], available, r["category_key"])
            self.assertIn(r["category_key"], PROD_OR_DECLARED_OK)

    def test_nothing_is_published_or_visible(self) -> None:
        for r in load()["resources"]:
            self.assertEqual(r["status"], "draft", r["title"])
            self.assertFalse(r["is_visible_to_end_users"], r["title"])

    def test_external_keys_are_unique(self) -> None:
        keys = [r["external_key"] for r in load()["resources"]]
        self.assertEqual(len(keys), len(set(keys)))

    def test_source_missing_blocks_are_not_imported(self) -> None:
        """A harvested block with source_missing=true must not become a resource."""
        titles_by_city: dict[tuple[str, str], set[str]] = {}
        for r in load()["resources"]:
            titles_by_city.setdefault((r["country_code"], r["city_name"]), set()).add(
                r["external_key"].rsplit("-", 1)[-1]
            )
        for nd in HARVEST.rglob("city-*.ndjson"):
            raw = nd.read_bytes().replace(b"(NN/RRN)\xa2,", b'(NN/RRN)",')
            rec = json.loads(raw.decode("utf-8", errors="replace").strip().splitlines()[0])
            iso2, city = rec["iso2"], rec["city"]
            present = titles_by_city.get((iso2, city), set())
            for topic, block in (rec.get("services") or {}).items():
                if isinstance(block, dict) and block.get("source_missing") is True:
                    self.assertNotIn(
                        topic, present,
                        f"{iso2}/{city} {topic} was source_missing but still imported",
                    )

    def test_the_generator_reproduces_the_committed_bundle(self) -> None:
        r = subprocess.run(
            [sys.executable, str(GEN), "--check"],
            capture_output=True, text=True, cwd=str(REPO),
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_validate_only_accepts_the_self_sufficient_bundle(self) -> None:
        r = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "import_resources.py"),
             "--bundle", str(FIXTURE), "--validate-only"],
            capture_output=True, text=True, cwd=str(REPO),
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_validate_only_rejects_an_undeclared_category(self) -> None:
        bad = load()
        bad["resources"][0]["category_key"] = "does_not_exist_anywhere"
        bad["categories"] = []
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(bad, fh)
            path = fh.name
        r = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "import_resources.py"),
             "--bundle", path, "--validate-only"],
            capture_output=True, text=True, cwd=str(REPO),
        )
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn("Validation errors", r.stdout)


if __name__ == "__main__":
    unittest.main()
