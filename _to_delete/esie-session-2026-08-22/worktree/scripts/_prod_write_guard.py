"""Refuse to run write-heavy probe/seed scripts against PRODUCTION unless
explicitly opted in.

Root-cause mitigation for AIQ-913: the verify_* probe scripts default
``RELOPASS_API_BASE`` to ``https://api.relopass.com``, so running one with no
env set silently seeds **production** through the real register / create-company
/ create-person endpoints — throwaway ``@testco.com`` tenants, "Test company"
rows, etc. that then pollute the admin Companies list and Mobility center.

Usage — at the top of a write-performing script, right after resolving the base
URL::

    from _prod_write_guard import guard_prod_writes
    guard_prod_writes(API)

* Against a local / test API:  ``RELOPASS_API_BASE=http://localhost:8000``
* Against prod ON PURPOSE:     ``RELOPASS_ALLOW_PROD_WRITES=1``

This is intentionally script-only and reversible. The complete fix (a dedicated
non-prod test target, or an ``is_test`` tenant flag) is tracked in the AIQ-913
root-cause follow-up.
"""
from __future__ import annotations

import os
import sys
from urllib.parse import urlparse

_PROD_HOST_SUFFIXES = ("relopass.com",)


def is_prod_base(api_base: str) -> bool:
    """True when ``api_base`` points at a production relopass.com host."""
    host = (urlparse(api_base or "").hostname or "").lower()
    return any(host == s or host.endswith("." + s) for s in _PROD_HOST_SUFFIXES)


def guard_prod_writes(api_base: str) -> None:
    """Abort (exit 2) if the script targets prod without an explicit opt-in."""
    if not is_prod_base(api_base):
        return
    if os.environ.get("RELOPASS_ALLOW_PROD_WRITES") == "1":
        sys.stderr.write(
            f"[prod-write-guard] RELOPASS_ALLOW_PROD_WRITES=1 — proceeding against PROD ({api_base}).\n"
        )
        return
    sys.stderr.write(
        "\n[prod-write-guard] REFUSING to run: this script writes data and is targeting "
        f"PRODUCTION ({api_base}).\n"
        "  Production must not be used as a test target — it pollutes the admin\n"
        "  Companies list / Mobility center with throwaway tenants (AIQ-913).\n"
        "    • local/test API:   RELOPASS_API_BASE=http://localhost:8000\n"
        "    • prod ON PURPOSE:   RELOPASS_ALLOW_PROD_WRITES=1\n\n"
    )
    sys.exit(2)
