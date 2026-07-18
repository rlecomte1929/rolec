"""AIQ-1607: Geoapify address-autocomplete proxy (disabled-until-keyed, fail-soft)."""
import os

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from backend.app.services import geocoding_service as svc
from backend.main import app
from backend.app.auth_deps import get_current_user


def test_disabled_when_no_key(monkeypatch):
    monkeypatch.delenv("GEOAPIFY_API_KEY", raising=False)
    assert svc.is_enabled() is False
    assert svc.autocomplete("10 Downing Street") == []  # no outbound call without a key


def test_short_query_returns_empty(monkeypatch):
    monkeypatch.setenv("GEOAPIFY_API_KEY", "test-key")
    assert svc.autocomplete("ab") == []  # < 3 chars — don't even call the provider


def test_parses_geoapify_results_and_forwards_query(monkeypatch):
    monkeypatch.setenv("GEOAPIFY_API_KEY", "test-key")
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "results": [
            {"formatted": "10 Downing Street, London, UK"},
            {"formatted": "10 Downing Ave, Springfield, US"},
            {"other": "no formatted key"},
        ]
    }
    import requests

    get = MagicMock(return_value=resp)
    monkeypatch.setattr(requests, "get", get)

    out = svc.autocomplete("10 Downing", limit=5)
    assert out == [
        {"formatted": "10 Downing Street, London, UK"},
        {"formatted": "10 Downing Ave, Springfield, US"},
    ]
    params = get.call_args.kwargs["params"]
    assert params["apiKey"] == "test-key"  # key is server-side only
    assert params["text"] == "10 Downing"


def test_fail_soft_on_provider_error(monkeypatch):
    monkeypatch.setenv("GEOAPIFY_API_KEY", "test-key")
    import requests

    monkeypatch.setattr(requests, "get", MagicMock(side_effect=RuntimeError("network")))
    assert svc.autocomplete("10 Downing Street") == []  # must not raise


def test_endpoint_disabled_shape_when_no_key(monkeypatch):
    monkeypatch.delenv("GEOAPIFY_API_KEY", raising=False)
    app.dependency_overrides[get_current_user] = lambda: {"id": "emp-1", "role": "EMPLOYEE"}
    try:
        client = TestClient(app)
        r = client.get("/api/employee/geocode/autocomplete", params={"q": "10 Downing"})
        assert r.status_code == 200
        assert r.json() == {"disabled": True, "suggestions": []}
    finally:
        app.dependency_overrides.pop(get_current_user, None)
