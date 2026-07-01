"""
Tests for _TRIAGE_SYSTEM template rendering in support.py.

The template embeds a literal JSON example containing { and } braces.
Using str.format() on such a template raises KeyError on every call
unless the literal braces are escaped as {{ / }}.

This test was written RED against the unfixed code, then turned GREEN
by the escape fix.
"""
from __future__ import annotations

import unittest
from unittest import mock

from backend.app.routers import support


class TriageSystemTemplateTests(unittest.TestCase):
    """Verify _TRIAGE_SYSTEM.format(domain_context=...) works correctly."""

    INJECTED_CONTEXT = "ReloPass test domain context for triage."

    def _render(self) -> str:
        """Render the template the same way _call_triage_model does."""
        return support._TRIAGE_SYSTEM.format(domain_context=self.INJECTED_CONTEXT)

    def test_render_does_not_raise(self):
        """str.format() must not raise KeyError or ValueError on literal JSON braces."""
        try:
            rendered = self._render()
        except (KeyError, ValueError) as exc:
            self.fail(
                f"_TRIAGE_SYSTEM.format(domain_context=...) raised {type(exc).__name__}: {exc}. "
                "Escape literal JSON braces with {{ / }} in the template."
            )

    def test_domain_context_is_injected(self):
        """The injected domain_context value must appear in the rendered prompt."""
        rendered = self._render()
        self.assertIn(self.INJECTED_CONTEXT, rendered)

    def test_json_example_has_single_braces(self):
        """The JSON example must appear with single braces (not doubled) in the output."""
        rendered = self._render()
        # The example block opens with a bare { on its own line
        self.assertIn('"issue_category"', rendered)
        # A single-brace JSON object boundary must be present
        self.assertIn("{", rendered)
        self.assertIn("}", rendered)
        # Doubled braces in the *output* would indicate the fix was not applied
        self.assertNotIn("{{", rendered)
        self.assertNotIn("}}", rendered)

    def test_call_triage_model_does_not_raise_on_template(self):
        """_call_triage_model must not crash before reaching the LLM call."""
        fake_result = (
            '{"issue_category":"bug","root_cause_hypothesis":"test",'
            '"fix_difficulty":"low","suggested_action":"notion_task",'
            '"draft_reply":"We are looking into this."}'
        )
        with mock.patch(
            "backend.app.services.llm_client.claude_complete_text_sync",
            return_value=fake_result,
        ):
            result = support._call_triage_model(
                content="The dashboard fails to load.",
                subject="Dashboard broken",
                user_role="hr",
                company_id=None,
                recent_events=[],
                domain_context=self.INJECTED_CONTEXT,
            )
        self.assertEqual(result["issue_category"], "bug")


if __name__ == "__main__":
    unittest.main()
