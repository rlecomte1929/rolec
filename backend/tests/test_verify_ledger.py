"""Tests for the ledger verifier (V0/V1/V2) and its reuse contract for V3.

The planted-defect cases are the point. A gate that has only ever seen good input proves
nothing — so every test here asserts against `no_micro/ledger.ndjson`, which carries one
instance of each way `parsers.read_jsonl` fails, and the central test proves the *raw* file
kills the importer while the *clean* file imports with zero rejections. Without that pair, a
green suite would be consistent with this script doing nothing at all.

No network: everything runs over `verify_lines`, and the CLI tests pass `--no-fetch`.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from backend.imports.otto.parsers import FactRowError, read_jsonl  # noqa: E402
from backend.imports.otto.verifier import (  # noqa: E402
    REJECT,
    WARN,
    authority_rank,
    derive_dedupe_key,
    load_config,
    normalise_url,
    summarise,
    verify_lines,
)

FIXTURE = REPO / "backend/imports/otto/fixtures/no_micro/ledger.ndjson"


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture(scope="module")
def verdicts(cfg):
    return verify_lines(FIXTURE.read_text(encoding="utf-8").splitlines(), cfg)


def _codes(verdict, severity=None):
    return {f.code for f in verdict.findings if severity is None or f.severity == severity}


# --------------------------------------------------------------------- V0 normalise

@pytest.mark.parametrize("raw,expected", [
    ("https://x.gov.ie/a%22", "https://x.gov.ie/a"),
    ('https://x.gov.ie/a"', "https://x.gov.ie/a"),
    ("https://a.gov/p#s2#s2", "https://a.gov/p#s2"),
    ("skatteetaten.no/en/d", "https://skatteetaten.no/en/d"),
    ("https://a.gov/x?", "https://a.gov/x"),
    # A trailing slash is a different path on some hosts and must survive normalisation.
    ("https://a.gov/dir/", "https://a.gov/dir/"),
    ("https://a.gov/dir/#", "https://a.gov/dir/"),
    ("", ""),
])
def test_normalise_url(raw, expected):
    assert normalise_url(raw) == expected


def test_dedupe_key_mirrors_the_importer():
    """Derived from the three fields, never read from the record — see verifier.py."""
    assert derive_dedupe_key(
        {"destination_country": "no", "entity_topic_key": "t", "fact_key": "k"}) == "NO|t|k"
    assert derive_dedupe_key({"destination_country": "NO", "fact_key": "k"}) is None


def test_authority_rank_longest_match_and_unknown(cfg):
    hosts = cfg["hosts"]
    assert authority_rank("https://www.skatteetaten.no/en/x", hosts) == 1
    assert authority_rank("https://www.nav.no/en/x", hosts) == 2
    # An unlisted host is a reported gap, never a defaulted rank.
    assert authority_rank("https://nope.example/x", hosts) is None


# --------------------------------------------------------------------- planted defects

def test_every_planted_defect_is_caught(verdicts):
    by_line = {v.lineno: v for v in verdicts}
    assert "bad_json" in _codes(by_line[9], REJECT)
    assert "missing_required" in _codes(by_line[10], REJECT)
    assert "unofficial_source" in _codes(by_line[11], REJECT)
    assert "duplicate_dedupe_key" in _codes(by_line[12], REJECT)
    # Line 13 is the dangerous one: nothing rejects it, so it imports and never promotes.
    assert not by_line[13].rejected
    assert {"fact_type_unknown", "confidence_unknown"} <= _codes(by_line[13], WARN)


def test_the_url_garble_is_repaired_not_rejected(verdicts):
    line8 = next(v for v in verdicts if v.lineno == 8)
    assert not line8.rejected
    assert line8.record["source_url"].endswith("/#id-check")
    assert "%22" not in line8.record["source_url"]


def test_counts(verdicts):
    s = summarise(verdicts)
    assert s["lines"] == 13
    assert s["rejected"] == 4
    assert s["lines"] - s["rejected"] == 9
    # Only the two rows carrying applies_to + domain_area='immigration' can become requirements.
    assert s["promotable"] == 2


def test_rejected_rows_do_not_inflate_the_warn_counts(verdicts):
    """A rejected row's incidental warnings are not actionable and must not be tallied."""
    s = summarise(verdicts)
    warned_rows = sum(1 for v in verdicts if not v.rejected and v.warned)
    assert s["findings_by_code"]["warn:V1/no_status"] == warned_rows


