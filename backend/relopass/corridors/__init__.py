"""ReloPass corridor configuration loader (C1-09).

A "corridor" is a (origin_country, destination_country, immigration_pathway)
triple captured as a versioned YAML file under :file:`corridors/`. Each YAML
encodes the applicable rules, required documents, salary thresholds,
eligibility logic, exception cases, and the step graph.

This module loads + structurally validates a corridor YAML. The
*evaluator* — the function that runs a Case against the loaded corridor
and emits a verdict + citations — lives in C1-05 (Extraction Agent +
corridor runtime) and is intentionally out of scope here.
"""

from .loader import (
    CorridorAgent,
    CorridorEligibilityBranch,
    CorridorExceptionCase,
    CorridorLoadError,
    CorridorRule,
    CorridorStep,
    load_corridor,
    load_corridor_text,
)

__all__ = [
    "CorridorAgent",
    "CorridorEligibilityBranch",
    "CorridorExceptionCase",
    "CorridorLoadError",
    "CorridorRule",
    "CorridorStep",
    "load_corridor",
    "load_corridor_text",
]
