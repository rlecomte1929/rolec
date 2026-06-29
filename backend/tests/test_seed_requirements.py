"""AIQ-1349 — the requirement-seed loader's pure expansion (build_payloads).

Guards the YAML→payload contract: correct row count, assignment-type applicability,
provenance suffix, country/purpose co-location, deterministic ids (idempotency).
"""
import json
import os

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from backend.scripts.seed_requirements import build_payloads

SEED = {
    "purposes_by_country": {"GERMANY": ["other"], "NORWAY": ["employment", "other"]},
    "requirements": [
        {
            "key": "residence_registration", "pillar": "RESIDENCE", "severity": "WARN",
            "owner": "EMPLOYEE", "applies_to_assignment_types": ["LTA", "PERMANENT"],
            "countries": {
                "GERMANY": {"title": "Residence registration (Anmeldung)",
                            "description": "Register at the Bürgeramt. Indicative — confirm with the local Bürgeramt."},
                "NORWAY": {"title": "Residence registration (folkeregister)",
                           "description": "Report your move. Indicative — confirm with Skatteetaten."},
            },
        }
    ],
}


def test_expands_per_country_per_purpose():
    rows = build_payloads(SEED)
    # GERMANY×[other]=1 + NORWAY×[employment,other]=2 → 3
    assert len(rows) == 3
    keys = {(r["country_code"], r["purpose"], r["title"]) for r in rows}
    assert ("GERMANY", "other", "Residence registration (Anmeldung)") in keys
    assert ("NORWAY", "employment", "Residence registration (folkeregister)") in keys
    assert ("NORWAY", "other", "Residence registration (folkeregister)") in keys


def test_applies_to_and_provenance():
    rows = build_payloads(SEED)
    for r in rows:
        assert json.loads(r["applies_to_assignment_types_json"]) == ["LTA", "PERMANENT"]
        assert r["description"].rstrip().endswith(".")
        assert "Indicative — confirm with" in r["description"]
        assert r["pillar"] == "RESIDENCE"
        assert r["country_code"] == r["country_code"].upper()


def test_ids_are_deterministic_for_idempotency():
    ids1 = [r["id"] for r in build_payloads(SEED)]
    ids2 = [r["id"] for r in build_payloads(SEED)]
    assert ids1 == ids2  # stable id per (country|purpose|title) → re-runs don't churn


def test_country_filter():
    rows = build_payloads(SEED, only_country="norway")
    assert {r["country_code"] for r in rows} == {"NORWAY"}
    assert len(rows) == 2
