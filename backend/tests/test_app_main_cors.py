from fastapi.testclient import TestClient


def test_modular_app_does_not_allow_wildcard_origin_with_credentials(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://relopass.com")
    from importlib import reload
    import backend.app.main as m
    reload(m)
    client = TestClient(m.create_app())
    r = client.options(
        "/health",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert r.headers.get("access-control-allow-origin") != "*"
    assert r.headers.get("access-control-allow-origin") != "https://evil.example"
