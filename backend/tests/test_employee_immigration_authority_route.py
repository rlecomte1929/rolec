"""Route contract for GET /api/employee/immigration-authority/{country_code}."""
from backend.app.routers import employee_immigration_authority as route


def test_returns_lookup_payload(monkeypatch):
    monkeypatch.setattr(
        route,
        "lookup_destination_immigration_authority",
        lambda session, code: {"name": "IND", "url": "https://ind.nl/en", "source": "countries.key_authorities"}
        if (code or "").upper() == "NL"
        else None,
    )

    class _Sess:
        def __enter__(self):
            return object()

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(route, "SessionLocal", lambda: _Sess())

    out = route.get_destination_immigration_authority("nl", user={"id": "emp-1"})
    assert out["authority"]["url"] == "https://ind.nl/en"

    missing = route.get_destination_immigration_authority("zz", user={"id": "emp-1"})
    assert missing == {"authority": None}
