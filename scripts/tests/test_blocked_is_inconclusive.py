"""A throttled check is inconclusive, not a P0 failure.

The API runner emits BLOCKED for exactly one reason — `r.throttled || r.netfail`
(relopass_api_runner_patched.js:200-203) — and its own comment says the check is
"excluded from the score denominator". Both Python consumers used to contradict that:
`ingest_playwright_results` counted BLOCKED in `fail`, and `campaign_scorer` scored it
0.0, which also made `cur_bad` (`points == 0.0`) true and reported it as a regression.

Run 31974259630 is the worked example. The runner said:

    ⊘ [AT3_FRESH] Fresh Employee registration smoke test → BLOCKED
    Total: 9 | PASS: 8  FAIL: 0  WARN: 0  SKIP/BLOCKED: 1
    RESULT: INCONCLUSIVE (rate-limited) — 1 check(s) throttled.

and the scorer answered "[P0] AT3_FRESH NEW FAILURE — not seen in previous campaign",
then opened a Notion Work Queue ticket for it — while AT2_FRESH, a fresh HR
registration, PASSED in the same run. The throttle is self-inflicted: provisioning
spends the auth rate-limit budget immediately before the smoke layer runs, which
parse_preflight_wave2.py:29 already calls "a self-inflicted harness artifact".

That loop manufactured a P0 bug report about registration being broken when
registration demonstrably worked. These tests pin the contract so it cannot recur.
"""
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import campaign_scorer as cs  # noqa: E402
import ingest_playwright_results as ing  # noqa: E402


def test_blocked_scores_none_so_it_leaves_the_denominator():
    """None, not 0.0 — the difference between 'not measured' and 'measured, failed'."""
    assert cs.POINTS["BLOCKED"] is None, (
        "BLOCKED must be non-scoring like SKIP/ENV; 0.0 marks a throttled check as failed"
    )
    # The statuses that mean 'we did not get an answer' all agree.
    assert cs.POINTS["SKIP"] is None and cs.POINTS["ENV"] is None
    # ...and remain distinct from the ones that mean 'we got a bad answer'.
    assert cs.POINTS["FAIL"] == 0.0


def test_ingest_does_not_count_blocked_as_a_failure():
    c = ing.summarize([
        {"status": "PASS"},
        {"status": "BLOCKED"},   # throttled — inconclusive
        {"status": "FAIL"},      # genuinely broken
    ])
    assert c["fail"] == 1, f"only the real FAIL should count as a failure, got {c}"
    assert c["skip"] == 1, f"BLOCKED belongs with the non-scoring statuses, got {c}"
    assert c["pass"] == 1


def test_a_throttled_check_is_not_reported_as_a_new_failure():
    """The exact AT3_FRESH shape: absent from the previous campaign, BLOCKED in this one."""
    current = {
        "AT3_FRESH": {"points": cs.POINTS["BLOCKED"], "status": "BLOCKED"},
        "AT2_FRESH": {"points": cs.POINTS["PASS"], "status": "PASS"},
    }
    regressions, fixed, new_failures, still_broken = cs.diff_tests(current, {})
    assert "AT3_FRESH" not in new_failures, (
        "a rate-limited check must not be filed as a NEW FAILURE — this is the loop that "
        "auto-created a P0 Notion ticket claiming fresh registration was broken"
    )
    assert new_failures == [] and regressions == []


def test_a_real_failure_is_still_reported():
    """Guard the guard: the fix must not blind the scorer to genuine breakage."""
    current = {"AT9_REAL": {"points": cs.POINTS["FAIL"], "status": "FAIL"}}
    _, _, new_failures, _ = cs.diff_tests(current, {})
    assert new_failures == ["AT9_REAL"]


# ── The gate, added after the scorer ─────────────────────────────────────────
#
# The three tests above pinned the SCORING path. AIQ-1820 then armed a second,
# independent path — `check_against_baseline`, which fails the job on any failure not
# named in sentinel_baseline.json — and it kept BLOCKED in its failing set. So one run
# printed `fail: 0`, verdict GREEN, "No new Notion tasks needed", and then failed the
# job on "✖ 1 FAILING test(s) are not in the baseline: AT3_FRESH". Two paths in one
# file, disagreeing about the same status, for months.
#
# The baseline is a ratchet of KNOWN BUGS. A throttled check is not a bug, so there is
# nothing to write down — baselining it would have documented a fiction and hidden the
# real registration coverage behind a permanent excuse.


def test_baseline_gate_does_not_fail_the_run_on_a_throttled_check():
    """The exact run-32166812901 shape: everything passes, AT3_FRESH is throttled."""
    results = [
        {"id": "AT2_FRESH", "status": "PASS"},
        {"id": "AT3_FRESH", "status": "BLOCKED"},   # self-inflicted 429
    ]
    unexpected, stale = cs.check_against_baseline(results, {})
    assert unexpected == [], (
        "a throttled check must not fail the gate — the scorer calls the same run GREEN, "
        "and a gate that disagrees with its own scorer teaches everyone to ignore it"
    )
    assert stale == []


def test_baseline_gate_still_fails_the_run_on_a_real_failure():
    """Guard the guard: the gate must keep doing the job AIQ-1820 armed it for."""
    results = [
        {"id": "AT3_FRESH", "status": "BLOCKED"},
        {"id": "AT9_REAL", "status": "FAIL"},
    ]
    unexpected, _ = cs.check_against_baseline(results, {})
    assert unexpected == ["AT9_REAL"], (
        f"a genuine FAIL outside the baseline must still fail the run, got {unexpected}"
    )


def test_baseline_gate_still_honours_a_known_open_failure():
    results = [{"id": "KNOWN_BUG", "status": "FAIL"}]
    unexpected, stale = cs.check_against_baseline(results, {"KNOWN_BUG": "ticket AIQ-x"})
    assert unexpected == [] and stale == []


def test_baseline_gate_still_reports_a_stale_entry():
    """A baselined failure that now passes must be surfaced so the ratchet tightens."""
    results = [{"id": "KNOWN_BUG", "status": "PASS"}]
    unexpected, stale = cs.check_against_baseline(results, {"KNOWN_BUG": "ticket AIQ-x"})
    assert unexpected == [] and stale == ["KNOWN_BUG"]


def test_untagged_blocked_check_does_not_fail_the_run():
    """`report_unmapped` had the same defect: an untagged BLOCKED check failed the run
    for being untagged-and-failing, when it had simply not been measured."""
    assert cs.report_unmapped([{"id": "UNTAGGED_X", "status": "BLOCKED"}], {}) is False
    assert cs.report_unmapped([{"id": "UNTAGGED_Y", "status": "FAIL"}], {}) is True
