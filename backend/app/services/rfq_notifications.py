"""AIQ-2370 — in-app + outbox notifications for the RFQ loop.

Nobody was told when an RFQ went out, a quote arrived, quotes were ready for HR,
or HR validated a quote. These helpers wrap create_notification_with_preferences
and never raise to the caller.

Email egress is unchanged: this only writes notifications (+ outbox rows when
the type is email-default-on / the user opted in). Actual send still goes through
the existing outbox cron and RELOPASS_OUTBOX_ALLOWED_DOMAINS.
"""
from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

log = logging.getLogger(__name__)

TYPE_RFQ_SENT = "rfq.sent"
TYPE_QUOTE_RECEIVED = "rfq.quote_received"
TYPE_QUOTES_READY = "rfq.quotes_ready"
TYPE_QUOTE_VALIDATED = "rfq.quote_validated"

# Keep in sync with backend/db/support.py _EMAIL_DEFAULT_ON
RFQ_NOTIFICATION_TYPES = frozenset({
    TYPE_RFQ_SENT,
    TYPE_QUOTE_RECEIVED,
    TYPE_QUOTES_READY,
    TYPE_QUOTE_VALIDATED,
})

_PACK_TEMPLATE_IDS = {
    TYPE_RFQ_SENT: "employee_rfq_sent",
    TYPE_QUOTE_RECEIVED: "employee_quote_received",
    TYPE_QUOTES_READY: "hr_quotes_ready",
    TYPE_QUOTE_VALIDATED: "employee_quote_validated",
}

_TOKEN_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def _main_db():
    from ...database import db  # type: ignore[import]

    return db


def _engine():
    return _main_db().engine


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


@lru_cache(maxsize=1)
def _load_pack() -> Dict[str, Any]:
    path = _repo_root() / "docs" / "rfq-email" / "rfq_email_pack.json"
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _template(template_id: str) -> Dict[str, Any]:
    for item in _load_pack().get("templates") or []:
        if item.get("id") == template_id:
            return item
    return {}


def _fill(text: str, variables: Dict[str, Any], fallbacks: Optional[Dict[str, Any]] = None) -> str:
    fb = fallbacks or {}

    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in variables and variables[key] not in (None, ""):
            return str(variables[key])
        if key in fb and fb[key] not in (None, ""):
            return str(fb[key])
        return ""

    return _TOKEN_RE.sub(repl, text or "")


def _copy_for(type_: str, variables: Dict[str, Any]) -> Tuple[str, str, str]:
    """Title/body/html from the email pack so in-app and outbox stay identical."""
    try:
        from .rfq_email_templates import render
        rendered = render(_PACK_TEMPLATE_IDS[type_], variables)
        return rendered["subject"], rendered["text"], rendered["html"]
    except Exception:
        tpl = _template(_PACK_TEMPLATE_IDS[type_])
        fallbacks = tpl.get("fallbacks") or {}
        title = _fill(str(tpl.get("subject") or type_), variables, fallbacks)
        body = _fill(str(tpl.get("preheader") or tpl.get("body_text") or ""), variables, fallbacks)
        return title, body, ""


def _first_name(user: Optional[Dict[str, Any]]) -> str:
    if not user:
        return ""
    for key in ("first_name", "given_name"):
        val = (user.get(key) or "").strip()
        if val:
            return val
    full = (user.get("full_name") or user.get("name") or "").strip()
    if full:
        return full.split()[0]
    email = (user.get("email") or "").strip()
    if "@" in email:
        return email.split("@", 1)[0]
    return ""


def _full_name(user: Optional[Dict[str, Any]]) -> str:
    if not user:
        return ""
    return (user.get("full_name") or user.get("name") or _first_name(user) or "").strip()


