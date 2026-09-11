#!/usr/bin/env python3
"""Digest an official form URL or local PDF into one FormPacket JSON.

Classification is structural, not semantic:

* FILLABLE    — body is a PDF (``%PDF`` magic) and ``PdfReader.get_fields()`` count ≥ 1
* FLATTENED   — body is a PDF and field count is 0
* ONLINE_ONLY — HTML/JS shell, no PDF
* UNVERIFIED  — HTTP 403 or timeout (and other fetch failures that never yielded a body)

Field names and types come from ``pypdf.PdfReader.get_fields()``. Widget geometry
(page, rect, ``/MaxLen`` on the annot) is merged in when annotations exist.
A raw byte scan of ``/FT`` / ``/Widget`` is never used — compressed object
streams hide those tokens (see docs/form-autofill/ACROFORM-FEASIBILITY-DE-FR.md).

This script does not call an LLM, propose vault mappings, or write a migration.
``proposed_mappings`` is always ``[]``; ``choice_groups`` is always ``{}``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import socket
import ssl
import sys
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen as _urlopen

# Browser-shaped UA: several official portals 403 a bot UA and 200 this one.
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
FETCH_TIMEOUT_SECONDS = 30
PDF_MAGIC = b"%PDF"

CLASS_FILLABLE = "FILLABLE"
CLASS_FLATTENED = "FLATTENED"
CLASS_ONLINE_ONLY = "ONLINE_ONLY"
CLASS_UNVERIFIED = "UNVERIFIED"

urlopen = _urlopen


def empty_packet(
    *,
    url: Optional[str] = None,
    pdf: Optional[str] = None,
    classification: str = CLASS_UNVERIFIED,
    http_status: Optional[int] = None,
    content_type: Optional[str] = None,
    sha256: Optional[str] = None,
    page_count: Optional[int] = None,
    fields: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    field_list = fields or []
    return {
        "url": url,
        "pdf": pdf,
        "classification": classification,
        "http_status": http_status,
        "content_type": content_type,
        "sha256": sha256,
        "page_count": page_count,
        "acroform": {
            "field_count": len(field_list),
            "fields": field_list,
        },
        "proposed_mappings": [],
        "choice_groups": {},
    }


def is_pdf_bytes(data: bytes) -> bool:
    return data[:4] == PDF_MAGIC


def looks_like_html_or_js(data: bytes, content_type: Optional[str]) -> bool:
    ct = (content_type or "").lower()
    if "html" in ct or "javascript" in ct or "ecmascript" in ct:
        return True
    head = data[:4096].lstrip().lower()
    if head.startswith(b"<!doctype html") or head.startswith(b"<html"):
        return True
    if b"<script" in head:
        return True
    return False


def _name_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    return text if text.startswith("/") else f"/{text}"


def _as_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_rect(rect: Any) -> Optional[List[float]]:
    if rect is None:
        return None
    try:
        parts = [float(x) for x in rect]
    except (TypeError, ValueError):
        return None
    if len(parts) != 4:
        return None
    return parts


def _widget_name(obj: Any) -> Optional[str]:
    title = obj.get("/T")
    if title:
        return str(title)
    parent = obj.get("/Parent")
    if parent is None:
        return None
    parent_obj = parent.get_object() if hasattr(parent, "get_object") else parent
    title = parent_obj.get("/T")
    return str(title) if title else None


def _widget_index(reader: Any) -> Dict[str, Dict[str, Any]]:
    """First widget per field name: /FT, maxLen, page, rect."""
    by_name: Dict[str, Dict[str, Any]] = {}
    for page_idx, page in enumerate(reader.pages):
        annots = page.annotations
        if not annots:
            continue
        for annot in annots:
            obj = annot.get_object()
            subtype = obj.get("/Subtype")
            if str(subtype) != "/Widget":
                continue
            name = _widget_name(obj)
            if not name or name in by_name:
                continue
            parent = obj.get("/Parent")
            parent_obj = None
            if parent is not None:
                parent_obj = parent.get_object() if hasattr(parent, "get_object") else parent
            ft = obj.get("/FT")
            if ft is None and parent_obj is not None:
                ft = parent_obj.get("/FT")
            max_len = obj.get("/MaxLen")
            if max_len is None and parent_obj is not None:
                max_len = parent_obj.get("/MaxLen")
            by_name[name] = {
                "/FT": _name_str(ft),
                "maxLen": _as_int(max_len),
                "page": page_idx,
                "rect": _as_rect(obj.get("/Rect")),
            }
    return by_name


def extract_acroform_fields(pdf_bytes: bytes) -> tuple[Optional[int], List[Dict[str, Any]]]:
    """Return (page_count, fields) using pypdf only. Raises on unreadable PDF."""
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(pdf_bytes))
    raw = reader.get_fields() or {}
    widgets = _widget_index(reader)
    fields: List[Dict[str, Any]] = []
    for name, field in raw.items():
        widget = widgets.get(str(name), {})
        ft = _name_str(field.get("/FT")) if hasattr(field, "get") else None
        if ft is None:
            ft = widget.get("/FT")
        max_len = _as_int(field.get("/MaxLen")) if hasattr(field, "get") else None
        if max_len is None:
            max_len = widget.get("maxLen")
        page = widget.get("page")
        rect = widget.get("rect")
        fields.append(
            {
                "name": str(name),
                "/FT": ft,
                "maxLen": max_len,
                "page": page,
                "rect": rect,
            }
        )
    return len(reader.pages), fields


def digest_pdf_bytes(
    pdf_bytes: bytes,
    *,
    url: Optional[str] = None,
    pdf: Optional[str] = None,
    http_status: Optional[int] = None,
    content_type: Optional[str] = None,
) -> Dict[str, Any]:
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    try:
        page_count, fields = extract_acroform_fields(pdf_bytes)
    except Exception:  # noqa: BLE001 — unreadable AcroForm is not a fillable form
        packet = empty_packet(
            url=url,
            pdf=pdf,
            classification=CLASS_UNVERIFIED,
            http_status=http_status,
            content_type=content_type,
            sha256=digest,
        )
        return packet
    classification = CLASS_FILLABLE if fields else CLASS_FLATTENED
    return empty_packet(
        url=url,
        pdf=pdf,
        classification=classification,
        http_status=http_status,
        content_type=content_type,
        sha256=digest,
        page_count=page_count,
        fields=fields,
    )


def digest_body(
    body: bytes,
    *,
    url: Optional[str] = None,
    pdf: Optional[str] = None,
    http_status: Optional[int] = None,
    content_type: Optional[str] = None,
) -> Dict[str, Any]:
    if is_pdf_bytes(body):
        return digest_pdf_bytes(
            body,
            url=url,
            pdf=pdf,
            http_status=http_status,
            content_type=content_type,
        )
    if looks_like_html_or_js(body, content_type):
        return empty_packet(
            url=url,
            pdf=pdf,
            classification=CLASS_ONLINE_ONLY,
            http_status=http_status,
            content_type=content_type,
        )
    return empty_packet(
        url=url,
        pdf=pdf,
        classification=CLASS_UNVERIFIED,
        http_status=http_status,
        content_type=content_type,
    )


def _unverified(
    *,
    url: Optional[str] = None,
    http_status: Optional[int] = None,
    content_type: Optional[str] = None,
) -> Dict[str, Any]:
    return empty_packet(
        url=url,
        classification=CLASS_UNVERIFIED,
        http_status=http_status,
        content_type=content_type,
    )


def _is_timeout(exc: BaseException) -> bool:
    if isinstance(exc, TimeoutError):
        return True
    if isinstance(exc, socket.timeout):
        return True
    reason = getattr(exc, "reason", None)
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return True
    return "timed out" in str(exc).lower()


def fetch_url(url: str) -> tuple[Optional[int], Optional[str], Optional[bytes], Optional[str]]:
    """GET ``url`` with a browser User-Agent.

    Returns (status, content_type, body, error) where error is ``forbidden``,
    ``timeout``, or another short reason. On error, body is None.
    """
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("url must be official HTTPS")
    request = Request(
        url,
        headers={
            "User-Agent": BROWSER_USER_AGENT,
            "Accept": "application/pdf,text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.9",
        },
    )
    try:
        with urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as resp:
            status = getattr(resp, "status", None) or getattr(resp, "code", None)
            content_type = resp.headers.get("Content-Type") if resp.headers else None
            body = resp.read()
            return status, content_type, body, None
    except HTTPError as exc:
        if exc.code == 403:
            return 403, exc.headers.get("Content-Type") if exc.headers else None, None, "forbidden"
        content_type = exc.headers.get("Content-Type") if exc.headers else None
        try:
            body = exc.read()
        except Exception:  # noqa: BLE001
            body = None
        if body:
            return exc.code, content_type, body, None
        return exc.code, content_type, None, f"http_{exc.code}"
    except (TimeoutError, socket.timeout) as exc:
        return None, None, None, "timeout" if _is_timeout(exc) else "timeout"
    except URLError as exc:
        if _is_timeout(exc):
            return None, None, None, "timeout"
        return None, None, None, "urlerror"
    except ssl.SSLError:
        return None, None, None, "ssl"


def digest_url(url: str) -> Dict[str, Any]:
    status, content_type, body, error = fetch_url(url)
    if error == "forbidden":
        return _unverified(url=url, http_status=403, content_type=content_type)
    if error == "timeout":
        return _unverified(url=url, http_status=status, content_type=content_type)
    if body is None:
        return _unverified(url=url, http_status=status, content_type=content_type)
    return digest_body(
        body, url=url, http_status=status, content_type=content_type
    )


def digest_pdf_path(path: Path) -> Dict[str, Any]:
    data = path.read_bytes()
    return digest_body(data, pdf=str(path))


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Digest an official form URL or local PDF into one FormPacket JSON."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="Official HTTPS URL of the form or portal")
    group.add_argument("--pdf", help="Local PDF path")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.url:
        try:
            packet = digest_url(args.url)
        except ValueError as exc:
            print(f"digest_form: {exc}", file=sys.stderr)
            return 2
    else:
        path = Path(args.pdf)
        if not path.is_file():
            print(f"digest_form: not a file: {path}", file=sys.stderr)
            return 2
        packet = digest_pdf_path(path)
    json.dump(packet, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
