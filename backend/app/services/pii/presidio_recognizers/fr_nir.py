"""French NIR recognizer (INSEE social-security number, key check). STUB — AI-I.3d.

Detects the French Numéro d'Inscription au Répertoire (sécurité sociale) — a
15-digit number whose final two digits are a mod-97 control key over the first
thirteen.

Returns no recognizers until AI-I.3d implements it.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from presidio_analyzer import EntityRecognizer


def get_recognizers() -> "List[EntityRecognizer]":
    # TODO [AI-I.3d]: implement the FR NIR recognizer (mod-97 control key) and
    # return [FrNirRecognizer(...)]. Lazy-import presidio inside.
    return []
