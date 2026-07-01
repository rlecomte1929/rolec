"""
Employee immigration snapshot (relocation-assistant Slice 2) — the pure builder
that turns a case into a proactive "your move at a glance" payload: risk flags +
checklist summary, scoped to one case, PII-safe. Reuses the same engine the HR
panel uses (get_requirements / evaluate_risks) so the employee sees the same risks.
"""
from datetime import date

import backend.app.services.immigration_snapshot_service as snap
from backend.app.services.immigration_requirement_service import RiskFlag


class _Req:
    def __init__(self, is_required=True, is_conditional=False):
        self.is_required = is_required
        self.is_conditional = is_conditional


def _patch(monkeypatch, *, case, requirements, profile, risks):
    monkeypatch.setattr(snap, "_get_case_details", lambda case_id, org_id: case)
    monkeypatch.setattr(snap, "get_requirements", lambda *a, **k: requirements)
    monkeypatch.setattr(snap, "_load_profile_for_case", lambda case_id: profile)
    monkeypatch.setattr(snap, "evaluate_risks", lambda *a, **k: risks)


def test_covered_case_returns_serialized_risks_and_checklist(monkeypatch):
    risks = [
        RiskFlag(
            flag_type="PASSPORT_EXPIRY_WITHIN_90_DAYS",
            severity="critical",
            title="Passport expires soon",
            description="Your passport expires within 90 days.",
            recommended_action="Renew your passport before applying.",
            deadline=date(2026, 9, 1),
        )
    ]
    _patch(
        monkeypatch,
        case={"origin_country": "IN", "dest_country": "DE"},
        requirements=[_Req(is_required=True), _Req(is_required=False, is_conditional=True)],
        profile={"nationality": "IN", "passport_expiry": "2026-08-01", "_move_date": "2026-09-01"},
        risks=risks,
    )
    out = snap.build_immigration_snapshot("case-1", visa_type="blue_card")

    assert out["covered"] is True
    assert out["corridor_from"] == "IN" and out["corridor_to"] == "DE"
    assert out["checklist_summary"]["total"] == 2
    assert out["checklist_summary"]["required"] == 1
    assert out["checklist_summary"]["conditional"] == 1
    assert len(out["risk_flags"]) == 1
    rf = out["risk_flags"][0]
    assert rf["flag_type"] == "PASSPORT_EXPIRY_WITHIN_90_DAYS"
    assert rf["severity"] == "critical"
    assert rf["deadline"] == "2026-09-01"
    # PII-safe: the raw profile fields must NOT leak into the snapshot.
    assert "passport_expiry" not in rf
    blob = repr(out)
    assert "2026-08-01" not in blob  # raw passport date never surfaced


def test_missing_corridor_fails_closed(monkeypatch):
    _patch(monkeypatch, case=None, requirements=[], profile=None, risks=[])
    out = snap.build_immigration_snapshot("case-x")
    assert out["covered"] is False
    assert out["risk_flags"] == []
    assert out["checklist_summary"]["total"] == 0


def test_unseeded_corridor_fails_closed(monkeypatch):
    # Corridor known, but no requirements seeded → report uncovered, not an empty checklist.
    _patch(
        monkeypatch,
        case={"origin_country": "IN", "dest_country": "DE"},
        requirements=[],
        profile={"nationality": "IN"},
        risks=[],
    )
    out = snap.build_immigration_snapshot("case-y")
    assert out["covered"] is False


def test_no_profile_means_no_risks_but_still_covered(monkeypatch):
    _patch(
        monkeypatch,
        case={"origin_country": "IN", "dest_country": "DE"},
        requirements=[_Req(is_required=True)],
        profile=None,
        risks=[],
    )
    out = snap.build_immigration_snapshot("case-z")
    assert out["covered"] is True
    assert out["risk_flags"] == []
    assert out["checklist_summary"]["total"] == 1
