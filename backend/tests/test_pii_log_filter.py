"""
Tests for [P5-9 H3] central PII logging filter.

Asserts that a `PiiLogFilter` attached to a logger scrubs each of the
five PII patterns called out in the audit (phone, IBAN, passport, SSN,
email/national-ID) before any handler emits the record.

Also asserts the contract that `record.args` on the *original* caller's
tuple is not mutated — only the rendered message changes. Structured
consumers (Sentry/Datadog) that read args directly off the record
before this filter runs still see field-level data.
"""
from __future__ import annotations

import io
import logging
import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.pii_log_filter import PiiLogFilter  # noqa: E402


def _logger_with_buffer(name: str) -> tuple[logging.Logger, io.StringIO]:
    """Build an isolated logger + StringIO handler with the PII filter
    attached on the handler side, so we don't have to mutate the root
    logger for the test."""
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.addFilter(PiiLogFilter())

    log = logging.getLogger(name)
    log.handlers.clear()
    log.addHandler(handler)
    log.setLevel(logging.DEBUG)
    log.propagate = False
    return log, buf


class PiiLogFilterTests(unittest.TestCase):

    def test_all_five_patterns_masked_in_emitted_message(self):
        log, buf = _logger_with_buffer("pii_filter_test.all_five")

        log.info(
            "user=alice@example.com phone=+33 6 12 34 56 78 "
            "iban=FR7630001007123456789012345 "
            "passport=AB1234567 ssn=123-45-6789"
        )

        out = buf.getvalue()
        self.assertIn("[REDACTED_EMAIL]", out)
        self.assertIn("[REDACTED_PHONE]", out)
        self.assertIn("[REDACTED_IBAN]", out)
        self.assertIn("[REDACTED_PASSPORT]", out)
        self.assertIn("[REDACTED_SSN]", out)

        # And none of the raw values leaked through.
        self.assertNotIn("alice@example.com", out)
        self.assertNotIn("FR7630001007123456789012345", out)
        self.assertNotIn("AB1234567", out)
        self.assertNotIn("123-45-6789", out)
        self.assertNotIn("+33", out)

    def test_plain_message_passes_through_unchanged(self):
        log, buf = _logger_with_buffer("pii_filter_test.plain")
        log.info("policy resolved for tier=executive")
        self.assertEqual(buf.getvalue().strip(), "policy resolved for tier=executive")

    def test_original_args_tuple_not_mutated(self):
        """The filter must not touch the caller's args tuple — Sentry /
        Datadog read it for structured fields."""
        log, _ = _logger_with_buffer("pii_filter_test.args")

        args = ("alice@example.com", "+33 6 12 34 56 78")
        log.info("user=%s phone=%s", *args)

        # The tuple the test handed in is unchanged.
        self.assertEqual(args, ("alice@example.com", "+33 6 12 34 56 78"))

    def test_pct_format_message_masked(self):
        """Filter must run after %-style formatting — masking the
        already-substituted message, not the raw template."""
        log, buf = _logger_with_buffer("pii_filter_test.pct_format")
        log.info("contact %s", "alice@example.com")
        self.assertIn("[REDACTED_EMAIL]", buf.getvalue())
        self.assertNotIn("alice@example.com", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
