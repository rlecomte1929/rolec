"""Unit tests for scripts/corridor_harness.py — no DB, no network."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "corridor_harness.py"


def _load():
    spec = importlib.util.spec_from_file_location("corridor_harness_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


h = _load()


def _fact(**over):
    rec = {
        "destination_country": "IE",
        "entity_topic_key": "ie-eu-eea-proof-of-address",
        "entity_title": "Ireland Proof of Address",
        "fact_key": "ie-eu-eea-ppsn-proof-of-address-required",
        "fact_text": "An EEA professional applying for a PPS Number must provide proof of address.",
        "fact_type": "document",
        "source_url": "https://www.irishimmigration.ie/registering-your-immigration-permission/",
        "evidence_quote": "The document must show your name and address.",
        "applies_to": {"nationality": "EEA", "status": "professional"},
    }
    rec.update(over)
    return rec


def _write_ndjson(path: Path, rows: list[dict]) -> Path:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def _batch(tmp_path: Path, rows: list[dict] | None = None, *, shape: str = "A") -> Path:
    batch = tmp_path / "otto-resource-2026-09-08"
    batch.mkdir()
    rows = rows or [_fact()]
    _write_ndjson(batch / "facts.ndjson", rows)
    if shape == "A":
        manifest = {
            "batch_id": batch.name,
            "files": {"facts.ndjson": {"records": len(rows), "sha256": "abc"}},
        }
    else:
        manifest = {
            "batch_id": batch.name,
            "artifacts": [{"path": "facts.ndjson", "record_count": len(rows), "sha256": "abc"}],
        }
    (batch / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return batch


class FakeResult:
    def __init__(self, row):
        self._row = row

    def mappings(self):
        return self

    def first(self):
        return self._row

    def all(self):
        return [self._row] if self._row is not None else []


class FakeSession:
    def __init__(self, fingerprints=None, ready_count: int = 1):
        self.fingerprints = list(fingerprints or [(1, 0, "aaa"), (1, 0, "aaa")])
        self._fp_i = 0
        self.ready_count = ready_count
        self.executed: list[tuple[str, dict | None]] = []
        self.rolled_back = False
        self.committed = False
        self.began = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def begin(self):
        self.began = True

    def rollback(self):
        self.rolled_back = True

    def commit(self):
        self.committed = True

    def execute(self, sql, params=None):
        s = str(sql)
        self.executed.append((s, params))
        if "fp_protected" in s or "requirement_items" in s:
            row = self.fingerprints[min(self._fp_i, len(self.fingerprints) - 1)]
            self._fp_i += 1
            return FakeResult(row)
        if "immigration_fact_candidates" in s and "count" in s.lower():
            return FakeResult((self.ready_count,))
        return FakeResult(None)


class FakeToolRunner:
    def __init__(self, exits: dict[str, int] | None = None, quote_rows: list[dict] | None = None):
        self.exits = exits or {}
        self.calls: list[list[str]] = []
        self.quote_rows = quote_rows

    def run(self, argv: list[str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(argv))
        name = h.script_basename(argv)
        code = self.exits.get(name, 0)
        if name == "check_otto_batches.py":
            out = _flag(argv, "--json")
            if out:
                Path(out).write_text(json.dumps({"ok": True, "exit": code}), encoding="utf-8")
        elif name == "convert_otto_batch.py":
            dest = _flag(argv, "--out")
            src = next(
                (Path(a) for a in argv if str(a).endswith(".ndjson") and Path(a).name != Path(dest or "").name),
                None,
            )
            if dest and src and src.is_file() and code == 0:
                Path(dest).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        elif name == "verify_ledger.py":
            out_dir = Path(_flag(argv, "--out") or ".")
            src = next((Path(a) for a in argv if str(a).endswith("clean-input.ndjson")), None)
            dest = out_dir / "clean.ndjson"
            if src and src.is_file():
                dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            else:
                dest.write_text("", encoding="utf-8")
            (out_dir / "worklist.ndjson").write_text("", encoding="utf-8")
        elif name == "verify_batch_quotes.py":
            report = _flag(argv, "--report")
            rows = self.quote_rows
            if rows is None:
                rows = [
                    {
                        "source_url": "https://www.irishimmigration.ie/",
                        "evidence_quote": "ok",
                        "dedupe_key": "k",
                        "status": "confirmed",
                    }
                ]
            if report:
                Path(report).write_text(json.dumps(rows), encoding="utf-8")
        return subprocess.CompletedProcess(argv, code, stdout=f"{name} ok\n", stderr="")


def _flag(argv: list[str], flag: str) -> str | None:
    if flag in argv:
        i = argv.index(flag)
        if i + 1 < len(argv):
            return argv[i + 1]
    return None


def _script_calls(runner: FakeToolRunner, name: str) -> list[list[str]]:
    return [c for c in runner.calls if h.script_basename(c) == name]


def _promote_result(n: int = 1):
    return h.PromoteResult(
        promoted=n,
        skipped_verified=[],
        unmapped=[],
        drafts=[SimpleNamespace(title="Ireland Proof of Address")],
    )


def _run(batch: Path, runner: FakeToolRunner, session: FakeSession, **kwargs):
    harness = batch / "_harness"
    kwargs.setdefault("stage", False)
    kwargs.setdefault("no_fetch", True)
    return h.run_harness(
        str(batch),
        out=harness,
        runner=runner,
        session_factory=lambda: session,
        promote_fn=lambda _s, **_k: _promote_result(),
        **kwargs,
    )


def test_happy_path_dry_no_stage(tmp_path):
    batch = _batch(tmp_path)
    runner = FakeToolRunner()
    session = FakeSession()
    code = _run(batch, runner, session)
    ckpt = json.loads((batch / "_harness" / "run.json").read_text())
    assert code == 0
    assert ckpt["harness_exit"] == 0
    assert (batch / "_harness" / "report.md").is_file()
    statuses = [s["status"] for s in ckpt["stages"]]
    assert statuses == ["ok", "ok", "skipped", "ok", "ok", "ok", "ok"]
    for call in runner.calls:
        if h.script_basename(call) == "verify_ledger.py":
            continue
        assert "--apply" not in call
    assert session.rolled_back is True
    assert session.committed is False


def test_stage_path_passes_apply_and_expected(tmp_path):
    batch = _batch(tmp_path, [_fact(), _fact(fact_key="b")])
    runner = FakeToolRunner()
    session = FakeSession()
    code = _run(batch, runner, session, stage=True)
    assert code == 0
    calls = _script_calls(runner, "import_otto_facts.py")
    assert calls, "stage 4 must invoke import_otto_facts"
    argv = calls[0]
    assert "--apply" in argv
    n = int(argv[argv.index("--expected") + 1])
    assert n == 2
    assert session.committed is False


def test_reconcile_gate(tmp_path):
    batch = _batch(tmp_path)
    runner = FakeToolRunner(exits={"check_otto_batches.py": 1})
    session = FakeSession()
    code = _run(batch, runner, session)
    ckpt = json.loads((batch / "_harness" / "run.json").read_text())
    assert code == 10
    assert ckpt["harness_exit"] == 10
    assert ckpt["stages"][1]["status"] == "gated"
    assert all(s["status"] == "pending" for s in ckpt["stages"][2:])


def test_referee_pause_unreachable(tmp_path):
    batch = _batch(tmp_path)
    runner = FakeToolRunner(
        quote_rows=[
            {
                "source_url": "https://www.gob.ec/blocked",
                "evidence_quote": "x",
                "dedupe_key": "k1",
                "status": "unreachable",
            }
        ]
    )
    session = FakeSession()
    code = _run(batch, runner, session)
    ckpt = json.loads((batch / "_harness" / "run.json").read_text())
    work = batch / "_harness" / "grounding" / "worklist.json"
    assert code == 20
    assert ckpt["harness_exit"] == 20
    assert ckpt["stages"][3]["status"] == "paused"
    assert work.is_file()
    rows = json.loads(work.read_text())
    assert rows[0]["source_url"] == "https://www.gob.ec/blocked"


def test_referee_pause_unreachable_when_verifier_exists_without_report(tmp_path, monkeypatch):
    """Fail-closed: always pass --report even if the on-disk verifier lacks the flag."""
    scripts = tmp_path / "scripts_on_disk"
    scripts.mkdir()
    (scripts / "verify_batch_quotes.py").write_text("# sibling verifier; no --report flag\n")
    monkeypatch.setattr(h, "SCRIPTS", scripts)
    batch = _batch(tmp_path)
    runner = FakeToolRunner(
        quote_rows=[
            {
                "source_url": "https://www.gob.ec/blocked",
                "evidence_quote": "x",
                "dedupe_key": "k1",
                "status": "unreachable",
            }
        ]
    )
    session = FakeSession()
    code = _run(batch, runner, session)
    assert code == 20
    argv = _script_calls(runner, "verify_batch_quotes.py")[0]
    assert "--report" in argv
    assert "--grounding-dir" in argv
    work = batch / "_harness" / "grounding" / "worklist.json"
    assert json.loads(work.read_text())[0]["source_url"] == "https://www.gob.ec/blocked"


def test_resume_after_pause(tmp_path):
    batch = _batch(tmp_path)
    paused = FakeToolRunner(
        quote_rows=[
            {
                "source_url": "https://www.gob.ec/blocked",
                "evidence_quote": "x",
                "dedupe_key": "k1",
                "status": "unreachable",
            }
        ]
    )
    session = FakeSession()
    assert _run(batch, paused, session) == 20
    runner = FakeToolRunner()
    session2 = FakeSession()
    code = h.resume_harness(
        batch.name,
        no_fetch=True,
        out=batch / "_harness",
        runner=runner,
        session_factory=lambda: session2,
        promote_fn=lambda _s, **_k: _promote_result(),
    )
    ckpt = json.loads((batch / "_harness" / "run.json").read_text())
    assert code == 0
    assert ckpt["harness_exit"] == 0
    assert ckpt["stages"][3]["status"] == "ok"
    assert (batch / "_harness" / "report.md").is_file()


def test_stage4_partial_is_gate_10(tmp_path):
    batch = _batch(tmp_path)
    runner = FakeToolRunner(exits={"import_otto_facts.py": 3})
    session = FakeSession()
    code = _run(batch, runner, session)
    ckpt = json.loads((batch / "_harness" / "run.json").read_text())
    assert code == 10
    assert ckpt["harness_exit"] == 10
    assert ckpt["stages"][4]["status"] == "gated"


def test_scope_gate(tmp_path):
    batch = _batch(tmp_path)
    runner = FakeToolRunner(exits={"check_nationality_scope.py": 1})
    session = FakeSession()
    code = _run(batch, runner, session, stage=True)
    ckpt = json.loads((batch / "_harness" / "run.json").read_text())
    assert code == 30
    assert ckpt["harness_exit"] == 30
    assert ckpt["stages"][5]["status"] == "gated"


def test_fingerprint_invariant(tmp_path):
    batch = _batch(tmp_path)
    runner = FakeToolRunner()
    bad = FakeSession(fingerprints=[(1, 0, "before"), (2, 0, "after")])
    code = _run(batch, runner, bad)
    assert code == 30
    assert bad.rolled_back is True
    assert bad.committed is False

    good = FakeSession(fingerprints=[(4, 1, "same"), (4, 1, "same")])
    code2 = _run(batch, runner, good)
    # completed checkpoint from the mismatch run is NOT complete; a new run starts fresh
    # but wait — mismatch gated so checkpoint is not complete. run() always starts fresh.
    assert code2 == 0


def test_manifest_normalization():
    shape_a = {
        "batch_id": "sg-ec",
        "files": {"facts.ndjson": {"records": 10, "sha256": "x"}},
    }
    shape_b = {
        "batch_id": "B3",
        "artifacts": [{"path": "corridor_facts.ndjson", "record_count": 20, "sha256": "y"}],
    }
    assert h.manifest_records(shape_a) == 10
    assert h.manifest_records(shape_b) == 20
    assert h.manifest_ndjson_urls(shape_a, "https://example.com/dir/manifest.json") == [
        "https://example.com/dir/facts.ndjson"
    ]
    assert h.manifest_ndjson_urls(shape_b, "https://example.com/dir/manifest.json") == [
        "https://example.com/dir/corridor_facts.ndjson"
    ]
    with pytest.raises(h.UsageError) as exc:
        h.manifest_records({"batch_id": "nope", "oops": True})
    assert exc.value.code == 2


def test_unknown_manifest_shape_exits_2(tmp_path):
    batch = tmp_path / "weird"
    batch.mkdir()
    (batch / "manifest.json").write_text(json.dumps({"batch_id": "weird"}), encoding="utf-8")
    (batch / "facts.ndjson").write_text("{}\n", encoding="utf-8")
    runner = FakeToolRunner()
    session = FakeSession()
    code = _run(batch, runner, session)
    assert code == 2


def test_checkpoint_atomicity_idempotency_and_status(tmp_path, capsys):
    batch = _batch(tmp_path)
    runner = FakeToolRunner()
    session = FakeSession()
    assert _run(batch, runner, session) == 0
    first_calls = len(runner.calls)
    code2 = _run(batch, runner, session)
    assert code2 == 0
    assert len(runner.calls) == first_calls
    st = h.status_harness(batch.name, out=batch / "_harness")
    assert st == 0
    printed = capsys.readouterr().out
    assert batch.name in printed
    assert "harness_exit" in printed


def test_convert_gates_when_converter_fails(tmp_path):
    rec = {"topic": "not-vocab", "text": "nope"}
    batch = _batch(tmp_path, [rec])
    _write_ndjson(batch / "facts.ndjson", [rec])
    runner = FakeToolRunner(exits={"convert_otto_batch.py": 1})
    session = FakeSession()
    code = _run(batch, runner, session)
    ckpt = json.loads((batch / "_harness" / "run.json").read_text())
    assert code == 10
    assert ckpt["stages"][2]["status"] == "gated"
    assert _script_calls(runner, "convert_otto_batch.py")



@pytest.mark.integration
def test_integration_rolled_back_tx_leaves_zero_rows_changed():
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set")
    pytest.skip("applier-owned live DB assertion")


@pytest.mark.integration
def test_integration_expected_reconciles_pass():
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set")
    pytest.skip("applier-owned live DB assertion")


def test_harness_module_does_not_import_executor_at_load():
    src = SCRIPT.read_text(encoding="utf-8")
    head, _, _ = src.partition("def default_promote_fn")
    assert "backend.imports.otto.executor" not in head
    assert "default_promote_fn" in h.__dict__