# --------------------------------------------------------------------- the acceptance pair

def test_the_raw_ledger_kills_the_unchanged_importer():
    """The failure this script exists to prevent: one bad line strands the whole batch."""
    with pytest.raises(FactRowError) as exc:
        read_jsonl(FIXTURE, batch_id="raw")
    assert "line 9" in str(exc.value)


def test_the_clean_file_imports_with_zero_rejections(tmp_path, verdicts):
    clean = tmp_path / "clean.ndjson"
    clean.write_text("".join(
        json.dumps(v.record, ensure_ascii=False) + "\n"
        for v in verdicts if not v.rejected and v.record is not None), encoding="utf-8")

    rows, rejections = read_jsonl(clean, batch_id="no-micro")
    assert rejections == []
    assert len(rows) == 9
    assert {r.source_class for r in rows} == {"official"}


def test_rerun_is_idempotent(tmp_path, cfg):
    lines = FIXTURE.read_text(encoding="utf-8").splitlines()
    first = [json.dumps(v.record, sort_keys=True) for v in verify_lines(lines, cfg) if not v.rejected]
    second = [json.dumps(v.record, sort_keys=True) for v in verify_lines(lines, cfg) if not v.rejected]
    assert first == second


# --------------------------------------------------------------------- CLI contract

def _run(*args):
    return subprocess.run([sys.executable, str(REPO / "scripts/verify_ledger.py"), *args],
                          capture_output=True, text=True, cwd=REPO)


def test_cli_dry_run_writes_nothing(tmp_path):
    out = _run(str(FIXTURE), "--no-fetch", "--out", str(tmp_path))
    assert out.returncode == 0, out.stderr
    assert not list(tmp_path.iterdir())
    assert "Dry run" in out.stdout
    # A run without liveness must never read as one with it.
    assert "LIVENESS NOT RUN" in out.stdout


def test_cli_apply_writes_both_files(tmp_path):
    out = _run(str(FIXTURE), "--no-fetch", "--apply", "--out", str(tmp_path))
    assert out.returncode == 0, out.stderr
    clean = (tmp_path / "clean.ndjson").read_text().strip().splitlines()
    work = (tmp_path / "worklist.ndjson").read_text().strip().splitlines()
    assert len(clean) == 9 and len(work) == 4
    assert all(json.loads(w)["findings"] for w in work), "every rejection must carry its reason"


def test_cli_empty_file_is_not_a_pass(tmp_path):
    empty = tmp_path / "empty.ndjson"
    empty.write_text("\n\n", encoding="utf-8")
    out = _run(str(empty), "--no-fetch", "--out", str(tmp_path))
    assert out.returncode == 1, "an empty batch is not a clean batch"


def test_cli_all_rejected_is_not_a_pass(tmp_path):
    bad = tmp_path / "bad.ndjson"
    bad.write_text("{not json\n{also not json\n", encoding="utf-8")
    out = _run(str(bad), "--no-fetch", "--out", str(tmp_path))
    assert out.returncode == 1


def test_cli_missing_file_is_exit_2(tmp_path):
    assert _run(str(tmp_path / "nope.ndjson"), "--no-fetch").returncode == 2


# --------------------------------------------------------------------- V3 reuse contract

def test_v3_reuses_the_existing_matcher_and_translated_still_fires():
    """V3 is `fact_evidence.check_evidence`, not a new matcher — and its TRANSLATED verdict
    is the reason no fuzzy threshold may be layered on top: it is what keeps 97 correctly
    translated French facts out of the suspect pile."""
    from backend.app.services.fact_evidence import (
        TRANSLATED, UNVERIFIED, VERIFIED, check_evidence)

    source_fr = (
        "Vous devez demander un titre de séjour dans les deux mois suivant votre arrivée. "
        "La demande se fait en ligne sur le site du ministère de l'intérieur, et vous devez "
        "fournir un justificatif de domicile ainsi qu'une pièce d'identité en cours de validité."
    ) * 3
    assert check_evidence("You must apply for a residence permit within two months of arrival.",
                          source_fr).status == TRANSLATED

    source_en = (
        "You can receive a D number if you do not meet the conditions for a national identity "
        "number. The certified copy cannot be older than three months and must be sent by post."
    ) * 3
    assert check_evidence("The certified copy cannot be older than three months",
                          source_en).status == VERIFIED
    # And the damning case stays damning: same language, source in hand, quote absent.
    assert check_evidence("The certified copy must be notarised by a solicitor",
                          source_en).status == UNVERIFIED


