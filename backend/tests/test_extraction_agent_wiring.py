"""AIQ-1765 — every extraction agent must be reachable from the orchestrator.

Four agents (DiplomaAgent, TaxCertDeAgent, TaxCertFrAgent, TaxCertNoAgent) were fully
built, exported from ``extraction/__init__.py`` — and referenced nowhere else, so
``_agent_class`` returned None and the orchestrator recorded ``skipped_no_agent``. The
VISA_PERMIT agent had the same defect before it. Twice is a pattern; this test is the
thing that stops a third.

It DISCOVERS agent classes rather than listing them, so a newly added agent module is
covered the moment it lands. It deliberately does not assert a count — a count would
just have to be bumped, which is how the first two slipped through.
"""
from __future__ import annotations

import importlib
import inspect
import pkgutil
import unittest

from backend.app.services.rce_extraction_orchestrator import _agent_class, agent_kwargs
from backend.relopass.agents import (
    AgentRegistry,
    InMemoryAgentStorage,
    extraction as extraction_pkg,
)
from backend.relopass.agents.extraction import EXTRACTION_AGENT_REGISTRY
from backend.relopass.agents.runtime import InMemoryExtractionSink

# Reachable without a code in the registry, and why.
_SPECIAL_CASES = {
    "PassportTd3Agent": "routed by the PASSPORT_TD3 / PASSPORT special case in _agent_class",
}


def _discover_agent_classes():
    """Every ``*Agent`` class defined in a module under ``agents/extraction/``."""
    found = {}
    for mod_info in pkgutil.iter_modules(extraction_pkg.__path__):
        if mod_info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{extraction_pkg.__name__}.{mod_info.name}")
        for name, obj in vars(module).items():
            # Defined here, not imported from a sibling — otherwise every re-export counts.
            if (
                inspect.isclass(obj)
                and name.endswith("Agent")
                and obj.__module__ == module.__name__
            ):
                found[name] = (obj, mod_info.name)
    return found


