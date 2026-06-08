"""EU passport recognizer (ICAO 9303 MRZ format). STUB — AI-I.3c.

Detects machine-readable passport numbers following the ICAO Doc 9303
format used across EU member states.

Returns no recognizers until AI-I.3c implements it.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from presidio_analyzer import EntityRecognizer


def get_recognizers() -> "List[EntityRecognizer]":
    # TODO [AI-I.3c]: implement the EU passport recognizer (ICAO 9303) and
    # return [EuPassportRecognizer(...)]. Lazy-import presidio inside.
    return []
