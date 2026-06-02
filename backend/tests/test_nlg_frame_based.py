"""Parker-J: frame-based NLG — slot-validated incident/case reports."""
from __future__ import annotations

import datetime
import os
import sys

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.nlg.frame_based import (  # noqa: E402
    Frame,
    MissingSlotError,
    UnknownFrameError,
    registered_event_types,
    render,
    translation_key_for,
)


def test_all_four_frames_registered():
    assert set(registered_event_types()) == {
        "passport_expiry_at_risk",
        "assignment_milestone_missed",
        "policy_change_required",
        "supplier_unresponsive",
    }


def test_passport_frame_renders():
    out = render(
        Frame(
            "passport_expiry_at_risk",
            {
                "employee_name": "Mara Okonkwo",
                "passport_country": "Nigeria",
                "expiry_date": datetime.date(2026, 8, 1),
                "days_left": 62,
            },
        )
    )
    assert "Mara Okonkwo's Nigeria passport expires on 2026-08-01 (62 days away)" in out
    assert out.endswith("avoid travel disruption.")


def test_each_frame_renders_with_minimal_slots():
    samples = {
        "assignment_milestone_missed": {
            "employee_name": "Lee", "milestone": "Visa filed",
            "due_date": datetime.date(2026, 5, 1), "days_overdue": 3,
        },
        "policy_change_required": {
            "company_name": "Acme", "category": "Housing",
            "reason": "cap below market", "effective_date": datetime.date(2026, 6, 1),
        },
        "supplier_unresponsive": {
            "supplier_name": "MoveCo", "service": "shipment",
            "days_silent": 5, "case_ref": "C-1001",
        },
    }
    for event_type, slots in samples.items():
        out = render(Frame(event_type, slots))
        assert isinstance(out, str) and len(out) > 0


def test_missing_slot_raises_typed_error():
    with pytest.raises(MissingSlotError) as exc:
        render(Frame("passport_expiry_at_risk", {"employee_name": "X"}))
    assert "passport_country" in str(exc.value)


def test_unknown_event_raises_typed_error():
    with pytest.raises(UnknownFrameError):
        render(Frame("not_a_real_event", {}))
    with pytest.raises(UnknownFrameError):
        translation_key_for("not_a_real_event")


def test_locale_number_grouping():
    slots = {
        "company_name": "Acme", "category": "Housing",
        "reason": "cap raised by 12500 euros", "effective_date": datetime.date(2026, 6, 1),
    }
    # Int grouping only affects integer slots; here the reason is free text, so
    # render the milestone frame which has an integer slot for grouping.
    out_en = render(Frame("supplier_unresponsive", {
        "supplier_name": "MoveCo", "service": "shipment",
        "days_silent": 1500, "case_ref": "C-1"}), locale="en")
    out_de = render(Frame("supplier_unresponsive", {
        "supplier_name": "MoveCo", "service": "shipment",
        "days_silent": 1500, "case_ref": "C-1"}), locale="de")
    assert "1,500" in out_en
    assert "1.500" in out_de


def test_translate_hook_applied():
    out = render(
        Frame("supplier_unresponsive", {
            "supplier_name": "MoveCo", "service": "shipment",
            "days_silent": 5, "case_ref": "C-1001"}),
        translate=lambda s: s.upper(),
    )
    assert out == out.upper()


def test_determinism_identical_bytes():
    f = Frame("supplier_unresponsive", {
        "supplier_name": "MoveCo", "service": "shipment",
        "days_silent": 5, "case_ref": "C-1001"})
    a, b = render(f), render(f)
    assert a == b and a.encode("utf-8") == b.encode("utf-8")
