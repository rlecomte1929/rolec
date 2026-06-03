"""Policy-evidence registry (C2-06).

Pluggable evidence-check system that powers the policy-versus-reality gap
detector. Each clause type (LANGUAGE_TRAINING, HOUSING_BENEFIT,
IMMIGRATION_SUPPORT, etc.) is implemented as a separate module that
declares (a) which subjects on a case the clause applies to, and (b) what
counts as evidence of delivery for each subject.

Adding a new clause type is config not code: create a new module under this
package, subclass :class:`EvidenceCheck`, and call ``register(YourClass())``.
The :func:`detect_gaps` orchestrator picks it up automatically.

Architecture Report references:
    §6.1 — clause type taxonomy (11 types; 3 covered at C2-06 launch)
    §6.4 — gap detection (the killer HR feature)
    §6.5 — citation traceability

Public surface:
    EvidenceCheck     — base class / contract
    register / get    — registry mutation + lookup
    Case, FamilyMember, PolicyClause, Artefact, Subject, Gap, GapType
                      — the lightweight projection types the detector
                        works against
    detect_gaps       — the orchestrator (pure function)

The package has zero non-stdlib imports beyond ``dataclasses`` and
``typing`` — same convention as the C2-02a freshness validator. The
concrete adapter that maps rce.cases / rce.family_members / rce.documents
into these projection types lives one layer up in
``backend/app/services/policy_gap_detector_adapter.py`` (next session).
"""

from __future__ import annotations

from ._models import (
    Artefact,
    Case,
    FamilyMember,
    Gap,
    GapType,
    PolicyClause,
    Subject,
    SubjectKind,
)
from .base import EvidenceCheck
from .detector import detect_gaps
from .registry import all_registered, get, register, registered_clause_types

# Importing the concrete checks triggers their self-registration.
from . import housing_benefit, immigration_support, language_training  # noqa: F401,E402

__all__ = [
    "Artefact",
    "Case",
    "FamilyMember",
    "Gap",
    "GapType",
    "PolicyClause",
    "Subject",
    "SubjectKind",
    "EvidenceCheck",
    "detect_gaps",
    "all_registered",
    "get",
    "register",
    "registered_clause_types",
]
