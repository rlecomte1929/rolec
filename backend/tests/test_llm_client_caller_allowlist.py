"""H1 — defense-in-depth guard for the generic LLM egress boundary (GDPR Art. 28/44).

``backend/app/services/llm_client.py`` is the generic LLM wrapper. Unlike the
policy-assistant client (``AnthropicClient.complete`` masks ``user_message`` at a
single chokepoint), the generic client does NOT mask anything — its own docstring
states masking is the CALLER's responsibility. That makes every call site a place
where raw user PII can silently leak to OpenAI/Anthropic if the author forgets to
``mask_pii()`` first.

This is a STATIC enumeration guard: it walks ``backend/app`` for every module that
imports one of the generic client's four entry points (and their sync bridges) and
asserts the set matches a hand-reviewed allowlist. When a NEW caller appears, this
test fails — forcing a human to add it to the allowlist with an explicit
``MASKED`` / ``EXEMPT`` classification (which is the review). It cannot be bypassed
at runtime because it inspects source, not behaviour.

If you are here because the test failed: you added (or removed) an ``llm_client``
caller. Confirm the new call site masks user free-text via
``backend/app/services/pii_masker.py::mask_pii`` before building the prompt (or is
genuinely non-personal / published-corpus text), then add it to ``_ALLOWLIST``
below with a one-line justification.
"""
from __future__ import annotations

import os
import re
import unittest

# Repo root = three levels up from this file (backend/tests/<file>).
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_APP_ROOT = os.path.join(_REPO_ROOT, "backend", "app")

# The generic client's public entry points + sync bridges. A module that imports
# any of these is sending a payload across the OpenAI/Anthropic boundary.
_ENTRY_POINTS = {
    "complete",
    "complete_text",
    "claude_complete",
    "claude_complete_text",
    "complete_sync",
    "complete_text_sync",
    "claude_complete_text_sync",
}

# Matches ``from .llm_client import ...`` / ``from ..services.llm_client import ...``
# but NOT ``from .policy_assistant_llm_client import ...`` (the masking chokepoint
# is a different module): the negative lookbehind rejects a word char before
# ``llm_client`` so ``..._llm_client`` does not match.
_IMPORT_RE = re.compile(r"(?<![\w])llm_client\s+import\s+([^\n]+)")

# ---------------------------------------------------------------------------
# Hand-reviewed allowlist. Key = repo-relative module path. Value = (status,
# justification). status ∈ {"MASKED", "EXEMPT"}.
#   MASKED  — the call site passes user free-text through mask_pii() first.
#   EXEMPT  — the prompt carries no user free-text (country/corridor codes,
#             firmographics, aggregates) OR published corpus text we must NOT
#             mask (masking would corrupt grounding). Justify per CLAUDE.md.
# ---------------------------------------------------------------------------
_ALLOWLIST = {
    "backend/app/services/receipt_field_extractor.py": (
        "MASKED", "mask_pii(ocr_text) before complete() — receipt OCR free-text."),
    "backend/app/services/requirement_fact_extractor.py": (
        "MASKED", "mask_pii(raw) before complete_text() — document/answer free-text."),
    "backend/app/services/policy_query_answering.py": (
        "MASKED", "query redacted via redact_pii_from_query()->mask_pii() upstream; "
                  "context = published policy chunks (exempt)."),
    "backend/app/routers/support.py": (
        "MASKED", "mask_pii(subject)+mask_pii(content) — support ticket free-text (H1)."),
    "backend/app/routers/analytics_query.py": (
        "MASKED", "mask_pii(question) — analyst free-text; context is aggregate analytics (H1)."),
    "backend/app/services/prospect_enrichment_service.py": (
        "MASKED", "mask_pii(raw_input_notes) — admin free-text; web evidence is "
                  "published grounding (H1)."),
    "backend/app/services/catalog_scraper.py": (
        "EXEMPT", "prompt = service category + destination city/country codes; no user PII."),
    "backend/app/services/policy_canonical_extraction.py": (
        "EXEMPT", "user = published corporate policy document text; masking would "
                  "corrupt extraction grounding."),
    "backend/app/services/ocr_passport_extractor.py": (
        "EXEMPT", "prompt text is a static extraction instruction; PII lives in the "
                  "image (vision OCR is the inherent purpose; mask_pii is text-only)."),
}


def _discover_callers() -> dict:
    """Return {repo_relative_path: sorted(entry_points_imported)} for every module
    under backend/app that imports a generic llm_client entry point."""
    found: dict = {}
    for dirpath, _dirs, files in os.walk(_APP_ROOT):
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, _REPO_ROOT)
            # Skip the wrapper itself.
            if rel.endswith(os.path.join("services", "llm_client.py")):
                continue
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            names: set = set()
            for m in _IMPORT_RE.finditer(text):
                segment = m.group(1).split("#", 1)[0]
                for tok in re.split(r"[ ,()]+", segment):
                    names.add(tok.strip())
            hit = names & _ENTRY_POINTS
            if hit:
                found[rel.replace(os.sep, "/")] = sorted(hit)
    return found


class LlmClientCallerAllowlistTests(unittest.TestCase):
    def test_no_unreviewed_llm_client_callers(self):
        callers = set(_discover_callers())
        allowlisted = set(_ALLOWLIST)

        new_callers = sorted(callers - allowlisted)
        self.assertFalse(
            new_callers,
            "New generic llm_client caller(s) detected that have NOT been reviewed "
            "for PII masking (GDPR Art. 28/44). For each, confirm user free-text is "
            "passed through pii_masker.mask_pii() before the prompt is built (or that "
            "it carries no user PII / is published corpus), then add it to _ALLOWLIST "
            f"in this test with a justification:\n  {new_callers}",
        )

        stale = sorted(allowlisted - callers)
        self.assertFalse(
            stale,
            "Allowlisted module(s) no longer import a generic llm_client entry point. "
            f"Remove them from _ALLOWLIST to keep the guard honest:\n  {stale}",
        )

    def test_every_allowlist_entry_has_valid_status(self):
        for path, (status, justification) in _ALLOWLIST.items():
            self.assertIn(status, {"MASKED", "EXEMPT"}, f"{path}: bad status {status!r}")
            self.assertTrue(justification.strip(), f"{path}: empty justification")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
