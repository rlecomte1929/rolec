"""
PolicyTextExtractionService — extract text, normalize whitespace, chunk for assistant knowledge.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from .policy_document_intake import extract_text_from_bytes

_CHARS_PER_TOKEN = 4
_MAX_CHUNK_CHARS = 4500
_MIN_SECTION_CHARS = 80


def _normalize_whitespace(text: str) -> str:
    lines = []
    for line in text.splitlines():
        s = re.sub(r"\s+", " ", line.strip())
        if s:
            lines.append(s)
    return "\n".join(lines)


def _looks_like_heading(line: str) -> bool:
    s = line.strip()
    if not s or len(s) > 120:
        return False
    if s.isupper() and len(s) >= 4:
        return True
    if re.match(r"^(?:Chapter|Section|Article|\d+[\.)]\s+)", s, re.I):
        return True
    if len(s) < 80 and not s.endswith(".") and s[:1].isupper():
        return True
    return False


def _split_semantic_sections(lines: List[str]) -> List[Tuple[Optional[str], List[str]]]:
    sections: List[Tuple[Optional[str], List[str]]] = []
    current_title: Optional[str] = None
    buf: List[str] = []
    for ln in lines:
        if _looks_like_heading(ln):
            if buf:
                sections.append((current_title, buf))
                buf = []
            current_title = ln.strip()
            continue
        buf.append(ln)
    if buf:
        sections.append((current_title, buf))
    if not sections:
        return [(None, lines)]
    return sections


def _chunk_block(text: str, max_chars: int) -> List[str]:
    t = text.strip()
    if not t:
        return []
    if len(t) <= max_chars:
        return [t]
    parts: List[str] = []
    start = 0
    while start < len(t):
        end = min(len(t), start + max_chars)
        chunk = t[start:end]
        if end < len(t):
            cut = chunk.rfind("\n")
            if cut > max_chars // 2:
                chunk = chunk[:cut]
                end = start + cut
        parts.append(chunk.strip())
        start = end
    return [p for p in parts if p]


def extract_plain_text(data: bytes, mime_type: str) -> Tuple[str, Optional[str]]:
    """Returns (normalized full text, error)."""
    lines, err = extract_text_from_bytes(data, mime_type)
    if err:
        return "", err
    raw = "\n".join(lines)
    return _normalize_whitespace(raw), None


def build_chunks(full_text: str) -> List[Dict[str, Any]]:
    """Build chunk rows (pre-persist)."""
    lines = [ln for ln in full_text.split("\n") if ln.strip()]
    sections = _split_semantic_sections(lines)
    out: List[Dict[str, Any]] = []
    idx = 0
    for title, block_lines in sections:
        block = "\n".join(block_lines).strip()
        if not block:
            continue
        if len(block) < _MIN_SECTION_CHARS and title:
            block = f"{title}\n{block}"
        subchunks = _chunk_block(block, _MAX_CHUNK_CHARS)
        for sc in subchunks:
            meta: Dict[str, Any] = {}
            if title:
                meta["heading"] = title
            out.append(
                {
                    "chunk_index": idx,
                    "text_content": sc,
                    "section_title": title,
                    "page_number": None,
                    "metadata_json": meta,
                }
            )
            idx += 1
    if not out and full_text.strip():
        for i, sc in enumerate(_chunk_block(full_text.strip(), _MAX_CHUNK_CHARS)):
            out.append(
                {
                    "chunk_index": i,
                    "text_content": sc,
                    "section_title": None,
                    "page_number": None,
                    "metadata_json": {},
                }
            )
    return out


class PolicyTextExtractionService:
    def extract_text_from_document(self, data: bytes, mime_type: str) -> Tuple[str, Optional[str]]:
        return extract_plain_text(data, mime_type)

    def normalize_whitespace(self, text: str) -> str:
        return _normalize_whitespace(text)

    def chunk_by_semantic_sections(self, full_text: str) -> List[Dict[str, Any]]:
        return build_chunks(full_text)
