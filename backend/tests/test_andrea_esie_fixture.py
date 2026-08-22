"""ES→IE golden fixture — Andrea. The Phase A acceptance contract (AIQ-1984.1).

Spec: `docs/esie-andrea-golden-fixture.md`.

Andrea is a **Spanish (EU/EEA) national** moving Madrid→Dublin as a direct-employee
professional. She needs no employment permit and no ISD registration. The whole
`es-ie-thirdcountry-requirements-2026-08-22` batch is `THIRD_COUNTRY`-scoped and describes a
different person; if any of it reaches her, the product has told a free mover she needs a visa.

Every test here is `xfail(strict=False)` until AIQ-1984.4 (step 6) flips them. They are written
against the *intended* serving behaviour, not today's — that is the point of a golden fixture.
`strict=False` because the pure-data assertions (the audience-scope split) may already hold
today while the rendering ones cannot; an XPASS is information, not a failure.

Nothing here writes: no DB mutation, no promotion, no network.
"""
from __future__ import annotations

import pytest

# --- persona ---------------------------------------------------------------------------

ANDREA = {
    "name": "Andrea",
    "corridor": ("ES", "IE"),
    "country_code": "IRELAND",
    "purpose": "employment",
    "nationality_classes": ["OWN_NATIONAL", "EU_EEA"],
    "employee_type": "professional_direct",
}

#: The move date the dated-action assertions are relative to (AIQ-1972).
MOVE_DATE = "2026-10-01"

# --- expected_served_rules (PROVISIONAL — derived from prod, not relayed) ----------------
# `otto_to_claude` was empty when this fixture was frozen, so these are read from prod rather
# than from Otto's Tier-1 list. Reconcile when the relay lands; a difference is a finding.

EXPECTED_SERVED_RULE_IDS = [
    "de5418cf-887d-52a4-b6c5-e8297f01efe7",  # Irish tax residence 183/280
    "8e4041a0-63a6-5945-b99e-83c2c4719a18",  # Register the job with Revenue (emergency tax)
    "d47357e6-c886-53d9-942b-608f8158047a",  # Split-year treatment
    "91bd4c65-e307-572d-9ea3-08c1a4e995fc",  # Employer's RPN drives IT/USC/PRSI
    "618091c7-c704-59ac-bfe2-0e6c48cf610c",  # Contributions abroad combine
    "6a3bc272-03e3-5fa4-9100-19b674ec0c50",  # PRSI compulsory
]

#: EEA-scoped rows that exist but are `pending` — they serve nothing until a human approves
#: them at /admin/countries. Asserted only after that approval; see the spec §2b.
EXPECTED_AFTER_APPROVAL_RULE_IDS = [
    "78c86802-f32f-5208-944d-4b642677280a",  # A1 Certificate — Posted Workers
    "3db4efb6-a5d7-52b3-be20-7d42f7a31410",  # PPS Number (EU/EEA)
    "c5bcb3ab-6634-57e0-9a88-7695e6f84522",  # Public Health Entitlement (EU/EEA)
    "cdf091ad-1b5b-56d1-ba4d-777b0a22d6ca",  # PRSI (EU/EEA)
    "ab45d82c-524f-52ce-b831-8d16a702f671",  # USC threshold (EU/EEA)
    "e7284e86-f6a1-5c72-b6ae-3af6cdda7402",  # Irish Income Tax rates/bands (EU/EEA)
]

# --- must_not_assert -------------------------------------------------------------------

#: THIRD_COUNTRY rows that must never reach Andrea. The last three were promoted into this
#: corridor on 2026-08-22 and are the nearest misses.
FORBIDDEN_RULE_IDS = [
    "6bff7336-efb0-582b-b0db-38fb1ae1b1a0",  # Work Permission Requirement for Non-EEA Workers
    "57073a0e-85fb-5926-9213-e6564812ae7e",  # CSEP — eligibility
    "c07c4900-7792-561c-b07e-b2464c2f913b",  # Stamp 1 / IRP registration
    "04c9ba47-8c41-5b28-9012-4a10393cfb45",  # Spanish residence does not grant Irish entry
    "466feb22-4242-508a-a9b8-d610bc60d7fd",  # CSEP nine-month employer lock
    "57f1720c-fa9b-5de0-a048-e2dad9816d31",  # CSEP employer 50:50 rule
    "94837181-c418-5a94-8702-a3657684b7cd",  # Employment permit 12-week lead time
]

#: Phrases that must not appear in Andrea's served copy.
FORBIDDEN_ASSERTIONS = [
    "employment permit",
    "work permit",
    "work visa",
    "entry visa",
    "critical skills",
    "register with immigration service delivery",
    "irish residence permit",
]

#: The Emergency-Tax trap: relief is conditional on a PPS number AND a correct employer RPN.
UNCONDITIONAL_EXEMPTION_PHRASES = [
    "you are exempt",
    "you're exempt",
    "exempt from emergency tax",
    "no emergency tax applies",
]


def _served_items_for_andrea():
    """The served roadmap for Andrea. Implemented at AIQ-1984.4 (step 6).

    Deliberately raises rather than returning [] — an empty list would let every
    `must_not_assert` test pass vacuously, which is the silent-empty failure AIQ-1938 exists
    to prevent.
    """
    raise NotImplementedError(
        "wired at AIQ-1984.4 (step 6) — see docs/esie-andrea-golden-fixture.md"
    )


