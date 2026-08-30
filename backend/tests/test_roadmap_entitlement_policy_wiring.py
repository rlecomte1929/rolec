"""The roadmap gate, now that it asks WHO IS PAYING before it asks whether they paid.

`unlocked_from_lookup` answers three questions in order, and only the last is about money:

    1. is the mechanism on at all?               roadmap_paywall_enabled()
    2. does THIS case's funder gate the roadmap? resolve_paywall_policy(...)
    3. has it been paid for?                     access_tier in PAID_TIERS

Question 2 is the new one. It is what lets a sponsored mover — a refugee programme, an NGO or
university scheme — never meet a wall, and what lets an SME sit on the execution gate
(option D: free to know, pay to do) while still reading their own plan.

The two fail-open rules from AIQ-1699 are unchanged and re-asserted here, because a policy
layer is exactly the kind of addition that quietly inverts them: store unreachable still
GRANTS, resolved-and-absent still DENIES.
"""
from __future__ import annotations

import pytest

from backend.app.services import roadmap_entitlement as re_mod
from backend.app.services.paywall_policy import (
    FUNDING_EMPLOYER,
    FUNDING_INTERNAL,
    FUNDING_SELF,
    FUNDING_SPONSOR,
    GATE_INTAKE,
    GATE_ROADMAP_REVEAL,
    ROADMAP_GATING_STAGES,
)
from backend.app.services.roadmap_entitlement import EntitlementLookup, unlocked_from_lookup


@pytest.fixture
def paywall_on(monkeypatch):
    """The mechanism switched on. Every test below runs in this state — with it off,
    `unlocked_from_lookup` short-circuits and proves nothing about the policy."""
    monkeypatch.setattr(re_mod, "roadmap_paywall_enabled", lambda: True)


def _row(tier="free", funding=FUNDING_EMPLOYER, sponsor=None):
    return EntitlementLookup(
        {"access_tier": tier, "payment_status": None,
         "funding_source": funding, "sponsor_id": sponsor},
        True,
    )


class TestTheFailOpenRulesSurvive:
    """AIQ-1699's asymmetry. A policy layer must not quietly invert it."""

    def test_an_unreachable_store_still_grants(self, paywall_on):
        assert unlocked_from_lookup(EntitlementLookup(None, False)) is True

    def test_a_resolved_missing_case_still_denies(self, paywall_on):
        assert unlocked_from_lookup(EntitlementLookup(None, True)) is False

    def test_the_mechanism_being_off_still_short_circuits(self, monkeypatch):
        monkeypatch.setattr(re_mod, "roadmap_paywall_enabled", lambda: False)
        assert unlocked_from_lookup(EntitlementLookup(None, True)) is True


class TestWhoIsPayingIsAskedFirst:
    def test_a_sponsored_case_is_never_walled_even_unpaid(self, paywall_on):
        """The whole reason funding_source exists. A programme is covering this move; the
        mover must never be asked for money, whatever their tier says."""
        assert unlocked_from_lookup(_row(tier="free", funding=FUNDING_SPONSOR, sponsor="ngo-1")) is True

    def test_an_internal_case_is_never_walled(self, paywall_on):
        assert unlocked_from_lookup(_row(tier="free", funding=FUNDING_INTERNAL)) is True

    @pytest.mark.parametrize("funding", [None, "", "charity"])
    def test_an_unknown_funder_falls_back_to_the_legacy_tier_check(self, paywall_on, funding):
        """Silence is not permission.

        `resolve_paywall_policy` is generous about unknown input — it returns "no gate" — but
        it also marks that decision `applies=False`, and the enforcement layer must not read
        the two the same way. An unrecognised funder means NO POLICY SPOKE, so we do exactly
        what we did before this change rather than treating absence of a rule as a licence to
        open the gate. Same distinction `EntitlementLookup.available` already draws between
        "the store said no" and "the store did not answer".
        """
        assert unlocked_from_lookup(_row(tier="free", funding=funding)) is False
        assert unlocked_from_lookup(_row(tier="roadmap", funding=funding)) is True

    def test_todays_employer_case_keeps_its_existing_behaviour(self, paywall_on):
        """The employer policy is defined but disabled, so nothing about an SME case changes:
        with the mechanism on, an unpaid case is still walled exactly as before. Enabling
        option D for employers is a separate, reviewed decision — not a side effect of wiring
        the resolver in."""
        assert unlocked_from_lookup(_row(tier="free", funding=FUNDING_EMPLOYER)) is False
        assert unlocked_from_lookup(_row(tier="roadmap", funding=FUNDING_EMPLOYER)) is True


