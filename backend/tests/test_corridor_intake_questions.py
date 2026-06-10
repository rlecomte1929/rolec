"""
I-3 Stage 3 — per-corridor intake follow-up questions.

Covers the registry `intake` block + path resolution, the interview engine's
per-corridor `load_questions(corridor=...)` seam (custom set when a corridor
declares one; global fallback otherwise), and the corridor derivation helper.
Fallback-safe: any miss → the global interview_questions.json.
"""
from __future__ import annotations

import json
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
from backend.app.services import immigration_interview_engine as eng  # noqa: E402
from backend.app.services import immigration_service as svc  # noqa: E402

_CUSTOM_QUESTIONS = {
    "sections": [{"id": "s1", "title": "S", "description": "", "order": 1}],
    "questions": [
        {"id": "corridor_only_q", "section": "s1", "order": 10, "label": "L",
         "type": "text", "required": True},
    ],
}


def _set_registry_dir(case, tmp):
    prev = os.environ.get("CORRIDOR_REGISTRY_DIR")
    os.environ["CORRIDOR_REGISTRY_DIR"] = tmp
    reg._reset_cache_for_tests()
    eng._QUESTION_CACHE.clear()

    def restore():
        reg._reset_cache_for_tests()
        eng._QUESTION_CACHE.clear()
        if prev is None:
            os.environ.pop("CORRIDOR_REGISTRY_DIR", None)
        else:
            os.environ["CORRIDOR_REGISTRY_DIR"] = prev
    case.addCleanup(restore)


def _write_corridor(tmp, cid, yaml_body, questions=None):
    d = os.path.join(tmp, cid)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "corridor.yaml"), "w", encoding="utf-8") as f:
        f.write(yaml_body)
    if questions is not None:
        with open(os.path.join(d, "questions.json"), "w", encoding="utf-8") as f:
            json.dump(questions, f)


# --------------------------------------------------------------------------- #
# Registry intake parsing + path resolution                                   #
# --------------------------------------------------------------------------- #
class IntakeConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        _set_registry_dir(self, self.tmp)

    def test_intake_block_parsed(self):
        _write_corridor(self.tmp, "XX_YY",
                        "corridor:\n  id: XX_YY\n  intake:\n    questions_file: questions.json\n",
                        questions=_CUSTOM_QUESTIONS)
        cfg = reg.get_intake_config("XX_YY")
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg.questions_file, "questions.json")

    def test_absent_intake_is_none(self):
        _write_corridor(self.tmp, "XX_YY", "corridor:\n  id: XX_YY\n")
        self.assertIsNone(reg.get_intake_config("XX_YY"))
        self.assertIsNone(reg.get_intake_questions_path("XX_YY"))

    def test_path_resolves_only_when_file_exists(self):
        # Declares a file that doesn't exist → path None (fallback-safe).
        _write_corridor(self.tmp, "XX_YY",
                        "corridor:\n  id: XX_YY\n  intake:\n    questions_file: nope.json\n")
        self.assertIsNone(reg.get_intake_questions_path("XX_YY"))
        # Now with the file present → resolves.
        _write_corridor(self.tmp, "XX_ZZ",
                        "corridor:\n  id: XX_ZZ\n  intake:\n    questions_file: questions.json\n",
                        questions=_CUSTOM_QUESTIONS)
        p = reg.get_intake_questions_path("XX_ZZ")
        self.assertIsNotNone(p)
        self.assertTrue(str(p).endswith("XX_ZZ/questions.json"))


# --------------------------------------------------------------------------- #
# Interview engine load_questions seam                                        #
# --------------------------------------------------------------------------- #
class LoadQuestionsCorridorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        _set_registry_dir(self, self.tmp)

    def test_no_corridor_loads_global_set(self):
        qs = eng.load_questions()
        ids = {q.id for q in qs}
        self.assertGreater(len(qs), 1)
        self.assertNotIn("corridor_only_q", ids)   # not the custom set

    def test_corridor_without_intake_uses_global(self):
        _write_corridor(self.tmp, "XX_YY", "corridor:\n  id: XX_YY\n")
        glob = {q.id for q in eng.load_questions()}
        scoped = {q.id for q in eng.load_questions(corridor="XX_YY")}
        self.assertEqual(glob, scoped)             # identical → global fallback

    def test_corridor_with_intake_loads_custom_set(self):
        _write_corridor(self.tmp, "XX_YY",
                        "corridor:\n  id: XX_YY\n  intake:\n    questions_file: questions.json\n",
                        questions=_CUSTOM_QUESTIONS)
        qs = eng.load_questions(corridor="FR→XX")  # arrow form is irrelevant here
        scoped = eng.load_questions(corridor="XX_YY")
        self.assertEqual([q.id for q in scoped], ["corridor_only_q"])
        # Global still distinct (per-corridor cache keys).
        self.assertNotEqual([q.id for q in scoped], [q.id for q in eng.load_questions()])

    def test_missing_custom_file_falls_back_to_global(self):
        _write_corridor(self.tmp, "XX_YY",
                        "corridor:\n  id: XX_YY\n  intake:\n    questions_file: nope.json\n")
        scoped = {q.id for q in eng.load_questions(corridor="XX_YY")}
        glob = {q.id for q in eng.load_questions()}
        self.assertEqual(scoped, glob)


# --------------------------------------------------------------------------- #
# Corridor derivation helper                                                  #
# --------------------------------------------------------------------------- #
class ResolveCaseCorridorTests(unittest.TestCase):
    def test_resolves_from_case_geography(self):
        with mock.patch.object(svc, "_get_case_details",
                               return_value={"origin_country": "FR", "dest_country": "NO"}):
            self.assertEqual(svc.resolve_case_corridor("case-1", ""), "FR_NO")

    def test_missing_case_or_geography_is_none(self):
        with mock.patch.object(svc, "_get_case_details", return_value=None):
            self.assertIsNone(svc.resolve_case_corridor("nope", ""))
        with mock.patch.object(svc, "_get_case_details",
                               return_value={"origin_country": "FR", "dest_country": None}):
            self.assertIsNone(svc.resolve_case_corridor("case-1", ""))


if __name__ == "__main__":
    unittest.main()
