"""AIQ-2010 — the crawler must target the URLs the rule engine actually cites.

THE DEFECT THIS PINS (audited 2026-08-19)

`rce.rule_versions` cites 28 distinct source_urls. `crawled_source_documents` held 11 distinct
URLs. The join between them returned ZERO — so a detected source change could never be
attributed to a rule, and `source_change_reviews.rule_version_id` (NOT NULL) could never be
satisfied. The two sets were disjoint by construction: the crawler targeted general newcomer
portals, while the rule engine cites legal texts.

This test pins the eight legal sources that ARE cited and that returned HTTP 200 on audit.
It is deliberately offline: it asserts the *configuration*, not live reachability, so it stays
deterministic in CI. Reachability was verified once, by hand, and is recorded in
docs/findings/AIQ-2010-rule-source-url-audit.md.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_SOURCES = _REPO_ROOT / "backend" / "crawler" / "config" / "sources.json"

#: The eight rce.rule_versions source_urls that returned HTTP 200 on 2026-08-19.
#: The other twenty cited URLs are fabricated 404s and are deliberately NOT crawl targets —
#: they need re-sourcing, not crawling. See the finding doc.
AUDITED_LIVE_RULE_SOURCES = {
    "https://eur-lex.europa.eu/eli/dir/2021/1883/oj",
    "https://www.gesetze-im-internet.de/aufenthg_2004/__18.html",
    "https://www.gesetze-im-internet.de/aufenthg_2004/__18b.html",
    "https://www.gesetze-im-internet.de/aufenthg_2004/__18g.html",
    "https://www.gesetze-im-internet.de/aufenthg_2004/__27.html",
    "https://www.gesetze-im-internet.de/aufenthg_2004/__82.html",
    "https://www.gesetze-im-internet.de/beschv_2013/",
    "https://www.bundesanzeiger.de/",
}

#: Never crawl a fabricated citation. These 404 — pointing the crawler at them would
#: manufacture "unchanged" evidence for rules that have no real source.
FABRICATED_PREFIX = "https://www.gesetze-im-internet.de/Teilliste_"


def _sources():
    return json.loads(_SOURCES.read_text(encoding="utf-8"))["sources"]


class CrawlSourcesConfigTests(unittest.TestCase):
    def test_config_is_valid_and_complete(self) -> None:
        for s in _sources():
            for field in ("source_name", "base_url", "country_code", "trust_tier", "is_active"):
                self.assertIn(field, s, f"{s.get('source_name')!r} is missing {field}")
            self.assertTrue(s["base_url"].startswith("https://"),
                            f"{s['source_name']!r} must be https")

    def test_every_audited_live_rule_source_is_a_target(self) -> None:
        """The regression: before AIQ-2010 none of these were crawled, so no change event
        could be attributed to a rule version."""
        targets = {s["base_url"] for s in _sources() if s.get("is_active")}
        missing = AUDITED_LIVE_RULE_SOURCES - targets
        self.assertEqual(
            missing, set(),
            f"these rule-cited, HTTP-200 sources are not active crawl targets: {sorted(missing)}",
        )

    def test_no_fabricated_citation_is_ever_crawled(self) -> None:
        """Twenty cited URLs are fabricated 404s. Crawling one would produce a stream of
        'unchanged' results that reads as a stable source rather than a missing one."""
        bad = [s["base_url"] for s in _sources() if s["base_url"].startswith(FABRICATED_PREFIX)]
        self.assertEqual(bad, [], f"fabricated citations must never be crawl targets: {bad}")

    def test_source_names_are_unique(self) -> None:
        names = [s["source_name"] for s in _sources()]
        dupes = {n for n in names if names.count(n) > 1}
        self.assertEqual(dupes, set(), f"duplicate source_name(s): {sorted(dupes)}")

    def test_preexisting_portal_sources_were_not_removed(self) -> None:
        """The newcomer portals feed the corpus and serve a different purpose from the legal
        texts. This change is additive; losing them would be a silent regression elsewhere."""
        targets = {s["base_url"] for s in _sources()}
        for portal in (
            "https://www.make-it-in-germany.com/en/living-in-germany",
            "https://www.service-public.fr/particuliers/vosdroits/N20360",
            "https://www.oslo.kommune.no/english/",
        ):
            self.assertIn(portal, targets, f"pre-existing portal source lost: {portal}")


if __name__ == "__main__":
    unittest.main()
