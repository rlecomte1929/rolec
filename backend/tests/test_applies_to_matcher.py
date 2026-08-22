"""Phase 5: scope-aware applies_to matching (backend/app/services/applies_to_matcher.py).

Proves the two failures of the old strict-equality matcher are fixed:
  1. metadata keys in applies_to (persona, topic, nationality_scope_basis, assertion_mode, …)
     no longer drop a fact;
  2. audience_scope rules reach an EEA mover, while nationality_determined rules do not — i.e.
     a Spanish (EEA) mover is not wrongly told they are exempt from Emergency Tax / PPSN.

Imports only the pure matcher (+ nationality_class); no DB, so it runs in the plain unit lane.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.services.applies_to_matcher import apply_applies_to  # noqa: F401
from backend.app.services.applies_to_matcher import nationality_applies, TARGETING_KEYS  # noqa: F401

IE = "IE"
ANDREA = {"nationality": "VE", "destination_country": IE}    # non-EEA (third country)
SPANIARD = {"nationality": "ES", "destination_country": IE}  # EEA free movement
IRISH = {"nationality": "IE", "destination_country": IE}     # own national


def _nd(**extra):
    """A nationality_determined non-EEA rule, carrying the usual metadata."""
    base = {"nationality": "non-EEA", "status": "professional",
            "nationality_scope_basis": "nationality_determined",
            "persona": "third-country professional", "topic": "x"}
    base.update(extra)
    return base


def _au(**extra):
    """An audience_scope rule: nationality-neutral in law, shown to a non-EEA audience."""
    base = {"nationality": "non-EEA", "status": "professional",
            "nationality_scope_basis": "audience_scope",
            "persona": "third-country professional", "topic": "y"}
    base.update(extra)
    return base


# ── nationality scope ────────────────────────────────────────────────────────
def test_nationality_determined_gates_out_eea_and_own_national():
    assert apply_applies_to(_nd(), ANDREA) is True
    assert apply_applies_to(_nd(), SPANIARD) is False
    assert apply_applies_to(_nd(), IRISH) is False


def test_audience_scope_reaches_everyone():
    # The core anti-mis-serve: an EEA mover STILL sees Emergency-Tax / PPSN-style rules.
    assert apply_applies_to(_au(), ANDREA) is True
    assert apply_applies_to(_au(), SPANIARD) is True
    assert apply_applies_to(_au(), IRISH) is True


def test_nationality_accepts_iso_or_country_name():
    assert apply_applies_to(_nd(), {"nationality": "Spain", "destination_country": "IE"}) is False
    assert apply_applies_to(_nd(), {"nationality": "Venezuela", "destination_country": "IE"}) is True


def test_unknown_mover_nationality_fails_open():
    # Never fabricate "nothing required": an unrecognised nationality keeps the rule.
    assert apply_applies_to(_nd(), {"nationality": "Wakanda", "destination_country": "IE"}) is True


# ── metadata keys never filter ───────────────────────────────────────────────
def test_metadata_keys_do_not_filter():
    heavy = _au(assertion_mode=None, conditional_on=None, non_obvious=True,
                needs_lawyer_review=True, quote_verbatim_confirmed=True, corridor="ES->IE")
    assert apply_applies_to(heavy, SPANIARD) is True


def test_conditional_records_still_apply():
    # assertion_mode is NOT a targeting key: a conditional fact applies; rendering handles it.
    assert apply_applies_to(_nd(assertion_mode="conditional", conditional_on="A3"), ANDREA) is True


# ── status / employee_profile: fail-open when the snapshot lacks the field ────
def test_empty_applies_to_applies():
    assert apply_applies_to({}, SPANIARD) is True


def test_absent_targeting_field_fails_open():
    # snapshot has no employee_profile -> do not drop (fixes the employee_profile:"all" over-filter)
    assert apply_applies_to({"employee_profile": "all"}, SPANIARD) is True


def test_present_targeting_field_mismatch_filters():
    assert apply_applies_to({"employee_profile": "hr"}, {"employee_profile": "employee"}) is False


# ── golden fixture: the real ES→IE batch serves correctly by nationality ─────
_BATCH = (Path(__file__).resolve().parents[2]
          / "docs" / "imports" / "es-ie-thirdcountry-requirements-2026-08-22"
          / "es_ie_thirdcountry_requirements.ndjson")


def _load_batch():
    if not _BATCH.is_file():
        pytest.skip("ES->IE third-country batch not present in this checkout")
    return [json.loads(l) for l in _BATCH.read_text().splitlines() if l.strip()]


def _basis(rec):
    return (rec.get("applies_to") or {}).get("nationality_scope_basis")


def test_batch_andrea_non_eea_gets_everything():
    recs = _load_batch()
    served = [r for r in recs if apply_applies_to(r.get("applies_to") or {}, ANDREA)]
    assert len(served) == len(recs) == 38


def test_batch_eea_mover_gets_only_audience_scope():
    recs = _load_batch()
    audience = {r["fact_key"] for r in recs if _basis(r) == "audience_scope"}
    determined = {r["fact_key"] for r in recs if _basis(r) == "nationality_determined"}
    served = {r["fact_key"] for r in recs if apply_applies_to(r.get("applies_to") or {}, SPANIARD)}
    assert served == audience            # exactly the nationality-neutral rules
    assert len(served) == 17
    assert served.isdisjoint(determined)  # no nationality_determined rule leaks to an EEA mover
