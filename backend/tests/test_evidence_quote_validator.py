"""Ingest-time rejection of truncated or corrupted legal quotes (AIQ-1956).

A lovdata sentence cut at a VARCHAR byte cap still reads as an authoritative quote.
These tests pin the ingest gate: reject that class of corruption, keep multilingual
UTF-8 intact, and compare legal text only after a presentation fold — never with
raw ``==``.
"""
from __future__ import annotations

import hashlib
import pytest

from backend.app.services.evidence_quote_validator import (
    COLUMN_BYTE_CAPS,
    CorruptedEvidenceError,
    decode_utf8,
    legal_text_equal,
    normalize_legal_text,
    quote_checksum,
    validate_ingest_text,
)


LOVDATA = (
    "Arbeidstaker som skal arbeide i Norge må ha skattekort. "
    "Skattekortet er et vedtak om forskuddstrekk etter skatteloven § 5-1."
)
FRENCH = "La carte de séjour est délivrée gratuitement."


def test_complete_multibyte_quote_is_stored_verbatim():
    stored = validate_ingest_text(LOVDATA, field="evidence_quote")
    assert stored == LOVDATA
    assert "skattekort" in stored
    assert stored.encode("utf-8").decode("utf-8") == stored


def test_french_quote_is_not_mojibake():
    stored = validate_ingest_text(FRENCH, field="evidence_quote")
    assert stored == FRENCH
    assert "séjour" in stored
    assert "sÃ©jour" not in stored


def test_short_complete_quote_is_not_rejected():
    """Min-length is a truncation heuristic, not a hard cap on legitimate short quotes."""
    short = "Fee: €50."
    assert validate_ingest_text(short, field="fact_text") == short


def test_empty_optional_quote_is_allowed():
    assert validate_ingest_text(None, field="evidence_quote") is None
    assert validate_ingest_text("   ", field="evidence_quote") is None


def test_replacement_char_is_rejected():
    with pytest.raises(CorruptedEvidenceError, match="U\\+FFFD"):
        validate_ingest_text("skattekort\ufffd cut", field="evidence_quote")


def test_invalid_utf8_bytes_are_rejected_not_replaced():
    with pytest.raises(UnicodeDecodeError):
        decode_utf8(b"skattekort \xff\xfe")


def test_checksum_mismatch_is_rejected():
    digest = quote_checksum(LOVDATA)
    with pytest.raises(CorruptedEvidenceError, match="checksum"):
        validate_ingest_text(LOVDATA, field="evidence_quote", checksum="0" * 64)
    assert (
        validate_ingest_text(LOVDATA, field="evidence_quote", checksum=digest) == LOVDATA
    )


def test_checksum_uses_normalized_form_not_raw_equality():
    curly = 'the “permit” is free'
    straight = 'the "permit" is free'
    assert quote_checksum(curly) == quote_checksum(straight)
    assert hashlib.sha256(curly.encode("utf-8")).hexdigest() != quote_checksum(curly)


def test_text_cut_at_varchar_byte_cap_is_rejected():
    """Exactly 255 ASCII bytes ending mid-token is the classic column-limit cut."""
    assert 255 in COLUMN_BYTE_CAPS
    cut = "a" * 255
    with pytest.raises(CorruptedEvidenceError, match="column limit"):
        validate_ingest_text(cut, field="evidence_quote")


def test_255_bytes_that_end_on_a_sentence_are_kept():
    """A complete sentence whose UTF-8 length happens to be 255 is not truncation."""
    body = ("Skattekortet er et vedtak. " * 20)
    padded = body[:254] + "."
    assert len(padded.encode("utf-8")) == 255
    assert validate_ingest_text(padded, field="fact_text") == padded


def test_mid_word_ellipsis_on_a_long_quote_is_rejected():
    cut = ("Arbeidstaker som skal arbeide i Norge må ha skattekort og fremvise det hos "
           "arbeidsgiver innen tre dager etter at arbeidet tar til skattekort...")
    assert len(cut) >= 40
    with pytest.raises(CorruptedEvidenceError, match="truncated"):
        validate_ingest_text(cut, field="evidence_quote")


def test_legal_text_equal_folds_quotes_and_nbsp_not_words():
    assert legal_text_equal("fee\u00a0is  320–340", "fee is 320-340")
    assert legal_text_equal('the “permit”', 'the "permit"')
    assert not legal_text_equal("eight months", "eight weeks")


def test_normalize_legal_text_does_not_byte_slice():
    text = "øæå " + FRENCH
    folded = normalize_legal_text(text)
    assert "øæå" in folded
    assert "séjour" in folded
