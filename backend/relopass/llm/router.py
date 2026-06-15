"""Deterministic per-task LLM router (C1-13, Architecture Report §11).

Rules-first by construction — the choice of which model to use is decided
by ordinary Python, never by an LLM call. Adding a new task class or
escalation rule means editing :data:`ROUTING_TABLE` in this file, not
prompting another model.

Public surface:

* :func:`route_llm` — pick the right :class:`LLMHandle` for a task class.
* :class:`LLMHandle` — the result. Exposes ``model_name``, ``cost_usd``,
  ``tokens_in``, ``tokens_out`` and an async ``complete()``.
* :func:`register_completer` — install the concrete callable that runs
  the SDK request. Done at process boot by the service layer; tests
  install a fake completer per case.

The vendor SDK imports live in a higher layer (see
``backend/services/llm_router_clients.py``); this module stays pure
Python so it can be unit-tested without network access or SDK installs.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    Awaitable,
    Callable,
    Dict,
    Literal,
    Mapping,
    MutableMapping,
    Optional,
    Tuple,
)

# ─────────────────────────────────────────────────────────────────────────────
# Routing table (Architecture Report §11)
# ─────────────────────────────────────────────────────────────────────────────

TaskClass = Literal[
    "document_classification",
    "mrz_extraction",
    "field_extraction",
    "entity_resolution_fallback",
    "eligibility_reasoning",
    "policy_clause_extraction",
    "pathway_conversational",
]

# Aliases — keeps the validation-criteria phrasing ("extraction") working
# alongside the §11 canonical name ("field_extraction"). Add aliases sparingly.
_TASK_ALIASES: Dict[str, TaskClass] = {
    "extraction": "field_extraction",
}


@dataclass(frozen=True)
class RoutingDecision:
    """One row of the §11 routing table."""

    task_class: TaskClass
    default_model: Optional[str]
    escalate_model: Optional[str]
    escalation_reason: Optional[str]


ROUTING_TABLE: Mapping[TaskClass, RoutingDecision] = {
    "document_classification": RoutingDecision(
        task_class="document_classification",
        default_model="gpt-4o-mini",
        escalate_model="gpt-4o",
        escalation_reason="classifier confidence < 0.80",
    ),
    "mrz_extraction": RoutingDecision(
        # MRZ is a pure-regex job (backend/relopass/docs/mrz.py). No model.
        task_class="mrz_extraction",
        default_model=None,
        escalate_model=None,
        escalation_reason=None,
    ),
    "field_extraction": RoutingDecision(
        task_class="field_extraction",
        default_model="gpt-4o-mini",
        # LLM-MODEL-DRIFT/AIQ-1085: escalate off the retired claude-3-7-sonnet
        # onto the current Sonnet (same $3/$15 tier — cost-neutral). Extraction
        # is a structured-output task, not deep reasoning, so Sonnet (not Opus).
        escalate_model="claude-sonnet-4-6",
        escalation_reason="validator failure or confidence < 0.85",
    ),
    "entity_resolution_fallback": RoutingDecision(
        task_class="entity_resolution_fallback",
        default_model="gpt-4o-mini",
        # LLM-MODEL-DRIFT/AIQ-1085: retired 3.7 → current Sonnet (cost-neutral).
        # Disambiguating a tight candidate cluster is well within Sonnet's range.
        escalate_model="claude-sonnet-4-6",
        escalation_reason="candidate cluster within 0.05 cosine",
    ),
    "eligibility_reasoning": RoutingDecision(
        task_class="eligibility_reasoning",
        # LLM-MODEL-DRIFT/AIQ-1085: retired 3.7 → current Sonnet (same $3/$15
        # tier — cost-neutral for this per-call default). This is the most
        # reasoning-heavy route; if eligibility accuracy ever needs the stronger
        # tier, claude-opus-4-8 is the lever, but that warrants a benchmark +
        # adding Opus pricing to costs.yaml first (kept cost-neutral here).
        default_model="claude-sonnet-4-6",
        escalate_model=None,
        escalation_reason="always uses claude-sonnet-4-6",
    ),
    "policy_clause_extraction": RoutingDecision(
        task_class="policy_clause_extraction",
        # FD-2/AIQ-994: baseline off the retired claude-3-7-sonnet onto the
        # current Sonnet (same $3/$15 tier, the Fable-5 benchmark baseline). The
        # POLICY_PARSING_FABLE5 env override still routes to claude-fable-5 when set.
        default_model="claude-sonnet-4-6",
        escalate_model=None,
        escalation_reason="always uses claude-sonnet-4-6",
    ),
    "pathway_conversational": RoutingDecision(
        task_class="pathway_conversational",
        default_model="gpt-4o-mini",
        # LLM-MODEL-DRIFT/AIQ-1085: retired 3.7 → current Sonnet (cost-neutral).
        # Conversational 'explain'/sensitive-topic handling fits Sonnet well.
        escalate_model="claude-sonnet-4-6",
        escalation_reason="'explain' intent or sensitive topic",
    ),
}

# Escalation thresholds. Centralised so tests + callers reference the same
# constants instead of magic numbers scattered through the codebase.
ESCALATION_CONFIDENCE_THRESHOLDS: Mapping[TaskClass, float] = {
    "document_classification": 0.80,
    "field_extraction": 0.85,
}


# ─────────────────────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────────────────────


class LLMRoutingError(Exception):
    """Raised when routing or pricing inputs are inconsistent."""


# ─────────────────────────────────────────────────────────────────────────────
# Cost table
# ─────────────────────────────────────────────────────────────────────────────


_COSTS_YAML_PATH = Path(__file__).with_name("costs.yaml")
_COSTS_CACHE: Optional[Dict[str, Dict[str, float]]] = None


def _parse_costs_yaml(text: str) -> Dict[str, Dict[str, float]]:
    """Minimal YAML loader for the two-level structure costs.yaml uses.

    Avoids a hard dependency on PyYAML in this primitive module. The file
    shape is rigid (model → {in_per_million, out_per_million}); a real
    YAML parser is overkill.
    """
    out: Dict[str, Dict[str, float]] = {}
    current_model: Optional[str] = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith(" ") and not line.startswith("\t"):
            # New top-level key: "model-name:"
            key = line.rstrip(":").strip()
            if not key:
                continue
            current_model = key
            out[current_model] = {}
        else:
            if current_model is None:
                raise LLMRoutingError(
                    f"costs.yaml has an indented line before any model key: {raw!r}"
                )
            key_value = line.strip()
            if ":" not in key_value:
                continue
            key, _, value = key_value.partition(":")
            try:
                out[current_model][key.strip()] = float(value.strip())
            except ValueError as exc:
                raise LLMRoutingError(
                    f"costs.yaml: could not parse {key.strip()} for {current_model!r}: {value!r}"
                ) from exc
    return out


def _load_costs() -> Dict[str, Dict[str, float]]:
    global _COSTS_CACHE
    if _COSTS_CACHE is None:
        _COSTS_CACHE = _parse_costs_yaml(_COSTS_YAML_PATH.read_text(encoding="utf-8"))
    return _COSTS_CACHE


def reset_costs_cache() -> None:
    """Test hook — drop the in-memory cost cache."""
    global _COSTS_CACHE
    _COSTS_CACHE = None


def usd_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """Calculate USD cost from per-million prices in :file:`costs.yaml`."""
    if tokens_in < 0 or tokens_out < 0:
        raise LLMRoutingError("Token counts must be non-negative")
    costs = _load_costs()
    if model not in costs:
        raise LLMRoutingError(
            f"No pricing entry for model {model!r} in costs.yaml — add it before routing."
        )
    entry = costs[model]
    in_rate = entry.get("in_per_million", 0.0) / 1_000_000.0
    out_rate = entry.get("out_per_million", 0.0) / 1_000_000.0
    return tokens_in * in_rate + tokens_out * out_rate


# ─────────────────────────────────────────────────────────────────────────────
# Completer registry
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class CompletionResult:
    """What a registered completer must return from :meth:`complete`."""

    text: str
    tokens_in: int
    tokens_out: int


# A completer is an async callable accepting (prompt, **kwargs) and returning
# a :class:`CompletionResult`. Vendor SDK calls live inside the registered
# completer, not in this module.
Completer = Callable[..., Awaitable[CompletionResult]]


_REGISTRY: MutableMapping[str, Completer] = {}


def register_completer(model_name: str, completer: Completer) -> None:
    """Install or replace the completer for a model.

    Called by the service layer once at boot. Tests install a fake completer
    per case via this function.
    """
    _REGISTRY[model_name] = completer


def reset_registry() -> None:
    """Test hook — clear all registered completers."""
    _REGISTRY.clear()


def _get_completer(model_name: str) -> Completer:
    if model_name not in _REGISTRY:
        raise LLMRoutingError(
            f"No completer registered for {model_name!r}. "
            f"Call register_completer({model_name!r}, …) at boot."
        )
    return _REGISTRY[model_name]


# ─────────────────────────────────────────────────────────────────────────────
# agent_runs logging hook
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class AgentRunRecord:
    """Payload written to ``rce.agent_runs`` after each LLM call.

    Forward-compatible with the C1-01 schema (``rce.agent_runs``):
    ``agent_run_id, agent_id, agent_version, case_id, inputs_digest,
    output_digest, status, started_at, finished_at, llm_model_used, cost_tokens``.
    """

    agent_id: str  # e.g. "llm_router"
    model_name: str
    task_class: TaskClass
    tokens_in: int
    tokens_out: int
    cost_usd: float
    inputs_digest: str
    output_digest: str
    case_id: Optional[str] = None
    extra: Mapping[str, object] = field(default_factory=dict)


AgentRunLogger = Callable[[AgentRunRecord], None]


_LOGGER: Optional[AgentRunLogger] = None


def set_agent_run_logger(logger: Optional[AgentRunLogger]) -> None:
    """Install the callable that persists an :class:`AgentRunRecord`.

    Production wires this to a function that INSERTs into ``rce.agent_runs``
    once C1-01 lands. Tests install a list-appender and assert against it.
    Setting to ``None`` disables logging.
    """
    global _LOGGER
    _LOGGER = logger


def _log_agent_run(record: AgentRunRecord) -> None:
    if _LOGGER is not None:
        _LOGGER(record)


# ─────────────────────────────────────────────────────────────────────────────
# LLMHandle
# ─────────────────────────────────────────────────────────────────────────────


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


@dataclass
class LLMHandle:
    """Concrete result of :func:`route_llm`. Carries the model identity and
    metadata about the last :meth:`complete` call.

    Use the dataclass attributes (``model_name``, ``token_budget``, ``escalated``,
    ``escalation_reason``) before calling :meth:`complete`. After the call,
    ``cost_usd``, ``tokens_in``, ``tokens_out``, and ``output_digest`` are
    populated and a row is written via the registered agent_runs logger.
    """

    model_name: str
    task_class: TaskClass
    token_budget: int
    escalated: bool = False
    escalation_reason: Optional[str] = None

    # Populated by complete()
    cost_usd: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    inputs_digest: str = ""
    output_digest: str = ""

    async def complete(
        self,
        prompt: str,
        *,
        max_tokens: int = 2048,
        case_id: Optional[str] = None,
        **kwargs: object,
    ) -> str:
        """Call the registered completer for :attr:`model_name`.

        Records token + cost on this handle and forwards to the agent_runs
        logger (if installed). Returns the model's text output.
        """
        if self.model_name is None:
            raise LLMRoutingError(
                f"Task class {self.task_class!r} has no model "
                f"(use the pure-regex / rule path instead)."
            )
        completer = _get_completer(self.model_name)
        result = await completer(prompt, max_tokens=max_tokens, **kwargs)
        self.tokens_in = result.tokens_in
        self.tokens_out = result.tokens_out
        self.inputs_digest = _digest(prompt)
        self.output_digest = _digest(result.text)
        self.cost_usd = usd_cost(self.model_name, self.tokens_in, self.tokens_out)
        _log_agent_run(
            AgentRunRecord(
                agent_id="llm_router",
                model_name=self.model_name,
                task_class=self.task_class,
                tokens_in=self.tokens_in,
                tokens_out=self.tokens_out,
                cost_usd=self.cost_usd,
                inputs_digest=self.inputs_digest,
                output_digest=self.output_digest,
                case_id=case_id,
                extra={
                    "escalated": self.escalated,
                    "escalation_reason": self.escalation_reason,
                    "max_tokens": max_tokens,
                },
            )
        )
        return result.text

    def complete_sync(
        self,
        prompt: str,
        *,
        max_tokens: int = 2048,
        case_id: Optional[str] = None,
        **kwargs: object,
    ) -> str:
        """Synchronous convenience wrapper for non-async call sites."""
        return asyncio.run(
            self.complete(prompt, max_tokens=max_tokens, case_id=case_id, **kwargs)
        )


# ─────────────────────────────────────────────────────────────────────────────
# Public router function
# ─────────────────────────────────────────────────────────────────────────────


def _resolve_task_class(task_class: str) -> TaskClass:
    if task_class in ROUTING_TABLE:
        return task_class  # type: ignore[return-value]
    aliased = _TASK_ALIASES.get(task_class)
    if aliased is None:
        raise LLMRoutingError(
            f"Unknown task_class {task_class!r}. "
            f"Known: {sorted(ROUTING_TABLE)} (aliases: {sorted(_TASK_ALIASES)})"
        )
    return aliased


def _should_escalate(
    task_class: TaskClass,
    *,
    current_confidence: Optional[float] = None,
    validator_failed: bool = False,
    cosine_gap: Optional[float] = None,
    intent: Optional[str] = None,
    sensitive_topic: bool = False,
) -> Tuple[bool, Optional[str]]:
    if task_class == "document_classification":
        threshold = ESCALATION_CONFIDENCE_THRESHOLDS[task_class]
        if current_confidence is not None and current_confidence < threshold:
            return True, f"classifier confidence {current_confidence:.2f} < {threshold:.2f}"
        return False, None

    if task_class == "field_extraction":
        threshold = ESCALATION_CONFIDENCE_THRESHOLDS[task_class]
        if validator_failed:
            return True, "validator failure"
        if current_confidence is not None and current_confidence < threshold:
            return True, f"confidence {current_confidence:.2f} < {threshold:.2f}"
        return False, None

    if task_class == "entity_resolution_fallback":
        if cosine_gap is not None and cosine_gap < 0.05:
            return True, f"candidate cluster within 0.05 cosine ({cosine_gap:.3f})"
        return False, None

    if task_class == "pathway_conversational":
        if intent == "explain":
            return True, "'explain' intent"
        if sensitive_topic:
            return True, "sensitive topic"
        return False, None

    # eligibility_reasoning + policy_clause_extraction default to the
    # premium model already; no escalation path exists.
    return False, None


_DEFAULT_TOKEN_BUDGETS: Mapping[TaskClass, int] = {
    "document_classification": 512,
    "mrz_extraction": 0,  # no model; budget is meaningless
    "field_extraction": 2048,
    "entity_resolution_fallback": 1024,
    "eligibility_reasoning": 4096,
    "policy_clause_extraction": 4096,
    "pathway_conversational": 1024,
}


def route_llm(
    task_class: str,
    *,
    current_confidence: Optional[float] = None,
    validator_failed: bool = False,
    cosine_gap: Optional[float] = None,
    intent: Optional[str] = None,
    sensitive_topic: bool = False,
    token_budget: Optional[int] = None,
) -> LLMHandle:
    """Pick the right model for ``task_class`` per Architecture Report §11.

    Keyword arguments express the inputs to the escalation rules (none of
    which require an LLM call). Returns an :class:`LLMHandle` bound to the
    selected model — call ``await handle.complete(prompt)`` to actually run
    the request.

    Raises :class:`LLMRoutingError` for unknown task classes or pricing
    inconsistencies.

    Aliases: ``"extraction"`` maps to ``"field_extraction"`` for ergonomic
    callers; the canonical §11 name is preferred.
    """
    resolved = _resolve_task_class(task_class)
    decision = ROUTING_TABLE[resolved]
    escalate, reason = _should_escalate(
        resolved,
        current_confidence=current_confidence,
        validator_failed=validator_failed,
        cosine_gap=cosine_gap,
        intent=intent,
        sensitive_topic=sensitive_topic,
    )

    if decision.default_model is None:
        # mrz_extraction — return a handle that documents the no-LLM path.
        return LLMHandle(
            model_name=cast_no_model_sentinel(),
            task_class=resolved,
            token_budget=0,
            escalated=False,
            escalation_reason=decision.escalation_reason,
        )

    model = decision.escalate_model if escalate and decision.escalate_model else decision.default_model

    # FD-2/AIQ-994: staged Claude Fable 5 migration for policy-clause extraction.
    # OFF by default — only when POLICY_PARSING_FABLE5 is truthy does this route
    # policy_clause_extraction to claude-fable-5 (1M context, whole-manual single
    # pass). Gated so the live cost+accuracy benchmark (scripts/benchmark_policy_fable5.py)
    # justifies the switch before it reaches prod; the chunking fallback stays the
    # default path until then. Fable 5 is ~3.3x Sonnet's price — do not enable blindly.
    if (
        resolved == "policy_clause_extraction"
        and os.environ.get("POLICY_PARSING_FABLE5", "").strip().lower() in ("1", "true", "yes")
    ):
        model = "claude-fable-5"

    budget = token_budget if token_budget is not None else _DEFAULT_TOKEN_BUDGETS[resolved]

    # Validate pricing up-front so misconfiguration fails fast.
    _ = usd_cost(model, 0, 0)

    return LLMHandle(
        model_name=model,
        task_class=resolved,
        token_budget=budget,
        escalated=escalate and decision.escalate_model is not None,
        escalation_reason=reason if (escalate and decision.escalate_model is not None) else None,
    )


_NO_MODEL_SENTINEL = "__no_model__"


def cast_no_model_sentinel() -> str:
    """Sentinel returned by :func:`route_llm` for purely-deterministic tasks
    (currently only MRZ extraction). Callers must not pass this to a
    completer — guard with :func:`is_no_model_handle` before calling
    :meth:`LLMHandle.complete`.
    """
    return _NO_MODEL_SENTINEL


def is_no_model_handle(handle: LLMHandle) -> bool:
    return handle.model_name == _NO_MODEL_SENTINEL


# ─────────────────────────────────────────────────────────────────────────────
# Passport OCR backend split (Parker Step F)
# ─────────────────────────────────────────────────────────────────────────────
#
# The mrz_extraction routing row above models the *MRZ-string* regex job. Passport
# *image* OCR (the GPT-4o vision extractor vs. the self-hosted OSS path) is a
# different axis that the cost-table ROUTING_TABLE doesn't describe, so the split
# lives here as pure, env-driven helpers. The OSS path is dark by default
# (PASSPORT_OCR_OSS_SHARE=0.0) — production passport traffic is unchanged until a
# human raises the share after reviewing the shadow comparison.

PassportOcrBackend = Literal["gpt4o", "oss"]


def passport_ocr_oss_share() -> float:
    """Fraction of passport-OCR traffic routed to the OSS path. Default 0.0.

    Read from ``PASSPORT_OCR_OSS_SHARE`` and clamped to ``[0.0, 1.0]``. A
    malformed value falls back to 0.0 (fail-safe: keep GPT-4o).
    """
    try:
        share = float(os.environ.get("PASSPORT_OCR_OSS_SHARE", "0.0"))
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, share))


def shadow_compare_enabled() -> bool:
    """Whether SHADOW_COMPARE mode is on (run both extractors, return GPT-4o)."""
    return os.environ.get("SHADOW_COMPARE", "").strip().lower() in {"1", "true", "yes", "on"}


def choose_passport_ocr_backend(
    roll: float, share: Optional[float] = None
) -> PassportOcrBackend:
    """Pure backend choice: ``oss`` iff ``roll < share`` (default share from env).

    ``roll`` is a caller-supplied uniform in ``[0, 1)`` (e.g. a hash of the case
    id). With the default share of 0.0 this always returns ``gpt4o``.
    """
    s = passport_ocr_oss_share() if share is None else max(0.0, min(1.0, share))
    return "oss" if roll < s else "gpt4o"
