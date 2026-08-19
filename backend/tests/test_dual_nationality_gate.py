"""A dual national is judged by their BEST nationality, not their first.

Intake asks for a second nationality (`q_has_second_nationality`), stores it on
`employee_profiles.second_nationality` and exports it under GDPR — and until this change
nothing consulted it at the requirements gate. Whichever nationality happened to be captured
first decided the entire journey.

The live case that forced this: a Venezuelan/Italian dual moving Madrid→Dublin on 2026-09-01.
Classified on the Venezuelan nationality they get the ES→IE employment-permit track, whose
pre-arrival chain needs 104 days — so the product would have told them their move was
impossible AND told them to apply for a DETE permit an EU citizen must not apply for. On the
Italian nationality they simply have free movement.
"""
from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.nationality_class import (  # noqa: E402
    EU_EEA,
    OWN_NATIONAL,
    THIRD_COUNTRY,
    classify,
    classify_best,
)


# ─── the case that forced the change ────────────────────────────────────────

def test_the_venezuelan_italian_dual_moving_to_ireland_has_free_movement():
    # "Venezuelan" is not in the adjectival table, so alone it classifies as None —
    # which rules_engine turns into THIRD_COUNTRY via `nationality_class or THIRD_COUNTRY`.
    # Either way the employee lands on the permit track. The second nationality is what
    # rescues them.
    assert classify("Venezuelan", "IRELAND") is None
    assert classify_best(("Venezuelan", "Italian"), "IRELAND") == EU_EEA


def test_order_does_not_matter():
    """Whichever nationality intake captured first must not change the outcome."""
    assert classify_best(("Italian", "Venezuelan"), "IRELAND") == EU_EEA
    assert classify_best(("Venezuelan", "Italian"), "IRELAND") == EU_EEA


# ─── precedence ─────────────────────────────────────────────────────────────

def test_own_national_beats_eu_eea():
    assert classify_best(("Irish", "Italian"), "IRELAND") == OWN_NATIONAL


def test_eu_eea_beats_third_country():
    assert classify_best(("Brazilian", "Portuguese"), "GERMANY") == EU_EEA


def test_two_non_free_movement_nationalities_never_yield_free_movement():
    # Both unrecognised -> None, which the caller treats as THIRD_COUNTRY. The property
    # that matters is that nothing here can produce EU_EEA.
    assert classify_best(("Venezuelan", "Brazilian"), "IRELAND") is None
    # A recognised non-EEA nationality classifies positively.
    assert classify_best(("American", "Japanese"), "IRELAND") in (None, THIRD_COUNTRY)


def test_an_unrecognised_adjectival_is_not_silently_free_movement():
    """The gap this exposed: the adjectival table covers the free-movement area well and
    the rest patchily. An unrecognised nationality must never round UP to EU_EEA — it
    returns None, and rules_engine falls back to the full requirement list."""
    assert classify_best(("Venezuelan",), "IRELAND") is None


# ─── the honesty rule is preserved ──────────────────────────────────────────

def test_an_unrecognised_nationality_does_not_discard_a_recognised_one():
    assert classify_best(("Wakandan", "Italian"), "IRELAND") == EU_EEA


def test_all_unrecognised_still_returns_none():
    """None keeps the FULL requirement list. Suppression happens only when we
    positively know free movement applies — never on a guess."""
    assert classify_best(("Wakandan", None), "IRELAND") is None
    assert classify_best((None, None), "IRELAND") is None


def test_a_single_nationality_behaves_exactly_as_before():
    """No regression for the overwhelmingly common case."""
    for nat in ("Italian", "Venezuelan", "Irish", None):
        for dest in ("IRELAND", "FRANCE", "UNITED STATES"):
            assert classify_best((nat, None), dest) == classify(nat, dest)


def test_an_eu_passport_still_buys_nothing_outside_the_free_movement_area():
    """The union of rights is not a union of fictions — free movement is
    destination-dependent."""
    assert classify_best(("Venezuelan", "Italian"), "UNITED STATES") == THIRD_COUNTRY
