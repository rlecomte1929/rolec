"""[AIQ-1804] The Sentinel must not drop a failing test in silence.

WHY THIS EXISTS
---------------
A result has to survive two filters before anyone hears about it:

    Playwright title --[1: leading [TAG]]--> ingester --[2: scoring_map entry]--> scorer

Both filters used to discard silently, and on 2026-08-11 both were losing real coverage:

- `tests/e2e/tests/public/crawler-surface.spec.ts` had no tags at all, so filter 1 ate it.
  It runs against production and asserts that OAI-SearchBot / GPTBot / ChatGPT-User can
  fetch a page — all three were returning 403 from Cloudflare. The campaign stayed green.
- `[R4X-A]` / `[R4X-B]` were tagged but missing from `scoring_map.json`, so filter 2 ate
  them. Same outcome: they ran, and reported to nobody.

In both cases the only trace was a raw `_results.json` inside a 30-day artifact.

The tests here pin the guards, not the specific ids — the ids get fixed by adding entries,
but the guards are what stop the *next* spec from vanishing the same way.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent


def _load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ing = _load("ingest_playwright_results")
scorer = _load("campaign_scorer")


def _pw_report(specs):
    """Minimal Playwright JSON report: [(title, status), ...]."""
    return {
        "suites": [
            {
                "specs": [
                    {"title": title, "tests": [{"results": [{"status": status}]}]}
                    for title, status in specs
                ]
            }
        ]
    }


def _write(tmp_path, specs):
    p = tmp_path / "_results.json"
    p.write_text(json.dumps(_pw_report(specs)), encoding="utf-8")
    return p


# ── filter 1: the missing-[TAG] drop ─────────────────────────────────────────────────

def test_untagged_specs_are_returned_not_discarded(tmp_path):
    pw = _write(tmp_path, [
        ("[CORE-RLS] scoped list", "passed"),
        ("sitemap.xml parses as XML", "failed"),
    ])
    rows, untagged = ing.parse_playwright(pw)

    assert [r["id"] for r in rows] == ["CORE-RLS"]
    assert len(untagged) == 1
    assert untagged[0]["title"] == "sitemap.xml parses as XML"
    assert untagged[0]["status"] == "FAIL"


def test_a_failing_untagged_spec_is_an_error(capsys):
    rc = ing._report_untagged(
        [{"title": "OAI-SearchBot can actually fetch a published page", "status": "FAIL"}],
        allow_failures=False,
    )
    assert rc == 1, "a failing test that reaches no scorer must not exit 0"
    out = capsys.readouterr().out
    assert "OAI-SearchBot" in out, "the operator must be told WHICH spec vanished"


def test_a_passing_untagged_spec_is_reported_but_not_fatal(capsys):
    rc = ing._report_untagged(
        [{"title": "some untagged smoke check", "status": "PASS"}],
        allow_failures=False,
    )
    assert rc == 0, "an untagged spec that passes is a gap, not a break"
    assert "some untagged smoke check" in capsys.readouterr().out


def test_no_untagged_specs_is_silent(capsys):
    assert ing._report_untagged([], allow_failures=False) == 0
    assert capsys.readouterr().out == ""


def test_the_escape_hatch_still_reports(capsys):
    rc = ing._report_untagged(
        [{"title": "known-untagged spec", "status": "FAIL"}], allow_failures=True
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "known-untagged spec" in out and "exiting 0" in out


# ── filter 2: the missing-scoring_map drop ───────────────────────────────────────────

MAP = {"tests": {"CORE-RLS": {"domain": "Security & RLS", "priority": "P0"}}}


def test_unmapped_failing_id_is_an_error(capsys):
    fatal = scorer.report_unmapped(
        [{"id": "CORE-RLS", "status": "PASS"}, {"id": "R4X-A", "status": "FAIL"}], MAP
    )
    assert fatal is True
    out = capsys.readouterr().out
    assert "R4X-A" in out and "scoring_map.json" in out


def test_unmapped_passing_id_is_reported_but_not_fatal(capsys):
    fatal = scorer.report_unmapped([{"id": "R4X-B", "status": "PASS"}], MAP)
    assert fatal is False
    assert "R4X-B" in capsys.readouterr().out


def test_fully_mapped_run_is_silent(capsys):
    assert scorer.report_unmapped([{"id": "CORE-RLS", "status": "FAIL"}], MAP) is False
    assert capsys.readouterr().out == ""


# ── filter 3: the muzzled verdict, now a baseline ratchet ────────────────────────────

BASE = {"VND-05": {"reason": "known RFQ 500", "ticket": "VND-05"}}


def test_a_new_failure_is_unexpected():
    unexpected, stale = scorer.check_against_baseline(
        [{"id": "VND-05", "status": "FAIL"}, {"id": "CORE-RLS", "status": "FAIL"}], BASE
    )
    assert unexpected == ["CORE-RLS"], "a failure nobody wrote down must fail the run"
    assert stale == []


def test_a_baselined_failure_is_expected():
    unexpected, _ = scorer.check_against_baseline([{"id": "VND-05", "status": "FAIL"}], BASE)
    assert unexpected == [], "known-open bugs must not fail the run — that is why the mask existed"


def test_a_baselined_test_that_now_passes_is_reported_stale():
    """The ratchet has to tighten. A baseline entry that starts passing and is never removed
    silently re-opens the hole it was documenting."""
    unexpected, stale = scorer.check_against_baseline([{"id": "VND-05", "status": "PASS"}], BASE)
    assert unexpected == []
    assert stale == ["VND-05"]


def test_blocked_does_not_count_as_failing():
    """REVERSED. This asserted `unexpected == ["CORE-RLS"]` — that a BLOCKED check fails
    the run — which contradicted `test_blocked_is_inconclusive.py` in the same directory
    and the runner that emits the status. The runner sets BLOCKED for exactly one reason,
    `r.throttled || r.netfail` (relopass_api_runner_patched.js:200-203), and its own
    comment says the check is "excluded from the score denominator".

    The cost of the disagreement: the scorer printed `fail: 0` and GREEN while this gate
    failed the same run on AT3_FRESH — a self-inflicted 429, not a bug — on every push
    for months. A gate that contradicts its own scorer trains people to ignore it.

    The original assertion carried no docstring and no reason, while every other test in
    this file explains itself; it reads as a description of the code as-built rather than
    a decision. The decision is in test_blocked_is_inconclusive.py, which cites the run it
    cost. A real FAIL still fails the gate — see the test below.
    """
    unexpected, _ = scorer.check_against_baseline([{"id": "CORE-RLS", "status": "BLOCKED"}], BASE)
    assert unexpected == [], "a throttled/unreachable check is inconclusive, not a failure"


def test_a_real_failure_beside_a_blocked_one_still_fails_the_run():
    """The reversal above must not blind the gate to genuine breakage in the same run."""
    unexpected, _ = scorer.check_against_baseline(
        [{"id": "CORE-RLS", "status": "BLOCKED"}, {"id": "CORE-AUTH", "status": "FAIL"}], BASE
    )
    assert unexpected == ["CORE-AUTH"]


def test_missing_baseline_file_means_every_failure_is_unexpected(tmp_path):
    assert scorer.load_baseline(tmp_path / "nope.json") == {}
    unexpected, _ = scorer.check_against_baseline([{"id": "X", "status": "FAIL"}], {})
    assert unexpected == ["X"]


def test_the_shipped_baseline_is_wellformed():
    """Every entry needs a reason and a ticket — otherwise the file becomes a place to hide
    failures rather than a record of them."""
    raw = json.loads((SCRIPTS / "sentinel_baseline.json").read_text(encoding="utf-8"))
    real_map = json.loads((SCRIPTS / "scoring_map.json").read_text(encoding="utf-8"))
    for tid, meta in raw["known_failures"].items():
        assert meta.get("reason"), f"{tid} has no reason"
        assert meta.get("ticket"), f"{tid} has no ticket"
        assert tid in real_map["tests"], (
            f"{tid} is baselined but not in scoring_map.json — it would be invisible anyway"
        )


# ── the two ids that were actually lost, now mapped ──────────────────────────────────

@pytest.mark.parametrize(
    "test_id",
    ["R4X-A", "R4X-B", "SEO-LANDING", "AEO-CRAWLER-FETCH", "SEO-ROBOTS",
     "SEO-BLOG-INDEX", "SEO-SITEMAP"],
)
def test_previously_invisible_ids_are_now_scored(test_id):
    """Regression pin for the specific coverage that was being lost."""
    real_map = json.loads((SCRIPTS / "scoring_map.json").read_text(encoding="utf-8"))
    assert test_id in real_map["tests"], f"{test_id} runs in CI but is scored nowhere"
    assert real_map["tests"][test_id]["domain"] in \
        real_map["_meta"]["scoring_rules"]["domain_weights"], \
        f"{test_id}'s domain has no weight, so it silently counts for 1"


#: Tagged ids with no `scoring_map.json` entry, accepted as pre-existing debt.
#:
#: Every one lives in the demo-login lane (`admin` / `hr` / `employee` / `cross-company`),
#: which `e2e-campaign.yml` does not run — its project list is public, provision, readiness,
#: core, write-flow, deep, r4x-provision, run004x. So these are *latent*: unmapped, but also
#: unrun, and therefore not currently causing a false green. They become real the moment
#: someone adds those projects to the campaign.
#:
#: This list is a ratchet. Do not add to it — map the id instead. Shortening it is always
#: welcome. Discovered by this guard on 2026-08-11 (AIQ-1804); the two ids that WERE
#: actively running unmapped, [R4X-A] and [R4X-B], were mapped rather than listed here.
KNOWN_UNMAPPED = {
    "VND-01", "VND-02", "VND-03", "VND-03b", "VND-04", "VND-06",
    "PER-A1", "PER-A2", "PER-E1", "PER-H2",
    "MSG-09", "IMM-DISP-01", "UX-CLARITY-admin", "UX-CLARITY-emp",
}


def test_every_tagged_spec_in_the_repo_is_mapped():
    """The end state this whole file exists to protect: no NEW tagged spec is unmapped.

    Catches the R4X case at authoring time — someone tags a spec correctly and forgets the
    map entry, which looks completely fine in review and produces a test that runs and
    reports to nobody.
    """
    import re

    repo = SCRIPTS.parent
    real_map = json.loads((SCRIPTS / "scoring_map.json").read_text(encoding="utf-8"))
    tag_re = re.compile(r"""\btest\(\s*[`'"]\s*\[([A-Za-z0-9][^\]]*)\]""")

    missing = {}
    for spec_file in (repo / "tests" / "e2e" / "tests").rglob("*.spec.ts"):
        for raw in tag_re.findall(spec_file.read_text(encoding="utf-8")):
            tid = re.split(r"[\s/]+", raw.strip())[0]
            # A template-literal tag (`[CORE-HR-${label}]`) cannot be resolved statically.
            # Its runtime ids are real and mapped; the placeholder text never is.
            if "${" in tid or tid in KNOWN_UNMAPPED or tid in real_map["tests"]:
                continue
            missing.setdefault(tid, str(spec_file.relative_to(repo)))

    assert not missing, (
        "these specs carry a [TAG] but have no scoring_map.json entry, so they run and "
        f"report to nobody: {missing}"
    )


def test_the_known_unmapped_list_does_not_rot():
    """If someone maps one of these, make them delete it from the list.

    A stale allowlist quietly re-opens the hole it was documenting.
    """
    real_map = json.loads((SCRIPTS / "scoring_map.json").read_text(encoding="utf-8"))
    now_mapped = sorted(KNOWN_UNMAPPED & set(real_map["tests"]))
    assert not now_mapped, (
        f"these are mapped now — remove them from KNOWN_UNMAPPED: {now_mapped}"
    )
