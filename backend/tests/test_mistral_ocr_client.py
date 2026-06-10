"""Tests for E-PIPE-OCR Mistral Document AI client.

The HTTP call is monkeypatched, so no network / real key is needed. Covers the
no-key degrade path (returns "") and the page-text join.
"""

from __future__ import annotations

from types import SimpleNamespace

from backend.app.services import mistral_ocr_client as moc


def test_no_key_returns_empty(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    assert moc.mistral_ocr_text(b"bytes", "application/pdf") == ""


def test_joins_page_markdown(monkeypatch):
    captured = {}

    def _fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["auth"] = headers["Authorization"]
        captured["doc_type"] = json["document"]["type"]
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"pages": [{"markdown": "page one"}, {"markdown": "page two"}]},
        )

    monkeypatch.setattr(moc.requests, "post", _fake_post)
    out = moc.mistral_ocr_text(b"pdf-bytes", "application/pdf", api_key="sk-test")
    assert out == "page one\n\npage two"
    assert captured["url"] == "https://api.mistral.ai/v1/ocr"
    assert captured["auth"] == "Bearer sk-test"
    assert captured["doc_type"] == "document_url"  # PDF → document_url channel


def test_image_uses_image_url_channel(monkeypatch):
    captured = {}

    def _fake_post(url, headers=None, json=None, timeout=None):
        captured["doc_type"] = json["document"]["type"]
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"pages": [{"text": "scanned"}]},  # falls back to .text
        )

    monkeypatch.setattr(moc.requests, "post", _fake_post)
    out = moc.mistral_ocr_text(b"img-bytes", "image/png", api_key="sk-test")
    assert out == "scanned"
    assert captured["doc_type"] == "image_url"
