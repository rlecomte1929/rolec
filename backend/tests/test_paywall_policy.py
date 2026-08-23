"""Where the paywall falls, per funding arrangement.

Two jobs. The first is to prove this ships doing NOTHING — every employer- and self-funded
case resolves to no gate today, which is exactly production's behaviour since the paywall was
switched off on 2026-08-23. A refactor that quietly changed who is walled would be the worst
possible outcome of a change whose entire purpose is optionality.

The second is to write the INTENT down executably. `test_the_intended_grid` asserts what each
policy will do once its `enabled` flag is flipped, so the funding × stage mapping is checked
by CI long before it is live. That is the difference between a plan and a comment.

The rules most worth pinning are the two that are easy to invert, and both fail safe:
unknown funding grants, and a raised exception grants. Getting either backwards turns a
misconfiguration into a lockout — which has already happened here once, to 1,845 cases.
"""
from __future__ import annotations

import pytest

from backend.app.services.paywall_policy import (
    FUNDING_EMPLOYER,
    FUNDING_INTERNAL,
    FUNDING_SELF,
    FUNDING_SPONSOR,
    GATE_EXECUTION,
    GATE_NONE,
    GATE_ROADMAP_REVEAL,
    GATE_STAGES,
    POLICIES,
    ROADMAP_PRICE_CENTS,
    PaywallContext,
    resolve_paywall_policy,
)

ALL_FUNDING = [FUNDING_EMPLOYER, FUNDING_SELF, FUNDING_SPONSOR, FUNDING_INTERNAL]


class TestItIsPure:
    def test_it_needs_no_database_and_no_environment(self):
        """The property that makes the whole grid table-testable. If this module ever grows a
        DB session or an env read, the tests below stop being a table and start being
        fixtures, and the intent stops being cheap to check."""
        import inspect

        from backend.app.services import paywall_policy

        source = inspect.getsource(paywall_policy)
        for forbidden in ("SessionLocal", "os.environ", "os.getenv", "requests.", "httpx."):
            assert forbidden not in source, f"paywall_policy must stay pure; found {forbidden!r}"

    def test_the_same_context_always_gives_the_same_answer(self):
        ctx = PaywallContext(funding_source=FUNDING_EMPLOYER)
        assert resolve_paywall_policy(ctx) == resolve_paywall_policy(ctx)


class TestItShipsDoingNothing:
    """Criterion 2. Every path must resolve to no gate today."""

    @pytest.mark.parametrize("funding", ALL_FUNDING)
    def test_every_known_funding_source_resolves_to_no_gate(self, funding):
        decision = resolve_paywall_policy(PaywallContext(funding_source=funding))
        assert decision.gate_stage == GATE_NONE
        assert decision.gated is False

    @pytest.mark.parametrize("funding", ALL_FUNDING)
    def test_nothing_is_priced_today(self, funding):
        assert resolve_paywall_policy(PaywallContext(funding_source=funding)).price_cents == 0

    def test_the_two_paying_policies_are_switched_off(self):
        """The employer and self policies are the ones that would gate somebody. Both must be
        disabled; enabling either is its own reviewed change, never a side effect."""
        assert POLICIES[FUNDING_EMPLOYER].enabled is False
        assert POLICIES[FUNDING_SELF].enabled is False

    def test_the_never_gated_policies_may_be_live(self):
        """A policy whose intent IS 'no gate' is safe on from the start — it cannot wall
        anyone, and having it live proves the enabled path executes."""
        assert POLICIES[FUNDING_SPONSOR].enabled is True
        assert POLICIES[FUNDING_INTERNAL].enabled is True
        assert POLICIES[FUNDING_SPONSOR].intended_gate_stage == GATE_NONE
        assert POLICIES[FUNDING_INTERNAL].intended_gate_stage == GATE_NONE


class TestTheIntendedGrid:
    """Criterion 4 — the plan, made executable before it is live."""

    INTENDED = {
        FUNDING_EMPLOYER: GATE_EXECUTION,        # option D — free to know, pay to do
        FUNDING_SELF: GATE_ROADMAP_REVEAL,       # option B — reveal, then charge
        FUNDING_SPONSOR: GATE_NONE,              # never gated
        FUNDING_INTERNAL: GATE_NONE,             # never gated
    }

    @pytest.mark.parametrize("funding,stage", sorted(INTENDED.items()))
    def test_each_funding_arrangement_has_its_intended_stage(self, funding, stage):
        assert POLICIES[funding].intended_gate_stage == stage

    def test_a_sponsored_case_is_never_priced(self):
        """The whole point of the sponsor arrangement. A programme is covering the move."""
        assert POLICIES[FUNDING_SPONSOR].price_cents == 0

    def test_the_paying_policies_carry_the_shipped_price(self):
        assert POLICIES[FUNDING_EMPLOYER].price_cents == ROADMAP_PRICE_CENTS
        assert POLICIES[FUNDING_SELF].price_cents == ROADMAP_PRICE_CENTS

    def test_every_policy_targets_a_stage_in_the_closed_set(self):
        for policy in POLICIES.values():
            assert policy.intended_gate_stage in GATE_STAGES

    def test_every_policy_explains_itself(self):
        """`reason` reaches a human eventually. A grant nobody can explain is what the
        entitlement audit log exists to prevent."""
        for funding, policy in POLICIES.items():
            assert policy.rationale.strip(), f"{funding} policy has no rationale"
            assert len(policy.rationale) > 40


