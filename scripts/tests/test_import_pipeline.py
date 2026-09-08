"""The import pipeline is a chain, not a second importer.

Happy path: confirm_quotes CONFIRMED → verify_ledger 0 → import_otto_facts (no --apply) →
promote(dry_run=True) with the append-only tripwire printed.

Blocked/fail paths: HOLD_* quotes, verify_ledger non-zero, unofficial rejections,
OWN_NATIONAL permission drafts, a missing ledger, a prod DATABASE_URL.

No network. No database. The real scripts are loaded only where they already exist;
confirm_quotes / verify_ledger are injected because this checkout may not carry them.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import import_pipeline as pipeline  # noqa: E402
from backend.imports.otto.executor import PromoteResult  # noqa: E402

OFFICIAL = "https://www.irishimmigration.ie/registering-your-immigration-permission/"
UNOFFICIAL = "https://relocation-tips.example.com/ireland/ppsn"


def _ledger(tmp_path: Path, records: list[dict], name: str = "facts.ndjson") -> Path:
    path = tmp_path / name
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records),
        encoding="utf-8",
    )
    return path


def _fact(**over) -> dict:
    rec = {
        "destination_country": "IE",
        "entity_topic_key": "ie-eu-eea-proof-of-address",
        "entity_title": "Ireland Proof of Address for PPSN and Banking",
        "fact_key": "ie-eu-eea-ppsn-proof-of-address-required",
        "fact_text": "An EEA professional applying for a PPS Number must provide proof of address.",
        "fact_type": "document",
        "source_url": OFFICIAL,
        "evidence_quote": "The document must show your name and address and not be older than 3 months.",
        "confidence": "high",
        "applies_to": {"nationality": "EEA", "status": "professional"},
    }
    rec.update(over)
    return rec


def _confirmed(_rec, _cache):
    return {"verdict": "CONFIRMED", "entity_topic_key": _rec.get("entity_topic_key")}


def _import_mod():
    return pipeline.load_script("import_otto_facts")


def _run(ledger: Path, **kwargs):
    kwargs.setdefault("classify_fn", _confirmed)
    kwargs.setdefault("verify_fn", lambda _p: 0)
    kwargs.setdefault("import_mod", _import_mod())
    kwargs.setdefault("tripwire_fn", lambda: {
        "approved_count": 12,
        "approved_md5": pipeline.approved_fingerprint(["a", "b"]),
        "expert_verified_count": 3,
        "queried": False,
    })
    return pipeline.run_pipeline(str(ledger), **kwargs)


def test_approved_fingerprint_is_order_insensitive_and_moves_when_an_id_does():
    assert pipeline.approved_fingerprint(["b", "a"]) == pipeline.approved_fingerprint(["a", "b"])
    assert pipeline.approved_fingerprint(["a"]) != pipeline.approved_fingerprint(["a", "b"])
    assert pipeline.approved_fingerprint(()) == pipeline.approved_fingerprint([])


def test_happy_path_promote_is_dry_run_and_prints_tripwire(tmp_path):
    ledger = _ledger(tmp_path, [_fact()])
    report = _run(ledger)
    assert report.status == "pass" and report.exit_code == 0
    assert [s.name for s in report.steps] == [
        "confirm_quotes",
        "verify_ledger",
        "import_otto_facts",
        "check_nationality_scope",
        "promote",
    ]
    assert all(s.ok for s in report.steps)
    assert report.promote["dry_run"] is True
    assert report.promote["review_status"] == "pending"
    assert report.promote["promoted"] >= 1
    assert "apply" in report.steps[2].extra and report.steps[2].extra["apply"] is False
    assert report.tripwire["approved_count"] == 12
    assert report.tripwire["expert_verified_count"] == 3
    text = pipeline.format_tripwire(report.tripwire)
    assert "append-only tripwire" in text
    assert report.tripwire["approved_md5"] in text
    assert "12" in text and "3" in text


def test_cli_happy_path_against_tmp_ledger_with_injected_steps(tmp_path, monkeypatch, capsys):
    ledger = _ledger(tmp_path, [_fact()])
    orig = pipeline.run_pipeline

    def fake_run(target, fetch=False, **_kwargs):
        return orig(
            str(target),
            classify_fn=_confirmed,
            verify_fn=lambda _p: 0,
            import_mod=_import_mod(),
            tripwire_fn=lambda: {
                "approved_count": 12,
                "approved_md5": pipeline.approved_fingerprint(["a", "b"]),
                "expert_verified_count": 3,
                "queried": False,
            },
        )

    monkeypatch.setattr(pipeline, "run_pipeline", fake_run)
    code = pipeline.main(["--ledger", str(ledger)])
    out = capsys.readouterr()[0]
    assert code == 0
    assert "append-only tripwire" in out
    assert "dry_run" in out or "promote" in out.lower()
    assert "pending" in out


def test_hold_quote_blocks_before_verify(tmp_path):
    ledger = _ledger(tmp_path, [_fact()])
    called = {"verify": False}

    def classify(rec, cache):
        return {"verdict": "HOLD_WRONG_SRC", "entity_topic_key": rec["entity_topic_key"]}

    def verify(_p):
        called["verify"] = True
        return 0

    report = _run(ledger, classify_fn=classify, verify_fn=verify)
    assert report.status == "blocked" and report.exit_code == 1
    assert report.steps[0].blocked is True
    assert called["verify"] is False
    assert report.promote == {}


def test_verify_ledger_nonzero_blocks_import(tmp_path):
    ledger = _ledger(tmp_path, [_fact()])
    imported = {"n": 0}

    class Boom:
        def read_jsonl(self, *a, **k):
            imported["n"] += 1
            raise AssertionError("import must not run after verify_ledger fails")

        def destinations_for(self, rows):
            return []

    report = _run(ledger, verify_fn=lambda _p: 1, import_mod=Boom())
    assert report.status == "blocked" and report.exit_code == 1
    assert imported["n"] == 0
    assert report.steps[-1].name == "verify_ledger"


def test_unofficial_source_is_a_blocked_import(tmp_path):
    ledger = _ledger(tmp_path, [_fact(source_url=UNOFFICIAL)])
    report = _run(ledger)
    assert report.status == "blocked" and report.exit_code == 1
    assert report.steps[-1].name == "import_otto_facts"
    assert report.steps[-1].blocked is True


def test_malformed_jsonl_is_a_fail(tmp_path):
    ledger = tmp_path / "facts.ndjson"
    ledger.write_text("{not json\n", encoding="utf-8")
    report = _run(ledger)
    assert report.exit_code == 2
    assert report.status == "fail"
    assert report.steps[-1].name == "import_otto_facts"


def test_permission_own_national_draft_is_blocked(tmp_path):
    ledger = _ledger(tmp_path, [_fact(
        entity_topic_key="ie-eu-eea-residence-registration",
        entity_title="Ireland EU/EEA Residence Registration",
        fact_key="ie-eu-eea-residence-registration-not-required",
        fact_text="EEA nationals living in Ireland are not required to register.",
    )])
    report = _run(ledger)
    assert report.status == "blocked" and report.exit_code == 1
    names = [s.name for s in report.steps]
    assert "check_nationality_scope" in names
    assert report.steps[-1].blocked is True


def test_missing_ledger_is_exit_2(tmp_path):
    report = pipeline.run_pipeline(str(tmp_path / "no-such-batch"))
    assert report.exit_code == 2 and report.status == "fail"


def test_promote_fn_cannot_flip_dry_run_off(tmp_path):
    ledger = _ledger(tmp_path, [_fact()])
    result = PromoteResult()
    result.dry_run = False  # type: ignore[attr-defined]

    def promote_fn(rows, destinations):
        return result

    report = _run(ledger, promote_fn=promote_fn)
    assert report.status == "fail" and report.exit_code == 2
    assert "dry_run=False" in report.steps[-1].detail


def test_looks_like_prod_and_cli_refuses(monkeypatch, tmp_path):
    assert pipeline.looks_like_prod_database_url("postgresql://x.supabase.co/postgres")
    assert pipeline.looks_like_prod_database_url("postgres://user@localhost/db") is False
    monkeypatch.setenv("DATABASE_URL", "postgresql://aws-0-eu-west-1.pooler.supabase.co/postgres")
    monkeypatch.setenv("ENV", "production")
    ledger = _ledger(tmp_path, [_fact()])
    assert pipeline.main(["--ledger", str(ledger)]) == 2


def test_offline_tripwire_is_a_real_fingerprint_not_a_skip():
    tw = pipeline._offline_tripwire()
    assert tw["queried"] is False
    assert tw["approved_md5"] == pipeline.approved_fingerprint(())
    assert tw["approved_count"] == 0


def test_committed_sample_resolves_when_present():
    """docs/imports/<batch>/facts.ndjson is the operator path; skip if this checkout lacks it."""
    try:
        path = pipeline.resolve_ledger("ie-eu-eea-freemover-2026-08-22")
    except FileNotFoundError:
        pytest.skip("sample batch not in this checkout")
    assert path.name == "facts.ndjson"
    assert path.is_file()


def test_cli_against_committed_sample_is_dry_run_only(monkeypatch, capsys):
    try:
        ledger = pipeline.resolve_ledger("ie-eu-eea-freemover-2026-08-22")
    except FileNotFoundError:
        pytest.skip("sample batch not in this checkout")

    orig = pipeline.run_pipeline

    def fake_run(target, fetch=False, **_kwargs):
        return orig(
            str(target),
            classify_fn=_confirmed,
            verify_fn=lambda _p: 0,
            import_mod=_import_mod(),
            tripwire_fn=lambda: pipeline._offline_tripwire(),
        )

    monkeypatch.setattr(pipeline, "run_pipeline", fake_run)
    code = pipeline.main([str(ledger)])
    out = capsys.readouterr()[0]
    assert code in (0, 1)  # nationality scope may block this particular sample
    assert "append-only tripwire" in out
    assert "no writes" in out
    assert '"dry_run": true' in out or '"status": "blocked"' in out
