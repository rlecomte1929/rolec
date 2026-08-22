"""AIQ-2011 — a bot-block interstitial must never be stored as a parsed source document.

THE DEFECT THIS PINS (measured in prod 2026-08-19)

Six of fifteen `crawled_source_documents` rows were the interstitial at
`validate.perfdrive.com`, every one recorded `http_status 200`, `parse_status 'parsed'`,
`page_title 'Radware Captcha Page'`. `_crawl_source` only skips `write_document` when
`fetch_result.success` is False, and a challenge page returns HTTP 200 with a body that
parses — so it sailed through and the crawl run reported success.

These tests assert both directions. A test that only proves the interstitial is caught would
pass on a detector that rejects everything, so the "a real page still parses" case is
load-bearing, not decorative.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.crawler.fetchers.bot_block import (  # noqa: E402
    SMALL_BODY_BYTES,
    detect_bot_block,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "bot_block_interstitial.html"

# A plausible source page: comfortably over the size floor, no challenge vocabulary.
_REAL_PAGE = (
    "<!DOCTYPE html><html><head><title>Employment permits — fees</title></head><body>"
    + "<p>The processing fee for a Critical Skills Employment Permit is EUR 1,000.</p>"
    + ("<p>Guidance paragraph explaining the application procedure in detail.</p>" * 80)
    + "</body></html>"
)


class BotBlockDetectionTests(unittest.TestCase):
    def test_captured_interstitial_is_detected(self) -> None:
        """The real captured block page, redirected off-host, must be rejected."""
        reason = detect_bot_block(
            url="https://www.make-it-in-germany.com/en/living-in-germany",
            final_url="https://validate.perfdrive.com/?ssa=21a2e2c1-a17f-48ca",
            content=_FIXTURE.read_text(encoding="utf-8"),
            page_title="Radware Captcha Page",
        )
        self.assertIsNotNone(reason, "the captured interstitial must be detected")
        self.assertIn("title", reason)

    def test_a_real_source_page_still_passes(self) -> None:
        """Load-bearing: a detector that rejects everything would pass the test above."""
        self.assertIsNone(
            detect_bot_block(
                url="https://enterprise.gov.ie/en/employment-permits/fees/",
                final_url="https://enterprise.gov.ie/en/employment-permits/fees/",
                content=_REAL_PAGE,
                page_title="Employment permits — fees",
            )
        )

    def test_challenge_title_alone_is_enough(self) -> None:
        for title in ("Just a moment...", "Attention Required!", "Security check", "Access Denied"):
            with self.subTest(title=title):
                self.assertIsNotNone(
                    detect_bot_block(
                        url="https://example.gov/page", final_url="https://example.gov/page",
                        content="<html><body>short</body></html>", page_title=title,
                    )
                )

    def test_title_is_read_from_the_body_when_not_supplied(self) -> None:
        """The detector runs before parsing in the pipeline, so it must find its own title."""
        reason = detect_bot_block(
            url="https://example.gov/page",
            final_url="https://example.gov/page",
            content="<html><head><title>Just a moment...</title></head><body></body></html>",
        )
        self.assertIsNotNone(reason)

    def test_challenge_marker_needs_a_small_body(self) -> None:
        """A long legitimate page that merely mentions the word must NOT be rejected."""
        long_page_mentioning_it = (
            "<html><head><title>How we verify documents</title></head><body>"
            + "<p>Some sites use a captcha to deter automated queries.</p>"
            + ("<p>Substantive guidance content continues at length here.</p>" * 80)
            + "</body></html>"
        )
        self.assertGreater(len(long_page_mentioning_it.encode()), SMALL_BODY_BYTES)
        self.assertIsNone(
            detect_bot_block(
                url="https://example.gov/p", final_url="https://example.gov/p",
                content=long_page_mentioning_it, page_title="How we verify documents",
            )
        )
        # ...but the same marker in a tiny body is a challenge.
        self.assertIsNotNone(
            detect_bot_block(
                url="https://example.gov/p", final_url="https://example.gov/p",
                content="<html><body>captcha</body></html>", page_title="",
            )
        )

    def test_benign_redirects_are_not_blocks(self) -> None:
        """http->https, www stripping and path changes must not read as interception."""
        for url, final_url in (
            ("http://example.gov/p", "https://example.gov/p"),
            ("https://www.example.gov/p", "https://example.gov/p"),
            ("https://example.gov/p", "https://example.gov/p/index.html"),
        ):
            with self.subTest(final_url=final_url):
                self.assertIsNone(
                    detect_bot_block(
                        url=url, final_url=final_url,
                        content="<html><body>tiny</body></html>", page_title="Fees",
                    ),
                    "a same-host redirect must not be treated as a bot block",
                )

    def test_offhost_redirect_with_tiny_body_is_a_block(self) -> None:
        self.assertIsNotNone(
            detect_bot_block(
                url="https://example.gov/p",
                final_url="https://someinterceptor.example.net/challenge",
                content="<html><body>tiny</body></html>",
                page_title="",
            )
        )

    def test_offhost_redirect_with_a_full_page_is_not_a_block(self) -> None:
        """A genuine cross-domain move (agency rebrand) must survive."""
        self.assertIsNone(
            detect_bot_block(
                url="https://old-agency.gov/fees",
                final_url="https://new-agency.gov/fees",
                content=_REAL_PAGE,
                page_title="Employment permits — fees",
            )
        )

    def test_empty_and_malformed_input_does_not_crash(self) -> None:
        for kwargs in (
            {"url": "", "final_url": "", "content": ""},
            {"url": "not a url", "final_url": "also not", "content": ""},
        ):
            with self.subTest(kwargs=kwargs):
                detect_bot_block(**kwargs)  # must not raise


if __name__ == "__main__":
    unittest.main()


class CrawlPipelineBotBlockTests(unittest.TestCase):
    """The detector is only useful if `_crawl_source` actually refuses to write the row.

    `write_document` is mocked and asserted NOT called — the previous behaviour was that it
    WAS called with a CAPTCHA page, producing `parse_status='parsed'`. This is the assertion
    that fails against the pre-fix code.
    """

    def _run(self, *, final_url: str, content: str, title: str):
        from unittest import mock

        from backend.crawler import pipeline as pipe

        fetch_result = mock.Mock()
        fetch_result.success = True
        fetch_result.error = None
        fetch_result.http_status = 200
        fetch_result.final_url = final_url
        fetch_result.content = content

        source = mock.Mock()
        source.base_url = "https://www.make-it-in-germany.com/en/living-in-germany"
        source.source_name = "make_it_in_germany_living"
        source.country_code = "DE"
        source.city_name = None
        source.source_type = "gov"
        source.trust_tier = "tier-1-critical"

        config = mock.Mock()
        config.user_agent = "test"
        config.timeout_seconds = 5
        config.retry_count = 0
        config.retry_backoff_base_seconds = 0
        config.parse_only = False

        report = pipe.PipelineReport(run_id="run-1")

        # Everything downstream of write_document is mocked: this suite is about whether the
        # document is written at all, not about chunking or extraction behaviour.
        with mock.patch.object(pipe, "fetch_page", return_value=fetch_result), \
             mock.patch.object(pipe, "write_document") as write_doc, \
             mock.patch.object(pipe, "chunk_document", return_value=[]), \
             mock.patch.object(pipe, "parse_html") as parse_html:
            parse_html.return_value = mock.Mock(page_title=title, parse_error=None)
            pipe._crawl_source(source, config, "run-1", report)
        return report, write_doc

    def test_blocked_fetch_never_writes_a_document(self) -> None:
        report, write_doc = self._run(
            final_url="https://validate.perfdrive.com/?ssa=21a2e2c1",
            content=_FIXTURE.read_text(encoding="utf-8"),
            title="Radware Captcha Page",
        )
        write_doc.assert_not_called()
        self.assertEqual(report.documents_fetched, 0, "a block must not count as a fetch")
        self.assertEqual(report.documents_failed, 1)
        self.assertTrue(
            any("bot-block detected" in e for e in report.errors),
            f"the block must surface in crawl-run errors; got {report.errors}",
        )

    def test_a_genuine_page_is_still_written(self) -> None:
        """Load-bearing counterpart: the fix must not stop the crawler working."""
        report, write_doc = self._run(
            final_url="https://enterprise.gov.ie/en/employment-permits/fees/",
            content=_REAL_PAGE,
            title="Employment permits — fees",
        )
        write_doc.assert_called_once()
        self.assertEqual(report.documents_fetched, 1)
        self.assertEqual(report.documents_failed, 0)
        self.assertEqual(report.errors, [])
