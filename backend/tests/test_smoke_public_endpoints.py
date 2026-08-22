"""Unit tests for scripts/smoke_public_endpoints.py.

`check_payload` is the half that decides whether a 200 actually means anything, so it is
pure and tested without a network. The HTTP half is proven separately against a local
server in the PR description (500 → exit 1, empty → exit 1, control down → exit 2).

The empty-list case is the point of this file. A 200 carrying zero rows has shipped here
repeatedly — a filter that can never match, a nationality gate excluding everyone, a
country absent from a lookup map — and every one of those looked healthy to a check that
only read the status line.
"""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "smoke_public_endpoints.py"

_spec = importlib.util.spec_from_file_location("smoke_public_endpoints", SCRIPT)
smoke = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(smoke)


class CheckPayloadTests(unittest.TestCase):
    def test_a_real_response_passes(self):
        body = json.dumps({"corridor": "ES->IE", "requirements": [{"key": "a"}]})
        self.assertIsNone(smoke.check_payload(body, "requirements"))

    def test_empty_list_is_a_failure_even_though_the_status_was_200(self):
        body = json.dumps({"corridor": "ES->IE", "requirements": []})
        reason = smoke.check_payload(body, "requirements")
        self.assertIsNotNone(reason)
        self.assertIn("EMPTY", reason)

    def test_missing_key_is_a_failure(self):
        reason = smoke.check_payload(json.dumps({"corridor": "ES->IE"}), "requirements")
        self.assertIn("no 'requirements' key", reason)

    def test_non_json_body_is_a_failure(self):
        """Cloudflare serves a text/plain error page over an origin 502 — that must read
        as broken, not as an unparseable success."""
        reason = smoke.check_payload("<html>502 Bad Gateway</html>", "requirements")
        self.assertIn("not JSON", reason)

    def test_json_that_is_not_an_object_is_a_failure(self):
        self.assertIn("expected a JSON object", smoke.check_payload("[1,2,3]", "requirements"))

    def test_key_present_but_not_a_list_is_a_failure(self):
        body = json.dumps({"requirements": "nope"})
        self.assertIn("expected a list", smoke.check_payload(body, "requirements"))


class ProbeConfigTests(unittest.TestCase):
    def test_probes_cover_both_corridors_that_went_down(self):
        paths = " ".join(p for _, p, _ in smoke.PROBES)
        self.assertIn("from=ES&to=IE", paths)
        self.assertIn("from=FR&to=NO", paths)

    def test_every_probe_asserts_a_payload_key(self):
        """A probe with no key would degrade to a status-only check — exactly the gap
        keepalive.yml had while it ran green through a 7.5-hour outage."""
        for label, _, key in smoke.PROBES:
            self.assertTrue(key, f"{label} has no payload key to assert")


if __name__ == "__main__":
    unittest.main()
