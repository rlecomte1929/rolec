"""Two guards that never ran, because a shadow route won the match.

`backend/routes/compat.py` is included at `backend/main.py:827`, ahead of every modular
router, and FastAPI matches the FIRST registered route. So each compat handler wins and its
modular twin is dead code. AIQ-1535 noticed this for `GET /api/cases/{id}` and added the
tenant guard to the *winner*. The other two were left:

  GET /api/cases/{id}/requirements  winner had NO tenant guard; the dead copy had one
  GET /api/admin/context            winner had NO auth at all; the dead copy had require_admin

`compat_get_requirements` authenticated the caller and then never used `user` to authorise,
reading through the service-role connection which bypasses RLS — any authenticated session
could read any case's requirements, and with them the case's origin and destination country.

`compat_admin_context` had no `Depends` of any kind and granted `admin_or_hr` from an
UNVERIFIED JWT claim (`_jwt_claims.py`: "No signature verification"), so a hand-made base64
blob claiming an `@relopass.com` email was enough. It was deleted so the guarded
`backend/main.py` handler wins.

THE ROUTE-ORDER ASSERTIONS ARE THE POINT. A guard on a shadowed handler protects nothing, so
these tests pin WHICH module serves each path. If the order changes, they fail loudly rather
than letting the protection silently move to a handler nobody calls.
"""
from __future__ import annotations

import base64
import json
import os
import sys

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402

client = TestClient(app)


def _handlers_for(path: str):
    return [
        r.endpoint.__module__
        for r in app.routes
        if getattr(r, "path", "") == path and getattr(r, "endpoint", None) is not None
    ]


def _forged_unsigned_jwt(email: str = "attacker@relopass.com") -> str:
    """A syntactically valid, cryptographically worthless JWT.

    Three base64 segments is all `_is_jwt` checks and all the unverified decoder needs.
    """
    def seg(obj):
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")

    return f"{seg({'alg': 'none'})}.{seg({'email': email, 'role': 'admin', 'sub': 'x'})}.not-a-signature"


# ── GET /api/admin/context ───────────────────────────────────────────────────────────

def test_admin_context_is_served_by_the_guarded_handler():
    handlers = _handlers_for("/api/admin/context")
    assert handlers, "the admin context route disappeared"
    assert handlers[0] == "backend.main", (
        f"first-match handler is {handlers[0]!r}; the compat shadow is back and it has no "
        "auth dependency"
    )
    assert "backend.routes.compat" not in handlers, "the unguarded compat shadow was re-added"


def test_admin_context_rejects_an_unauthenticated_caller():
    res = client.get("/api/admin/context")
    assert res.status_code in (401, 403), (
        f"expected a refusal, got {res.status_code} {res.text[:200]}"
    )


def test_admin_context_validates_the_token_instead_of_trusting_its_claims():
    """The surviving handler must resolve the caller through `require_admin`.

    That dependency runs `get_current_user`, which looks the token up in the database
    (`db.get_user_context_by_token`) and 401s when it resolves to nobody — so a claim in the
    token buys nothing. The deleted compat handler never consulted the database at all; it
    decoded the payload with a decoder whose own docstring says "No signature verification"
    and granted `admin_or_hr` on the claimed email.

    ASSERTED STRUCTURALLY, ON PURPOSE. `backend/conftest.py:35` replaces `backend.database`
    with a MagicMock, so `get_user_context_by_token` returns a truthy mock for ANY token and
    every auth check passes in this suite. A runtime "forged token gets 401" assertion would
    therefore pass or fail for reasons that have nothing to do with the product. Proving the
    dependency is wired is the honest assertion available here; the runtime behaviour belongs
    in an integration test with a real database.
    """
    route = next(
        r for r in app.routes
        if getattr(r, "path", "") == "/api/admin/context"
    )
    dep_names = {d.call.__name__ for d in route.dependant.dependencies if d.call}
    assert "require_admin" in dep_names, (
        f"/api/admin/context no longer depends on require_admin (deps: {dep_names})"
    )

    # And the forged-claim shape the deleted handler emitted must be gone for good.
    forged = _forged_unsigned_jwt()
    assert "admin_or_hr" not in client.get(
        "/api/admin/context", headers={"Authorization": f"Bearer {forged}"}
    ).text


# ── GET /api/cases/{id}/requirements ─────────────────────────────────────────────────

def test_requirements_is_served_by_compat_and_compat_has_the_guard():
    """The guard must live in the handler that actually runs."""
    handlers = _handlers_for("/api/cases/{case_id}/requirements")
    assert handlers, "the requirements route disappeared"
    assert handlers[0] == "backend.routes.compat", (
        f"first-match handler is now {handlers[0]!r}; move the tenant guard there"
    )

    import inspect

    from backend.routes import compat

    src = inspect.getsource(compat.compat_get_requirements)
    assert "_assert_case_access" in src, (
        "the serving handler lost its tenant guard — any authenticated session can then read "
        "any case's requirements and corridor"
    )


def test_requirements_rejects_an_unauthenticated_caller():
    res = client.get("/api/cases/some-case-id/requirements")
    assert res.status_code in (401, 403), (
        f"expected a refusal, got {res.status_code} {res.text[:200]}"
    )
