"""AIQ-945 / C2-03-FU criterion 5 — weekly corrections digest.

Covers the testable acceptance: the digest renders for a 0-correction week AND a
mixed-reason week; delivery is best-effort (no RESEND_API_KEY → logged, no raise);
the run endpoint is admin-only (403 for non-admin).
"""

import os
from datetime import date

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.app.services import corrections_digest as cd  # noqa: E402
from backend.app.services.correction_analytics import REASON_CODES  # noqa: E402

_WK = date(2026, 6, 1)


# ── render (the acceptance core) ─────────────────────────────────────────────

def test_render_zero_correction_week():
    totals = {c: 0 for c in REASON_CODES}
    out = cd.render_corrections_digest(totals, _WK)
    assert _WK.isoformat() in out["subject"]
    assert "No corrections" in out["text"]
    # every one of the 6 reasons is listed (zero-filled)
    for c in REASON_CODES:
        assert c in out["text"]
    assert out["html"].startswith("<h2>")


def test_render_mixed_reason_week():
    totals = {c: 0 for c in REASON_CODES}
    totals.update({"OCR_ERROR": 3, "FRAUD_SUSPECTED": 1, "OTHER": 2})
    out = cd.render_corrections_digest(totals, _WK)
    assert "OCR_ERROR): 3" in out["text"]
    assert "FRAUD_SUSPECTED): 1" in out["text"]
    assert "OTHER): 2" in out["text"]
    assert "TYPO_IN_SOURCE): 0" in out["text"]  # zero-fill on absent codes
    assert "3 correction(s)" not in out["text"]  # total is 6, not 3
    assert "6 correction(s)" in out["text"]


# ── run: best-effort delivery, never raises ──────────────────────────────────

@pytest.fixture
def _no_resend(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    # Avoid the DB — canned weekly rows.
    monkeypatch.setattr(
        cd, "weekly_corrections_by_reason",
        lambda employer_id=None, weeks_back=1: [
            {"reason_code": "OCR_ERROR", "count": 4},
            {"reason_code": "OTHER", "count": 1},
        ],
    )
    yield


def test_run_no_recipients_logs_and_ok(_no_resend, monkeypatch):
    monkeypatch.delenv("CORRECTIONS_DIGEST_TO", raising=False)
    out = cd.run_corrections_digest()
    assert out["ok"] is True
    assert out["total"] == 5
    assert out["totals"]["OCR_ERROR"] == 4
    assert out["results"] == [{"to": None, "status": "no_recipients"}]


def test_run_with_recipient_no_key_logs(_no_resend, monkeypatch):
    monkeypatch.setenv("CORRECTIONS_DIGEST_TO", "ops@relopass.com, founder@relopass.com")
    out = cd.run_corrections_digest()
    assert out["ok"] is True
    assert {r["to"] for r in out["results"]} == {"ops@relopass.com", "founder@relopass.com"}
    # no RESEND_API_KEY → best-effort "no_key", never raises
    assert all(r["status"] == "no_key" for r in out["results"])


# ── endpoint: admin-only ─────────────────────────────────────────────────────

def test_digest_run_endpoint_403_for_non_admin():
    from backend.main import app
    import backend.app.auth_deps as auth_deps

    app.dependency_overrides[auth_deps.get_current_user] = lambda: {
        "id": "u-emp", "role": "EMPLOYEE", "is_admin": False,
    }
    try:
        client = TestClient(app)
        r = client.post("/api/admin/corrections/digest/run")
        assert r.status_code == 403
    finally:
        app.dependency_overrides.clear()
