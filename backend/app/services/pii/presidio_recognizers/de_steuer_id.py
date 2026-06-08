"""German Steuer-ID recognizer (11-digit tax ID, ISO 7064 check). STUB — AI-I.3d.

Detects the German Steueridentifikationsnummer — an 11-digit identifier with a
defined digit-uniqueness rule and an ISO 7064 MOD 11,10 check digit.

Returns no recognizers until AI-I.3d implements it.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from presidio_analyzer import EntityRecognizer


def get_recognizers() -> "List[EntityRecognizer]":
    # TODO [AI-I.3d]: implement the DE Steuer-ID recognizer (ISO 7064 check)
    # and return [DeSteuerIdRecognizer(...)]. Lazy-import presidio inside.
    return []
