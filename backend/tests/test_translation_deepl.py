"""Parker-I — DeepL adapter (SDK mocked, no network/keys)."""
from __future__ import annotations

import os
import sys
import types

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services import translation_deepl as adapter  # noqa: E402
from backend.app.services.translation_types import TranslationUnavailable  # noqa: E402


def _install_fake_deepl(monkeypatch, captured):
    class _Result:
        def __init__(self, text):
            self.text = text

    class _Translator:
        def __init__(self, api_key):
            captured["api_key"] = api_key

        def translate_text(self, text, source_lang=None, target_lang=None):
            captured["source_lang"] = source_lang
            captured["target_lang"] = target_lang
            return _Result(f"<{target_lang}>{text}")

    fake = types.ModuleType("deepl")
    fake.Translator = _Translator
    monkeypatch.setitem(sys.modules, "deepl", fake)


def test_missing_api_key_raises_unavailable(monkeypatch):
    monkeypatch.delenv("DEEPL_API_KEY", raising=False)
    with pytest.raises(TranslationUnavailable):
        adapter.translate("hello", "en", "de")


def test_translate_uses_sdk_and_records_cost(monkeypatch):
    monkeypatch.setenv("DEEPL_API_KEY", "k-123")
    captured = {}
    _install_fake_deepl(monkeypatch, captured)

    out = adapter.translate("hello", "en", "de")

    assert out.provider == "deepl"
    assert out.model_version == "deepl-pro"
    assert out.text == "<DE>hello"
    assert captured["api_key"] == "k-123"
    # Source code strips region, target keeps it; bare 'de' → 'DE'.
    assert captured["source_lang"] == "EN"
    assert captured["target_lang"] == "DE"
    # Cost is per-character.
    assert out.cost_usd == pytest.approx(len("hello") * adapter.USD_PER_CHAR, rel=1e-9)


def test_target_region_is_preserved(monkeypatch):
    monkeypatch.setenv("DEEPL_API_KEY", "k")
    captured = {}
    _install_fake_deepl(monkeypatch, captured)
    adapter.translate("hi", "en-US", "en-GB")
    assert captured["source_lang"] == "EN"
    assert captured["target_lang"] == "EN-GB"


def test_sdk_exception_becomes_unavailable(monkeypatch):
    monkeypatch.setenv("DEEPL_API_KEY", "k")

    class _Boom:
        def __init__(self, *a, **k):
            pass

        def translate_text(self, *a, **k):
            raise RuntimeError("deepl 456")

    fake = types.ModuleType("deepl")
    fake.Translator = _Boom
    monkeypatch.setitem(sys.modules, "deepl", fake)

    with pytest.raises(TranslationUnavailable):
        adapter.translate("hi", "en", "de")
