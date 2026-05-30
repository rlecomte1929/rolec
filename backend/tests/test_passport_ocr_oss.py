"""
Tests for the OSS passport-OCR fallback + shadow comparison — Parker Step F.

The heavy ML inference (PaddleOCR / Florence-2) cannot run in CI, so these tests
exercise the reviewed surface: the pure diff + confidence logic, the env-driven
router split, the best-effort shadow logging, and the admin rollup route. An
in-memory SQLite DB stands in for the ocr_shadow_comparisons table.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services import passport_ocr_oss as oss  # noqa: E402
from backend.app.services.ocr_passport_extractor import (  # noqa: E402
    OcrExtractionError,
    PassportExtractionResult,
)
from backend.app.routers import admin_ocr_shadow  # noqa: E402
from backend.app.auth_deps import require_admin  # noqa: E402
from backend.relopass.llm import router as llm_router  # noqa: E402


_SCHEMA = """
CREATE TABLE ocr_shadow_comparisons (
  id TEXT PRIMARY KEY,
  created_at TEXT,
  case_id TEXT,
  mrz_pass_gpt4o INTEGER NOT NULL DEFAULT 0,
  mrz_pass_oss INTEGER NOT NULL DEFAULT 0,
  field_agreement TEXT NOT NULL DEFAULT '{}',
  compared_count INTEGER NOT NULL DEFAULT 0,
  agreed_count INTEGER NOT NULL DEFAULT 0,
  disagreement_count INTEGER NOT NULL DEFAULT 0,
  gpt4o_cost_usd REAL NOT NULL DEFAULT 0,
  oss_cost_usd REAL NOT NULL DEFAULT 0
)
"""


@pytest.fixture
def sqlite_sessionmaker(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as conn:
        conn.execute(text(_SCHEMA))
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(oss, "SessionLocal", Session)
    return Session


def _result(**overrides) -> PassportExtractionResult:
    base = dict(
        surname="SMITH",
        given_names="JOHN MICHAEL",
        date_of_birth="1985-03-15",
        gender="M",
        place_of_birth="LONDON",
        nationality="GBR",
        issuing_country="GBR",
        passport_number="AB1234567",
        issue_date="2020-01-10",
        expiry_date="2030-01-09",
    )
    base.update(overrides)
    return PassportExtractionResult(**base)


# ── Pure diff ─────────────────────────────────────────────────────────────────


def test_identical_extractions_have_no_disagreement():
    diff = oss.diff_extractions(_result(), _result())
    assert diff.disagreement_count == 0
    assert diff.compared_count == len(oss.COMPARABLE_FIELDS)
    assert diff.agreement_rate == 1.0
    assert all(diff.field_agreement.values())


def test_two_field_disagreement_is_counted():
    gpt4o = _result()
    o = _result(surname="SMYTHE", expiry_date="2031-01-09")
    diff = oss.diff_extractions(gpt4o, o)
    assert diff.disagreement_count == 2
    assert diff.field_agreement["surname"] is False
    assert diff.field_agreement["expiry_date"] is False
    assert diff.field_agreement["given_names"] is True


def test_field_empty_in_both_is_skipped():
    gpt4o = _result(place_of_birth=None)
    o = _result(place_of_birth=None)
    diff = oss.diff_extractions(gpt4o, o)
    assert "place_of_birth" not in diff.field_agreement
    assert diff.compared_count == len(oss.COMPARABLE_FIELDS) - 1


def test_mrz_pass_flag_false_without_mrz_lines():
    diff = oss.diff_extractions(_result(), _result())
    assert diff.mrz_pass_gpt4o is False
    assert diff.mrz_pass_oss is False


# ── Confidence heuristic ──────────────────────────────────────────────────────


def test_confidence_heuristic():
    assert oss.heuristic_confidence("GBR", "GBR") == 0.95
    assert oss.heuristic_confidence("GBR", None) == 0.60
    assert oss.heuristic_confidence(None, "GBR") == 0.60
    assert oss.heuristic_confidence("GBR", "FRA") == 0.40
    assert oss.heuristic_confidence(None, None) == 0.0


# ── Router split helpers ──────────────────────────────────────────────────────


def test_oss_share_default_and_clamping(monkeypatch):
    monkeypatch.delenv("PASSPORT_OCR_OSS_SHARE", raising=False)
    assert llm_router.passport_ocr_oss_share() == 0.0
    monkeypatch.setenv("PASSPORT_OCR_OSS_SHARE", "2.0")
    assert llm_router.passport_ocr_oss_share() == 1.0
    monkeypatch.setenv("PASSPORT_OCR_OSS_SHARE", "-1")
    assert llm_router.passport_ocr_oss_share() == 0.0
    monkeypatch.setenv("PASSPORT_OCR_OSS_SHARE", "not-a-number")
    assert llm_router.passport_ocr_oss_share() == 0.0


def test_shadow_compare_enabled(monkeypatch):
    monkeypatch.delenv("SHADOW_COMPARE", raising=False)
    assert llm_router.shadow_compare_enabled() is False
    for truthy in ("1", "true", "YES", "on"):
        monkeypatch.setenv("SHADOW_COMPARE", truthy)
        assert llm_router.shadow_compare_enabled() is True
    monkeypatch.setenv("SHADOW_COMPARE", "false")
    assert llm_router.shadow_compare_enabled() is False


def test_choose_backend_default_is_gpt4o():
    assert llm_router.choose_passport_ocr_backend(0.0, share=0.0) == "gpt4o"
    assert llm_router.choose_passport_ocr_backend(0.05, share=0.10) == "oss"
    assert llm_router.choose_passport_ocr_backend(0.20, share=0.10) == "gpt4o"


# ── Shadow logging ────────────────────────────────────────────────────────────


def test_record_shadow_comparison_writes_row(sqlite_sessionmaker):
    diff = oss.diff_extractions(_result(), _result(surname="SMYTHE"))
    s = sqlite_sessionmaker()
    try:
        row_id = oss.record_shadow_comparison(diff, case_id="case-1", session=s)
        assert row_id is not None
        n = s.execute(text("SELECT COUNT(*) FROM ocr_shadow_comparisons")).scalar()
        dc = s.execute(text("SELECT disagreement_count FROM ocr_shadow_comparisons")).scalar()
        fa = s.execute(text("SELECT field_agreement FROM ocr_shadow_comparisons")).scalar()
    finally:
        s.close()
    assert n == 1
    assert dc == 1
    assert json.loads(fa)["surname"] is False


def test_extract_passport_shadow_returns_gpt4o_and_logs(sqlite_sessionmaker):
    gpt4o_out = _result()
    oss_out = _result(surname="SMYTHE", nationality="FRA")

    async def fake_gpt4o(image_bytes, mime_type):
        return gpt4o_out

    async def fake_oss(image_bytes, mime_type):
        return oss_out

    returned = asyncio.run(
        oss.extract_passport_shadow(
            b"img",
            gpt4o_extractor=fake_gpt4o,
            oss_extractor=fake_oss,
            case_id="case-2",
        )
    )
    assert returned is gpt4o_out  # caller always gets GPT-4o

    s = sqlite_sessionmaker()
    try:
        n = s.execute(text("SELECT COUNT(*) FROM ocr_shadow_comparisons")).scalar()
        dc = s.execute(text("SELECT disagreement_count FROM ocr_shadow_comparisons")).scalar()
    finally:
        s.close()
    assert n == 1
    assert dc == 2  # surname + nationality differ


def test_shadow_returns_gpt4o_even_if_oss_raises(sqlite_sessionmaker):
    gpt4o_out = _result()

    async def fake_gpt4o(image_bytes, mime_type):
        return gpt4o_out

    async def boom(image_bytes, mime_type):
        raise OcrExtractionError("oss_backend_unavailable", "nope")

    returned = asyncio.run(
        oss.extract_passport_shadow(b"img", gpt4o_extractor=fake_gpt4o, oss_extractor=boom)
    )
    assert returned is gpt4o_out
    s = sqlite_sessionmaker()
    try:
        n = s.execute(text("SELECT COUNT(*) FROM ocr_shadow_comparisons")).scalar()
    finally:
        s.close()
    assert n == 0  # no shadow row when OSS failed


# ── OSS backend unavailable ───────────────────────────────────────────────────


def test_oss_extract_without_ml_deps_raises():
    with pytest.raises(OcrExtractionError) as exc:
        asyncio.run(oss.extract_passport(b"img"))
    assert exc.value.code == "oss_backend_unavailable"


# ── Admin rollup route ────────────────────────────────────────────────────────


def _seed_rows(Session):
    s = Session()
    try:
        rows = [
            # agreed 8/10, mrz both pass, costs
            ("r1", "2026-05-01T10:00:00+00:00", 1, 1, 10, 8, 2, 0.00765, 0.00040),
            # agreed 10/10, mrz gpt4o pass / oss fail
            ("r2", "2026-05-02T10:00:00+00:00", 1, 0, 10, 10, 0, 0.00765, 0.00040),
        ]
        for r in rows:
            s.execute(
                text(
                    "INSERT INTO ocr_shadow_comparisons "
                    "(id, created_at, mrz_pass_gpt4o, mrz_pass_oss, compared_count, "
                    " agreed_count, disagreement_count, gpt4o_cost_usd, oss_cost_usd) "
                    "VALUES (:id, :ca, :mg, :mo, :cc, :ac, :dc, :gc, :oc)"
                ),
                {"id": r[0], "ca": r[1], "mg": r[2], "mo": r[3], "cc": r[4],
                 "ac": r[5], "dc": r[6], "gc": r[7], "oc": r[8]},
            )
        s.commit()
    finally:
        s.close()


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(admin_ocr_shadow.router)
    app.dependency_overrides[require_admin] = lambda: {"id": "admin-1", "is_admin": True}
    return app


def test_rollup_route_returns_well_formed(sqlite_sessionmaker):
    _seed_rows(sqlite_sessionmaker)
    client = TestClient(_app())
    r = client.get("/api/admin/ocr-shadow-comparison")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["n"] == 2
    # 18 agreed / 20 compared
    assert body["field_agreement_rate"] == 0.9
    assert body["mrz_pass_rate_gpt4o"] == 1.0
    assert body["mrz_pass_rate_oss"] == 0.5
    assert body["avg_cost_usd_gpt4o"] == pytest.approx(0.00765, rel=1e-3)
    assert body["disagreement_count"] == 2


def test_rollup_route_empty_range_is_zeroed(sqlite_sessionmaker):
    client = TestClient(_app())
    r = client.get("/api/admin/ocr-shadow-comparison", params={"from": "2099-01-01", "to": "2099-12-31"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["n"] == 0
    assert body["field_agreement_rate"] == 0.0
    assert body["avg_cost_usd_oss"] == 0.0
