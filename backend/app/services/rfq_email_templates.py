"""AIQ-2371 — RFQ email pack loader and HTML-escaping renderer.

Templates live in backend/seed_data/rfq_email_pack.json (copy of docs/rfq-email/).
Every scalar is html.escape'd. Supplier-audience templates drop employee/company/HR
identity even if the caller passed it.
"""
from __future__ import annotations

import html
import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

log = logging.getLogger(__name__)

ALLOWED_VARIABLES = frozenset({
    "rfq_ref", "supplier_name", "company_name", "employee_first_name", "employee_full_name",
    "hr_first_name", "hr_full_name", "service_labels", "brief_rows", "move_from", "move_to",
    "target_move_date", "respond_by", "link_expires_days", "magic_link", "employee_rfq_url",
    "hr_rfq_url", "employee_quotes_url", "quote_total", "quote_currency", "quote_valid_until",
    "quote_lines", "quotes_received_count", "recipients_count", "contacted_supplier_names",
    "not_contacted", "reminder_days_left", "validated_supplier_name", "validation_reason",
    "support_email",
})

_SUPPLIER_STRIP = frozenset({
    "employee_first_name", "employee_full_name", "company_name",
    "hr_first_name", "hr_full_name",
})

_TOKEN_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")
_PACK_PATH = Path(__file__).resolve().parents[2] / "seed_data" / "rfq_email_pack.json"

_ROW_TR = (
    '<tr>'
    '<td style="padding:4px 12px 4px 0;color:#64748b;white-space:nowrap">{label}</td>'
    '<td style="padding:4px 0;color:#0b2b43;font-weight:600">{value}</td>'
    '</tr>'
)


class PackError(RuntimeError):
    """Raised when the pack is missing or uses an unknown variable."""


def load_pack() -> Dict[str, Any]:
    if not _PACK_PATH.is_file():
        raise PackError(f"RFQ email pack missing: {_PACK_PATH}")
    with _PACK_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def _pack() -> Dict[str, Any]:
    pack = load_pack()
    unknown: List[str] = []
    for tpl in pack.get("templates") or []:
        for var in tpl.get("variables_used") or []:
            if var not in ALLOWED_VARIABLES:
                unknown.append(f"{tpl.get('id')}:{var}")
    if unknown:
        raise PackError("variables_used not in allowed list: " + ", ".join(unknown))
    return pack


def _assert_pack_on_import() -> None:
    try:
        _pack()
    except Exception as exc:  # noqa: BLE001 — fail loudly at boot if the pack is corrupt
        log.error("rfq_email_templates: pack check failed: %s", exc)
        raise


_assert_pack_on_import()


def _templates_by_id() -> Dict[str, Dict[str, Any]]:
    return {t["id"]: t for t in _pack().get("templates") or [] if t.get("id")}


def _escape_scalar(value: Any) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def _brief_rows_table(rows: Any) -> str:
    items = rows if isinstance(rows, list) else []
    if not items:
        return ""
    parts = []
    for r in items:
        if isinstance(r, dict):
            label = _escape_scalar(r.get("label") or "")
            value = _escape_scalar(r.get("value") or r.get("notes") or "")
        else:
            label, value = "", _escape_scalar(r)
        parts.append(_ROW_TR.format(label=label, value=value))
    return f'<table style="border-collapse:collapse;margin:16px 0;font-size:14px">{"".join(parts)}</table>'


def _quote_lines_table(lines: Any) -> str:
    items = lines if isinstance(lines, list) else []
    if not items:
        return ""
    parts = []
    for ln in items:
        if isinstance(ln, dict):
            label = _escape_scalar(ln.get("label") or "")
            amount = _escape_scalar(ln.get("amount") if ln.get("amount") is not None else "")
            value = f"{amount}".strip()
        else:
            label, value = "", _escape_scalar(ln)
        parts.append(_ROW_TR.format(label=label, value=value))
    return (
        '<h2 style="margin:16px 0 10px 0;font-size:15px;color:#0b2b43;">Itemised lines</h2>'
        f'<table style="border-collapse:collapse;margin:0 0 16px 0;font-size:14px">{"".join(parts)}</table>'
    )


