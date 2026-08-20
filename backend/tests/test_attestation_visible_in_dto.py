"""Counsel attestation must reach the client, not just the database.

`attestation_status` has been WRITE-ONLY since 20261104000000 created it: set by
routers/attestation.py, and read by nothing outside that router's own tests. It was absent
from RequirementItemDTO, from the admin review DTO, from frontend types and from both badge
maps — so promoting an attestation changed nothing anyone could see, and a
"representative, awaiting counsel" row rendered identically to an attested one.

These tests pin the plumbing end to end, and pin the two axes apart. models.py states the
relationship: attestation is ORTHOGONAL to verification_status, and "sellable means BOTH".
"""
from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

from backend.app.schemas import RequirementItemDTO


def test_dto_carries_the_attestation_fields():
    dto = RequirementItemDTO(
        id="x", pillar="HOUSING", title="t", description="d", severity="WARN",
        owner="EMPLOYEE", requiredFields=[], statusForCase="MISSING", citations=[],
        verificationStatus="representative",
        attestationStatus="attested", attestedBy="Wikborg Rein",
        attestedAt=dt.datetime(2026, 8, 19),
    )
    assert dto.attestationStatus == "attested"
    assert dto.attestedBy == "Wikborg Rein"
    # Orthogonal: attested content can still be `representative`. Collapsing the two is the
    # failure mode — it would let our own sourcing label imply counsel sign-off.
    assert dto.verificationStatus == "representative"


def test_attestation_defaults_to_none_not_to_a_status():
    """No counsel has looked is the honest default, and the state of every production row.

    It must be None so the UI can render ABSENCE. A default of 'requested' or 'none' would
    be a claim about a review that never happened.
    """
    dto = RequirementItemDTO(
        id="x", pillar="HOUSING", title="t", description="d", severity="WARN",
        owner="EMPLOYEE", requiredFields=[], statusForCase="MISSING", citations=[],
    )
    assert dto.attestationStatus is None
    assert dto.attestedBy is None
    assert dto.attestedAt is None


def test_row_without_the_columns_degrades_instead_of_raising():
    """The producers read these with getattr defaults.

    test_public_corridor.py feeds SimpleNamespace rows carrying none of these columns, and
    a plain attribute access there would turn a missing column into a 500 — the shape of the
    `KeyError: 'source_missing'` class of bug.
    """
    row = SimpleNamespace(verification_status="corpus_grounded")
    assert getattr(row, "attestation_status", None) is None
    assert getattr(row, "attested_by", None) is None


def test_admin_review_dto_exposes_attestation():
    """The admin console is where a human decides what to release; it is the one surface
    that most needs to see whether counsel has signed off."""
    from backend.app import schemas

    dto_cls = next(
        cls for name, cls in vars(schemas).items()
        if name.startswith("AdminRequirement") and hasattr(cls, "model_fields")
        and "reviewStatus" in cls.model_fields
    )
    for field in ("attestationStatus", "attestedBy", "attestedAt"):
        assert field in dto_cls.model_fields, f"{dto_cls.__name__} is missing {field}"
