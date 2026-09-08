"""
Unit tests for the hierarchical semantic chunking engine (AIQ-228 / P2-2).

Exercises the pure builder `build_canonical_chunks_from_elements`, which maps
page-aware extraction elements -> retrieval chunks. No DB / network involved.
"""
from __future__ import annotations

from backend.app.services.policy_canonical_chunking import (
    build_canonical_chunks_from_elements,
    count_tokens,
)

MAX_TOKENS = 600
MIN_TOKENS = 150
OVERLAP_TOKENS = 50


def _sentence(words: int, label: str) -> str:
    return ("%s " % label) * (words - 1) + "%s." % label


def test_table_header_prepended_to_every_row_chunk():
    """No table data row appears in a chunk without its column header."""
    header = "Grade | Monthly Cap | Currency"
    elements = [
        {"text": "4. Housing Benefits", "page": 8, "is_table_row": False},
        {"text": header, "page": 8, "is_table_row": True},
        {"text": "Manager | 3500 | EUR", "page": 8, "is_table_row": True},
        {"text": "Director | 5000 | EUR", "page": 8, "is_table_row": True},
    ]
    chunks = build_canonical_chunks_from_elements(elements)
    row_chunks = [c for c in chunks if c["structure_type"] == "table_row"]
    # Two data rows -> two row chunks, each carrying the header.
    assert len(row_chunks) == 2
    for c in row_chunks:
        assert header in c["text_content"], c["text_content"]
        assert c["metadata_json"]["table_header"] == header
    assert "Manager | 3500 | EUR" in row_chunks[0]["text_content"]
    assert "Director | 5000 | EUR" in row_chunks[1]["text_content"]


def test_every_chunk_has_section_path_and_page_start():
    elements = [
        {"text": "1. Introduction", "page": 1, "is_table_row": False},
        {"text": _sentence(40, "intro"), "page": 1, "is_table_row": False},
        {"text": "2. Benefits", "page": 2, "is_table_row": False},
        {"text": _sentence(40, "benefit"), "page": 2, "is_table_row": False},
    ]
    chunks = build_canonical_chunks_from_elements(elements)
    assert chunks
    for c in chunks:
        assert c["section_path"], c
        assert c["section_path"] is not None
        assert c["metadata_json"]["page_start"] is not None
        assert c["page_number"] is not None


def test_nested_section_path_from_numbered_headings():
    elements = [
        {"text": "4. Housing Benefits", "page": 1, "is_table_row": False},
        # >= MIN tokens so this section flushes on its own and 4.2 starts fresh.
        {"text": _sentence(200, "house"), "page": 1, "is_table_row": False},
        {"text": "4.2 Monthly Cap", "page": 1, "is_table_row": False},
        {"text": _sentence(200, "cap"), "page": 1, "is_table_row": False},
    ]
    chunks = build_canonical_chunks_from_elements(elements)
    cap_chunks = [c for c in chunks if "cap" in c["text_content"]]
    assert cap_chunks
    assert cap_chunks[0]["section_path"] == "4. Housing Benefits > 4.2 Monthly Cap"


def test_paragraph_chunks_stay_within_max_tokens():
    big = _sentence(40, "clause") + " " + " ".join(_sentence(40, "clause") for _ in range(40))
    elements = [
        {"text": "1. Long Section", "page": 1, "is_table_row": False},
        {"text": big, "page": 1, "is_table_row": False},
    ]
    chunks = build_canonical_chunks_from_elements(elements)
    para_chunks = [c for c in chunks if c["structure_type"] != "table_row"]
    assert len(para_chunks) >= 2  # must have split
    for c in para_chunks:
        assert count_tokens(c["text_content"]) <= MAX_TOKENS, count_tokens(c["text_content"])
        assert c["metadata_json"]["token_count"] == count_tokens(c["text_content"])


def test_overlap_between_consecutive_paragraph_chunks():
    from backend.app.services.policy_canonical_chunking import _tail_tokens

    big = " ".join(_sentence(30, "para%d" % i) for i in range(60))
    elements = [
        {"text": "1. Overlap Section", "page": 1, "is_table_row": False},
        {"text": big, "page": 1, "is_table_row": False},
    ]
    chunks = build_canonical_chunks_from_elements(elements)
    para_chunks = [c for c in chunks if c["structure_type"] != "table_row"]
    assert len(para_chunks) >= 2
    for prev, nxt in zip(para_chunks, para_chunks[1:]):
        tail = _tail_tokens(prev["text_content"], OVERLAP_TOKENS).strip()
        assert tail, "expected a non-empty overlap tail"
        assert nxt["text_content"].startswith(tail), (
            tail[:60],
            nxt["text_content"][:60],
        )


def test_list_items_not_split_mid_item():
    items = [{"text": "- %s" % _sentence(30, "item%d" % i), "page": 1, "is_table_row": False}
             for i in range(40)]
    elements = [{"text": "1. The List", "page": 1, "is_table_row": False}] + items
    chunks = build_canonical_chunks_from_elements(elements)
    # Every original list item text must survive intact inside exactly some chunk.
    blob = "\n".join(c["text_content"] for c in chunks)
    for it in items:
        assert it["text"] in blob, it["text"]


def test_runon_paragraph_never_exceeds_max():
    """A 2000-token paragraph with no sentence punctuation still respects the cap."""
    runon = "word " * 2000  # no '.', '!' or '?'
    elements = [
        {"text": "1. Run On", "page": 1, "is_table_row": False},
        {"text": runon.strip(), "page": 1, "is_table_row": False},
    ]
    chunks = build_canonical_chunks_from_elements(elements)
    assert len(chunks) >= 3
    for c in chunks:
        assert count_tokens(c["text_content"]) <= MAX_TOKENS, count_tokens(c["text_content"])


def test_short_section_merges_forward():
    elements = [
        {"text": "1. Tiny", "page": 1, "is_table_row": False},
        {"text": _sentence(10, "tiny"), "page": 1, "is_table_row": False},
        {"text": "2. Also Tiny", "page": 1, "is_table_row": False},
        {"text": _sentence(10, "also"), "page": 1, "is_table_row": False},
    ]
    chunks = build_canonical_chunks_from_elements(elements)
    para_chunks = [c for c in chunks if c["structure_type"] != "table_row"]
    # Both tiny sections (each < MIN) merge into a single chunk.
    assert len(para_chunks) == 1
    assert "tiny" in para_chunks[0]["text_content"]
    assert "also" in para_chunks[0]["text_content"]
