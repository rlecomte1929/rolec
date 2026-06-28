"""AIQ-1311 PR2 · Unit tests for the relocation_cases route-field extractor.

Pure (no DB). Verifies camelCase-preferred / snake-tolerant extraction and the
ISO-date guard the DATE column relies on.
"""
from backend.intake_route_fields import wizard_basics_to_route


def test_camelcase_basics_extracted():
    route = wizard_basics_to_route(
        {
            "originCountry": "FR",
            "originCity": "Paris",
            "destCountry": "NL",
            "destCity": "Amsterdam",
            "targetMoveDate": "2026-09-25",
        }
    )
    assert route == {
        "origin_country": "FR",
        "dest_country": "NL",
        "origin_city": "Paris",
        "dest_city": "Amsterdam",
        "target_start_date": "2026-09-25",
    }


def test_snake_and_alias_fallbacks():
    route = wizard_basics_to_route(
        {"origin_country": "DE", "host_country": "NO", "origin_city": "Berlin", "target_date": "2027-01-02"}
    )
    assert route["origin_country"] == "DE"
    assert route["dest_country"] == "NO"  # host_country alias
    assert route["origin_city"] == "Berlin"
    assert route["target_start_date"] == "2027-01-02"


def test_blank_and_missing_become_none():
    route = wizard_basics_to_route({"originCountry": "  ", "destCountry": "NL"})
    assert route["origin_country"] is None
    assert route["dest_country"] == "NL"
    assert route["origin_city"] is None
    assert route["target_start_date"] is None


def test_unparseable_date_dropped():
    # Non-ISO / garbage dates must not reach the DATE column.
    assert wizard_basics_to_route({"targetMoveDate": "next tuesday"})["target_start_date"] is None
    assert wizard_basics_to_route({"targetMoveDate": "25/09/2026"})["target_start_date"] is None


def test_datetime_string_truncated_to_date():
    assert (
        wizard_basics_to_route({"targetMoveDate": "2026-09-25T00:00:00Z"})["target_start_date"]
        == "2026-09-25"
    )


def test_empty_basics_all_none():
    assert all(v is None for v in wizard_basics_to_route({}).values())
