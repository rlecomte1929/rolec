"""Parker-I — translation service routing, caching and fallback.

Pure unit tests: the DeepL/NLLB adapters are monkeypatched to deterministic fakes
(no network, no API keys) and persistence runs against an in-memory SQLite DB built
from the ORM Base. A session is passed explicitly to ``translate`` so no global
SessionLocal patching is needed.
"""
from __future__ import annotations

import os
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.db import Base  # noqa: E402
from backend.app import models  # noqa: E402,F401 — registers TranslationCache on Base
from backend.app.services import translation_service as svc  # noqa: E402
from backend.app.services import translation_deepl, translation_nllb  # noqa: E402
from backend.app.services.translation_types import AdapterResult, TranslationUnavailable  # noqa: E402


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture(autouse=True)
def _clear_force_provider(monkeypatch):
    monkeypatch.delenv("TRANSLATION_FORCE_PROVIDER", raising=False)


def _fake(provider: str):
    def _translate(text, src, tgt):
        return AdapterResult(
            text=f"[{provider}:{tgt}] {text}",
            provider=provider,
            model_version=f"{provider}-test",
            cost_usd=round(len(text) * 1e-6, 6),
            quality_score=None,
        )
    return _translate


@pytest.fixture()
def both_providers(monkeypatch):
    monkeypatch.setattr(translation_deepl, "translate", _fake("deepl"))
    monkeypatch.setattr(translation_nllb, "translate", _fake("nllb"))


def test_short_text_routes_to_deepl(session, both_providers):
    out = svc.translate("hallo", "de", "en", domain="comm", session=session)
    assert out.provider == "deepl"
    assert out.cache_hit is False


def test_long_text_routes_to_nllb(session, both_providers):
    long_text = "x" * 600
    out = svc.translate(long_text, "de", "en", domain="policy", session=session)
    assert out.provider == "nllb"


def test_premium_tier_forces_deepl_even_for_long_text(session, both_providers):
    long_text = "y" * 800
    out = svc.translate(long_text, "de", "en", quality_tier="premium", session=session)
    assert out.provider == "deepl"


def test_env_override_forces_provider(session, both_providers, monkeypatch):
    monkeypatch.setenv("TRANSLATION_FORCE_PROVIDER", "nllb")
    out = svc.translate("hallo", "de", "en", session=session)  # short → would be deepl
    assert out.provider == "nllb"


def test_cache_hit_on_second_identical_call(session, both_providers):
    first = svc.translate("guten morgen", "de", "en", domain="comm", session=session)
    assert first.cache_hit is False
    assert first.cost_usd > 0

    second = svc.translate("guten morgen", "de", "en", domain="comm", session=session)
    assert second.cache_hit is True
    assert second.cost_usd == 0.0
    assert second.text == first.text

    # Exactly one row persisted.
    assert session.query(models.TranslationCache).count() == 1


def test_domain_is_part_of_cache_key(session, both_providers):
    svc.translate("same text", "de", "en", domain="comm", session=session)
    svc.translate("same text", "de", "en", domain="policy", session=session)
    assert session.query(models.TranslationCache).count() == 2


def test_falls_back_to_other_provider_when_chosen_unavailable(session, monkeypatch):
    def _unavailable(text, src, tgt):
        raise TranslationUnavailable("no key")
    monkeypatch.setattr(translation_deepl, "translate", _unavailable)
    monkeypatch.setattr(translation_nllb, "translate", _fake("nllb"))

    # Short text would normally pick DeepL; DeepL is down → NLLB serves it.
    out = svc.translate("hi", "de", "en", session=session)
    assert out.provider == "nllb"


def test_raises_when_no_provider_available(session, monkeypatch):
    def _unavailable(text, src, tgt):
        raise TranslationUnavailable("down")
    monkeypatch.setattr(translation_deepl, "translate", _unavailable)
    monkeypatch.setattr(translation_nllb, "translate", _unavailable)
    with pytest.raises(TranslationUnavailable):
        svc.translate("hi", "de", "en", session=session)


def test_blank_text_is_noop(session, both_providers):
    out = svc.translate("   ", "de", "en", session=session)
    assert out.cache_hit is False
    assert out.provider == "none"
    assert session.query(models.TranslationCache).count() == 0