class TestExtractionAgentWiring(unittest.TestCase):
    def test_every_agent_class_has_a_route(self):
        """The guard. Comment out a registry line and this fails, naming the agent."""
        routed = set(EXTRACTION_AGENT_REGISTRY.values())
        unreachable = [
            f"{name} ({module}.py)"
            for name, (cls, module) in sorted(_discover_agent_classes().items())
            if cls not in routed and name not in _SPECIAL_CASES
        ]
        self.assertEqual(
            unreachable, [],
            "Extraction agents exist with no route from _agent_class — they will record "
            "skipped_no_agent forever. Register each in EXTRACTION_AGENT_REGISTRY, or add "
            f"an explicit entry to _SPECIAL_CASES with the reason: {unreachable}",
        )

    def test_discovery_actually_finds_agents(self):
        """Guard the guard: if discovery silently found nothing, the test above passes
        vacuously and stops protecting anything."""
        found = _discover_agent_classes()
        self.assertGreater(len(found), 5)
        for expected in ("DiplomaAgent", "TaxCertDeAgent", "TaxCertFrAgent",
                         "TaxCertNoAgent", "PassportTd3Agent"):
            self.assertIn(expected, found)

    def test_diploma_is_routable(self):
        self.assertIsNotNone(_agent_class("DIPLOMA"))

    def test_each_tax_cert_routes_by_its_own_code(self):
        """[AIQ-1774] One code per locale, resolved by the flat registry.

        Previously all three shared a bare ``TAX_CERT`` code and were discriminated
        by an ``issuing_country`` argument nothing ever supplied, so all three were
        inert. These three assertions are what "the split landed" means.
        """
        from backend.relopass.agents.extraction import (
            TaxCertDeAgent, TaxCertFrAgent, TaxCertNoAgent,
        )
        self.assertIs(_agent_class("TAX_CERT_DE"), TaxCertDeAgent)
        self.assertIs(_agent_class("TAX_CERT_FR"), TaxCertFrAgent)
        self.assertIs(_agent_class("TAX_CERT_NO"), TaxCertNoAgent)

    def test_bare_tax_cert_still_refuses_to_guess(self):
        """The old shared code must not silently resolve to one of the three.

        It is retired, but an old row or a stale caller can still present it. Three
        genuinely different documents mean picking one blind would emit confidently
        wrong fields — so it stays unrouted, and the orchestrator records
        skipped_no_agent rather than guessing.
        """
        self.assertIsNone(_agent_class("TAX_CERT"))

    def test_the_three_tax_codes_are_distinct(self):
        """Guard against a copy-paste that gives two locales the same code — which
        would make the registry silently drop one agent (dict key collision)."""
        from backend.relopass.agents.extraction import (
            TAX_CERT_DE_DOCUMENT_TYPE,
            TAX_CERT_FR_DOCUMENT_TYPE,
            TAX_CERT_NO_DOCUMENT_TYPE,
        )
        codes = [TAX_CERT_DE_DOCUMENT_TYPE, TAX_CERT_FR_DOCUMENT_TYPE,
                 TAX_CERT_NO_DOCUMENT_TYPE]
        self.assertEqual(len(set(codes)), 3, f"tax-cert codes collide: {codes}")
        for code in codes:
            self.assertIn(code, EXTRACTION_AGENT_REGISTRY)

    def test_existing_registrations_unchanged(self):
        """The 5 agents registered before this change must keep working untouched."""
        for code in ("MARRIAGE_CERT", "BIRTH_CERT", "FOSTER_CARE_ORDER", "ID_CARD",
                     "VISA_PERMIT"):
            self.assertIsNotNone(_agent_class(code), f"{code} lost its route")
        self.assertIsNotNone(_agent_class("PASSPORT_TD3"))
        self.assertIsNotNone(_agent_class("PASSPORT"))

    def test_unknown_type_still_returns_none(self):
        """No behaviour change for document types that genuinely have no agent."""
        self.assertIsNone(_agent_class("CONTRACT"))
        self.assertIsNone(_agent_class(""))

    # ── Reachable is not the same as constructible ────────────────────────────

    def test_every_routed_code_actually_constructs(self):
        """[AIQ-1780] Routing an agent proves nothing if building it raises.

        PassportTd3Agent declares ``di_provider`` with no default while the
        orchestrator built every agent with only (registry, sink) — so it resolved
        fine, then died with TypeError inside the fail-soft, and EVERY passport
        recorded status='failed'. The tests above could not see it: they assert
        ``_agent_class()`` returns a class and never instantiate one.

        This closes the whole class rather than that one instance, and it calls the
        SAME ``agent_kwargs`` production uses — a test that reimplemented the
        constructor contract could drift from it and prove nothing.
        """
        failures = []
        for code in sorted(set(EXTRACTION_AGENT_REGISTRY) | {"PASSPORT_TD3", "PASSPORT"}):
            cls = _agent_class(code)
            self.assertIsNotNone(cls, f"{code} lost its route")
            try:
                cls(**agent_kwargs(
                    code,
                    registry=AgentRegistry(InMemoryAgentStorage()),
                    sink=InMemoryExtractionSink(),
                ))
            except Exception as exc:  # noqa: BLE001 — report every one, not just the first
                failures.append(f"{code} -> {cls.__name__}: {type(exc).__name__}: {exc}")

        self.assertEqual(
            failures, [],
            "Registered agents that the orchestrator cannot construct. They resolve, "
            "then raise inside dispatch_and_run's fail-soft and record status='failed' "
            f"for every document of that type: {failures}",
        )

    def test_passport_gets_a_di_provider(self):
        """The specific regression: passport is the only type whose OCR key is
        configured in production, so it is the one that must construct."""
        for code in ("PASSPORT_TD3", "PASSPORT"):
            kwargs = agent_kwargs(
                code,
                registry=AgentRegistry(InMemoryAgentStorage()),
                sink=InMemoryExtractionSink(),
            )
            self.assertIn("di_provider", kwargs, f"{code} must be given a di_provider")

    def test_non_passport_types_get_no_di_provider(self):
        """Don't hand di_provider to agents that don't accept it — that would swap
        one TypeError for another."""
        kwargs = agent_kwargs(
            "MARRIAGE_CERT",
            registry=AgentRegistry(InMemoryAgentStorage()),
            sink=InMemoryExtractionSink(),
        )
        self.assertNotIn("di_provider", kwargs)
        self.assertNotIn("resolver", kwargs)  # no resolver passed → not injected


if __name__ == "__main__":
    unittest.main()