class TestPaymentIsStillCheckedWhenAPolicyGates:
    """The gate must still be able to CLOSE, or none of the above means anything."""

    @pytest.mark.parametrize("stage", sorted(ROADMAP_GATING_STAGES))
    def test_a_roadmap_gating_stage_falls_through_to_the_tier_check(self, paywall_on, monkeypatch, stage):
        import dataclasses

        from backend.app.services import paywall_policy as pp

        live = dataclasses.replace(pp.POLICIES[FUNDING_SELF], enabled=True, intended_gate_stage=stage)
        monkeypatch.setitem(pp.POLICIES, FUNDING_SELF, live)

        assert unlocked_from_lookup(_row(tier="free", funding=FUNDING_SELF)) is False
        assert unlocked_from_lookup(_row(tier="roadmap", funding=FUNDING_SELF)) is True

    def test_the_execution_gate_does_not_wall_the_roadmap(self, paywall_on, monkeypatch):
        """Option D, stated as a test. The plan is free; the charge lands on the work done
        afterwards. An SME on the execution gate reads its own roadmap unpaid."""
        import dataclasses

        from backend.app.services import paywall_policy as pp

        live = dataclasses.replace(pp.POLICIES[FUNDING_EMPLOYER], enabled=True)
        monkeypatch.setitem(pp.POLICIES, FUNDING_EMPLOYER, live)

        assert pp.POLICIES[FUNDING_EMPLOYER].intended_gate_stage not in ROADMAP_GATING_STAGES
        assert unlocked_from_lookup(_row(tier="free", funding=FUNDING_EMPLOYER)) is True


class TestItDiscriminates:
    def test_two_funders_on_the_same_tier_get_opposite_answers(self, paywall_on, monkeypatch):
        """A gate that answers the same for everyone is not a segmented paywall."""
        import dataclasses

        from backend.app.services import paywall_policy as pp

        monkeypatch.setitem(
            pp.POLICIES, FUNDING_SELF,
            dataclasses.replace(pp.POLICIES[FUNDING_SELF], enabled=True),
        )
        individual = unlocked_from_lookup(_row(tier="free", funding=FUNDING_SELF))
        sponsored = unlocked_from_lookup(_row(tier="free", funding=FUNDING_SPONSOR, sponsor="ngo-1"))

        assert individual is False and sponsored is True

    def test_the_switch_no_longer_walls_every_case(self, paywall_on):
        """A narrower claim than the one I first wrote, and the true one.

        Flipping RELOPASS_ROADMAP_PAYWALL_ENABLED back on still walls unpaid employer- and
        self-funded cases — that behaviour is deliberately unchanged, because silently
        disarming an existing enforcement path inside a wiring PR would be worse than the
        problem it solved. What the switch can no longer do is wall EVERYONE: sponsored and
        internal cases are now exempt by policy, whatever the flag says.

        On 2026-08-23 one flag flip denied 1,845 cases their own roadmap. This does not make
        that impossible; it makes the exempt segments genuinely exempt.
        """
        walled = {f for f in (FUNDING_EMPLOYER, FUNDING_SELF, FUNDING_SPONSOR, FUNDING_INTERNAL)
                  if unlocked_from_lookup(_row(tier="free", funding=f)) is False}
        assert walled == {FUNDING_EMPLOYER, FUNDING_SELF}