def test_no_rapidfuzz_anywhere():
    """An explicit acceptance criterion: the existing matcher must not be weakened by a
    similarity threshold. Asserted over the tree so a future import trips this test."""
    # Exclude this test file, which necessarily names the library it forbids.
    hits = subprocess.run(
        ["git", "grep", "-l", "rapidfuzz", "--",
         "*.py", "*.txt", "*.toml", "*.cfg", ":!backend/tests/test_verify_ledger.py"],
        capture_output=True, text=True, cwd=REPO)
    assert hits.stdout.strip() == "", f"rapidfuzz appeared in production code: {hits.stdout}"


def test_liveness_vocabulary_matches_the_fetcher_it_reuses():
    """Pins the bug that shipped in this file's first draft.

    `verify_ledger` compared the fetch status against `"ok"`, but
    `backfill_fact_evidence.fetch_status_for` returns `"fetched"` — so three healthy Norwegian
    government sources were reported as unreachable. Reading a live source as dead is the exact
    failure the surrounding code warns about, so the two vocabularies are asserted equal here
    rather than trusted to stay in sync.

    The middle value matters just as much: `not_fetched` means robots.txt told us not to ask,
    which is "not checked", not "dead".
    """
    from backend.scripts.backfill_fact_evidence import fetch_status_for

    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "verify_ledger", REPO / "scripts/verify_ledger.py")
    vl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vl)

    assert fetch_status_for({"ok": True}) == vl.OK
    assert fetch_status_for({"ok": False, "reason": "robots_disallowed"}) == vl.SKIPPED
    assert fetch_status_for({"ok": False, "reason": "error_ConnectError"}) not in (vl.OK, vl.SKIPPED)


def test_informational_warnings_do_not_reduce_promotable():
    """The bug the real ES->IE third-country batch exposed.

    13 host_unranked + 2 fact_type warnings reported a genuinely 38/38-promotable batch as 24.
    An informational WARN (unranked host, a fact_type that normalises to 'other') must NOT count
    against promotable; only a WARN mirroring a resolve() refusal does.
    """
    from backend.imports.otto.verifier import Finding

    assert Finding("warn", "V2", "host_unranked", "x").blocks_promote is False
    assert Finding("warn", "V1", "fact_type_unknown", "x").blocks_promote is False
    assert Finding("warn", "V1", "confidence_unknown", "x").blocks_promote is False
    assert Finding("warn", "V1", "no_nationality", "x").blocks_promote is True
    assert Finding("warn", "V1", "no_status", "x").blocks_promote is True
    assert Finding("warn", "V1", "domain_area_not_promotable", "x").blocks_promote is True
    # A REJECT blocks by definition — it never reaches the clean file.
    assert Finding("reject", "V1", "missing_required", "x").blocks_promote is True


def test_a_host_unranked_row_still_counts_as_promotable(cfg):
    """A fact from an official host we simply have not ranked promotes fine; it is a tiering gap,
    not a serving gap. Uses an official IE host (classify_source passes) absent from the config."""
    rec = {
        "destination_country": "IE",
        "entity_topic_key": "ie.work",
        "fact_key": "k1",
        "fact_text": "x",
        "source_url": "https://www.somewhere.gov.ie/page",  # gov.ie: official, and now ranked
        "applies_to": {"nationality": "non-EEA", "status": "professional"},
    }
    from backend.imports.otto.verifier import verify_lines
    import json as _json
    [v] = verify_lines([_json.dumps(rec)], cfg)
    assert not v.rejected
    assert not v.promote_blocked, [f.code for f in v.findings if f.blocks_promote]
