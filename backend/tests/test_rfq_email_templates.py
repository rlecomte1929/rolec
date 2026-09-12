"""AIQ-2371 — pack renderer: fallbacks, escaping, supplier identity strip."""
from __future__ import annotations

import os
import sys

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from backend.app.services.rfq_email_templates import (  # noqa: E402
    ALLOWED_VARIABLES,
    load_pack,
    render,
)

FULL = {
    "rfq_ref": "RFQ-1",
    "supplier_name": "Acme Movers",
    "company_name": "Acme Corp",
    "employee_first_name": "Alex",
    "employee_full_name": "Alex Employee",
    "hr_first_name": "Pat",
    "hr_full_name": "Pat HR",
    "service_labels": "movers",
    "brief_rows": [{"label": "Move from", "value": "Paris"}, {"label": "Notes", "value": "fragile"}],
    "move_from": "Paris, FR",
    "move_to": "Oslo, NO",
    "target_move_date": "2026-10-01",
    "respond_by": "2026-09-20",
    "link_expires_days": "14",
    "magic_link": "https://relopass.com/supplier/quote?token=abc",
    "employee_rfq_url": "https://relopass.com/e",
    "hr_rfq_url": "https://relopass.com/h",
    "employee_quotes_url": "https://relopass.com/q",
    "quote_total": "1200",
    "quote_currency": "EUR",
    "quote_valid_until": "2026-10-15",
    "quote_lines": [{"label": "Packing", "amount": 400}],
    "quotes_received_count": "2",
    "recipients_count": "3",
    "contacted_supplier_names": "Acme",
    "not_contacted": [{"supplier": "Ghost Co", "reason": "no address"}],
    "reminder_days_left": "2",
    "validated_supplier_name": "Acme Movers",
    "validation_reason": "best value",
    "support_email": "support@relopass.com",
}

INJECT = {
    **FULL,
    "supplier_name": '<a href=x>y</a>',
    "brief_rows": [{"label": "Notes", "value": "<script>alert(1)</script>"}],
    "quote_lines": [{"label": "<script>x</script>", "amount": "<b>1</b>"}],
    "not_contacted": [{"supplier": "<script>", "reason": "<img src=x>"}],
}


def _ids():
    return [t["id"] for t in load_pack()["templates"]]


def test_pack_variables_used_subset_of_allowed():
    for tpl in load_pack()["templates"]:
        extra = set(tpl.get("variables_used") or []) - ALLOWED_VARIABLES
        assert not extra, f"{tpl['id']} unknown vars {extra}"


def test_every_template_renders_full_and_empty():
    leftover = r"{{"
    for tid in _ids():
        full = render(tid, FULL)
        empty = render(tid, {})
        for label, out in (("full", full), ("empty", empty)):
            blob = out["subject"] + out["text"] + out["html"]
            assert leftover not in blob, f"{tid} {label} still has {blob[blob.find(leftover):blob.find(leftover)+40] if leftover in blob else ''}"
            assert out["subject"]
            assert out["text"]
            assert out["html"]


def test_injection_escaped_in_all_ten_templates():
    for tpl in load_pack()["templates"]:
        tid = tpl["id"]
        used = set(tpl.get("variables_used") or [])
        out = render(tid, INJECT)
        blob = out["subject"] + out["text"] + out["html"]
        assert "<script>" not in blob, tid
        assert "<a href=x>y</a>" not in blob, tid
        assert "<a href=x>" not in out["html"], tid
        if "supplier_name" in used:
            assert "&lt;a href=x&gt;" in blob, tid
        if "brief_rows" in used:
            assert "&lt;script&gt;" in blob, tid


def test_supplier_templates_strip_employee_and_company_and_hr_identity():
    leaked = ("Alex Employee", "Acme Corp", "Pat HR", "Alex", "Pat")
    for tpl in load_pack()["templates"]:
        if tpl.get("audience") != "supplier":
            continue
        out = render(tpl["id"], FULL)
        blob = out["subject"] + out["text"] + out["html"]
        for token in leaked:
            assert token not in blob, f"{tpl['id']} leaked {token}"


def test_hr_quotes_ready_subject_has_employee_and_ref():
    out = render("hr_quotes_ready", FULL)
    assert "Alex Employee" in out["subject"]
    assert "RFQ-1" in out["subject"]
    assert out["subject"].startswith("Quotes ready:")


def test_unknown_route_fallback_subject():
    out = render("supplier_rfq_invite", {"rfq_ref": "RFQ-9", "supplier_name": "there"})
    assert out["subject"] == "Quote request from a relocating company: RFQ-9"


def test_invite_keeps_itemised_ask():
    out = render("supplier_rfq_invite", FULL)
    assert "itemised" in out["text"].lower() or "itemised" in out["html"].lower()


def test_employee_rfq_sent_retitled():
    out = render("employee_rfq_sent", FULL)
    assert "Suppliers we could not reach" in out["html"]
    assert "SERVICES NOT COVERED" not in out["text"]