def _format_not_contacted(not_contacted: List[Any]) -> str:
    if not not_contacted:
        return "None"
    parts: List[str] = []
    for row in not_contacted:
        if isinstance(row, dict):
            name = row.get("supplier") or row.get("supplier_name") or "A supplier"
            reason = row.get("reason") or ""
            parts.append(f"{name}: {reason}" if reason else str(name))
        else:
            parts.append(str(row))
    return "; ".join(parts)


def _assignment_for_rfq(rfq: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
    case_id = str(rfq.get("case_id") or "").strip() or None
    assignment = None
    if case_id:
        try:
            assignment = _main_db().get_assignment_by_case_id(case_id)
        except Exception:
            log.warning("rfq_notifications: assignment lookup failed case_id=%s", case_id, exc_info=True)
            assignment = None
    employee_id = (assignment or {}).get("employee_user_id") if assignment else None
    hr_id = (assignment or {}).get("hr_user_id") if assignment else None
    assignment_id = str((assignment or {}).get("id") or "") or None
    return assignment, (str(employee_id) if employee_id else None), (str(hr_id) if hr_id else None)


def _notify(
    *,
    user_id: Optional[str],
    type_: str,
    title: str,
    body: str,
    case_id: Optional[str],
    assignment_id: Optional[str],
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    if not user_id:
        return
    try:
        _main_db().create_notification_with_preferences(
            user_id=user_id,
            type_=type_,
            title=title,
            body=body,
            assignment_id=assignment_id,
            case_id=case_id,
            metadata=metadata or {},
        )
    except Exception:
        log.warning(
            "rfq_notifications: create_notification_with_preferences failed user=%s type=%s",
            user_id, type_, exc_info=True,
        )


def _load_rfq(rfq_id: str) -> Optional[Dict[str, Any]]:
    try:
        return _main_db().get_rfq(rfq_id)
    except Exception:
        log.warning("rfq_notifications: get_rfq failed rfq=%s", rfq_id, exc_info=True)
        return None


def _quotes_ready_already_sent(rfq_id: str) -> bool:
    try:
        with _engine().connect() as conn:
            row = conn.execute(
                text(
                    "SELECT 1 FROM notifications WHERE type = :t "
                    "AND CAST(metadata AS TEXT) LIKE :m LIMIT 1"
                ),
                {"t": TYPE_QUOTES_READY, "m": f'%"rfq_id": "{rfq_id}"%'},
            ).first()
        return row is not None
    except Exception:
        log.warning("rfq_notifications: quotes_ready idempotency lookup failed rfq=%s", rfq_id, exc_info=True)
        return False


def _all_recipients_replied(rfq: Dict[str, Any]) -> bool:
    recipients = rfq.get("recipients") or []
    if not recipients:
        return False
    for rec in recipients:
        if rec.get("quote_submitted_at"):
            continue
        status = str(rec.get("status") or "").lower()
        if status != "replied":
            return False
    return True


def _supplier_name(rfq: Dict[str, Any], vendor_id: Optional[str]) -> str:
    if not vendor_id:
        return "A supplier"
    for rec in rfq.get("recipients") or []:
        if str(rec.get("vendor_id")) == str(vendor_id):
            name = rec.get("supplier_name") or rec.get("vendor_name") or rec.get("invited_email")
            if name:
                return str(name)
    try:
        with _engine().connect() as conn:
            row = conn.execute(
                text(
                    "SELECT COALESCE(s.name, v.name) AS name "
                    "FROM vendors v LEFT JOIN suppliers s ON CAST(s.id AS TEXT) = CAST(v.id AS TEXT) "
                    "WHERE CAST(v.id AS TEXT) = :vid LIMIT 1"
                ),
                {"vid": str(vendor_id)},
            ).mappings().first()
        if row and row.get("name"):
            return str(row["name"])
    except Exception:
        pass
    return "A supplier"


def _service_labels(rfq: Dict[str, Any]) -> str:
    keys = [str(i.get("service_key") or "") for i in (rfq.get("items") or []) if i.get("service_key")]
    return ", ".join(k for k in keys if k) or "relocation services"


def notify_rfq_sent(
    rfq_id: str,
    contacted: Optional[List[str]] = None,
    not_contacted: Optional[List[Any]] = None,
) -> None:
    """Employee: your RFQ was dispatched. Best-effort."""
    try:
        rfq = _load_rfq(rfq_id)
        if not rfq:
            return
        assignment, employee_id, _hr_id = _assignment_for_rfq(rfq)
        employee = _main_db().get_user_by_id(employee_id) if employee_id else None
        contacted_names = [str(n) for n in (contacted or []) if n]
        variables = {
            "rfq_ref": rfq.get("rfq_ref") or rfq_id,
            "employee_first_name": _first_name(employee),
            "service_labels": _service_labels(rfq),
            "recipients_count": str(len(rfq.get("recipients") or [])),
            "contacted_supplier_names": ", ".join(contacted_names) or "No suppliers were successfully contacted.",
            "not_contacted": _format_not_contacted(not_contacted or []),
            "respond_by": "",
            "employee_rfq_url": "",
            "support_email": "support@relopass.com",
        }
        title, body, html_body = _copy_for(TYPE_RFQ_SENT, variables)
        _notify(
            user_id=employee_id,
            type_=TYPE_RFQ_SENT,
            title=title,
            body=body,
            case_id=str(rfq.get("case_id") or "") or None,
            assignment_id=str((assignment or {}).get("id") or "") or None,
            metadata={
                "rfq_id": rfq_id,
                "contacted": contacted_names,
                "not_contacted": not_contacted or [],
                "html_body": html_body,
            },
        )
    except Exception:
        log.warning("rfq_notifications: notify_rfq_sent failed rfq=%s", rfq_id, exc_info=True)


def notify_quote_received(rfq_id: str, quote: Optional[Dict[str, Any]] = None) -> None:
    """Employee + HR: a supplier submitted a quote. Then maybe quotes-ready."""
    try:
        rfq = _load_rfq(rfq_id)
        if not rfq:
            return
        quote = quote or {}
        assignment, employee_id, hr_id = _assignment_for_rfq(rfq)
        employee = _main_db().get_user_by_id(employee_id) if employee_id else None
        quotes = []
        try:
            quotes = _main_db().list_quotes_for_rfq(rfq_id) or []
        except Exception:
            log.warning("rfq_notifications: list_quotes_for_rfq failed rfq=%s", rfq_id, exc_info=True)
        recipients_count = len(rfq.get("recipients") or [])
        quotes_count = len(quotes) or 1
        supplier = _supplier_name(rfq, quote.get("vendor_id"))
        variables = {
            "rfq_ref": rfq.get("rfq_ref") or rfq_id,
            "employee_first_name": _first_name(employee),
            "supplier_name": supplier,
            "quote_total": quote.get("total_amount") if quote.get("total_amount") is not None else "",
            "quote_currency": quote.get("currency") or "",
            "quote_valid_until": quote.get("valid_until") or "",
            "quotes_received_count": str(quotes_count),
            "recipients_count": str(recipients_count),
            "employee_quotes_url": "",
            "support_email": "support@relopass.com",
        }
        title, body, html_body = _copy_for(TYPE_QUOTE_RECEIVED, variables)
        meta = {
            "rfq_id": rfq_id,
            "quote_id": quote.get("id"),
            "vendor_id": quote.get("vendor_id"),
            "html_body": html_body,
        }
        case_id = str(rfq.get("case_id") or "") or None
        assignment_id = str((assignment or {}).get("id") or "") or None
        _notify(
            user_id=employee_id,
            type_=TYPE_QUOTE_RECEIVED,
            title=title,
            body=body,
            case_id=case_id,
            assignment_id=assignment_id,
            metadata=meta,
        )
        hr_title, hr_body = title, body
        _notify(
            user_id=hr_id,
            type_=TYPE_QUOTE_RECEIVED,
            title=hr_title,
            body=hr_body,
            case_id=case_id,
            assignment_id=assignment_id,
            metadata=meta,
        )
        if _all_recipients_replied(rfq):
            notify_quotes_ready(rfq_id)
    except Exception:
        log.warning("rfq_notifications: notify_quote_received failed rfq=%s", rfq_id, exc_info=True)


def notify_quotes_ready(rfq_id: str) -> None:
    """HR: quotes are ready to validate. Once per RFQ."""
    try:
        if _quotes_ready_already_sent(rfq_id):
            return
        rfq = _load_rfq(rfq_id)
        if not rfq:
            return
        assignment, employee_id, hr_id = _assignment_for_rfq(rfq)
        if not hr_id:
            return
        employee = _main_db().get_user_by_id(employee_id) if employee_id else None
        hr = _main_db().get_user_by_id(hr_id) if hr_id else None
        quotes = []
        try:
            quotes = _main_db().list_quotes_for_rfq(rfq_id) or []
        except Exception:
            pass
        if not quotes and not rfq.get("preferred_quote_id"):
            # Pack: do not send when zero quotes and the employee has not proposed.
            if not _all_recipients_replied(rfq):
                return
        variables = {
            "rfq_ref": rfq.get("rfq_ref") or rfq_id,
            "hr_first_name": _first_name(hr),
            "employee_full_name": _full_name(employee) or "the employee",
            "employee_first_name": _first_name(employee) or "the employee",
            "quotes_received_count": str(len(quotes)),
            "recipients_count": str(len(rfq.get("recipients") or [])),
            "hr_rfq_url": "",
            "support_email": "support@relopass.com",
        }
        title, body, html_body = _copy_for(TYPE_QUOTES_READY, variables)
        _notify(
            user_id=hr_id,
            type_=TYPE_QUOTES_READY,
            title=title,
            body=body,
            case_id=str(rfq.get("case_id") or "") or None,
            assignment_id=str((assignment or {}).get("id") or "") or None,
            metadata={"rfq_id": rfq_id, "html_body": html_body},
        )
    except Exception:
        log.warning("rfq_notifications: notify_quotes_ready failed rfq=%s", rfq_id, exc_info=True)


def notify_quote_validated(rfq_id: str, quote_id: Optional[str] = None) -> None:
    """Employee: HR validated a quote."""
    try:
        rfq = _load_rfq(rfq_id)
        if not rfq:
            return
        assignment, employee_id, _hr_id = _assignment_for_rfq(rfq)
        employee = _main_db().get_user_by_id(employee_id) if employee_id else None
        quote: Dict[str, Any] = {}
        if quote_id:
            try:
                for q in _main_db().list_quotes_for_rfq(rfq_id) or []:
                    if str(q.get("id")) == str(quote_id):
                        quote = q
                        break
            except Exception:
                pass
        variables = {
            "rfq_ref": rfq.get("rfq_ref") or rfq_id,
            "employee_first_name": _first_name(employee),
            "validated_supplier_name": _supplier_name(rfq, quote.get("vendor_id")),
            "quote_total": quote.get("total_amount") if quote.get("total_amount") is not None else "",
            "quote_currency": quote.get("currency") or "",
            "employee_quotes_url": "",
            "support_email": "support@relopass.com",
        }
        title, body, html_body = _copy_for(TYPE_QUOTE_VALIDATED, variables)
        _notify(
            user_id=employee_id,
            type_=TYPE_QUOTE_VALIDATED,
            title=title,
            body=body,
            case_id=str(rfq.get("case_id") or "") or None,
            assignment_id=str((assignment or {}).get("id") or "") or None,
            metadata={"rfq_id": rfq_id, "quote_id": quote_id, "html_body": html_body},
        )
    except Exception:
        log.warning("rfq_notifications: notify_quote_validated failed rfq=%s", rfq_id, exc_info=True)
