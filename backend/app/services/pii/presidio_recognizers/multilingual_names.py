"""Multilingual person-name recognizer (FR/DE/NO/Hindi boosters). STUB — AI-I.3e.

Improves person-name recall in the languages mobility cases run in by adding
language-specific context words (e.g. FR "né(e)", DE "geboren", NO "født",
Hindi honorifics) as score boosters on top of Presidio's NER.

Returns no recognizers until AI-I.3e implements it.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from presidio_analyzer import EntityRecognizer


def get_recognizers() -> "List[EntityRecognizer]":
    # TODO [AI-I.3e]: implement the multilingual name recognizer(s) (FR/DE/NO/
    # Hindi context boosters) and return them. Lazy-import presidio inside.
    return []
