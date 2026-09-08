"""[AIQ-1821] The required_field ↔ profile_snapshot contract.

`requirements_sufficiency` reports any `required_field` absent from the profile snapshot as
a `missing_field`, which the employee UI renders as "information we still need from you". So
a field the snapshot can never carry becomes a to-do nobody can ever complete.

That was live: `_required_fields_from_text` emitted `visa_type` and `passport_expiry_date`,
and `build_profile_snapshot` produced neither. Both were permanently "missing".

These tests pin the contract in both directions so it cannot silently regress when either
side is edited. No DB, no network, no LLM.
"""
from __future__ import annotations

import backend.app.services.requirements_extractor as rx
from backend.app.services.guidance_pack_service import build_profile_snapshot

# Every text pattern that makes _required_fields_from_text emit something. Kept explicit so
# adding a branch without adding a probe here shows up as a coverage gap in the first test.
_PROBES = (
    "You must hold a valid visa before travelling.",
    "A valid passport is required.",
    "Your employer must submit the petition as your sponsor.",
    "Dependent family members must be registered separately.",
    "You must attend an appointment.",  # matches nothing — the empty case
)


def _all_emittable_fields() -> set[str]:
    fields: set[str] = set()
    for probe in _PROBES:
        fields.update(rx._required_fields_from_text(probe))
    return fields


def _snapshot_keys() -> set[str]:
    """Keys a fully-populated snapshot can produce."""
    draft = {
        "relocationBasics": {
            "originCountry": "FR", "destCountry": "NO",
            "targetMoveDate": "2026-09-01", "hasDependents": True,
        },
        "employeeProfile": {"nationality": "FR", "residenceCountry": "FR"},
        "assignmentContext": {
            "contractType": "LTA", "employerCountry": "FR", "notes": "n/a",
        },
        "familyMembers": {},
    }
    return set(build_profile_snapshot(draft, {"no.permit_type_confirmed": "EEA"}, "NO").keys())


def test_every_required_field_is_a_snapshot_key():
    """The invariant. A field the snapshot cannot carry is an impossible to-do."""
    emittable = _all_emittable_fields()
    assert emittable, "probes matched no branches — the probe list has drifted from the code"
    orphans = sorted(emittable - _snapshot_keys())
    assert not orphans, (
        f"{orphans} can be emitted as required_fields but are not profile-snapshot keys, "
        "so requirements_sufficiency would report them as permanently missing. Either carry "
        "them in build_profile_snapshot or stop emitting them."
    )


def test_visa_type_is_satisfiable_from_a_dossier_answer():
    """visa_type is the field this invariant was fixed by ADDING, not by dropping."""
    draft = {"relocationBasics": {}, "employeeProfile": {}, "assignmentContext": {}}
    assert "visa_type" in rx._required_fields_from_text("You need a visa.")

    unanswered = build_profile_snapshot(draft, {}, "NO")
    assert unanswered["visa_type"] is None

    for key in ("no.permit_type_confirmed", "de.visa_type_confirmed", "sg.pass_type_known",
                "us.visa_known", "fr.work_permit_route", "ca.permit_route_confirmed"):
        answered = build_profile_snapshot(draft, {key: "skilled-worker"}, "NO")
        assert answered["visa_type"] == "skilled-worker", key

    # Progress questions are not route questions — they must not satisfy visa_type.
    progress = build_profile_snapshot(draft, {"no.permit_granted": "yes"}, "NO")
    assert progress["visa_type"] is None


def test_passport_expiry_date_is_no_longer_emitted():
    """It has no source reachable from this pure snapshot, so it could only ever be missing."""
    fields = rx._required_fields_from_text("Your passport must be valid for six months.")
    assert "passport_expiry_date" not in fields
    assert "nationality" in fields, "the satisfiable half of the passport branch must remain"
