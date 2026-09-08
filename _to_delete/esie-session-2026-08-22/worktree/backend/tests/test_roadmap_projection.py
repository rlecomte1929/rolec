"""
[P1-6 / AIQ-800] Unit tests for the roadmap read-time projection.

These drive the REAL forms→tracks projection (the production code path) rather
than hand-seeding roadmap_steps fixtures — which is exactly the gap that let the
roadmap-step label ship green-but-dead. The projection is duck-typed on
CaseFormSummary, so we stub it with SimpleNamespace and avoid importing the
router/db layer.
"""
from types import SimpleNamespace

from backend.app.services.roadmap_projection import (
    project_tracks,
    track_key_for_form,
    track_label_for_form,
)


def _form(form_id, code, category, status="not_started", is_blocked=False, name=None, deadline=None):
    return SimpleNamespace(
        id=form_id,
        status=status,
        is_blocked=is_blocked,
        deadline=deadline,
        template=SimpleNamespace(code=code, category=category, name=name or code),
    )


# France→Norway acceptance set ------------------------------------------------

def _fr_no_forms():
    return [
        _form("f-eea", "POL-EEA-REG", "registration", name="EEA registration"),
        _form("f-dnum", "GP-7-04", "tax", name="D-number (GP-7-04)"),
        _form("f-apo", "APOSTILLE-FR", "civil_documents", name="Civil document apostille"),
    ]


def test_fr_no_forms_land_in_correct_tracks():
    tracks = project_tracks(_fr_no_forms())
    by_key = {t.key: t for t in tracks}

    # Three buckets, one form each — no empty tracks (no family forms).
    assert set(by_key) == {"visa", "civil", "settlement"}
    assert [s.title for s in by_key["visa"].steps] == ["EEA registration"]
    assert [s.title for s in by_key["civil"].steps] == ["Civil document apostille"]
    assert [s.title for s in by_key["settlement"].steps] == ["D-number (GP-7-04)"]


def test_tracks_returned_in_sort_order():
    tracks = project_tracks(_fr_no_forms())
    orders = [t.sort_order for t in tracks]
    assert orders == sorted(orders)
    # visa(0) before civil(1) before settlement(3); family(2) absent here.
    assert [t.key for t in tracks] == ["visa", "civil", "settlement"]


def test_step_id_is_the_case_form_id():
    tracks = project_tracks(_fr_no_forms())
    visa = next(t for t in tracks if t.key == "visa")
    assert visa.steps[0].id == "f-eea"


# Status mapping + progress ---------------------------------------------------

def test_status_mapping_and_progress():
    forms = [
        _form("a", "POL-EEA-REG", "registration", status="approved"),    # → completed
        _form("b", "RF-1234", "registration", status="submitted"),       # → completed (settlement via override)
        _form("c", "GP-7-04", "tax", status="in_progress"),              # → in_progress
        _form("d", "RF-1209", "tax", status="not_started"),              # → pending
    ]
    tracks = {t.key: t for t in project_tracks(forms)}

    visa = tracks["visa"]
    assert visa.steps[0].status == "completed"
    assert visa.progress_pct == 100  # only the approved EEA form

    settle = tracks["settlement"]
    statuses = {s.id: s.status for s in settle.steps}
    assert statuses == {"b": "completed", "c": "in_progress", "d": "pending"}
    # 1 of 3 settlement steps completed → 33%
    assert settle.progress_pct == 33


def test_rejected_and_blocked_map_to_blocked():
    forms = [
        _form("r", "GP-7-04", "tax", status="rejected"),
        _form("k", "HELFO-1", "health", status="not_started", is_blocked=True),
    ]
    settle = project_tracks(forms)[0]
    assert {s.id: s.status for s in settle.steps} == {"r": "blocked", "k": "blocked"}
    assert settle.progress_pct == 0


# Mapping rules ---------------------------------------------------------------

def test_registration_category_defaults_to_visa_but_rf1234_overrides_to_settlement():
    assert track_key_for_form("registration", "POL-EEA-REG") == "visa"
    assert track_key_for_form("registration", "RF-1234") == "settlement"


def test_unknown_category_and_adhoc_fall_back_to_settlement():
    assert track_key_for_form(None, "CUSTOM") == "settlement"
    assert track_key_for_form("something_new", "X-1") == "settlement"


def test_family_forms_grouped_into_family_track():
    forms = [
        _form("s", "UTL-2011F", "family", name="Spouse permit"),
        _form("c", "UTL-2011B", "family", name="Child documents"),
    ]
    tracks = project_tracks(forms)
    assert len(tracks) == 1
    assert tracks[0].key == "family"
    assert len(tracks[0].steps) == 2


def test_track_label_for_form_is_human_readable():
    assert track_label_for_form("registration", "POL-EEA-REG") == "Visa & Permit"
    assert track_label_for_form("civil_documents", "APOSTILLE-FR") == "Civil Documents"
    assert track_label_for_form("tax", "GP-7-04") == "Settlement"


def test_empty_forms_yields_no_tracks():
    assert project_tracks([]) == []
