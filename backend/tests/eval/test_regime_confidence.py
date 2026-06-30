"""
WS-B — tests for the additive ImmigrationRegimeResult.confidence field.

The field is advisory match-specificity: a corridor-specific pathway is high
confidence, the standard_work_permit catch-all is medium, and "unknown" is low.
Ordering (exact > catch-all > unknown) must hold; existing fields untouched.
"""
from __future__ import annotations

from backend.app.services.immigration_regime import (
    ImmigrationRegimeResult,
    ImmigrationRegimeRouter,
)

router = ImmigrationRegimeRouter()


def test_confidence_field_present_and_in_range():
    r = router.detect_regime(
        nationality="Germany", destination_country="United States", contract_type="lta"
    )
    assert hasattr(r, "confidence")
    assert 0.0 <= r.confidence <= 1.0


def test_confidence_ordering_exact_gt_catchall_gt_unknown():
    exact = router.detect_regime(
        nationality="Germany", destination_country="United States", contract_type="lta"
    )  # us_l1b
    catch_all = router.detect_regime(
        nationality="Indian", destination_country="Germany", contract_type="lta"
    )  # standard_work_permit
    unknown = router.detect_regime(nationality="Indian")  # no destination → unknown

    assert exact.regime_id == "us_l1b"
    assert catch_all.regime_id == "standard_work_permit"
    assert unknown.regime_id == "unknown"

    assert exact.confidence > catch_all.confidence > unknown.confidence


def test_eu_free_movement_is_high_confidence():
    r = router.detect_regime(nationality="France", destination_country="Norway")
    assert r.regime_id == "eu_free_movement"
    assert r.confidence >= 0.9


def test_existing_fields_preserved():
    r = router.detect_regime(
        nationality="Germany", destination_country="United States", contract_type="lta"
    )
    # Spot-check a few pre-existing fields are still populated as before.
    assert r.priority == "critical"
    assert r.requires_employer_petition is True
    assert "l1b_support_letter" in r.task_codes


def test_default_confidence_on_bare_construction():
    """Direct construction (no router) keeps the additive default — back-compat."""
    r = ImmigrationRegimeResult(regime_id="domestic")
    assert r.confidence == 0.0
