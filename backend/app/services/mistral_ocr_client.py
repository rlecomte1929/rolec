"""E-PIPE-OCR · Mistral Document AI — the general OCR engine.

Gives the rce extraction pipeline the engine it was missing: every non-passport
document (marriage/birth certs, foster orders, tax certs, diplomas) gets real
text via Mistral's Document AI OCR API. Passport/ID MRZ documents keep using the
existing GPT-4o extractor — ``rce_ocr_parser`` routes those; this is only invoked
for the general types.

GDPR (PRIV-004): Mistral is a sub-processor receiving document content. OCR sends
the document image/PDF itself — you cannot ``mask_pii`` an image you must OCR, so
this mirrors the existing GPT-4o passport path. Never log the returned text; it is
PHI. ``MISTRAL_API_KEY`` is the only new env var (see ``.env.example``).
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Optional

import requests

log = logging.getLogger(__name__)

_OCR_URL = "https://api.mistral.ai/v1/ocr"
_MODEL = "mistral-ocr-latest"
_TIMEOUT_S = 60


def mistral_ocr_text(
    content: bytes,
    mime_type: str,
    *,
    api_key: Optional[str] = None,
    timeout: int = _TIMEOUT_S,
) -> str:
    """OCR a document's bytes via Mistral Document AI; return its combined text.

    Degrades to ``""`` (engine disabled) when ``MISTRAL_API_KEY`` is unset, so the
    pipeline keeps its prior fail-soft behaviour — a document simply yields no text
    until the key is provisioned. Raises on an API/HTTP error; the ``rce_ocr_parser``
    caller catches it → fail-soft empty ParsedDocument with a logged reason.
    """
    key = api_key or os.environ.get("MISTRAL_API_KEY")
    if not key:
        log.info("MISTRAL_API_KEY unset — general OCR disabled (document yields no text)")
        return ""

    b64 = base64.b64encode(content).decode("ascii")
    if (mime_type or "").lower().startswith("image/"):
        document = {"type": "image_url", "image_url": f"data:{mime_type};base64,{b64}"}
    else:
        # PDFs (and anything non-image) go through the document_url channel.
        document = {"type": "document_url", "document_url": f"data:application/pdf;base64,{b64}"}

    resp = requests.post(
        _OCR_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": _MODEL, "document": document, "include_image_base64": False},
        timeout=timeout,
    )
    resp.raise_for_status()
    pages = resp.json().get("pages") or []
    return "\n\n".join((p.get("markdown") or p.get("text") or "").strip() for p in pages).strip()
