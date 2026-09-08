"""
[P5-9 H3] Central logging filter that masks the 5 PII patterns out of
every log record before it's emitted.

Per the security review (`docs/security/P5-9_security_review_2026-05-22.md`),
per-callsite masking is brittle — any new `log.info(f"... {email} ...")`
re-introduces the leak. Attaching a `logging.Filter` to the root logger
guarantees every record passes through `mask_pii` on its rendered message.

Contract
────────
- Mutates `record.msg` to the fully-rendered + masked string and clears
  `record.args` on the record we hand to the formatter.
- Does **NOT** mutate the original `record.args` tuple/dict in-place —
  structured-logging consumers (Sentry, Datadog) that read args directly
  off the record before the filter chain runs still see field-level
  data. The compromise is acceptable per the audit's note about
  LangSmith/Helicone traces: we mask the human-readable line, not the
  structured payload.
- Never raises. If formatting fails for any reason the original record
  passes through unchanged.
"""
from __future__ import annotations

import logging

from .pii_masker import mask_pii


class PiiLogFilter(logging.Filter):
    """Scrub PII from every log record's rendered message."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            rendered = record.getMessage()
        except Exception:
            return True

        masked = mask_pii(rendered)
        if masked != rendered:
            record.msg = masked
            record.args = None
        return True


def install_pii_log_filter() -> PiiLogFilter:
    """Attach a `PiiLogFilter` to the root logger and to every existing
    handler, so records are scrubbed regardless of which handler emits
    them. Idempotent — calling twice attaches only one instance.

    Returns the installed filter so callers can detach it in tests.
    """
    root = logging.getLogger()
    for existing in root.filters:
        if isinstance(existing, PiiLogFilter):
            return existing

    flt = PiiLogFilter()
    root.addFilter(flt)
    for handler in root.handlers:
        if not any(isinstance(f, PiiLogFilter) for f in handler.filters):
            handler.addFilter(flt)
    return flt
