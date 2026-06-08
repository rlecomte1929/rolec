"""ReloPass custom Presidio recognizers + registry factory (epic AI-I.3).

Stock Presidio misses 220+ GDPR entities (per a third-party audit), so we add
custom recognizers for the ones that matter to cross-border mobility: IBANs,
EU passports, national IDs (NO fødselsnummer, DE Steuer-ID, FR NIR), and
multilingual person names.

This module (AI-I.3a) is the **scaffold**: it exposes the
``build_relopass_recognizer_registry()`` factory and wires in the six
recognizer modules. Each recognizer module ships as an empty stub
(``get_recognizers()`` returns ``[]``) until its own subtask implements it:

    AI-I.3b -> iban
    AI-I.3c -> eu_passport
    AI-I.3d -> no_fnr, de_steuer_id, fr_nir
    AI-I.3e -> multilingual_names
    AI-I.3f -> wire build_relopass_recognizer_registry() into pii_masker.py

Import-safety: ``presidio-analyzer`` is **not** a hard import of this package.
The package (and every stub) imports cleanly without presidio installed, and
the factory lazy-imports presidio only when actually called. That keeps the
scaffold dependency-free until a later subtask provisions presidio + spaCy in
the runtime (see `build_relopass_recognizer_registry`).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

from . import (
    de_steuer_id,
    eu_passport,
    fr_nir,
    iban,
    multilingual_names,
    no_fnr,
)

if TYPE_CHECKING:  # imported lazily at runtime — see the factory below.
    from presidio_analyzer import EntityRecognizer, RecognizerRegistry

# Order is stable and intentional: registration order only affects tie-breaks,
# and a fixed order keeps the registry reproducible across processes.
_RECOGNIZER_MODULES = (
    iban,
    eu_passport,
    no_fnr,
    de_steuer_id,
    fr_nir,
    multilingual_names,
)


def _collect_custom_recognizers() -> "List[EntityRecognizer]":
    """Gather every recognizer the stub modules expose. Stubs return ``[]``
    until implemented, so this is empty in the scaffold and grows as the
    AI-I.3b–e subtasks land — no edits to this file required."""
    recognizers: "List[EntityRecognizer]" = []
    for module in _RECOGNIZER_MODULES:
        recognizers.extend(module.get_recognizers())
    return recognizers


def build_relopass_recognizer_registry(
    *, load_predefined: bool = True
) -> "RecognizerRegistry":
    """Build a Presidio ``RecognizerRegistry`` with ReloPass's custom
    recognizers added on top of (optionally) the stock predefined set.

    Args:
        load_predefined: when True (default), also load Presidio's built-in
            recognizers so the registry recognises both stock and custom
            entities. Set False to get a registry with only ReloPass's
            recognizers.

    Returns:
        A configured ``presidio_analyzer.RecognizerRegistry``.

    Raises:
        ImportError: if ``presidio-analyzer`` is not installed. presidio is
            intentionally lazy-imported so this scaffold package stays
            import-safe without it; provisioning presidio (+ spaCy model) in
            the runtime is handled when the masker is wired up (AI-I.3f).
    """
    try:
        from presidio_analyzer import RecognizerRegistry
    except ImportError as exc:  # pragma: no cover - exercised only without presidio
        raise ImportError(
            "presidio-analyzer is required to build the recognizer registry. "
            "Add it (and a spaCy model) to backend/requirements.txt as part of "
            "wiring the registry into pii_masker.py (AI-I.3f)."
        ) from exc

    registry = RecognizerRegistry()
    if load_predefined:
        registry.load_predefined_recognizers()
    for recognizer in _collect_custom_recognizers():
        registry.add_recognizer(recognizer)
    return registry


__all__ = ["build_relopass_recognizer_registry"]
