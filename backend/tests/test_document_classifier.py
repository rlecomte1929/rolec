"""[AIQ-1854] The document classifier must read the DOCUMENT, not the filename.

The MVP heuristic routed on filename keywords, and its own docstring admitted it: a
payslip named ``scan_001.pdf`` returned OTHER and was never extracted, while a holiday
photo named ``my_contract.pdf`` was routed to the contract extractor.

Measured on 2026-08-22, before this change, it was worse than the ticket described —
**every** value it emits maps to ``runtime_code_for(...) is None``, because its four
codes (PASSPORT / CONTRACT / PAYSLIP / OTHER) share no key with ``CLASSIFIER_TO_RUNTIME``
(whose passport code is ``PASSPORT_TD3``). So the heuristic could never route anything to
an agent, correctly-named documents included.

DB-free and network-free: the LLM call is injected via ``complete_fn``.
"""
from __future__ import annotations

import json
import unittest

from backend.app.services.document_classifier import (
    METHOD_CONTENT,
    METHOD_FILENAME_FALLBACK,
    _PROMPT_PATH,
    classify_document,
    classify_document_content,
)
from backend.app.services.document_type_vocabulary import RUNTIME_DOCUMENT_TYPES

PAYSLIP_TEXT = (
    "BULLETIN DE PAIE\nEmployeur: ACME SAS\nSalaire brut: 4 200,00 EUR\n"
    "Periode: 01/07/2026 - 31/07/2026"
)
PASSPORT_TEXT = "P<GBRSMITH<<JOHN<ALBERT<<<<<<<<<<<<<<<<<<<<<\n1234567890GBR8001019M3001012<<<<<<<<<<<<<<02"


def responder(code: str, confidence: float = 0.95, signals=("s",)):
    """A stand-in for the LLM that records what it was asked."""
    captured = {}

    def _fn(**kwargs):
        captured.update(kwargs)
        return json.dumps({"code": code, "confidence": confidence, "signals": list(signals)})

    _fn.captured = captured  # type: ignore[attr-defined]
    return _fn


class TestClassifiesFromContent(unittest.TestCase):
    """Criterion 1 — a meaningless filename must not prevent correct classification."""

    def test_a_passport_named_scan_001_is_a_passport(self) -> None:
        fn = responder("PASSPORT_TD3")
        r = classify_document_content(PASSPORT_TEXT, file_name="scan_001.pdf", complete_fn=fn)
        self.assertEqual(r.code, "PASSPORT_TD3")
        self.assertEqual(r.method, METHOD_CONTENT)

    def test_the_old_heuristic_got_that_case_wrong(self) -> None:
        """The before-state, pinned so the improvement is not theoretical."""
        self.assertEqual(classify_document("scan_001.pdf", "application/pdf"), "OTHER")


class TestMisleadingFilename(unittest.TestCase):
    """Criterion 2 — content wins over a filename that lies."""

    def test_a_payslip_named_my_contract_is_not_a_contract(self) -> None:
        fn = responder("PAYSLIP")
        r = classify_document_content(PAYSLIP_TEXT, file_name="my_contract.pdf", complete_fn=fn)
        self.assertEqual(r.code, "PAYSLIP")
        self.assertNotEqual(r.code, "CONTRACT")

    def test_the_old_heuristic_would_have_said_contract(self) -> None:
        self.assertEqual(classify_document("my_contract.pdf", "image/jpeg"), "CONTRACT")


class TestFailSoft(unittest.TestCase):
    """Criterion 3 — never raise, never silently mislabel, always record the downgrade."""

    def test_an_llm_error_falls_back_instead_of_raising(self) -> None:
        def boom(**kwargs):
            raise TimeoutError("upstream timed out")

        r = classify_document_content(PAYSLIP_TEXT, file_name="payslip_july.pdf", complete_fn=boom)
        self.assertEqual(r.method, METHOD_FILENAME_FALLBACK)
        self.assertEqual(r.code, "PAYSLIP")  # the heuristic's answer, from the filename

    def test_the_fallback_records_why(self) -> None:
        """A silent downgrade is indistinguishable from a working classifier."""
        def boom(**kwargs):
            raise TimeoutError("upstream timed out")

        r = classify_document_content(PAYSLIP_TEXT, file_name="x.pdf", complete_fn=boom)
        self.assertIsNotNone(r.fallback_reason)
        self.assertIn("TimeoutError", r.fallback_reason or "")

    def test_unparseable_json_falls_back(self) -> None:
        r = classify_document_content(PAYSLIP_TEXT, file_name="x.pdf", complete_fn=lambda **k: "not json")
        self.assertEqual(r.method, METHOD_FILENAME_FALLBACK)

    def test_an_invented_code_is_refused_not_adopted(self) -> None:
        r = classify_document_content(
            PAYSLIP_TEXT, file_name="x.pdf", complete_fn=responder("SOME_NEW_CODE")
        )
        self.assertEqual(r.method, METHOD_FILENAME_FALLBACK)
        self.assertIn("out-of-vocabulary", r.fallback_reason or "")

    def test_low_confidence_is_refused(self) -> None:
        """The prompt's own contract says return UNKNOWN below 0.5."""
        r = classify_document_content(
            PAYSLIP_TEXT, file_name="x.pdf", complete_fn=responder("PAYSLIP", confidence=0.30)
        )
        self.assertEqual(r.method, METHOD_FILENAME_FALLBACK)
        self.assertIn("below", r.fallback_reason or "")

    def test_no_text_falls_back(self) -> None:
        r = classify_document_content("", file_name="passport.pdf")
        self.assertEqual(r.method, METHOD_FILENAME_FALLBACK)
        self.assertEqual(r.code, "PASSPORT")


