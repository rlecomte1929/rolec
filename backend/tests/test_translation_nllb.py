"""Parker-I — NLLB adapter (HTTP mocked, no network/endpoint)."""
from __future__ import annotations

import os
import sys

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import requests  # noqa: E402 — installed; we patch requests.post

from backend.app.services import translation_nllb as adapter  # noqa: E402
from backend.app.services.translation_types import TranslationUnavailable  # noqa: E402


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_missing_endpoint_raises_unavailable(monkeypatch):
    monkeypatch.delenv("TRANSLATION_NLLB_ENDPOINT", raising=False)
    with pytest.raises(TranslationUnavailable):
        adapter.translate("hello", "en", "de")


def test_translate_posts_flores_codes_and_parses(monkeypatch):
    monkeypatch.setenv("TRANSLATION_NLLB_ENDPOINT", "https://nllb.example/api")
    captured = {}

    def _post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _Resp({"translated_text": "hallo", "model_version": "nllb-test"})

    monkeypatch.setattr(requests, "post", _post)

    out = adapter.translate("hello", "en", "de")

    assert out.provider == "nllb"
    assert out.text == "hallo"
    assert out.model_version == "nllb-test"
    assert captured["url"] == "https://nllb.example/api/translate"
    assert captured["json"]["source_lang"] == "eng_Latn"
    assert captured["json"]["target_lang"] == "deu_Latn"
    assert out.cost_usd == pytest.approx(len("hello") * adapter.USD_PER_CHAR, rel=1e-9)


def test_unknown_lang_falls_back_to_latin_guess(monkeypatch):
    monkeypatch.setenv("TRANSLATION_NLLB_ENDPOINT", "https://nllb.example")
    captured = {}

    def _post(url, json=None, headers=None, timeout=None):
        captured["json"] = json
        return _Resp({"text": "ok"})

    monkeypatch.setattr(requests, "post", _post)
    adapter.translate("hi", "xx", "de")
    assert captured["json"]["source_lang"] == "xx_Latn"


def test_empty_response_raises_unavailable(monkeypatch):
    monkeypatch.setenv("TRANSLATION_NLLB_ENDPOINT", "https://nllb.example")

    def _post(url, json=None, headers=None, timeout=None):
        return _Resp({})

    monkeypatch.setattr(requests, "post", _post)
    with pytest.raises(TranslationUnavailable):
        adapter.translate("hi", "en", "de")


def test_transport_error_becomes_unavailable(monkeypatch):
    monkeypatch.setenv("TRANSLATION_NLLB_ENDPOINT", "https://nllb.example")

    def _post(*a, **k):
        raise requests.ConnectionError("boom")

    monkeypatch.setattr(requests, "post", _post)
    with pytest.raises(TranslationUnavailable):
        adapter.translate("hi", "en", "de")
