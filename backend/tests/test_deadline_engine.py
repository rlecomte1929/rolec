"""[DEADLINE-ENGINE] Corridor milestones get real dates from the pathway graph, and the
plan view surfaces the dossier's timing / consequence / source on each corridor task.

Pinned against Andrea's route (ES→IE, VE national, CSEP_2026). Before this change the
plan view showed the same suggested date for the four CSEP-chain steps and no date at all
for IRP / PPSN / Revenue, and every corridor task rendered a bare title.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.services import roadmap_requirement_copy as rrc  # noqa: E402
from backend.app.services.roadmap_corridor_overlay import corridor_overlay  # noqa: E402
from backend.app.services.timeline_service import compute_default_milestones  # noqa: E402
from backend.relocation_plan_service import adapt_milestone_row  # noqa: E402


def _draft(target: str):
    return {
        "relocationBasics": {"originCountry": "ES", "destCountry": "IE", "nationality": "VE", "targetMoveDate": target},
        "employeeProfile": {"nationality": "VE"},
        "familyMembers": {"maritalStatus": "partner_kids", "spouse": {"fullName": "P"}, "children": [{"fullName": "C"}]},
    }


def _rows(target: str):
    return compute_default_milestones(
        case_id="test-case",
        case_draft=_draft(target),
        target_move_date=target,
        destination_country="IE",
        origin_country="ES",
        nationality="VE",
    )


def _by_title(rows, fragment):
    for r in rows:
        if "_corridor_" in r["milestone_type"] and fragment.lower() in r["title"].lower():
            return r
    raise AssertionError(f"no corridor row containing {fragment!r}")


def test_csep_chain_is_sequenced_backwards_from_the_target_date():
    target = (date.today() + timedelta(days=200)).isoformat()
    rows = _rows(target)
    permit_app = _by_title(rows, "Critical Skills Employment Permit application")
    permit_ok = _by_title(rows, "Employment permit granted")
    visa_app = _by_title(rows, "'D' Employment visa application")
    visa_ok = _by_title(rows, "'D' Employment visa granted")
    travel = _by_title(rows, "Travel to")
    dates = [permit_app["target_date"], permit_ok["target_date"], visa_app["target_date"], visa_ok["target_date"], travel["target_date"]]
    assert all(dates), dates
    assert dates == sorted(dates) and len(set(dates)) == 5, dates  # distinct and in order
    assert travel["target_date"] == target  # the arrival anchor is pinned to the move date
    assert permit_app["notes"].startswith("Planned: start by")


def test_irp_carries_the_legal_90_day_window_and_stamp4_has_no_date():
    target = (date.today() + timedelta(days=200)).isoformat()
    rows = _rows(target)
    irp = _by_title(rows, "Register immigration permission")
    assert irp["target_date"] == (date.fromisoformat(target) + timedelta(days=90)).isoformat()
    assert irp["notes"].startswith("Legal deadline: within 0–90 days")
    assert irp["criticality"] == "high"
    ppsn = _by_title(rows, "PPSN")
    assert ppsn["target_date"] == (date.fromisoformat(target) + timedelta(days=14)).isoformat()
    stamp4 = _by_title(rows, "Stamp 4")
    assert stamp4["target_date"] is None  # a milestone nobody performs on a date


def test_without_a_target_date_corridor_rows_keep_no_date():
    rows = compute_default_milestones(
        case_id="t", case_draft={"relocationBasics": {"originCountry": "ES", "destCountry": "IE", "nationality": "VE"}},
        destination_country="IE", origin_country="ES", nationality="VE",
    )
    assert all(r["target_date"] is None for r in rows if "_corridor_" in r["milestone_type"])


def test_infeasible_target_date_raises_an_asserted_advisory():
    soon = (date.today() + timedelta(days=30)).isoformat()
    overlay = corridor_overlay({"draft": _draft(soon)})
    ids = {a["id"]: a for a in overlay["advisories"]}
    assert "TARGET_DATE_INFEASIBLE" in ids and ids["TARGET_DATE_INFEASIBLE"]["asserted"] is True
    assert "104 days" in ids["TARGET_DATE_INFEASIBLE"]["text"] or "days before travel" in ids["TARGET_DATE_INFEASIBLE"]["text"]
    far = (date.today() + timedelta(days=400)).isoformat()
    overlay2 = corridor_overlay({"draft": _draft(far)})
    assert "TARGET_DATE_INFEASIBLE" not in {a["id"] for a in overlay2["advisories"]}


def _item(title, timing=None, desc="", non_obvious=False, url="https://www.gov.ie/x"):
    return SimpleNamespace(
        title=title, description=desc, timing=timing, nonObvious=non_obvious, severity="WARN",
        outcomeType="action", citations=[SimpleNamespace(url=url)],
    )


def test_corridor_row_is_bound_to_dossier_timing_sources_and_consequence():
    items = [
        _item("IRP registration appointments at Burgh Quay", timing="Book immediately on arrival; hard deadline 90 days", desc="Fee is €300; late registration is an offence.", non_obvious=True, url="https://www.irishimmigration.ie/registration"),
        _item("Unrelated housing deposit rule", timing="Before signing a lease", desc="RTB", url="https://www.rtb.ie"),
        _item("Non-EEA nationals must register within 90 days", timing="Within 90 days of arrival", desc="ISD registration", url="https://www.irishimmigration.ie/registration"),
    ]
    row = {"milestone_type": "arrival_corridor_05", "title": "Register immigration permission — IRP card / Stamp 1 (ISD, Burgh Quay)", "description": None, "notes": "Legal deadline: within 0–90 days of “Travel to Ireland”."}
    out = rrc._bind_corridor_row(row, items)
    assert out["instructions"][0].startswith("Legal deadline")
    assert any("Burgh Quay" in x and "hard deadline 90 days" in x for x in out["instructions"])
    assert not any("housing deposit" in x for x in out["instructions"])
    assert out["sources"] == ["https://www.irishimmigration.ie/registration"]
    assert "€300" in out["description"]  # the non-obvious consequence becomes why_this_matters


def test_plan_task_surfaces_corridor_description_and_instructions():
    row = {
        "id": "m1", "milestone_type": "arrival_corridor_05", "title": "Register immigration permission — IRP",
        "description": "Miss the 90-day window and you are unlawfully present.", "status": "pending", "owner": "employee",
        "target_date": "2027-03-01", "instructions": ["Legal deadline: within 0–90 days of arrival", "IRP: book on landing day"],
        "sources": ["https://www.irishimmigration.ie/registration"],
    }
    t = adapt_milestone_row(row)
    assert t.why_this_matters.startswith("Miss the 90-day window")
    assert t.instructions[0].startswith("Legal deadline")
    assert t.sources == ("https://www.irishimmigration.ie/registration",)
    assert t.target_date == "2027-03-01"
