"""Norwegian fødselsnummer recognizer (check-digit validation). STUB — AI-I.3d.

Detects the 11-digit Norwegian national identity number and validates its
two MOD-11 control digits to suppress false positives.

Returns no recognizers until AI-I.3d implements it.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from presidio_analyzer import EntityRecognizer


def get_recognizers() -> "List[EntityRecognizer]":
    # TODO [AI-I.3d]: implement the NO fødselsnummer recognizer (MOD-11 check
    # digits) and return [NoFnrRecognizer(...)]. Lazy-import presidio inside.
    return []
