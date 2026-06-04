"""
[P3-02a] Tests for production-grade retry + exponential backoff in the HTTP fetcher.

Validates the scheduler's fetch resilience: transient server errors (5xx / 429)
are retried with exponential backoff; permanent errors (4xx) are not retried;
exhausted retries log a failure without crashing.
"""
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.crawler.fetchers import http_fetcher
from backend.crawler.fetchers.http_fetcher import fetch_page


def _mock_response(status_code: int, body: str = "<html><body>ok</body></html>",
                   content_type: str = "text/html"):
    """Build a stand-in for a requests Response (streaming interface)."""
    resp = MagicMock()
    resp.url = "https://example.com"
    resp.status_code = status_code
    resp.headers = {"Content-Type": content_type}
    resp.encoding = "utf-8"
    resp.iter_content = lambda chunk_size=8192: [body.encode("utf-8")]
    return resp


class TestRetryOnTransientErrors(unittest.TestCase):
    def test_retries_on_502_then_logs_failure_without_crashing(self):
        """A persistent 502 retries 3 times (4 attempts total) then returns failure."""
        with patch.object(http_fetcher.requests, "get",
                          return_value=_mock_response(502)) as mock_get, \
             patch.object(http_fetcher.time, "sleep") as mock_sleep:
            result = fetch_page("https://example.com", retry_count=3,
                                backoff_base_seconds=0.01)

        self.assertEqual(mock_get.call_count, 4)  # 1 initial + 3 retries
        self.assertEqual(mock_sleep.call_count, 3)  # sleeps between retries only
        self.assertFalse(result.success)
        self.assertIn("502", result.error or "")

    def test_default_retry_count_is_three(self):
        """Default config retries 3 times on a transient error."""
        with patch.object(http_fetcher.requests, "get",
                          return_value=_mock_response(503)), \
             patch.object(http_fetcher.time, "sleep") as mock_sleep:
            result = fetch_page("https://example.com", backoff_base_seconds=0.01)
        self.assertEqual(mock_sleep.call_count, 3)
        self.assertFalse(result.success)

    def test_exponential_backoff_schedule(self):
        """Backoff is exponential: base * 2**attempt → 1, 2, 4 seconds."""
        with patch.object(http_fetcher.requests, "get",
                          return_value=_mock_response(504)), \
             patch.object(http_fetcher.time, "sleep") as mock_sleep:
            fetch_page("https://example.com", retry_count=3, backoff_base_seconds=1.0)
        sleeps = [c.args[0] for c in mock_sleep.call_args_list]
        self.assertEqual(sleeps, [1.0, 2.0, 4.0])

    def test_succeeds_after_transient_502(self):
        """A 502 followed by a 200 succeeds on the retry."""
        responses = [_mock_response(502), _mock_response(200)]
        with patch.object(http_fetcher.requests, "get",
                          side_effect=responses) as mock_get, \
             patch.object(http_fetcher.time, "sleep"):
            result = fetch_page("https://example.com", retry_count=3,
                                backoff_base_seconds=0.01)
        self.assertEqual(mock_get.call_count, 2)
        self.assertTrue(result.success)
        self.assertEqual(result.http_status, 200)


class TestNoRetryOnPermanentErrors(unittest.TestCase):
    def test_404_is_not_retried(self):
        """A 404 is a permanent error — fetched once, no retry (dead-link is P3-02d)."""
        with patch.object(http_fetcher.requests, "get",
                          return_value=_mock_response(404)) as mock_get, \
             patch.object(http_fetcher.time, "sleep") as mock_sleep:
            result = fetch_page("https://example.com", retry_count=3,
                                backoff_base_seconds=0.01)
        self.assertEqual(mock_get.call_count, 1)
        self.assertEqual(mock_sleep.call_count, 0)
        self.assertFalse(result.success)


class TestRetriesOnNetworkErrors(unittest.TestCase):
    def test_timeout_is_retried_with_exponential_backoff(self):
        """Network timeouts remain retryable and use the same exponential schedule."""
        import requests as _requests
        with patch.object(http_fetcher.requests, "get",
                          side_effect=_requests.exceptions.Timeout()), \
             patch.object(http_fetcher.time, "sleep") as mock_sleep:
            result = fetch_page("https://example.com", retry_count=3,
                                backoff_base_seconds=1.0)
        sleeps = [c.args[0] for c in mock_sleep.call_args_list]
        self.assertEqual(sleeps, [1.0, 2.0, 4.0])
        self.assertFalse(result.success)


if __name__ == "__main__":
    unittest.main()
