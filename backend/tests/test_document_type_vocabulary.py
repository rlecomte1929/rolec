"""AIQ-1774: the classifier and the runtime must agree on document-type codes.

The defect this guards: three vocabularies drifted apart with nothing to notice.
Measured 2026-08-04, the classifier and the runtime registry shared **exactly one**
code (`PASSPORT_TD3`) — so of seven wired extraction agents, only the passport one
could ever be selected once the real classifier lands. Every other agent was
reachable only from a code the classifier cannot emit.

Nothing failed. Documents would classify, resolve to no agent, and record
`skipped_no_agent` — the same silent-skip that hid the VISA_PERMIT and Diploma
defects. Silence is this area's characteristic failure mode.

The guard is the same shape as `test_extraction_agent_wiring.py`: every code must
be mapped, or explicitly listed with a reason, and the lists must stay honest.

Pure stdlib + a prompt-file read — no DB, no network.
"""
from __future__ import annotations

import os
import re
import unittest
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite://")

from backend.app.services.document_type_vocabulary import (  # noqa: E402
    CLASSIFIER_PENDING_RUNTIME,
    CLASSIFIER_TO_RUNTIME,
    RUNTIME_DOCUMENT_TYPES,
    RUNTIME_WITHOUT_CLASSIFIER,
    runtime_code_for,
)

_PROMPT = (
    Path(__file__).resolve().parents[2]
    / "prompts"
    / "docs"
    / "classifier"
    / "v1.txt"
)

# The prompt lists its codes as "- CODE: description" under the DOCUMENT TYPE
# CODES heading. Parsed rather than hardcoded so that adding a code to the prompt
# — the realistic way drift is reintroduced — is what trips this test.
_CODE_LINE = re.compile(r"^-\s+([A-Z][A-Z_0-9]{3,})\s*:")


def _classifier_codes() -> set:
    text = _PROMPT.read_text(encoding="utf-8")
    start = text.index("# DOCUMENT TYPE CODES")
    end = text.index("# OUTPUT SCHEMA")
    return {
        m.group(1)
        for line in text[start:end].splitlines()
        if (m := _CODE_LINE.match(line))
    }


class ClassifierPromptParsing(unittest.TestCase):
    """The guard is only as good as this parse — pin it, as AIQ-1735 taught."""

    def test_prompt_yields_a_plausible_code_set(self):
        codes = _classifier_codes()
        self.assertIn("PASSPORT_TD3", codes)
        self.assertIn("EMPLOYMENT_CONTRACT", codes)
        self.assertGreaterEqual(
            len(codes), 8, f"parsed too few codes — the prompt format likely changed: {sorted(codes)}"
        )

    def test_parser_ignores_prose_mentions(self):
        # UNKNOWN is discussed in the rules but is not a document-type entry.
        self.assertNotIn("UNKNOWN", _classifier_codes())


class VocabularyReconciliation(unittest.TestCase):
    def test_every_classifier_code_is_mapped_or_explained(self):
        """The core guard. A new classifier code needs a decision, not silence."""
        codes = _classifier_codes()
        accounted = set(CLASSIFIER_TO_RUNTIME) | set(CLASSIFIER_PENDING_RUNTIME)
        unaccounted = codes - accounted
        self.assertEqual(
            unaccounted,
            set(),
            "These classifier codes have no entry in document_type_vocabulary. A document "
            "classified as one of them resolves to no agent and is silently skipped. Either map "
            "it in CLASSIFIER_TO_RUNTIME, or record it in CLASSIFIER_PENDING_RUNTIME with the "
            f"reason no agent handles it yet: {sorted(unaccounted)}",
        )

    def test_every_runtime_code_is_reachable_or_explained(self):
        accounted = set(CLASSIFIER_TO_RUNTIME.values()) | set(RUNTIME_WITHOUT_CLASSIFIER)
        unaccounted = RUNTIME_DOCUMENT_TYPES - accounted
        self.assertEqual(
            unaccounted,
            set(),
            "These runtime document types cannot be produced by the classifier and are not "
            f"listed in RUNTIME_WITHOUT_CLASSIFIER with a reason: {sorted(unaccounted)}",
        )

    def test_mappings_target_real_runtime_codes(self):
        """A mapping to a code that does not exist is worse than none."""
        for classifier_code, runtime_code in CLASSIFIER_TO_RUNTIME.items():
            self.assertIn(
                runtime_code,
                RUNTIME_DOCUMENT_TYPES,
                f"{classifier_code} maps to {runtime_code}, which is not a runtime document type",
            )

    def test_every_mapped_code_reaches_a_registered_agent(self):
        """Mapping to a code with no agent looks like coverage but still skips."""
        from backend.app.services.rce_extraction_orchestrator import _agent_class

        for classifier_code, runtime_code in CLASSIFIER_TO_RUNTIME.items():
            self.assertIsNotNone(
                _agent_class(runtime_code),
                f"{classifier_code} -> {runtime_code}, but no agent is registered for it",
            )

    def test_lists_stay_honest(self):
        """A code cannot be both mapped and excused."""
        both = set(CLASSIFIER_TO_RUNTIME) & set(CLASSIFIER_PENDING_RUNTIME)
        self.assertEqual(both, set(), f"mapped AND listed as pending: {sorted(both)}")

        excused_but_reachable = set(RUNTIME_WITHOUT_CLASSIFIER) & set(
            CLASSIFIER_TO_RUNTIME.values()
        )
        self.assertEqual(
            excused_but_reachable,
            set(),
            f"listed as classifier-unreachable but a mapping targets it: {sorted(excused_but_reachable)}",
        )

    def test_every_exclusion_carries_a_substantive_reason(self):
        for name, reasons in (
            ("CLASSIFIER_PENDING_RUNTIME", CLASSIFIER_PENDING_RUNTIME),
            ("RUNTIME_WITHOUT_CLASSIFIER", RUNTIME_WITHOUT_CLASSIFIER),
        ):
            for code, reason in reasons.items():
                self.assertTrue(
                    reason and len(reason.strip()) > 25,
                    f"{name}[{code}] has no substantive reason: {reason!r}",
                )


class ResolutionBehaviour(unittest.TestCase):
    def test_diploma_levels_both_resolve_to_a_registered_agent(self):
        from backend.app.services.rce_extraction_orchestrator import _agent_class

        for code in ("DIPLOMA_BACHELOR", "DIPLOMA_MASTER"):
            runtime = runtime_code_for(code)
            self.assertEqual(runtime, "DIPLOMA")
            self.assertIsNotNone(_agent_class(runtime))

    def test_unmapped_code_returns_none_rather_than_a_near_match(self):
        """Fail-soft, and never a nearest-match guess.

        Sending a payslip to the contract extractor yields confident, wrong
        fields — worse than not extracting.
        """
        self.assertIsNone(runtime_code_for("PAYSLIP"))
        self.assertIsNone(runtime_code_for("UNKNOWN"))
        self.assertIsNone(runtime_code_for("NOT_A_REAL_CODE"))


if __name__ == "__main__":
    unittest.main()
