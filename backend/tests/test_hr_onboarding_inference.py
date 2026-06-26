"""AIQ-1223c — deterministic HR-onboarding inference engine unit tests.

The engine is pure deterministic table lookups (no LLM), so these tests pin the
size_band → tier-scaffold mapping, the published-tier reconciliation
(real data wins), destination pre-fill, dashboard density, and confidence.
"""
from types import SimpleNamespace

import pytest

from backend.app.services import hr_onboarding_inference as eng


# ── _size_bucket: robust to both band vocabularies ──────────────────────────

@pytest.mark.parametrize(
    "band,expected",
    [
        ("1–10", "small"),
        ("11–50", "small"),
        ("10–50", "small"),       # admin vocabulary
        ("51–200", "medium"),
        ("201–500", "medium"),
        ("501–1000", "large"),
        ("200–1000", "large"),    # admin vocabulary
        ("1001–5000", "large"),
        ("5000+", "large"),
        ("", "unknown"),
        (None, "unknown"),
        ("enterprise", "unknown"),
    ],
)
def test_size_bucket(band, expected):
    assert eng._size_bucket(band) == expected


# ── tier scaffolds ──────────────────────────────────────────────────────────

def test_scaffold_for_bucket():
    assert eng._scaffold_for_bucket("small") == ["All employees"]
    assert eng._scaffold_for_bucket("medium") == ["Standard", "Senior"]
    assert eng._scaffold_for_bucket("large") == ["Standard", "Senior", "Executive"]
    assert eng._scaffold_for_bucket("unknown") == ["All employees"]


def test_scaffold_for_count_reconciliation():
    assert eng._scaffold_for_count(0) == ["All employees"]
    assert eng._scaffold_for_count(1) == ["All employees"]
    assert eng._scaffold_for_count(2) == ["Standard", "Senior"]
    assert eng._scaffold_for_count(3) == ["Standard", "Senior", "Executive"]
    assert eng._scaffold_for_count(4) == ["Tier 1", "Tier 2", "Tier 3", "Tier 4"]


# ── infer_workspace_config: end-to-end deterministic behaviour ──────────────

def _patch_db(monkeypatch, *, company, tier_count=0, case_count=0):
    """Stub the module-level db + the two lookup helpers."""
    fake_db = SimpleNamespace(get_company=lambda cid: company)
    monkeypatch.setattr(eng, "db", fake_db)
    monkeypatch.setattr(eng, "_published_tier_count", lambda cid: tier_count)
    monkeypatch.setattr(eng, "_case_count", lambda cid: case_count)


def test_small_company_no_policy_no_cases(monkeypatch):
    _patch_db(monkeypatch, company={"size_band": "11–50"})
    out = eng.infer_workspace_config("co-1")
    cfg = out["proposed_config"]
    assert cfg["policy_tiers"] == ["All employees"]
    assert cfg["tier_source"] == "size_band_guess"
    assert cfg["dashboard_density"] == "compact"
    assert cfg["bulk_assign_enabled"] is False
    assert cfg["show_volume_nudges"] is False
    assert out["confidence"] == "medium"
    assert out["signals"]["size_bucket"] == "small"


def test_medium_company_destination_prefill(monkeypatch):
    _patch_db(
        monkeypatch,
        company={
            "size_band": "51–200",
            "default_destination_country": "DE",
            "default_working_location": "Berlin",
        },
    )
    out = eng.infer_workspace_config("co-2")
    cfg = out["proposed_config"]
    assert cfg["policy_tiers"] == ["Standard", "Senior"]
    assert cfg["default_destination_country"] == "DE"
    assert cfg["default_working_location"] == "Berlin"
    assert cfg["dashboard_density"] == "standard"
    assert cfg["show_volume_nudges"] is True
    assert out["confidence"] == "medium"


def test_large_company_enables_bulk_assign(monkeypatch):
    _patch_db(monkeypatch, company={"size_band": "5000+"})
    cfg = eng.infer_workspace_config("co-3")["proposed_config"]
    assert cfg["policy_tiers"] == ["Standard", "Senior", "Executive"]
    assert cfg["bulk_assign_enabled"] is True


def test_published_tiers_win_over_size_band_guess(monkeypatch):
    # Small size band would guess single tier, but a real 3-tier published
    # policy must win and bump confidence to high.
    _patch_db(monkeypatch, company={"size_band": "11–50"}, tier_count=3)
    out = eng.infer_workspace_config("co-4")
    cfg = out["proposed_config"]
    assert cfg["policy_tiers"] == ["Standard", "Senior", "Executive"]
    assert cfg["tier_source"] == "published"
    assert out["signals"]["has_published_policy"] is True
    assert out["confidence"] == "high"


def test_active_program_when_cases_exist(monkeypatch):
    _patch_db(monkeypatch, company={"size_band": "11–50"}, case_count=7)
    out = eng.infer_workspace_config("co-5")
    assert out["proposed_config"]["dashboard_density"] == "active_program"
    assert out["signals"]["has_active_program"] is True
    assert out["signals"]["case_count"] == 7


def test_no_size_band_is_low_confidence(monkeypatch):
    _patch_db(monkeypatch, company={})
    out = eng.infer_workspace_config("co-6")
    assert out["confidence"] == "low"
    assert out["signals"]["size_bucket"] == "unknown"
    assert out["proposed_config"]["policy_tiers"] == ["All employees"]
