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
from backend.relopass.agents.extraction import (
    EXTRACTION_AGENT_REGISTRY,
    TAX_CERT_AGENTS_BY_ISSUING_COUNTRY,
    TAX_CERT_DOCUMENT_TYPE,
)

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
        routed = set(EXTRACTION_AGENT_REGISTRY.values()) | set(
            TAX_CERT_AGENTS_BY_ISSUING_COUNTRY.values()
        )
        unreachable = [
            f"{name} ({module}.py)"
            for name, (cls, module) in sorted(_discover_agent_classes().items())
            if cls not in routed and name not in _SPECIAL_CASES
        ]
        self.assertEqual(
            unreachable, [],
            "Extraction agents exist with no route from _agent_class — they will record "
            "skipped_no_agent forever. Register each in EXTRACTION_AGENT_REGISTRY (or "
            "TAX_CERT_AGENTS_BY_ISSUING_COUNTRY), or add an explicit entry to _SPECIAL_CASES "
            f"with the reason: {unreachable}",
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

    def test_tax_cert_routes_by_issuing_country(self):
        from backend.relopass.agents.extraction import (
            TaxCertDeAgent, TaxCertFrAgent, TaxCertNoAgent,
        )
        self.assertIs(_agent_class("TAX_CERT", issuing_country="DEU"), TaxCertDeAgent)
        self.assertIs(_agent_class("TAX_CERT", issuing_country="FRA"), TaxCertFrAgent)
        self.assertIs(_agent_class("TAX_CERT", issuing_country="NOR"), TaxCertNoAgent)
        # Case/whitespace tolerant — the country may arrive from a DB column.
        self.assertIs(_agent_class("TAX_CERT", issuing_country=" fra "), TaxCertFrAgent)

    def test_tax_cert_without_a_country_refuses_to_guess(self):
        """Three genuinely different documents share one code. Picking one blind would
        emit confidently wrong fields, so an unknown country must return None."""
        self.assertIsNone(_agent_class("TAX_CERT"))
        self.assertIsNone(_agent_class("TAX_CERT", issuing_country=""))
        self.assertIsNone(_agent_class("TAX_CERT", issuing_country="ESP"))

    def test_all_three_tax_agents_answer_to_one_code(self):
        from backend.relopass.agents.extraction import (
            TAX_CERT_DE_DOCUMENT_TYPE,
            TAX_CERT_FR_DOCUMENT_TYPE,
            TAX_CERT_NO_DOCUMENT_TYPE,
        )
        self.assertEqual(
            {TAX_CERT_DE_DOCUMENT_TYPE, TAX_CERT_FR_DOCUMENT_TYPE, TAX_CERT_NO_DOCUMENT_TYPE},
            {TAX_CERT_DOCUMENT_TYPE},
        )

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
