"""A rule version whose source_url does not resolve must not be persistable.

BACKGROUND. Probing all 28 distinct `rce.rule_versions.source_url` values on 2026-08-19
found 20 rule versions across 20 URLs returning 404 — every one shaped
`gesetze-im-internet.de/Teilliste_<citation>.html`. Re-measured 2026-08-23: still 34 rule
versions, still exactly 20 matching `%/Teilliste_%`, and still 0 contamination in
`requirement_facts` (0 of 2,676 rows carrying a source_url).

They were not invented by a model. `corridor_persistence.derive_source_url` produces them
deterministically in its last fallback, because `rce.rule_versions.source_url` is NOT NULL
and the function's stated job is to always return "a usable, non-empty link".

This file pins two things:
  * the checker's THREE-state contract (the reason it is not a boolean), and
  * that `persist_corridor_case` refuses to write a dead citation.

The second assertion is the one that fails against the code as it stood before this
change: there was no check of any kind on that path.
"""
from __future__ import annotations

import unittest
from unittest import mock

from backend.app.services import corridor_persistence as cp
from backend.app.services.source_url_reachability import (
    Reachability,
    SourceURLUnverified,
    UnreachableSourceURL,
    Verdict,
    assert_source_urls_resolve,
    check_source_urls,
    probe_url,
)

DEAD = "https://www.gesetze-im-internet.de/Teilliste_Utlendingsloven+%C2%A7109.html"
LIVE = "https://eur-lex.europa.eu/eli/dir/2021/1883/oj"


def _fake(mapping):
    """A probe that answers from a dict — no network anywhere in this file."""
    def _p(url: str) -> Reachability:
        verdict = mapping.get(url, Verdict.OK)
        code = {Verdict.OK: 200, Verdict.DEAD: 404, Verdict.UNVERIFIED: None}[verdict]
        return Reachability(url, verdict, code, f"fake {verdict.value}")
    return _p


class TheContractIsThreeStatedNotTwo(unittest.TestCase):

    def test_404_is_dead_and_raises(self):
        with self.assertRaises(UnreachableSourceURL) as ctx:
            assert_source_urls_resolve([DEAD], probe=_fake({DEAD: Verdict.DEAD}))
        self.assertIn(DEAD, str(ctx.exception))

    def test_a_transient_failure_is_NOT_a_pass(self):
        """The distinction the whole design rests on. A two-state checker must map a
        timeout to accept or reject; both are wrong. Accepting means an outage silently
        readmits fabricated URLs."""
        with self.assertRaises(SourceURLUnverified):
            assert_source_urls_resolve([LIVE], probe=_fake({LIVE: Verdict.UNVERIFIED}))

    def test_a_transient_failure_is_NOT_a_rejection_either(self):
        """...and rejecting outright would block a legitimate seed on a flaky network,
        so the caller can accept it, but only by saying so."""
        results = assert_source_urls_resolve(
            [LIVE], probe=_fake({LIVE: Verdict.UNVERIFIED}), allow_unverified=True
        )
        self.assertEqual(results[0].verdict, Verdict.UNVERIFIED)

    def test_dead_is_reported_before_unverified(self):
        """A provably absent URL is the finding worth surfacing; reporting 'could not
        verify' first would bury it."""
        with self.assertRaises(UnreachableSourceURL):
            assert_source_urls_resolve(
                [LIVE, DEAD], probe=_fake({LIVE: Verdict.UNVERIFIED, DEAD: Verdict.DEAD})
            )

    def test_a_live_url_passes(self):
        results = assert_source_urls_resolve([LIVE], probe=_fake({}))
        self.assertEqual(results[0].verdict, Verdict.OK)

    def test_urls_are_deduplicated_and_probed_once(self):
        calls = []

        def counting(url):
            calls.append(url)
            return Reachability(url, Verdict.OK, 200, "ok")

        check_source_urls([LIVE, LIVE, " " + LIVE + " ", None, ""], probe=counting)
        self.assertEqual(calls, [LIVE], "one distinct url must mean one probe")

    def test_a_non_http_value_is_dead_not_unverified(self):
        """It can never resolve, so calling it 'unverified' would invite a retry loop."""
        self.assertEqual(probe_url("not-a-url").verdict, Verdict.DEAD)

    def test_403_and_405_do_not_count_as_dead(self):
        """Only 404/410 prove absence. A 403 is a bot block and a 429 is rate limiting —
        treating either as DEAD would reject the official sources this protects."""
        from backend.app.services.source_url_reachability import _DEAD_STATUSES
        self.assertEqual(set(_DEAD_STATUSES), {404, 410})


class PersistRefusesADeadCitation(unittest.TestCase):
    """THE REGRESSION TEST. Fails against the code before this change — that path had no
    check of any kind, so a 404 citation was written without complaint."""

    def test_persist_corridor_case_rejects_an_unreachable_source_url(self):
        rows = cp.RceRows()
        rows.rule_versions.append({"rule_version_id": "rv1", "source_url": DEAD})

        with mock.patch.object(cp, "build_rce_rows", return_value=rows), \
             mock.patch.object(cp, "db") as fake_db:
            with self.assertRaises(UnreachableSourceURL):
                cp.persist_corridor_case(
                    corridor=mock.Mock(corridor_id="ZZ_ZZ"),
                    target_arrival_date=__import__("datetime").date(2026, 1, 1),
                    source_url_probe=_fake({DEAD: Verdict.DEAD}),
                )
            fake_db.engine.begin.assert_not_called()

    def test_the_check_runs_BEFORE_the_transaction_opens(self):
        """Not a style point. Probing inside `db.engine.begin()` would hold a database
        transaction open across a network call to a third-party government site."""
        rows = cp.RceRows()
        rows.rule_versions.append({"rule_version_id": "rv1", "source_url": DEAD})
        order = []

        def probe(url):
            order.append("probe")
            return Reachability(url, Verdict.DEAD, 404, "fake")

        with mock.patch.object(cp, "build_rce_rows", return_value=rows), \
             mock.patch.object(cp, "db") as fake_db:
            fake_db.engine.begin.side_effect = lambda: order.append("begin")
            with self.assertRaises(UnreachableSourceURL):
                cp.persist_corridor_case(
                    corridor=mock.Mock(corridor_id="ZZ_ZZ"),
                    target_arrival_date=__import__("datetime").date(2026, 1, 1),
                    source_url_probe=probe,
                )
        self.assertEqual(order, ["probe"], "the transaction must never open")


if __name__ == "__main__":
    unittest.main()
