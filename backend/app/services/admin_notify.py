"""
Admin notification helper (AIQ-1602).

Sends a fail-soft Resend email to platform admins when HR takes an action that
needs admin attention. Currently used for catalog **gap requests** — when HR
asks the ReloPass team to source service providers for a destination/category
that has none.

Recipients come from the ``admin_allowlist`` table (the authority for who is an
admin — see auth_deps.is_admin_allowlisted). Everything here is best-effort: a
recipient-lookup or delivery failure must NEVER break the caller's write. The
in-app ``/api/notifications`` channel is dead in prod (uuid vs legacy-text id),
so Resend email is the only reliable admin push channel.

Content is deliberately non-PII: city/country/category/company id only — never
employee personal data.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from sqlalchemy import text

from ...database import db
from .assignment_invite_email import _resend_send

log = logging.getLogger(__name__)

# Matches scrape_safety.ALL_CATEGORIES_SENTINEL — a request that spans every
# category rather than a single one.
_ALL_CATEGORIES_SENTINEL = "_all_categories"


def resolve_admin_emails() -> List[str]:
    """Enabled ``admin_allowlist`` emails, de-duplicated. Best-effort — returns
    ``[]`` on any error so a lookup failure never breaks the caller."""
    try:
        with db.engine.connect() as conn:
            rows = (
                conn.execute(
                    text(
                        "SELECT email FROM admin_allowlist "
                        "WHERE enabled = 1 AND email IS NOT NULL"
                    )
                )
                .mappings()
                .all()
            )
        seen: set[str] = set()
        out: List[str] = []
        for r in rows:
            email = (r.get("email") or "").strip().lower()
            if email and email not in seen:
                seen.add(email)
                out.append(email)
        return out
    except Exception:  # noqa: BLE001 — recipient lookup must never break the caller
        log.warning("admin_notify: admin recipient lookup failed (suppressed)")
        return []


def _category_label(category: Optional[str]) -> str:
    if not category or category == _ALL_CATEGORIES_SENTINEL:
        return "all categories"
    return category


def notify_admins_gap_request(
    *,
    city: str,
    country: str,
    category: Optional[str],
    company_id: Optional[str] = None,
    requested_by: Optional[str] = None,
) -> Dict[str, str]:
    """Email admins that HR opened a catalog gap request. Fail-soft; returns a
    ``{email: status}`` map (empty when there are no recipients)."""
    recipients = resolve_admin_emails()
    if not recipients:
        return {}

    cat_label = _category_label(category)
    subject = f"[ReloPass] HR requested providers: {cat_label} in {city}, {country}"
    plain = (
        "An HR user has asked the ReloPass team to source service providers "
        "for a destination that currently has none.\n\n"
        f"Category:    {cat_label}\n"
        f"Destination: {city}, {country}\n"
        f"Company id:  {company_id or '—'}\n\n"
        "Review it in the admin catalog queue → Destination requests, then "
        "allowlist the destination or source vendors as appropriate."
    )

    results: Dict[str, str] = {}
    for to in recipients:
        try:
            res = _resend_send(
                to_email=to,
                subject=subject,
                plain=plain,
                context="admin_gap_request",
            )
            results[to] = str(res.get("status", "error"))
        except Exception:  # noqa: BLE001 — delivery must never break the caller
            log.warning("admin_notify: gap-request email failed (suppressed) to=%s", to)
            results[to] = "error"
    return results
