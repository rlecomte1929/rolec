"""`apply_rules` carries a caller's item dict through opaquely — pin the contract.

This is the gotcha the `non_obvious` / `timing` work turns on. The corridor endpoint and
`requirements_builder` both project extra keys onto their item dicts and expect to read them
back out of `expanded`. That works today only because `apply_rules` never rebuilds an item:
`expanded = list(base_requirements)` is a shallow copy of the SAME dict objects, and both
filter passes are comprehensions over them.

Nothing in the engine's own tests would notice if that changed. A refactor to
`[{k: r[k] for k in KNOWN_KEYS} ...]` would leave every rules_engine test green while the
public corridor payload silently went null on both new fields — the exact class of failure
`reference_silent_degrade_hides_dead_code` describes. Hence a test that asserts on a key the
engine has deliberately never heard of.
"""
from backend.app.services.rules_engine import apply_rules

_UNKNOWN_KEY = "a_key_the_engine_has_never_heard_of"


def _item(**overrides):
    base = {
        "id": "item-1",
        "pillar": "RESIDENCE",
        "title": "Register with the tax authority",
        "description": "d",
        "severity": "WARN",
        "owner": "EMPLOYEE",
        "requiredFields": [],
        "citations": [],
        "non_obvious": True,
        "timing": "within 8 days of arrival",
        _UNKNOWN_KEY: {"nested": ["value"]},
    }
    base.update(overrides)
    return base


def _draft(assignment_type="LTA", nationality="VE", dest="IE"):
    return {
        "relocationBasics": {"purpose": "employment", "destCountry": dest},
        "assignmentContext": {"assignmentType": assignment_type},
        "employeeProfile": {"nationality": nationality},
    }


def test_unknown_keys_survive_an_untouched_passthrough():
    """No filter fires: the item must come back byte-identical, not merely equal."""
    item = _item()
    _required, expanded, _flags = apply_rules(_draft(), [item])

    assert len(expanded) == 1
    assert expanded[0] is item, "apply_rules rebuilt the dict; extra keys are being dropped"
    assert expanded[0]["non_obvious"] is True
    assert expanded[0]["timing"] == "within 8 days of arrival"
    assert expanded[0][_UNKNOWN_KEY] == {"nested": ["value"]}


def test_unknown_keys_survive_the_assignment_type_filter():
    """The survivor of an assignment-type drop keeps its extra keys."""
    kept = _item(id="kept", appliesToAssignmentTypes=["LTA", "PERMANENT"])
    dropped = _item(id="dropped", title="STA-only", appliesToAssignmentTypes=["STA"])

    _required, expanded, flags = apply_rules(_draft("LTA"), [kept, dropped])

    assert [i["id"] for i in expanded] == ["kept"]
    assert "STA-only" in flags["staWaived"]
    assert expanded[0]["non_obvious"] is True
    assert expanded[0]["timing"] == "within 8 days of arrival"
    assert expanded[0][_UNKNOWN_KEY] == {"nested": ["value"]}


def test_unknown_keys_survive_the_regime_filter():
    kept = _item(id="kept", appliesToRegimes=["posted"])
    dropped = _item(id="dropped", title="Local-only", appliesToRegimes=["local"])

    draft = _draft("LTA")
    draft["assignmentContext"]["socialSecurityRegime"] = "posted"
    _required, expanded, flags = apply_rules(draft, [kept, dropped])

    assert [i["id"] for i in expanded] == ["kept"]
    assert "Local-only" in flags["regimeWaived"]
    assert expanded[0]["non_obvious"] is True
    assert expanded[0]["timing"] == "within 8 days of arrival"
    assert expanded[0][_UNKNOWN_KEY] == {"nested": ["value"]}
    assert expanded[0]["appliesToRegimes"] == ["posted"]


def test_unknown_keys_survive_the_nationality_filter():
    """Same, through the nationality gate — which also APPENDS a synthesised item."""
    kept = _item(id="kept", appliesToNationalityClasses=["EU_EEA"])
    dropped = _item(id="dropped", title="Third-country visa", appliesToNationalityClasses=["THIRD_COUNTRY"])

    # A French national moving to Germany => EU_EEA; the third-country item is dropped.
    _required, expanded, flags = apply_rules(_draft("LTA", nationality="FR", dest="DE"), [kept, dropped])

    assert flags["nationalityClass"] == "EU_EEA"
    survivor = next(i for i in expanded if i.get("id") == "kept")
    assert survivor["non_obvious"] is True
    assert survivor["timing"] == "within 8 days of arrival"
    assert survivor[_UNKNOWN_KEY] == {"nested": ["value"]}


def test_engine_synthesised_items_omit_the_keys_rather_than_faking_them():
    """The flip side of the contract, and why callers must read with `.get()`.

    `_immigration_confirmation` invents an item the catalog never had. It has no timing and
    no non_obvious data, and it must not pretend otherwise — a synthesised `False` would
    assert "we modeled this and it is obvious", which is a claim nobody made.
    """
    dropped = _item(id="dropped", appliesToNationalityClasses=["THIRD_COUNTRY"])

    _required, expanded, _flags = apply_rules(_draft("LTA", nationality="FR", dest="DE"), [dropped])

    synthesised = next(i for i in expanded if i.get("id") == "immigration_nothing_to_do")
    assert "non_obvious" not in synthesised
    assert "timing" not in synthesised
    assert synthesised.get("non_obvious") is None
    assert synthesised.get("timing") is None
