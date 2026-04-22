"""
Timezone-aware time helpers.

Legacy code across the backend uses `datetime.utcnow()` (naive UTC) and stores
`.isoformat()` as string in the DB. That's dangerous once users span multiple
timezones — a naive datetime compared to a timezone-aware one raises, and a
string "2026-04-21T10:00:00" read back and compared to a tz-aware "now" in
Python fails silently or inconsistently.

New code should use the helpers here:

  from ._time import utcnow, utcnow_iso
  now = utcnow()                       # datetime with tzinfo=UTC
  iso = utcnow_iso()                   # "2026-04-21T10:00:00+00:00" — safe for Postgres timestamptz
  naive_iso = utcnow_iso_naive()       # "2026-04-21T10:00:00" — only for legacy string columns

The migration plan is incremental: every new call site uses these helpers;
existing utcnow() sites get migrated opportunistically. A ruff rule (DTZ003)
can be turned on once the existing backlog is cleared. Tracked in docs/INDEX.md.
"""
from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Timezone-aware current UTC datetime. Prefer over datetime.utcnow()."""
    return datetime.now(timezone.utc)


def utcnow_iso() -> str:
    """
    ISO-8601 with UTC offset, e.g. '2026-04-21T10:00:00.123456+00:00'.
    Safe for Postgres `timestamptz` columns.
    """
    return utcnow().isoformat()


def utcnow_iso_naive() -> str:
    """
    ISO-8601 without a tz offset, e.g. '2026-04-21T10:00:00.123456'.
    Matches the format of existing `datetime.utcnow().isoformat()` string
    columns (most of the legacy SQLite / text-column storage). Use this
    when writing into a column already populated with naive ISO strings
    so ordering / equality stays consistent with existing rows.
    """
    return utcnow().replace(tzinfo=None).isoformat()