class TestUsesTheExistingPrompt(unittest.TestCase):
    """Criterion 4 — the C1-04a prompt, not a new one."""

    def test_it_reads_prompts_docs_classifier_v1(self) -> None:
        self.assertTrue(_PROMPT_PATH.exists(), f"{_PROMPT_PATH} must exist")
        self.assertEqual(_PROMPT_PATH.parts[-3:], ("docs", "classifier", "v1.txt"))

    def test_the_prompt_text_is_what_is_sent(self) -> None:
        fn = responder("PASSPORT_TD3")
        classify_document_content(PASSPORT_TEXT, file_name="a.pdf", complete_fn=fn)
        sent = fn.captured["user"]  # type: ignore[attr-defined]
        self.assertIn("You are a document classifier", sent)
        self.assertIn("PASSPORT_TD3", sent)

    def test_the_document_is_substituted_into_the_template(self) -> None:
        fn = responder("PASSPORT_TD3")
        classify_document_content(PASSPORT_TEXT, file_name="a.pdf", complete_fn=fn)
        sent = fn.captured["user"]  # type: ignore[attr-defined]
        self.assertNotIn("{{ document_text }}", sent)


class TestRuntimeCodeAlignment(unittest.TestCase):
    """Criterion 5 — route on rce.document_types codes, not the old 4-value set."""

    def test_a_classified_document_carries_a_real_runtime_code(self) -> None:
        r = classify_document_content(
            PASSPORT_TEXT, file_name="a.pdf", complete_fn=responder("PASSPORT_TD3")
        )
        self.assertEqual(r.runtime_code, "PASSPORT_TD3")
        self.assertIn(r.runtime_code, RUNTIME_DOCUMENT_TYPES)

    def test_a_classifier_code_is_translated_not_passed_through(self) -> None:
        """EU_NATIONAL_ID is not a runtime code; ID_CARD is."""
        r = classify_document_content(
            "IDENTITEITSKAART", file_name="a.pdf", complete_fn=responder("EU_NATIONAL_ID")
        )
        self.assertEqual(r.code, "EU_NATIONAL_ID")
        self.assertEqual(r.runtime_code, "ID_CARD")
        self.assertIn(r.runtime_code, RUNTIME_DOCUMENT_TYPES)

    def test_a_code_with_no_agent_routes_nowhere_rather_than_to_a_near_match(self) -> None:
        """PAYSLIP classifies fine and has no agent. None means skip, never 'try the closest'."""
        r = classify_document_content(
            PAYSLIP_TEXT, file_name="a.pdf", complete_fn=responder("PAYSLIP")
        )
        self.assertEqual(r.code, "PAYSLIP")
        self.assertIsNone(r.runtime_code)

    def test_unknown_routes_nowhere(self) -> None:
        r = classify_document_content(
            "LOHNSTEUERBESCHEINIGUNG 2025", file_name="a.pdf", complete_fn=responder("UNKNOWN")
        )
        self.assertIsNone(r.runtime_code)

    def test_the_fallback_never_invents_a_runtime_code(self) -> None:
        """The regression this guards: PASSPORT is not PASSPORT_TD3."""
        r = classify_document_content("", file_name="passport.pdf")
        self.assertEqual(r.code, "PASSPORT")
        self.assertIsNone(r.runtime_code)


class TestPiiIsMaskedBeforeTheCall(unittest.TestCase):
    """Criterion 6 — mask_pii before the sub-processor sees the document."""

    DOC = (
        "EMPLOYMENT CONTRACT\nEmployee email: john.smith@example.com\n"
        "Phone: +33 6 12 34 56 78\nIBAN: FR7630006000011234567890189\n"
    )

    def test_the_raw_email_never_reaches_the_model(self) -> None:
        fn = responder("EMPLOYMENT_CONTRACT")
        classify_document_content(self.DOC, file_name="c.pdf", complete_fn=fn)
        self.assertNotIn("john.smith@example.com", fn.captured["user"])  # type: ignore[attr-defined]

    def test_the_raw_iban_never_reaches_the_model(self) -> None:
        fn = responder("EMPLOYMENT_CONTRACT")
        classify_document_content(self.DOC, file_name="c.pdf", complete_fn=fn)
        self.assertNotIn("FR7630006000011234567890189", fn.captured["user"])  # type: ignore[attr-defined]

    def test_masking_does_not_destroy_the_classifiable_content(self) -> None:
        fn = responder("EMPLOYMENT_CONTRACT")
        classify_document_content(self.DOC, file_name="c.pdf", complete_fn=fn)
        self.assertIn("EMPLOYMENT CONTRACT", fn.captured["user"])  # type: ignore[attr-defined]


if __name__ == "__main__":
    unittest.main()
