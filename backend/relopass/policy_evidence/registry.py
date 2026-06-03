"""Evidence-check registry (C2-06).

A clause_type → EvidenceCheck map. Modules register at import time; the
detector reads via :func:`get` per clause encountered.

The registry is mutable but module-level — appropriate for the
configuration-as-code style of this package. Tests that need isolation
can call :func:`clear` in a fixture teardown.
"""

from __future__ import annotations

from typing import Dict, Tuple

from .base import EvidenceCheck

_REGISTRY: Dict[str, EvidenceCheck] = {}


class DuplicateRegistrationError(Exception):
    """Raised when a clause_type is registered more than once with a
    different check instance.

    Re-registering the same instance is idempotent (and silently
    accepted) so tests can re-import safely.
    """


def register(check: EvidenceCheck) -> EvidenceCheck:
    """Register an :class:`EvidenceCheck` instance.

    Returns the registered instance for fluent / decorator-friendly use.
    Raises :class:`DuplicateRegistrationError` if a DIFFERENT check is
    already registered for the same clause_type.

    Idempotent for the same instance (re-import of a registered module
    is a no-op).
    """
    clause_type = check.clause_type
    if not clause_type:
        raise ValueError(
            f"EvidenceCheck {type(check).__name__} has no clause_type set; "
            f"override the class attribute before registering."
        )
    existing = get(clause_type)
    if existing is not None and existing is not check:
        raise DuplicateRegistrationError(
            f"clause_type {clause_type} is already registered to "
            f"{type(existing).__name__}; cannot re-register to "
            f"{type(check).__name__}."
        )
    _REGISTRY[clause_type] = check
    return check


def get(clause_type: str) -> "EvidenceCheck | None":
    """Return the registered check for ``clause_type``, or None if absent.

    A None return is NOT an error — it just means this clause type has
    no evidence check yet (8 of the 11 §6.1 clause types are deferred
    beyond C2-06). The detector skips unregistered clause types
    silently and the unused clauses get a separate metric.
    """
    return _REGISTRY.get(clause_type)


def all_registered() -> Tuple[EvidenceCheck, ...]:
    """Return a tuple of all currently-registered checks."""
    return tuple(_REGISTRY.values())


def registered_clause_types() -> Tuple[str, ...]:
    """Return a tuple of all currently-registered clause_type strings."""
    return tuple(_REGISTRY.keys())


def clear() -> None:
    """Reset the registry. Test-only — production code never calls this."""
    _REGISTRY.clear()
