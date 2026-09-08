"""
[AIQ-1258b] Unit tests for the roadmap lead-time config.

Pure mapping + helper; no DB/router imports. Asserts the mapping covers every
track bucket that ``project_tracks`` can assign, plus the underlying form
categories, and that the helper returns the expected int / None.
"""
from backend.app.services.roadmap_lead_times import (
    LEAD_TIME_DAYS,
    lead_time_days_for,
)
from backend.app.services.roadmap_projection import CATEGORY_TO_TRACK, TRACKS


def test_every_projection_track_bucket_has_a_lead_time():
    for bucket in TRACKS:
        assert bucket in LEAD_TIME_DAYS
        assert isinstance(LEAD_TIME_DAYS[bucket], int)


def test_every_form_category_has_a_lead_time():
    for category in CATEGORY_TO_TRACK:
        assert category in LEAD_TIME_DAYS
        assert isinstance(LEAD_TIME_DAYS[category], int)


def test_known_keys_return_expected_ints():
    assert lead_time_days_for("visa") == 90
    assert lead_time_days_for("civil") == 30
    assert lead_time_days_for("settlement") == 45
    assert lead_time_days_for("family") == 60
    assert lead_time_days_for("work_permit") == 90
    assert lead_time_days_for("civil_documents") == 30


def test_category_lead_time_matches_its_track_bucket():
    # A category's lead time should agree with the bucket it projects into.
    for category, bucket in CATEGORY_TO_TRACK.items():
        assert lead_time_days_for(category) == lead_time_days_for(bucket)


def test_unknown_key_returns_none():
    assert lead_time_days_for("not_a_real_key") is None
    assert lead_time_days_for("") is None
