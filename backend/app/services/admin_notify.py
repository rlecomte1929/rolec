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

    return _send_to_admins(recipients, subject, plain, context="admin_gap_request")


def notify_admins_supplier_submission(
    *,
    name: str,
    service_category: str,
    city: Optional[str] = None,
    country: Optional[str] = None,
    company_id: Optional[str] = None,
) -> Dict[str, str]:
    """Email admins that HR proposed a preferred supplier awaiting review
    (AIQ-1602 Seg 4). Fail-soft; content is non-PII (vendor business data)."""
    recipients = resolve_admin_emails()
    if not recipients:
        return {}
    where = ", ".join([p for p in (city, country) if p]) or "—"
    subject = f"[ReloPass] HR proposed a supplier: {name} ({service_category})"
    plain = (
        "An HR user has proposed a preferred supplier for the ReloPass catalog. "
        "It is pending your review.\n\n"
        f"Supplier:  {name}\n"
        f"Category:  {service_category}\n"
        f"Coverage:  {where}\n"
        f"Company id: {company_id or '—'}\n\n"
        "Review it in Admin → Supplier submissions, then approve it into the "
        "registry or reject it."
    )
    return _send_to_admins(recipients, subject, plain, context="admin_supplier_submission")


def notify_admins_new_lead(
    *,
    company_domain: Optional[str],
    source: Optional[str] = None,
    utm_campaign: Optional[str] = None,
    matched_prospect: bool = False,
) -> Dict[str, str]:
    """Email admins that a lead arrived from the public marketing forms (AIQ-1783).

    ADS-3 requires captured leads to reach a *monitored* destination within the hour.
    Before this, they only landed in the ``leads`` table behind Admin → Leads, which
    nobody is paged about — a page someone must remember to open is not monitoring.

    Deliberately NON-PII, per this module's contract: the company domain (business
    data), the campaign, and whether the domain matches an existing outbound prospect.
    The lead's name, email address and free-text message stay in the admin UI — the
    email carries the signal, not the record. Fail-soft: never breaks lead capture.
    """
    recipients = resolve_admin_emails()
    if not recipients:
        return {}

    domain = (company_domain or "").strip() or "—"
    match_label = "YES — already in the outbound pipeline" if matched_prospect else "no"
    subject = f"[ReloPass] New lead: {domain}"
    plain = (
        "A lead was captured from the public marketing site.\n\n"
        f"Company domain: {domain}\n"
        f"Source:         {source or '—'}\n"
        f"Campaign:       {utm_campaign or '—'}\n"
        f"Known prospect: {match_label}\n\n"
        "Contact details are in Admin → Leads. This email deliberately carries no "
        "personal data."
    )
    return _send_to_admins(recipients, subject, plain, context="admin_new_lead")


def _send_to_admins(
    recipients: List[str], subject: str, plain: str, *, context: str
) -> Dict[str, str]:
    results: Dict[str, str] = {}
    for to in recipients:
        try:
            res = _resend_send(to_email=to, subject=subject, plain=plain, context=context)
            results[to] = str(res.get("status", "error"))
        except Exception:  # noqa: BLE001 — delivery must never break the caller
            log.warning("admin_notify: %s email failed (suppressed) to=%s", context, to)
            results[to] = "error"
    return results
