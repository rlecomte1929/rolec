"""Resolve a standing immigration-authority link for a destination country.

IDR-260820-28EC: the Relocation Assistant asked for a link to "the relevant
authorities website" *before* any question is asked. Product decision:

  The standing link names the destination country's **immigration** authority
  (not tax, civil registration, or labour). When several immigration entries
  exist, we take the first `type=immigration` row in `countries.key_authorities`
  — that array is curated and already ordered with the primary body first.

URLs are never invented. We only return an https URL already stored in
`public.countries.key_authorities` or, as a fallback, `form_templates.source_url`
for an immigration-related form category. Missing data → None (render nothing).
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

_ISO2 = re.compile(r"^[A-Z]{2}$")

# form_templates.category values used by the seeded immigration / permit catalog.
# Tax, health, banking, municipal registration are intentionally excluded.
_IMMIGRATION_FORM_CATEGORIES = frozenset(
    {
        "immigration",
        "visa",
        "work_permit",
        "work_visa",
        "residence",
        "residence_permit",
        "family_immigration",
    }
)


def normalize_country_code(raw: Optional[str]) -> Optional[str]:
    code = (raw or "").strip().upper()
    return code if _ISO2.fullmatch(code) else None


def _https_url(raw: Any) -> Optional[str]:
    url = (raw or "").strip() if isinstance(raw, str) else ""
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        return None
    return url


def pick_from_key_authorities(payload: Any) -> Optional[Dict[str, str]]:
    """First curated immigration authority with an https URL. Order is seed order."""
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return None
    if not isinstance(payload, list):
        return None
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("type") or "").strip().lower() != "immigration":
            continue
        url = _https_url(entry.get("url"))
        name = str(entry.get("name") or "").strip()
        if url:
            return {"name": name or url, "url": url, "source": "countries.key_authorities"}
    return None


def pick_from_form_templates(rows: Iterable[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    """Shortest stored https URL among immigration-category templates (homepage-like)."""
    candidates: List[Dict[str, str]] = []
    for row in rows:
        cat = str(row.get("category") or "").strip().lower()
        if cat not in _IMMIGRATION_FORM_CATEGORIES:
            continue
        url = _https_url(row.get("source_url"))
        if not url:
            continue
        name = str(row.get("authority_name") or row.get("authority_code") or "").strip()
        candidates.append({"name": name or url, "url": url, "source": "form_templates.source_url"})
    if not candidates:
        return None
    candidates.sort(key=lambda c: (len(c["url"]), c["url"]))
    return candidates[0]


def _qual(session: Session, name: str) -> str:
    dialect = session.get_bind().dialect.name if session.get_bind() is not None else "postgresql"
    return f"public.{name}" if dialect == "postgresql" else name


def lookup_destination_immigration_authority(
    session: Session, country_code: Optional[str]
) -> Optional[Dict[str, str]]:
    code = normalize_country_code(country_code)
    if not code:
        return None

    picked = _from_countries(session, code)
    if picked:
        return picked
    return _from_form_templates(session, code)


def _from_countries(session: Session, code: str) -> Optional[Dict[str, str]]:
    try:
        row = session.execute(
            text(f"SELECT key_authorities FROM {_qual(session, 'countries')} WHERE code = :c LIMIT 1"),
            {"c": code},
        ).fetchone()
    except SQLAlchemyError:
        log.debug("countries.key_authorities lookup skipped", exc_info=True)
        session.rollback()
        return None
    if not row:
        return None
    return pick_from_key_authorities(row[0])


def _from_form_templates(session: Session, code: str) -> Optional[Dict[str, str]]:
    try:
        rows = session.execute(
            text(
                f"SELECT category, authority_name, authority_code, source_url "
                f"FROM {_qual(session, 'form_templates')} WHERE country = :c"
            ),
            {"c": code},
        ).mappings().all()
    except SQLAlchemyError:
        log.debug("form_templates.source_url lookup skipped", exc_info=True)
        session.rollback()
        return None
    return pick_from_form_templates(list(rows))
