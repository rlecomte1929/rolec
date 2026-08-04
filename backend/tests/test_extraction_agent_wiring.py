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

from backend.app.services.rce_extraction_orchestrator import _agent_class
from backend.relopass.agents import extraction as extraction_pkg
from backend.relopass.agents.extraction import EXTRACTION_AGENT_REGISTRY

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


if __name__ == "__main__":
    unittest.main()
