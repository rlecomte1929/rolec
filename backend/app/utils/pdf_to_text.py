"""PDF bytes → plain text. Shared utility (reused as more document types land).

[FRIDAY-005] Used by the employee-briefing endpoint to turn a policy PDF
(downloaded from storage) into text when the intake-cached ``policy_documents.raw_text``
isn't available. Uses ``pypdf`` (pinned in backend/requirements.txt).

Sync, not async: ``pypdf`` extraction is CPU-bound and the HR routers in this
codebase are sync (FastAPI runs them in a threadpool), so an async signature would
add an awkward ``asyncio.run`` round-trip without any concurrency benefit.
"""
from __future__ import annotations

import hashlib
import io
import re
from typing import Dict


def _normalize_whitespace(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)        # collapse runs of spaces/tabs
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)      # collapse blank-line runs
    return text.strip()


def pdf_bytes_to_text(pdf_bytes: bytes) -> str:
    """Extract plain text from PDF bytes, with excess whitespace stripped.

    Raises ``ValueError`` if the bytes can't be parsed or yield no text — the
    caller maps that to a 422 ("Could not extract text from policy document").
    """
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
    except Exception as exc:  # malformed/encrypted/not-a-PDF
        raise ValueError(f"Could not read PDF: {exc}") from exc

    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            parts.append("")  # a single unreadable page shouldn't fail the whole doc

    text = _normalize_whitespace("\n\n".join(parts))
    if not text:
        raise ValueError("No extractable text in PDF (scanned/image-only?)")
    return text


# Policy PDFs change rarely, so cache the (expensive) extraction in-process,
# keyed on the content hash. TODO [FRIDAY-005 follow-up]: replace this unbounded
# in-process dict with Redis when the endpoint moves past single-instance.
_TEXT_CACHE: Dict[str, str] = {}


def pdf_bytes_to_text_cached(pdf_bytes: bytes) -> str:
    """``pdf_bytes_to_text`` memoised on the content SHA-256."""
    key = hashlib.sha256(pdf_bytes).hexdigest()
    cached = _TEXT_CACHE.get(key)
    if cached is None:
        cached = pdf_bytes_to_text(pdf_bytes)
        _TEXT_CACHE[key] = cached
    return cached
