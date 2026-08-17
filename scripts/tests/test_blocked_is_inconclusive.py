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