def _not_contacted_table(rows: Any) -> str:
    if isinstance(rows, str):
        if not rows.strip():
            return _escape_scalar("None")
        return f"<p>{_escape_scalar(rows)}</p>"
    items = rows if isinstance(rows, list) else []
    if not items:
        return _escape_scalar("None")
    parts = []
    for r in items:
        if isinstance(r, dict):
            label = _escape_scalar(r.get("supplier") or r.get("supplier_name") or "A supplier")
            value = _escape_scalar(r.get("reason") or "")
        else:
            label, value = _escape_scalar(r), ""
        parts.append(_ROW_TR.format(label=label, value=value))
    return f'<table style="border-collapse:collapse;margin:8px 0;font-size:14px">{"".join(parts)}</table>'


def _text_from_rows(rows: Any, empty: str = "") -> str:
    if isinstance(rows, str):
        return rows
    items = rows if isinstance(rows, list) else []
    if not items:
        return empty
    lines = []
    for r in items:
        if isinstance(r, dict):
            label = r.get("label") or r.get("supplier") or r.get("supplier_name") or ""
            value = r.get("value") if "value" in r else (r.get("reason") if "reason" in r else r.get("amount"))
            if value is None:
                value = ""
            lines.append(f"{label}: {value}".strip(": ").strip())
        else:
            lines.append(str(r))
    return "\n".join(lines)


def _fill(template: str, mapping: Mapping[str, str]) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        return mapping.get(key, "")

    return _TOKEN_RE.sub(repl, template or "")


def render(template_id: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """Return {subject, text, html} with every scalar escaped. Never raises on missing vars."""
    tpl = _templates_by_id().get(template_id)
    if not tpl:
        raise PackError(f"unknown template_id: {template_id}")
    raw = dict(variables or {})
    if tpl.get("audience") == "supplier":
        for key in list(raw.keys()):
            if key in _SUPPLIER_STRIP:
                raw.pop(key, None)

    fallbacks = dict(tpl.get("fallbacks") or {})
    scalars: Dict[str, str] = {}
    for key in ALLOWED_VARIABLES:
        if key in ("brief_rows", "quote_lines", "not_contacted"):
            continue
        val = raw.get(key)
        if val in (None, ""):
            val = fallbacks.get(key, "")
        scalars[key] = _escape_scalar(val)

    brief_rows = raw.get("brief_rows")
    quote_lines = raw.get("quote_lines")
    not_contacted = raw.get("not_contacted")

    scalars["brief_rows"] = html.escape(_text_from_rows(brief_rows), quote=True)
    scalars["quote_lines"] = html.escape(_text_from_rows(quote_lines), quote=True)
    if isinstance(not_contacted, str):
        nc_text = not_contacted or str(fallbacks.get("not_contacted") or "None")
    else:
        nc_text = _text_from_rows(not_contacted, empty=str(fallbacks.get("not_contacted") or "None"))
    scalars["not_contacted"] = html.escape(nc_text, quote=True)

    html_map = dict(scalars)
    html_map["brief_rows_table"] = _brief_rows_table(brief_rows)
    html_map["quote_lines_table"] = _quote_lines_table(quote_lines)
    html_map["not_contacted_table"] = _not_contacted_table(not_contacted)

    subject_src = str(tpl.get("subject") or "")
    route_unknown = (
        template_id == "supplier_rfq_invite"
        and (
            not str(raw.get("move_from") or "").strip()
            or not str(raw.get("move_to") or "").strip()
            or str(raw.get("move_from")) in ("(origin not confirmed)", "Not specified")
            or str(raw.get("move_to")) in ("(destination not confirmed)", "Not specified")
        )
    )
    if route_unknown:
        fallback_subj = fallbacks.get("subject_when_route_unknown")
        if fallback_subj:
            subject_src = str(fallback_subj)

    subject = _fill(subject_src, scalars)
    text = _fill(str(tpl.get("body_text") or ""), scalars)
    html_out = _fill(str(tpl.get("body_html") or ""), html_map)
    return {"subject": subject, "text": text, "html": html_out}
