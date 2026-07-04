"""Phase 3: school-age gating + nearby curated-school join for housing."""
from types import SimpleNamespace
from datetime import date

from backend.app.recommendations import schools_nearby as sn


def test_school_age_from_draft_dob():
    kid_year = date.today().year - 8
    draft = {"familyMembers": {"children": [{"dateOfBirth": f"{kid_year}-06-01"}]}}
    assert sn.school_age_from_draft(draft) is True


def test_school_age_from_draft_dependents_fallback():
    draft = {"relocationBasics": {"hasDependents": True}, "familyMembers": {"children": [{}]}}
    assert sn.school_age_from_draft(draft) is True


def test_school_age_from_draft_false_when_no_children():
    assert sn.school_age_from_draft({"relocationBasics": {"hasDependents": False}}) is False
    assert sn.school_age_from_draft({}) is False
    # adult-only child (too old) does not count
    old_year = date.today().year - 40
    assert sn.school_age_from_draft({"familyMembers": {"children": [{"dateOfBirth": f"{old_year}-01-01"}]}}) is False


def test_attach_nearby_schools_populates_reachable_sorted():
    # Tiong Bahru, Singapore coords — several curated SG schools sit within 35 min.
    resp = SimpleNamespace(recommendations=[SimpleNamespace(metadata={"lat": 1.286179, "lng": 103.827225})])
    sn.attach_nearby_schools(resp, "Singapore")
    schools = resp.recommendations[0].metadata.get("nearby_schools")
    assert isinstance(schools, list) and len(schools) > 0
    # sorted by ascending commute, each carries coords + minutes
    mins = [s["commute_min"] for s in schools]
    assert mins == sorted(mins)
    assert all("lat" in s and "lng" in s and "name" in s for s in schools)


def test_attach_nearby_schools_skips_items_without_coords():
    resp = SimpleNamespace(recommendations=[SimpleNamespace(metadata={})])
    sn.attach_nearby_schools(resp, "Singapore")
    assert "nearby_schools" not in resp.recommendations[0].metadata