# --- expected_served_rules --------------------------------------------------------------


@pytest.mark.xfail(reason="AIQ-1984.4 — serving path not wired to the fixture yet", strict=False)
def test_andrea_sees_the_audience_scope_rules():
    served = {item["id"] for item in _served_items_for_andrea()}
    missing = [rid for rid in EXPECTED_SERVED_RULE_IDS if rid not in served]
    assert not missing, f"expected_served_rules missing from Andrea's roadmap: {missing}"


@pytest.mark.xfail(reason="AIQ-1984.4 — serving path not wired", strict=False)
def test_andrea_roadmap_is_not_empty():
    """A silent empty must fail loudly — it is the failure mode, not a pass."""
    assert _served_items_for_andrea(), "Andrea's roadmap is empty — silent-empty degrade"


# --- must_not_assert --------------------------------------------------------------------


@pytest.mark.xfail(reason="AIQ-1984.4 — serving path not wired", strict=False)
def test_andrea_is_never_told_she_needs_a_permit_or_visa():
    """must_not_assert #1."""
    served = _served_items_for_andrea()
    by_id = {item["id"] for item in served}
    leaked = [rid for rid in FORBIDDEN_RULE_IDS if rid in by_id]
    assert not leaked, f"THIRD_COUNTRY rules reached an EEA mover: {leaked}"

    blob = " ".join(
        f"{item.get('title', '')} {item.get('description', '')}" for item in served
    ).lower()
    hits = [p for p in FORBIDDEN_ASSERTIONS if p in blob]
    assert not hits, f"Andrea's roadmap asserts permit/visa content: {hits}"


@pytest.mark.xfail(reason="AIQ-1969 — conditional rendering not implemented", strict=False)
def test_emergency_tax_relief_is_never_unconditional():
    """must_not_assert #2 — relief is conditional on PPSN + a correct employer RPN."""
    served = _served_items_for_andrea()
    blob = " ".join(
        f"{item.get('title', '')} {item.get('description', '')}" for item in served
    ).lower()
    hits = [p for p in UNCONDITIONAL_EXEMPTION_PHRASES if p in blob]
    assert not hits, f"Emergency-Tax exemption asserted unconditionally: {hits}"

    for item in served:
        if item.get("assertionMode") == "conditional":
            assert item.get(
                "conditionalOn"
            ), f"conditional fact {item['id']} rendered without its condition"


@pytest.mark.xfail(reason="AIQ-1984.4 — serving path not wired", strict=False)
def test_no_nationality_determined_rule_reaches_an_eea_mover():
    """must_not_assert #3 — the class-level invariant behind #1.

    Categorise, never name-match: a served item is legal for Andrea only if it is unscoped
    (None ⇒ everyone) or its classes intersect hers.
    """
    andrea = set(ANDREA["nationality_classes"])
    for item in _served_items_for_andrea():
        classes = item.get("appliesToNationalityClasses")
        if classes is None:
            continue
        assert andrea & set(classes), (
            f"{item['id']} is scoped {classes} and cannot apply to an EEA mover"
        )


# --- the other Phase A cards ------------------------------------------------------------


@pytest.mark.xfail(reason="AIQ-1969 — non_obvious not surfaced yet", strict=False)
def test_non_obvious_rules_are_flagged_easy_to_miss():
    served = {item["id"]: item for item in _served_items_for_andrea()}
    # All six of Andrea's served rows are non_obvious=true in prod.
    for rid in EXPECTED_SERVED_RULE_IDS:
        item = served.get(rid)
        if item is None:
            continue
        assert item.get("nonObvious") is True, f"{rid} lost its non_obvious flag"


@pytest.mark.xfail(reason="AIQ-1938 — OOD gate not implemented", strict=False)
def test_andrea_is_in_distribution():
    from backend.app.services.roadmap_confidence_gate import is_in_distribution  # noqa

    assert is_in_distribution(
        corridor=ANDREA["corridor"],
        nationality_classes=ANDREA["nationality_classes"],
        employee_type=ANDREA["employee_type"],
    )


@pytest.mark.xfail(reason="AIQ-1938 — OOD gate not implemented", strict=False)
def test_unsupported_tuple_degrades_visibly():
    """Never a fabricated timeline, never a silent empty."""
    from backend.app.services.roadmap_confidence_gate import is_in_distribution  # noqa

    assert not is_in_distribution(
        corridor=("ES", "JP"),
        nationality_classes=["THIRD_COUNTRY"],
        employee_type="seafarer",
    )


@pytest.mark.xfail(reason="AIQ-1971 — employee-type tree not populated", strict=False)
def test_andrea_resolves_to_the_professional_direct_branch():
    served = _served_items_for_andrea()
    assert served, "no branch resolved for Andrea"


@pytest.mark.xfail(reason="AIQ-1972 — dated actions not implemented", strict=False)
def test_deadlines_are_dated_not_literal():
    """Today all six served rows carry a literal timing string and zero dates."""
    undated = [
        item["id"]
        for item in _served_items_for_andrea()
        if item.get("timing") and not item.get("timingDate")
    ]
    assert not undated, f"literal-only deadlines still served: {undated}"
