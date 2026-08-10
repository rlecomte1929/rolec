"""AIQ-1780 — the relopass LLM router must have vendor completers registered at boot.

Nothing ever called ``register_completer`` in production. ``_get_completer`` raises
``LLMRoutingError`` for an unregistered model, ``_common.call_llm_with_retry`` catches
it and returns ``LLMCallResult.empty()`` — so every LLM-based extraction agent ran
against an empty payload, wrote an ``rce.agent_runs`` row stamped
``"(none — LLM unrouted)"`` and emitted zero fields. Silently, because every layer on
that path is fail-soft. These tests are the thing that notices if it regresses.
"""
from __future__ import annotations

import asyncio
import os
import unittest
from unittest.mock import patch

from backend.app.services.llm_router_clients import install_router_completers
from backend.relopass.llm import reset_registry, route_llm
from backend.relopass.llm.router import CompletionResult, set_agent_run_logger


class LlmRouterClientsTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry()
        set_agent_run_logger(None)

    def tearDown(self) -> None:
        reset_registry()
        set_agent_run_logger(None)

    # ── registration ──────────────────────────────────────────────────────────

    def test_registers_every_model_the_router_can_route_to(self):
        """A model the ROUTING_TABLE can pick but nobody registered is the whole bug."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "k", "ANTHROPIC_API_KEY": "k"},
                        clear=False):
            status = install_router_completers()
        for model in ("gpt-4o-mini", "gpt-4o", "claude-sonnet-4-6"):
            self.assertEqual(status.get(model), "registered", f"{model} not registered")

    def test_every_routed_task_class_resolves_to_a_registered_completer(self):
        """Walk the router the way production does, rather than trusting a model list."""
        from backend.relopass.llm.router import _get_completer

        with patch.dict(os.environ, {"OPENAI_API_KEY": "k", "ANTHROPIC_API_KEY": "k"},
                        clear=False):
            install_router_completers()

        for task_class in ("document_classification", "field_extraction",
                           "entity_resolution_fallback", "eligibility_reasoning",
                           "pathway_conversational"):
            for escalate in (False, True):
                handle = route_llm(task_class, validator_failed=escalate)
                if handle.model_name.startswith("__"):
                    continue  # sentinel: no model for this class (e.g. mrz_extraction)
                try:
                    _get_completer(handle.model_name)
                except Exception as exc:  # noqa: BLE001
                    self.fail(f"{task_class} (escalate={escalate}) -> "
                              f"{handle.model_name}: {type(exc).__name__}: {exc}")

    # ── the fail-soft trap ────────────────────────────────────────────────────

    def test_no_registration_without_an_api_key(self):
        """Load-bearing, not tidiness.

        call_llm_with_retry catches only LLMRoutingError. A completer that raised
        RuntimeError('OPENAI_API_KEY … not set') would escape it and convert today's
        quiet 'zero fields' into an exception inside the extraction pipeline. Leaving
        the model unregistered preserves the existing, already-handled degradation.
        """
        with patch.dict(os.environ, {}, clear=True):
            status = install_router_completers()
        for model in ("gpt-4o-mini", "gpt-4o", "claude-sonnet-4-6"):
            self.assertIn("skipped", status.get(model, ""),
                          f"{model} was registered without an API key")

    def test_partial_keys_register_only_that_vendor(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "k"}, clear=True):
            status = install_router_completers()
        self.assertEqual(status["gpt-4o-mini"], "registered")
        self.assertIn("skipped", status["claude-sonnet-4-6"])

    def test_single_vendor_escalation_raises_rather_than_silently_emptying(self):
        """Pins a deliberate behaviour change, so it is not rediscovered as a bug.

        With OpenAI registered but Anthropic not, a validator failure escalates to an
        unregistered claude-sonnet-4-6 and call_llm_with_retry raises
        ExtractionRuntimeError instead of returning an empty payload. The orchestrator's
        fail-soft still catches it (status='failed' rather than 'OK' with zero fields),
        which is the more honest outcome. Production sets both keys.
        """
        import json

        from backend.relopass.agents.extraction._common import call_llm_with_retry
        from backend.relopass.agents.runtime import ExtractionRuntimeError

        async def _missing_key(*, system, user, model, max_tokens=None):
            return (json.dumps({"something_else": True}), 10, 5)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "k"}, clear=True):
            install_router_completers()
        with patch("backend.app.services.llm_client.complete_text_with_usage", _missing_key):
            with self.assertRaises(ExtractionRuntimeError):
                asyncio.run(call_llm_with_retry("p", required_keys=("is_marriage_cert",)))

    def test_is_idempotent(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "k", "ANTHROPIC_API_KEY": "k"},
                        clear=False):
            first = install_router_completers()
            second = install_router_completers()
        self.assertEqual(first, second)

    # ── the completer contract ────────────────────────────────────────────────

    def test_openai_completer_returns_real_token_counts(self):
        """CompletionResult.tokens_* feed usd_cost() and land on every agent_runs row.
        Returning 0/0 would silently zero the AI unit-economics rollups."""
        async def _fake(*, system, user, model, max_tokens=None):
            return ("the-text", 321, 123)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "k"}, clear=False):
            install_router_completers()
        with patch("backend.app.services.llm_client.complete_text_with_usage", _fake):
            handle = route_llm("field_extraction")
            text = asyncio.run(handle.complete("prompt", max_tokens=2048))

        self.assertEqual(text, "the-text")
        self.assertEqual(handle.tokens_in, 321)
        self.assertEqual(handle.tokens_out, 123)
        self.assertGreater(handle.cost_usd, 0.0, "real tokens must produce a real cost")

    def test_completer_forwards_the_prompt_and_token_budget(self):
        seen: dict = {}

        async def _fake(*, system, user, model, max_tokens=None):
            seen.update(system=system, user=user, model=model, max_tokens=max_tokens)
            return ("{}", 1, 1)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "k"}, clear=False):
            install_router_completers()
        with patch("backend.app.services.llm_client.complete_text_with_usage", _fake):
            handle = route_llm("field_extraction")
            asyncio.run(handle.complete("THE PROMPT", max_tokens=777))

        self.assertEqual(seen["user"], "THE PROMPT")
        self.assertEqual(seen["system"], "")   # the agent prompt is the whole payload
        self.assertEqual(seen["max_tokens"], 777)
        self.assertEqual(seen["model"], "gpt-4o-mini")

    def test_completer_returns_a_completion_result(self):
        async def _fake(*, system, user, model, max_tokens=None):
            return ("x", 2, 3)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "k"}, clear=False):
            install_router_completers()
        from backend.relopass.llm.router import _get_completer

        with patch("backend.app.services.llm_client.complete_text_with_usage", _fake):
            out = asyncio.run(_get_completer("gpt-4o-mini")("p", max_tokens=10))
        self.assertIsInstance(out, CompletionResult)
        self.assertEqual((out.text, out.tokens_in, out.tokens_out), ("x", 2, 3))


class LlmClientUsageHelperTests(unittest.TestCase):
    """_text_and_usage is what makes real cost reporting possible."""

    def test_extracts_text_and_usage(self):
        from backend.app.services.llm_client import _text_and_usage

        class _U:
            prompt_tokens, completion_tokens = 11, 22

        class _M:
            content = "hello"

        class _C:
            message = _M()

        class _R:
            choices, usage = [_C()], _U()

        self.assertEqual(_text_and_usage(_R()), ("hello", 11, 22))

    def test_degrades_to_zero_when_usage_is_absent(self):
        """Some streaming/error shapes carry no usage — the text is what callers need."""
        from backend.app.services.llm_client import _text_and_usage

        class _M:
            content = "hi"

        class _C:
            message = _M()

        class _R:
            choices, usage = [_C()], None

        self.assertEqual(_text_and_usage(_R()), ("hi", 0, 0))

    def test_never_raises_on_a_malformed_response(self):
        from backend.app.services.llm_client import _text_and_usage

        class _R:
            choices, usage = [], None

        self.assertEqual(_text_and_usage(_R()), ("", 0, 0))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
