"""
Context-aware chunking for canonical policy documents.

Hierarchical semantic chunking (AIQ-228):
  1. Primary split at heading boundaries (numbering depth builds the section path).
  2. Secondary split at sentence boundaries when a section exceeds the token cap.
  3. Short sections (< min tokens) merge forward into the adjacent section.
  4. ~`overlap` tokens are carried between consecutive paragraph chunks.
  5. Table rows: the header row is prepended to EVERY data-row chunk so a cell is
     never separated from its column header.

Token counts use tiktoken (cl100k_base) when available, with a character-based
fallback so the module imports and runs even before the dependency is installed.
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

from ...database import Database
from .policy_canonical_ingestion import resolve_policy_source_bytes
from .policy_structural_parse import parse_policy_document_to_elements

_DEFAULT_SECTION = "Document Root"

# ---------------------------------------------------------------------------
# Token counting (tiktoken cl100k_base, with graceful fallback)
# ---------------------------------------------------------------------------
_ENCODER: Any = None
_ENCODER_READY = False


def _get_encoder() -> Any:
    global _ENCODER, _ENCODER_READY
    if _ENCODER_READY:
        return _ENCODER
    _ENCODER_READY = True
    try:
        import tiktoken

        _ENCODER = tiktoken.get_encoding("cl100k_base")
    except Exception:  # pragma: no cover - exercised only when tiktoken absent
        _ENCODER = None
    return _ENCODER


def count_tokens(text: str) -> int:
    """Token count using cl100k_base; ~4-chars/token fallback if tiktoken absent."""
    s = text or ""
    if not s.strip():
        return 0
    enc = _get_encoder()
    if enc is not None:
        try:
            return len(enc.encode(s))
        except Exception:  # pragma: no cover
            pass
    # Fallback: max of word count and ceil(chars/4) — close enough for bounds checks.
    return max(len(s.split()), -(-len(s) // 4))


def _tail_tokens(text: str, n: int) -> str:
    """Return roughly the last `n` tokens of `text` as a string (for overlap)."""
    if n <= 0 or not text:
        return ""
    enc = _get_encoder()
    if enc is not None:
        try:
            toks = enc.encode(text)
            if len(toks) <= n:
                return text
            return enc.decode(toks[-n:])
        except Exception:  # pragma: no cover
            pass
    words = text.split()
    return " ".join(words[-n:]) if len(words) > n else text


def _split_sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()] or [text.strip()]


def _hard_split_tokens(text: str, limit: int) -> List[str]:
    """Last-resort split of text with no sentence boundaries into <= limit pieces."""
    if limit <= 0:
        return [text]
    enc = _get_encoder()
    if enc is not None:
        try:
            toks = enc.encode(text)
            return [enc.decode(toks[i : i + limit]).strip() for i in range(0, len(toks), limit)]
        except Exception:  # pragma: no cover
            pass
    words = text.split()
    return [" ".join(words[i : i + limit]).strip() for i in range(0, len(words), limit)]


def _atomize(text: str, structure_type: str, limit: int) -> List[str]:
    """Break a buffer element into pieces each <= `limit` tokens.

    List items are atomic (never split mid-item). Paragraphs split at sentence
    boundaries first, then token-window as a last resort for run-on text.
    """
    if structure_type == "list_item" or count_tokens(text) <= limit:
        return [text]
    pieces: List[str] = []
    for sent in _split_sentences(text):
        if count_tokens(sent) <= limit:
            pieces.append(sent)
        else:
            pieces.extend(_hard_split_tokens(sent, limit))
    return [p for p in pieces if p.strip()]


def _token_limits() -> tuple[int, int, int]:
    max_tokens = int(os.getenv("RELOPASS_POLICY_CHUNK_MAX_TOKENS", "600"))
    min_tokens = int(os.getenv("RELOPASS_POLICY_CHUNK_MIN_TOKENS", "150"))
    overlap_tokens = int(os.getenv("RELOPASS_POLICY_CHUNK_OVERLAP_TOKENS", "50"))
    return max_tokens, min_tokens, overlap_tokens


# ---------------------------------------------------------------------------
# Structure detection
# ---------------------------------------------------------------------------
def _looks_like_heading(text: str) -> bool:
    s = text.strip()
    if not s or len(s) > 140:
        return False
    if s.isupper() and len(s) > 3:
        return True
    if re.match(r"^(?:\d+(?:\.\d+)*|[A-Z][\).])\s+", s):
        return True
    return len(s.split()) <= 12 and not s.endswith(".")


def _structure_type(item: Dict[str, Any]) -> str:
    if item.get("is_table_row"):
        return "table_row"
    text = str(item.get("text") or "")
    if _looks_like_heading(text):
        return "heading"
    if re.match(r"^(?:[-*•]|\d+[.)])\s+", text.strip()):
        return "list_item"
    return "paragraph"


def _heading_level(text: str) -> int:
    """Infer nesting depth from leading numbering (``4.`` → 1, ``4.2`` → 2)."""
    m = re.match(r"^(\d+(?:\.\d+)*)", text.strip())
    if not m:
        return 1
    return m.group(1).count(".") + 1


def _push_heading(stack: List[str], text: str) -> List[str]:
    level = _heading_level(text)
    new_stack = stack[: level - 1]
    while len(new_stack) < level - 1:
        new_stack.append("")
    new_stack.append(text.strip())
    return new_stack


def _derive_section_path(stack: List[str]) -> str:
    clean = [part.strip() for part in stack if part and part.strip()]
    return " > ".join(clean) if clean else _DEFAULT_SECTION


def _clean(item: Dict[str, Any]) -> str:
    return str(item.get("text") or "").strip()


# ---------------------------------------------------------------------------
# Chunk builder
# ---------------------------------------------------------------------------
def build_canonical_chunks_from_elements(elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    max_tokens, min_tokens, overlap_tokens = _token_limits()
    chunks: List[Dict[str, Any]] = []
    heading_stack: List[str] = []

    buf_items: List[Dict[str, Any]] = []
    buf_section: Optional[str] = None
    table_run: List[Dict[str, Any]] = []
    char_cursor = 0
    pending_overlap = ""  # tail carried between consecutive paragraph chunks

    def emit(
        text_content: str,
        structure_type: str,
        section_path: str,
        page_start: Optional[int],
        page_end: Optional[int],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        nonlocal char_cursor
        text_content = (text_content or "").strip()
        if not text_content:
            return
        tok = count_tokens(text_content)
        md: Dict[str, Any] = {
            "token_count": tok,
            "page_start": page_start,
            "page_end": page_end,
        }
        if metadata:
            md.update(metadata)
        chunk = {
            "chunk_index": len(chunks),
            "section_path": section_path,
            "structure_type": structure_type,
            "page_number": page_start,
            "char_start": char_cursor,
            "char_end": char_cursor + len(text_content),
            "text_content": text_content,
            "token_count": tok,
            "metadata_json": md,
        }
        chunks.append(chunk)
        char_cursor = chunk["char_end"] + 1

    def flush_paragraphs() -> None:
        """Emit the paragraph/list buffer as one or more <= max_tokens chunks."""
        nonlocal buf_items, buf_section, pending_overlap
        items = buf_items
        buf_items = []
        if not items:
            return
        section = buf_section or _DEFAULT_SECTION
        pages = [it.get("page") for it in items if it.get("page") is not None]
        page_start = pages[0] if pages else None
        page_end = pages[-1] if pages else None

        # Flatten to atomic pieces each <= (max - overlap) tokens so that a chunk
        # carrying an overlap prefix still respects the hard max. List items stay
        # whole (never split mid-item); paragraphs split at sentences then tokens.
        # Leave headroom for the overlap prefix + join token so concatenation,
        # which is not additive under BPE, still respects the hard max.
        piece_max = max(1, max_tokens - overlap_tokens - 5)
        pieces: List[tuple[str, str]] = []
        for it in items:
            t = _clean(it)
            if not t:
                continue
            st = it.get("structure_type", "paragraph")
            for sub in _atomize(t, st, piece_max):
                pieces.append((sub, st))
        if not pieces:
            return

        cur_text = pending_overlap
        cur_sts: List[str] = []

        def close_pack() -> None:
            nonlocal cur_text, cur_sts, pending_overlap
            if not cur_text.strip():
                cur_text, cur_sts = "", []
                return
            dom = cur_sts[0] if cur_sts and len(set(cur_sts)) == 1 else (
                "mixed" if cur_sts else "paragraph"
            )
            emit(
                cur_text,
                dom,
                section,
                page_start,
                page_end,
                {"structure_types": cur_sts, "element_count": len(cur_sts)},
            )
            pending_overlap = _tail_tokens(cur_text, overlap_tokens)
            cur_text, cur_sts = "", []

        for text_piece, st in pieces:
            candidate = (cur_text + "\n" + text_piece).strip() if cur_text else text_piece
            if cur_text and count_tokens(candidate) > max_tokens:
                if cur_sts:
                    close_pack()
                    cur_text = pending_overlap
                    candidate = (cur_text + "\n" + text_piece).strip() if cur_text else text_piece
                if not cur_sts and count_tokens(candidate) > max_tokens:
                    # Only an overlap seed present and it still overflows — drop it
                    # so a single piece never exceeds the hard max.
                    candidate = text_piece
            cur_text = candidate
            cur_sts.append(st)
        close_pack()

    def flush_table_run() -> None:
        """Emit each table row as its own chunk with the header row prepended."""
        nonlocal table_run, pending_overlap
        rows = table_run
        table_run = []
        if not rows:
            return
        pending_overlap = ""  # overlap does not flow into/out of tables
        section = _derive_section_path(heading_stack)
        header_text = _clean(rows[0])
        if len(rows) == 1:
            emit(
                header_text,
                "table_row",
                section,
                rows[0].get("page"),
                rows[0].get("page"),
                {"is_table_header": True},
            )
            return
        for row in rows[1:]:
            row_text = _clean(row)
            if not row_text:
                continue
            combined = f"{header_text}\n{row_text}" if header_text else row_text
            emit(
                combined,
                "table_row",
                section,
                row.get("page"),
                row.get("page"),
                {"table_header": header_text, "is_table_row": True},
            )

    for raw_item in elements:
        item = dict(raw_item)
        item["structure_type"] = _structure_type(item)
        text = _clean(item)
        if not text:
            continue

        if item.get("is_table_row"):
            flush_paragraphs()
            table_run.append(item)
            continue

        # Non-table element ends any open table run.
        if table_run:
            flush_table_run()

        if item["structure_type"] == "heading":
            # Primary split — but merge a short section forward (don't flush yet).
            if buf_items and count_tokens("\n".join(_clean(i) for i in buf_items)) >= min_tokens:
                flush_paragraphs()
            heading_stack = _push_heading(heading_stack, text)
            continue

        if not buf_items:
            buf_section = _derive_section_path(heading_stack)
        buf_items.append(item)

    flush_table_run()
    flush_paragraphs()
    return chunks


def canonical_chunks_to_assistant_chunks(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "id": chunk.get("id"),
            "chunk_index": chunk.get("chunk_index"),
            "text_content": chunk.get("text_content"),
            "section_title": chunk.get("section_path"),
            "page_number": chunk.get("page_number"),
        }
        for chunk in chunks
    ]


def chunk_canonical_policy_document(
    db: Database,
    canonical_document_id: str,
) -> List[Dict[str, Any]]:
    document = db.get_canonical_policy_document(canonical_document_id)
    if not document:
        raise RuntimeError("canonical_policy_document_not_found")

    source_doc_id = document.get("source_policy_document_id")
    company_id = str(document.get("company_id") or "").strip()
    source_uri = str(document.get("source_uri") or "")
    file_path = source_uri if source_uri.startswith("/") else None
    try:
        data, _source_doc = resolve_policy_source_bytes(
            db,
            file_path=file_path,
            source_policy_document_id=source_doc_id,
        )
        elements, err = parse_policy_document_to_elements(data, str(document.get("mime_type") or ""))
        if err:
            raise RuntimeError(err)
        chunks = build_canonical_chunks_from_elements(elements)
    except Exception:
        lines = [line for line in str(document.get("normalized_text") or "").splitlines() if line.strip()]
        fallback_elements = [{"text": line, "page": 1, "is_table_row": False} for line in lines]
        chunks = build_canonical_chunks_from_elements(fallback_elements)

    db.delete_canonical_policy_artifacts(canonical_document_id)
    stored: List[Dict[str, Any]] = []
    for chunk in chunks:
        chunk_id = db.insert_canonical_policy_document_chunk(
            company_id=company_id,
            canonical_policy_document_id=canonical_document_id,
            chunk_index=int(chunk["chunk_index"]),
            section_path=chunk.get("section_path"),
            structure_type=chunk.get("structure_type"),
            page_number=chunk.get("page_number"),
            char_start=chunk.get("char_start"),
            char_end=chunk.get("char_end"),
            text_content=str(chunk.get("text_content") or ""),
            metadata_json=chunk.get("metadata_json") or {},
        )
        stored.append(
            {
                "id": chunk_id,
                **chunk,
            }
        )
    db.update_canonical_policy_document(canonical_document_id, extraction_status="chunked")
    return stored
