"""Ingest-time checks for `evidence_quote` and `fact_text` (AIQ-1956).

A verbatim legal quote that was silently cut at a column byte-limit is data
corruption that still reads as authoritative. This module is the ingest gate:

* reject U+FFFD (already-replaced UTF-8) and checksum mismatches
* reject text that looks truncated (column-cap cut, mid-word ellipsis) once it
  is long enough that the heuristic applies — not a hard maximum length
* store the original Unicode string; never slice UTF-8 bytes
* compare legal text only after a presentation fold

No serving engine imports this. It is called from import parsers only.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import FrozenSet, Optional

COLUMN_BYTE_CAPS: FrozenSet[int] = frozenset(
    {255, 256, 511, 512, 1023, 1024, 1999, 2000, 3999, 4000, 4095, 4096}
)

#: Below this, do not treat trailing ellipsis as a column cut — a short citation
#: may legitimately end with "…". Completeness is judged by checksum / U+FFFD /
#: exact byte-cap cuts instead.
MIN_ELLIPSIS_HEURISTIC_CHARS = 40

_SENTENCE_END = frozenset('.!?;:»"\')]}')


class CorruptedEvidenceError(ValueError):
    """The quote or fact text is truncated or encoding-corrupted and must not be stored."""


def decode_utf8(data: bytes) -> str:
    """Decode inbound bytes as UTF-8. Never ``errors='replace'`` or ``'ignore'``."""
    return data.decode("utf-8")


def normalize_legal_text(value: str) -> str:
    """Presentation fold for comparison and checksums. Does not change stored text.

    Publishers disagree on NBSP, curly quotes and dash width. Folding those lets a
    vetted quote match its source. Words are never inserted, removed or reordered.
    """
    text = unicodedata.normalize("NFKC", value)
    text = (
        text.replace("‘", "'").replace("’", "'")
        .replace("“", '"').replace("”", '"')
        .replace("–", "-").replace("—", "-")
        .replace("\u00ad", "")
    )
    return re.sub(r"\s+", " ", text).strip()


def legal_text_equal(left: str, right: str) -> bool:
    """Compare legal text after the presentation fold. Do not use raw ``==``."""
    return normalize_legal_text(left).casefold() == normalize_legal_text(right).casefold()


def quote_checksum(value: str) -> str:
    return hashlib.sha256(normalize_legal_text(value).encode("utf-8")).hexdigest()


def validate_ingest_text(
    value: Optional[str],
    *,
    field: str,
    checksum: Optional[str] = None,
) -> Optional[str]:
    """Return the string to store, or raise ``CorruptedEvidenceError``.

    ``None`` / blank is allowed for optional quotes. The stored value is the
    original (stripped) Unicode, not the normalised form.
    """
    if value is None:
        return None
    if isinstance(value, bytes):
        value = decode_utf8(value)

    if "\ufffd" in value:
        raise CorruptedEvidenceError(
            f"{field} contains U+FFFD (corrupted UTF-8 was replaced, not rejected)"
        )

    # Round-trip proves we are not holding a byte-sliced str. Strict decode.
    stored = decode_utf8(value.encode("utf-8"))
    stripped = stored.strip()
    if not stripped:
        return None

    declared = (checksum or "").strip()
    if declared:
        got = quote_checksum(stripped)
        if got != declared.lower():
            raise CorruptedEvidenceError(
                f"{field} checksum mismatch (declared {declared[:12]}…, computed {got[:12]}…)"
            )

    n_bytes = len(stripped.encode("utf-8"))
    if n_bytes in COLUMN_BYTE_CAPS and _cut_mid_token(stripped):
        raise CorruptedEvidenceError(
            f"{field} looks truncated at a {n_bytes}-byte column limit"
        )

    if (
        len(stripped) >= MIN_ELLIPSIS_HEURISTIC_CHARS
        and _mid_word_ellipsis(stripped)
    ):
        raise CorruptedEvidenceError(
            f"{field} looks truncated (mid-word ellipsis)"
        )

    return stripped


def _cut_mid_token(text: str) -> bool:
    last = text[-1]
    if last in _SENTENCE_END or last.isspace():
        return False
    return last.isalnum()


def _mid_word_ellipsis(text: str) -> bool:
    if text.endswith("..."):
        body = text[:-3]
    elif text.endswith("…"):
        body = text[:-1]
    else:
        return False
    return bool(body) and body[-1].isalnum()