class TestUnknownMeansGenerous:
    """Criterion 5. Never infer 'individual, therefore charge them' from missing data."""

    @pytest.mark.parametrize("funding", [None, "", "   ", "charity", "unknown", "EMPLOYER_X"])
    def test_a_missing_or_unrecognised_funding_source_is_not_gated(self, funding):
        decision = resolve_paywall_policy(PaywallContext(funding_source=funding))
        assert decision.gate_stage == GATE_NONE
        assert decision.price_cents == 0

    def test_an_empty_context_is_not_gated(self):
        assert resolve_paywall_policy(PaywallContext()).gate_stage == GATE_NONE

    def test_case_and_whitespace_do_not_change_the_answer(self):
        """Intake data is not always tidy; a stray capital must not reroute somebody into a
        different commercial arrangement."""
        assert (
            resolve_paywall_policy(PaywallContext(funding_source="  SPONSOR ")).policy_key
            == resolve_paywall_policy(PaywallContext(funding_source="sponsor")).policy_key
        )


class TestFailureMeansGrant:
    """Criterion 6. The asymmetry `roadmap_entitlement` already documents, preserved here."""

    def test_a_raising_context_still_returns_a_decision(self):
        class Exploding:
            @property
            def funding_source(self):
                raise RuntimeError("boom")

            sponsor_id = None
            current_tier = None

        decision = resolve_paywall_policy(Exploding())  # type: ignore[arg-type]
        assert decision.gate_stage == GATE_NONE, "a bug in policy resolution must not gate anyone"

    def test_it_never_raises_for_any_junk_input(self):
        for junk in (None, 123, object(), [], {}):
            decision = resolve_paywall_policy(junk)  # type: ignore[arg-type]
            assert decision.gate_stage == GATE_NONE


class TestItWouldDiscriminateOnceEnabled:
    """A resolver that returns one answer for every input tells the caller nothing. These
    prove the mechanism can distinguish funders — the only thing holding it flat today is the
    `enabled` flag, which is exactly where that decision belongs."""

    def test_enabling_a_policy_changes_its_answer(self, monkeypatch):
        import dataclasses

        from backend.app.services import paywall_policy as pp

        live = dataclasses.replace(pp.POLICIES[FUNDING_SELF], enabled=True)
        monkeypatch.setitem(pp.POLICIES, FUNDING_SELF, live)

        gated = resolve_paywall_policy(PaywallContext(funding_source=FUNDING_SELF))
        assert gated.gate_stage == GATE_ROADMAP_REVEAL
        assert gated.price_cents == ROADMAP_PRICE_CENTS
        assert gated.gated is True

    def test_two_funders_get_different_answers_once_both_are_live(self, monkeypatch):
        """The whole purpose of the module: an individual and a sponsored mover on the same
        corridor must be able to see different walls."""
        import dataclasses

        from backend.app.services import paywall_policy as pp

        monkeypatch.setitem(
            pp.POLICIES, FUNDING_SELF, dataclasses.replace(pp.POLICIES[FUNDING_SELF], enabled=True)
        )

        individual = resolve_paywall_policy(PaywallContext(funding_source=FUNDING_SELF))
        sponsored = resolve_paywall_policy(PaywallContext(funding_source=FUNDING_SPONSOR))

        assert individual.gate_stage != sponsored.gate_stage
        assert individual.gated is True
        assert sponsored.gated is False


class TestThePriceCannotDrift:
    def test_it_matches_the_shipped_stripe_amount(self):
        """`ROADMAP_PRICE_CENTS` is a deliberate copy so this module stays free of FastAPI.
        A copy that can drift is worse than an import, so it is pinned."""
        from backend.app.routers.payment import ROADMAP_AMOUNT_CENTS

        assert ROADMAP_PRICE_CENTS == ROADMAP_AMOUNT_CENTS


class TestNothingKeysOnThePerson:
    def test_the_context_carries_no_personal_characteristic(self):
        """Sponsorship is a property of the FUNDING, never of the person being funded. If a
        field naming the mover's status appears here, it has become an access-control input —
        read the migration's rationale before adding one."""
        import dataclasses

        fields = {f.name.lower() for f in dataclasses.fields(PaywallContext)}
        banned = ("refugee", "asylum", "vulnerab", "nationality", "status_category")
        offenders = [f for f in fields if any(b in f for b in banned)]
        assert not offenders, f"PaywallContext gained a personal characteristic: {offenders}"
