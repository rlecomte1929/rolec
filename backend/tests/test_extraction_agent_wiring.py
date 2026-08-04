"""AIQ-1765: every built extraction agent must be reachable, or explicitly not.

The defect class this guards: an extraction agent is written, tested, merged —
and never wired into the registry the orchestrator selects from. It then sits
inert in prod. `rce_extraction_orchestrator._agent_class()` returns None, the
orchestrator records `skipped_no_agent`, and nothing errors. The document is
classified, then silently dropped.

This has now happened twice:
  * VISA_PERMIT (AIQ-1309 shipped the agent; the rce.document_types row was
    missing, so the same silent-skip resulted) — fixed 2026-08-04.
  * DiplomaAgent + TaxCert{De,Fr,No}Agent — found 2026-08-04 during the AIQ-1760
    decomposition. Prod `rce.document_types` advertises DIPLOMA and TAX_CERT,
    so both classified and then went nowhere.

Root cause both times: nothing forced the wiring. A new agent module could be
added with no route to it and every test stayed green. This test is that force.

Pure stdlib + AST — no DB, no network.
"""
from __future__ import annotations

import ast
import os
import unittest
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite://")

_EXTRACTION_DIR = (
    Path(__file__).resolve().parents[1] / "relopass" / "agents" / "extraction"
)

# Modules that are infrastructure, not agents.
_NON_AGENT_MODULES = {"__init__", "_common"}


def _agent_classes_by_module() -> dict:
    """Map module stem -> [class names ending in 'Agent'] declared in it.

    AST-based: importing every module would drag in optional heavy deps and
    would also mask the very thing under test (a module can import fine and
    still be unreachable).
    """
    out: dict = {}
    for path in sorted(_EXTRACTION_DIR.glob("*.py")):
        stem = path.stem
        if stem in _NON_AGENT_MODULES or stem.startswith("_"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        classes = [
            node.name
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name.endswith("Agent")
        ]
        if classes:
            out[stem] = classes
    return out


def _reachable_class_names() -> set:
    """Every agent class the orchestrator can actually reach.

    Two routes exist and both count: the registry, and the explicit special-case
    in `_agent_class` (PASSPORT_TD3 predates the registry and is selected before
    the lookup).
    """
    from backend.app.services import rce_extraction_orchestrator as orch
    from backend.relopass.agents.extraction import EXTRACTION_AGENT_REGISTRY

    reachable = {cls.__name__ for cls in EXTRACTION_AGENT_REGISTRY.values()}

    # Probe the special-cased codes through the real selector rather than
    # re-encoding the branch here — if the special case is refactored away, this
    # picks up the new behaviour instead of asserting a stale assumption.
    for code in ("PASSPORT_TD3", "PASSPORT"):
        cls = orch._agent_class(code)
        if cls is not None:
            reachable.add(cls.__name__)
    return reachable


class ExtractionAgentWiringTests(unittest.TestCase):
    def test_every_agent_is_reachable_or_explicitly_unreachable(self):
        """The core guard. A new agent module must be wired or justified."""
        from backend.relopass.agents.extraction import UNREACHABLE_AGENTS

        declared = {
            cls
            for classes in _agent_classes_by_module().values()
            for cls in classes
        }
        reachable = _reachable_class_names()
        unaccounted = declared - reachable - set(UNREACHABLE_AGENTS)

        self.assertEqual(
            unaccounted,
            set(),
            "These extraction agents exist but the orchestrator cannot reach them, "
            "and they are not listed in UNREACHABLE_AGENTS with a reason. They will "
            "be classified and then silently skipped in prod (skipped_no_agent). "
            "Either register the agent in EXTRACTION_AGENT_REGISTRY, or add it to "
            f"UNREACHABLE_AGENTS with the reason it cannot be wired yet: {sorted(unaccounted)}",
        )

    def test_unreachable_list_stays_honest(self):
        """An agent that becomes reachable must leave UNREACHABLE_AGENTS.

        Without this the list rots into a permanent excuse and stops meaning
        anything — the same property `test_allowlist_stays_honest` enforces for
        the case-id guard.
        """
        from backend.relopass.agents.extraction import UNREACHABLE_AGENTS

        reachable = _reachable_class_names()
        stale = set(UNREACHABLE_AGENTS) & reachable
        self.assertEqual(
            stale,
            set(),
            f"Listed as unreachable but now reachable — remove them: {sorted(stale)}",
        )

    def test_every_unreachable_entry_has_a_reason(self):
        from backend.relopass.agents.extraction import UNREACHABLE_AGENTS

        for name, reason in UNREACHABLE_AGENTS.items():
            self.assertTrue(
                reason and len(reason.strip()) > 20,
                f"{name} is excluded with no substantive reason: {reason!r}",
            )

    def test_diploma_is_reachable(self):
        """AIQ-1765's concrete fix: DIPLOMA resolves to an agent."""
        from backend.app.services.rce_extraction_orchestrator import _agent_class

        cls = _agent_class("DIPLOMA")
        self.assertIsNotNone(cls, "DIPLOMA has a prod document_types row but no agent")
        self.assertEqual(cls.__name__, "DiplomaAgent")

    def test_previously_registered_agents_are_untouched(self):
        """No-regression: the 5 pre-existing registrations still resolve."""
        from backend.app.services.rce_extraction_orchestrator import _agent_class

        for code, expected in (
            ("MARRIAGE_CERT", "MarriageCertAgent"),
            ("BIRTH_CERT", "BirthCertAgent"),
            ("FOSTER_CARE_ORDER", "FosterCareOrderAgent"),
            ("ID_CARD", "IdCardAgent"),
            ("VISA_PERMIT", "VisaPermitAgent"),
            ("PASSPORT_TD3", "PassportTd3Agent"),
        ):
            cls = _agent_class(code)
            self.assertIsNotNone(cls, f"{code} regressed to unreachable")
            self.assertEqual(cls.__name__, expected)

    def test_unknown_type_still_returns_none(self):
        """Fail-soft is preserved: an unmapped code must not raise."""
        from backend.app.services.rce_extraction_orchestrator import _agent_class

        self.assertIsNone(_agent_class("NOT_A_REAL_DOCUMENT_TYPE"))


if __name__ == "__main__":
    unittest.main()
