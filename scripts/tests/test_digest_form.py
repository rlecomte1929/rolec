"""Offline tests for scripts/digest_form.py against committed fixtures.

Network is mocked. Classification of the fillable vs flattened PDFs is the
load-bearing check: the flattened fixture contains the strings ``/FT`` and
``/Widget`` as page text, so a byte-grep would falsely call it FILLABLE.
"""
from __future__ import annotations

import ast
import hashlib
import io
import json
import socket
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import digest_form as df  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "digest_form"
FILLABLE = FIXTURES / "fillable.pdf"
FLATTENED = FIXTURES / "flattened.pdf"
ONLINE_HTML = FIXTURES / "online_only.html"
OFFICIAL_URL = "https://france-visas.gouv.fr/documents/d/france-visas/ls_14571-05_fr_09"


def _packet_from_stdout(argv: list[str]) -> dict:
    buf = io.StringIO()
    err = io.StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout, sys.stderr = buf, err
        code = df.main(argv)
    finally:
        sys.stdout, sys.stderr = old_out, old_err
    assert code == 0, err.getvalue()
    return json.loads(buf.getvalue())


class _FakeResponse:
    def __init__(self, body: bytes, status: int = 200, content_type: str = "application/pdf"):
        self.status = status
        self.code = status
        self.headers = {"Content-Type": content_type}
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False


def test_fixtures_are_committed():
    assert FILLABLE.is_file() and FILLABLE.read_bytes()[:4] == b"%PDF"
    assert FLATTENED.is_file() and FLATTENED.read_bytes()[:4] == b"%PDF"
    assert ONLINE_HTML.is_file()
    # Trap: flattened page text contains tokens a byte-grep would treat as fields.
    assert b"/FT" in FLATTENED.read_bytes()
    assert b"/Widget" in FLATTENED.read_bytes()


def test_pdf_fillable_enumerates_widgets():
    packet = _packet_from_stdout(["--pdf", str(FILLABLE)])
    assert packet["classification"] == df.CLASS_FILLABLE
    assert packet["proposed_mappings"] == []
    assert packet["choice_groups"] == {}
    assert packet["sha256"] == hashlib.sha256(FILLABLE.read_bytes()).hexdigest()
    assert packet["page_count"] == 2
    assert packet["acroform"]["field_count"] == 3
    by_name = {f["name"]: f for f in packet["acroform"]["fields"]}
    family = by_name["family_name"]
    assert family["/FT"] == "/Tx"
    assert family["maxLen"] == 40
    assert family["page"] == 0
    assert family["rect"] == [100.0, 700.0, 300.0, 716.0]
    assert by_name["eu_citizen"]["/FT"] == "/Btn"
    assert by_name["eu_citizen"]["page"] == 0
    assert by_name["notes"]["page"] == 1
    assert by_name["notes"]["rect"] is not None


def test_pdf_flattened_despite_ft_tokens_in_page_text():
    packet = _packet_from_stdout(["--pdf", str(FLATTENED)])
    assert packet["classification"] == df.CLASS_FLATTENED
    assert packet["acroform"]["field_count"] == 0
    assert packet["acroform"]["fields"] == []
    assert packet["proposed_mappings"] == []
    assert packet["choice_groups"] == {}


def test_url_pdf_uses_browser_user_agent(monkeypatch):
    seen: list[str] = []
    body = FILLABLE.read_bytes()

    def fake_urlopen(req: Request, timeout=None):
        seen.append(req.get_header("User-agent") or req.get_header("User-Agent") or "")
        assert timeout == df.FETCH_TIMEOUT_SECONDS
        return _FakeResponse(body, content_type="application/pdf")

    monkeypatch.setattr(df, "urlopen", fake_urlopen)
    packet = _packet_from_stdout(["--url", OFFICIAL_URL])
    assert seen, "GET must happen"
    assert seen[0] == df.BROWSER_USER_AGENT
    assert packet["classification"] == df.CLASS_FILLABLE
    assert packet["url"] == OFFICIAL_URL
    assert packet["http_status"] == 200
    assert packet["sha256"] == hashlib.sha256(body).hexdigest()
    assert packet["proposed_mappings"] == []


def test_url_html_js_shell_is_online_only(monkeypatch):
    html = ONLINE_HTML.read_bytes()

    def fake_urlopen(req: Request, timeout=None):
        return _FakeResponse(html, content_type="text/html; charset=utf-8")

    monkeypatch.setattr(df, "urlopen", fake_urlopen)
    packet = _packet_from_stdout(["--url", "https://videx.diplo.de/videx/visum-erfassung/de/videx-langfristiger-aufenthalt"])
    assert packet["classification"] == df.CLASS_ONLINE_ONLY
    assert packet["acroform"]["field_count"] == 0
    assert packet["sha256"] is None
    assert packet["choice_groups"] == {}


def test_url_403_is_unverified(monkeypatch):
    def fake_urlopen(req: Request, timeout=None):
        raise HTTPError(req.full_url, 403, "Forbidden", hdrs={"Content-Type": "text/html"}, fp=None)

    monkeypatch.setattr(df, "urlopen", fake_urlopen)
    packet = _packet_from_stdout(["--url", OFFICIAL_URL])
    assert packet["classification"] == df.CLASS_UNVERIFIED
    assert packet["http_status"] == 403
    assert packet["acroform"]["fields"] == []
    assert packet["proposed_mappings"] == []


def test_url_timeout_is_unverified(monkeypatch):
    def fake_urlopen(req: Request, timeout=None):
        raise URLError(socket.timeout("timed out"))

    monkeypatch.setattr(df, "urlopen", fake_urlopen)
    packet = _packet_from_stdout(["--url", OFFICIAL_URL])
    assert packet["classification"] == df.CLASS_UNVERIFIED
    assert packet["sha256"] is None


def test_pdf_magic_wins_over_html_content_type(monkeypatch):
    body = FILLABLE.read_bytes()

    def fake_urlopen(req: Request, timeout=None):
        return _FakeResponse(body, content_type="text/html")

    monkeypatch.setattr(df, "urlopen", fake_urlopen)
    packet = _packet_from_stdout(["--url", OFFICIAL_URL])
    assert packet["classification"] == df.CLASS_FILLABLE


def test_html_body_not_classified_as_pdf_from_content_type(monkeypatch):
    html = ONLINE_HTML.read_bytes()

    def fake_urlopen(req: Request, timeout=None):
        return _FakeResponse(html, content_type="application/pdf")

    monkeypatch.setattr(df, "urlopen", fake_urlopen)
    packet = _packet_from_stdout(["--url", OFFICIAL_URL])
    assert packet["classification"] == df.CLASS_ONLINE_ONLY


def test_http_url_rejected():
    err = io.StringIO()
    old_err = sys.stderr
    try:
        sys.stderr = err
        code = df.main(["--url", "http://example.test/form.pdf"])
    finally:
        sys.stderr = old_err
    assert code == 2
    assert "HTTPS" in err.getvalue()


def test_script_does_not_import_llm_or_vault():
    tree = ast.parse(Path(df.__file__).read_text(encoding="utf-8"))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(n.name.split(".")[0] for n in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module.split(".")[0])
    banned = {"openai", "anthropic", "langchain", "langsmith", "langfuse"}
    assert banned.isdisjoint(imported)
    source = Path(df.__file__).read_text(encoding="utf-8")
    assert "vault_field_path" not in source
    assert "supabase" not in source.lower()
