"""ReloPass LLM router primitives — deterministic, vendor-SDK-free.

This sub-package is the planner side of the LLM layer:

- `router.route_llm(task_class, **kwargs)` returns a `LLMHandle` carrying
  the model identifier and a pricing table reference. The handle's
  `.complete(...)` method delegates to a runtime-registered completer
  (registered by the higher service layer that owns the vendor SDKs).

Per the `backend/relopass/__init__.py` constraint, this package MUST NOT
import any vendor SDK or framework. The Anthropic / OpenAI / Mistral
clients are installed by `backend/services/llm_router_clients.py` (or
equivalent) via `router.register_completer(model_name, callable)`.

See Architecture Report §11 for the routing table and rationale.
"""

from .router import (
    ESCALATION_CONFIDENCE_THRESHOLDS,
    LLMHandle,
    LLMRoutingError,
    ROUTING_TABLE,
    RoutingDecision,
    TaskClass,
    register_completer,
    reset_registry,
    route_llm,
)

__all__ = [
    "ESCALATION_CONFIDENCE_THRESHOLDS",
    "LLMHandle",
    "LLMRoutingError",
    "ROUTING_TABLE",
    "RoutingDecision",
    "TaskClass",
    "register_completer",
    "reset_registry",
    "route_llm",
]
