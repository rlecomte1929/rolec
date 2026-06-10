"""
I-3 Stage 2 — per-corridor prompt selection.

Covers the registry `prompt` block parsing and immigration_answer_engine's
`_resolve_corridor_prompt` seam: registry profile names a prompt_registry
task_key whose active version supplies the base prompt + model; fallback-safe to
the module SYSTEM_PROMPT + _MODEL at every step.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest import mock

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ["POLICY_ASSISTANT_EMBEDDER"] = "hash"

from backend.app.services import corridor_registry as reg  # noqa: E402
from backend.app.services import immigration_answer_engine as eng  # noqa: E402


def _set_registry_dir(case, tmp):
    prev = os.environ.get("CORRIDOR_REGISTRY_DIR")
    os.environ["CORRIDOR_REGISTRY_DIR"] = tmp
    reg._reset_cache_for_tests()

    def restore():
        reg._reset_cache_for_tests()
        if prev is None:
            os.environ.pop("CORRIDOR_REGISTRY_DIR", None)
        else:
            os.environ["CORRIDOR_REGISTRY_DIR"] = prev
    case.addCleanup(restore)


def _write(tmp, cid, body):
    d = os.path.join(tmp, cid)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "corridor.yaml"), "w", encoding="utf-8") as f:
        f.write(body)


# --------------------------------------------------------------------------- #
# Registry prompt-block parsing                                               #
# --------------------------------------------------------------------------- #
class PromptConfigParsingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        _set_registry_dir(self, self.tmp)

    def test_prompt_block_parsed(self):
        _write(self.tmp, "XX_YY", "corridor:\n  id: XX_YY\n  prompt:\n    task_key: immigration_answer\n")
        cfg = reg.get_prompt_config("XX_YY")
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg.task_key, "immigration_answer")

    def test_absent_or_empty_prompt_is_none(self):
        _write(self.tmp, "XX_YY", "corridor:\n  id: XX_YY\n")
        self.assertIsNone(reg.get_prompt_config("XX_YY"))
        _write(self.tmp, "XX_ZZ", "corridor:\n  id: XX_ZZ\n  prompt:\n    task_key: '   '\n")
        self.assertIsNone(reg.get_prompt_config("XX_ZZ"))

    def test_real_fr_no_declares_prompt(self):
        # The committed corridors/FR_NO/corridor.yaml (no registry override).
        self.addCleanup(reg._reset_cache_for_tests)
        os.environ.pop("CORRIDOR_REGISTRY_DIR", None)
        reg._reset_cache_for_tests()
        cfg = reg.get_prompt_config("FR_NO")
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg.task_key, "immigration_answer")


# --------------------------------------------------------------------------- #
# Engine resolution seam                                                      #
# --------------------------------------------------------------------------- #
class ResolveCorridorPromptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        _set_registry_dir(self, self.tmp)

    def test_no_profile_falls_back_to_module_default(self):
        # Empty registry → no profile → module SYSTEM_PROMPT + _MODEL.
        base, model = eng._resolve_corridor_prompt("XX_YY")
        self.assertEqual(base, eng.SYSTEM_PROMPT)
        self.assertEqual(model, eng._MODEL)

    def test_registry_prompt_used_when_version_exists(self):
        _write(self.tmp, "XX_YY", "corridor:\n  id: XX_YY\n  prompt:\n    task_key: immigration_answer\n")
        active = mock.Mock(system_prompt="CORRIDOR PROMPT v9", model_name="claude-test-model")
        with mock.patch("backend.app.services.prompt_registry.get_active_prompt", return_value=active) as gap:
            base, model = eng._resolve_corridor_prompt("XX_YY")
        gap.assert_called_once_with("immigration_answer")
        self.assertEqual(base, "CORRIDOR PROMPT v9")
        self.assertEqual(model, "claude-test-model")

    def test_no_registered_version_falls_back(self):
        _write(self.tmp, "XX_YY", "corridor:\n  id: XX_YY\n  prompt:\n    task_key: immigration_answer\n")
        with mock.patch("backend.app.services.prompt_registry.get_active_prompt", return_value=None):
            base, model = eng._resolve_corridor_prompt("XX_YY")
        self.assertEqual(base, eng.SYSTEM_PROMPT)
        self.assertEqual(model, eng._MODEL)

    def test_registry_error_falls_back(self):
        _write(self.tmp, "XX_YY", "corridor:\n  id: XX_YY\n  prompt:\n    task_key: immigration_answer\n")
        with mock.patch("backend.app.services.prompt_registry.get_active_prompt", side_effect=RuntimeError("db down")):
            base, model = eng._resolve_corridor_prompt("XX_YY")
        self.assertEqual(base, eng.SYSTEM_PROMPT)
        self.assertEqual(model, eng._MODEL)

    def test_active_without_model_keeps_default_model(self):
        _write(self.tmp, "XX_YY", "corridor:\n  id: XX_YY\n  prompt:\n    task_key: immigration_answer\n")
        active = mock.Mock(system_prompt="P", model_name=None)
        with mock.patch("backend.app.services.prompt_registry.get_active_prompt", return_value=active):
            base, model = eng._resolve_corridor_prompt("XX_YY")
        self.assertEqual(base, "P")
        self.assertEqual(model, eng._MODEL)


if __name__ == "__main__":
    unittest.main()
