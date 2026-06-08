"""IBAN recognizer (mod-97 checksum validation). STUB — AI-I.3b.

Detects International Bank Account Numbers and validates them with the
ISO 13616 / ISO 7064 mod-97 checksum to keep false positives low.

Returns no recognizers until AI-I.3b implements it.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from presidio_analyzer import EntityRecognizer


def get_recognizers() -> "List[EntityRecognizer]":
    # TODO [AI-I.3b]: implement the IBAN recognizer (mod-97 checksum) and
    # return [IbanRecognizer(...)]. Lazy-import presidio inside this function.
    return []
