"""AIQ-1349 — resolve a case destination (ISO code or name) to the requirement
catalog's FULL-NAME country_code, so requirements actually surface for ISO-coded
cases (they were silently empty before)."""
import os

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

# AIQ-1473b: the resolver moved to the shared requirements_country_key module
# (single source of truth). Behaviour is unchanged — these assertions still hold.
from backend.app.services.requirements_country_key import (
    resolve_catalog_country as _resolve_catalog_country,
)


def test_iso_codes_map_to_catalog_names():
    assert _resolve_catalog_country("SG") == "SINGAPORE"
    assert _resolve_catalog_country("DE") == "GERMANY"
    assert _resolve_catalog_country("NO") == "NORWAY"
    assert _resolve_catalog_country("GB") == "UNITED KINGDOM"
    assert _resolve_catalog_country("UK") == "UNITED KINGDOM"
    assert _resolve_catalog_country("US") == "UNITED STATES"
    assert _resolve_catalog_country("usa") == "UNITED STATES"
    assert _resolve_catalog_country("FR") == "FRANCE"
    assert _resolve_catalog_country("NL") == "NETHERLANDS"


def test_full_names_pass_through_uppercased():
    assert _resolve_catalog_country("Singapore") == "SINGAPORE"
    assert _resolve_catalog_country("UNITED KINGDOM") == "UNITED KINGDOM"


def test_unknown_falls_back_to_raw_upper():
    assert _resolve_catalog_country("IT") == "IT"          # no catalog data yet
    assert _resolve_catalog_country("Japan") == "JAPAN"
    assert _resolve_catalog_country("") == "UNKNOWN"
