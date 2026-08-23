"""Where a case's paywall falls — one pure function, and four switches that are all off.

WHY THIS EXISTS

The paywall has to differ by who is paying. An SME employee sees no wall, because their
employer pays per move. An individual self-funder sees a reveal-then-pay wall: we show what
we found, then charge for the dated plan. A sponsored mover — a refugee programme, an NGO or
university scheme — never sees one.

Until this module, that was not expressible. The only paywall decision in the product was

    if (paywallOn && roadmapUnlocked === false)      EmployeeCaseRoadmapPage.tsx:322

where `paywallOn` came from `VITE_ENABLE_ROADMAP_PAYWALL`, a build-time constant compiled
into the bundle and identical for every visitor. There was no per-case input anywhere in the
path, so "different wall for different funders" was not hard here — it was impossible.

WHY IT SHIPS DOING NOTHING

Every policy below carries `enabled=False`, so `resolve_paywall_policy` returns
`GATE_NONE` for every input. That is exactly the behaviour production has had since the
paywall was switched off on 2026-08-23, and it is deliberate: turning a gate ON should always
be its own small, separately-reviewed change — a one-line flip of `enabled` — rather than
something that rides along inside a refactor. `intended_gate_stage` records what each policy
WILL do, and is asserted by the tests today, so the intent is executable long before it is
live.

THE TWO RULES THAT ARE EASY TO GET BACKWARDS

**Unknown means generous.** An unrecognised or missing funding source resolves to no gate, not
to the strictest one. Never infer "individual, therefore charge them" from a missing value —
the same only-restrict-on-positive-knowledge rule the nationality gate follows. Guessing the
other way charges somebody for a mistake in our own data.

**Failure means grant.** `resolve_paywall_policy` cannot raise. Any unexpected error resolves
to the most generous decision, mirroring the asymmetry `roadmap_entitlement` already
documents: could-not-consult grants, consulted-and-no-match denies. A policy layer that turns
an outage into a lockout would repeat 2026-08-23, when 1,845 cases were denied their own
roadmap for the length of a misconfiguration.

WHAT THIS MODULE IS NOT

Not a rules engine, and not a configurable policy DSL. Four named policies resolved by a
dictionary lookup is the whole design. A general rule system is where this class of feature
goes to die, and nothing in the roadmap needs one.

Not a decision about a PERSON, either. It keys on `funding_source` — a commercial fact about
the case — and never on who the mover is. See the migration that adds that column for why a
`refugee` flag would be the wrong shape and a GDPR liability besides.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# ── the closed set of places a gate can fall ────────────────────────────────────────────
# These are the four placements analysed on 2026-08-23; each maps 1:1 onto an option in the
# "Where the paywall belongs" decision. Widening the set is fine — inventing a fifth value at
# a call site is not, which is why callers compare against these constants.
GATE_NONE = "none"                      # option A — no wall in the employee's path
GATE_INTAKE = "intake"                  # option C — pay to open the case
GATE_ROADMAP_REVEAL = "roadmap_reveal"  # option B — show the findings, charge for the plan
GATE_EXECUTION = "execution"            # option D — free to know, pay to do

GATE_STAGES = frozenset({GATE_NONE, GATE_INTAKE, GATE_ROADMAP_REVEAL, GATE_EXECUTION})

#: Mirrors ROADMAP_AMOUNT_CENTS in backend/app/routers/payment.py. Kept here rather than
#: imported so this module stays free of FastAPI and stays a pure function; a test asserts the
#: two agree, so they cannot drift apart silently.
ROADMAP_PRICE_CENTS = 80000

FUNDING_EMPLOYER = "employer"
FUNDING_SELF = "self"
FUNDING_SPONSOR = "sponsor"
FUNDING_INTERNAL = "internal"


@dataclass(frozen=True)
class Policy:
    """What one funding arrangement pays, and where its gate would fall once switched on."""

    key: str
    intended_gate_stage: str
    price_cents: int
    rationale: str
    enabled: bool = False


@dataclass(frozen=True)
class PaywallContext:
    """Everything the decision may depend on. Passed IN — this module reads no DB and no env.

    That is what makes the funding × stage grid testable as a table rather than through
    fixtures, and it is why the caller, not the policy, owns the query.
    """

    funding_source: Optional[str] = None
    sponsor_id: Optional[str] = None
    current_tier: Optional[str] = None


@dataclass(frozen=True)
class PaywallDecision:
    """The answer, and enough of the reasoning to explain it to whoever it affected."""

    gate_stage: str
    price_cents: int
    policy_key: str
    reason: str

    @property
    def gated(self) -> bool:
        return self.gate_stage != GATE_NONE


#: One policy per funding arrangement. All disabled — see the module docstring.
POLICIES: Dict[str, Policy] = {
    FUNDING_EMPLOYER: Policy(
        key="employer_v1",
        intended_gate_stage=GATE_EXECUTION,
        price_cents=ROADMAP_PRICE_CENTS,
        rationale=(
            "The SME pays per move. Knowledge stays free so the accuracy engine is the "
            "marketing surface; the charge lands on the execution layer, where effort is "
            "visibly spent on the customer's behalf. Option D."
        ),
    ),
    FUNDING_SELF: Policy(
        key="self_v1",
        intended_gate_stage=GATE_ROADMAP_REVEAL,
        price_cents=ROADMAP_PRICE_CENTS,
        rationale=(
            "An individual with no HR buyer. Show what we found — the count, and the "
            "non-obvious requirements by name — then charge for the dated plan. Never charge "
            "before the reveal: nobody buys proof they have not been shown. Option B."
        ),
    ),
    FUNDING_SPONSOR: Policy(
        key="sponsor_v1",
        intended_gate_stage=GATE_NONE,
        price_cents=0,
        rationale=(
            "A programme is covering this move. Never gated, and never priced. This is the "
            "arrangement, not a fact about the person — the product does not record, and must "
            "not infer, why a programme is paying."
        ),
        enabled=True,  # a policy whose intent IS "no gate" is safe to have live from the start
    ),
    FUNDING_INTERNAL: Policy(
        key="internal_v1",
        intended_gate_stage=GATE_NONE,
        price_cents=0,
        rationale="Test-drive, demo and fixture cases. Never gated, never charged.",
        enabled=True,
    ),
}

#: The decision returned when nothing else applies: no gate, no charge.
_MOST_GENEROUS = PaywallDecision(
    gate_stage=GATE_NONE,
    price_cents=0,
    policy_key="default_open",
    reason="No policy positively applies, so nothing is gated.",
)


def resolve_paywall_policy(context: PaywallContext) -> PaywallDecision:
    """Where does this case's gate fall, and what would it cost?

    Never raises. Never reads a database, an environment variable or a clock — hand it a
    context and it returns a decision, which is what lets the whole funding × stage grid be
    tested as a table.

    Returns the most generous decision when the funding source is missing, unrecognised, or
    served by a policy that is not switched on yet.
    """
    try:
        funding = (context.funding_source or "").strip().lower()
        if not funding:
            return _MOST_GENEROUS

        policy = POLICIES.get(funding)
        if policy is None:
            # An unrecognised value is a gap in OUR data, not evidence about this mover.
            logger.warning(
                "paywall_policy: unrecognised funding_source %r — defaulting to no gate",
                funding,
            )
            return _MOST_GENEROUS

        if not policy.enabled:
            return PaywallDecision(
                gate_stage=GATE_NONE,
                price_cents=0,
                policy_key=policy.key,
                reason=(
                    f"Policy {policy.key} is defined but not enabled; "
                    f"it would otherwise gate at {policy.intended_gate_stage}."
                ),
            )

        return PaywallDecision(
            gate_stage=policy.intended_gate_stage,
            price_cents=policy.price_cents,
            policy_key=policy.key,
            reason=policy.rationale,
        )
    except Exception:  # noqa: BLE001 — a paywall must never lock someone out over a bug
        logger.exception("paywall_policy: resolution failed; granting access")
        return _MOST_GENEROUS
