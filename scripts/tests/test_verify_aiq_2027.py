"""The AIQ-2027 closure gate must fail for the right reason, not merely pass.

`scripts/verify_aiq_2027_ve_ie_load.py` is green against the batch as committed, which proves
nothing on its own — a gate that cannot fail reads exactly the same as one that checked
something. Each case below plants one defect and asserts the check named for it reports it.

Every mutation is written to a temp copy with the pinned sha256 re-pointed at the mutated
bytes, so the integrity check cannot be what fails. Otherwise these tests would pass with all
the semantic checks deleted.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "scripts" / "verify_aiq_2027_ve_ie_load.py"


def _load():
    spec = importlib.util.spec_from_file_location("verify_aiq_2027_ve_ie_load", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["verify_aiq_2027_ve_ie_load"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def mod():
    return _load()


def _records(mod):
    return [
        json.loads(l)
        for l in mod.NDJSON.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]


def _repoint(mod, monkeypatch, tmp_path, records):
    """Write `records` to a temp artifact and re-pin every integrity constant onto it."""
    nd = tmp_path / "mutated.ndjson"
    nd.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8"
    )
    digest = hashlib.sha256(nd.read_bytes()).hexdigest()
    manifest = json.loads(mod.MANIFEST.read_text(encoding="utf-8"))
    manifest["sha256"] = digest
    mf = tmp_path / "manifest.json"
    mf.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(mod, "NDJSON", nd)
    monkeypatch.setattr(mod, "MANIFEST", mf)
    monkeypatch.setattr(mod, "EXPECTED_SHA256", digest)
    monkeypatch.setattr(sys, "argv", ["verify"])


def _run(mod):
    return mod.main()


def test_passes_against_the_committed_batch(mod, monkeypatch):
    """The baseline. If this ever fails, the batch changed — not the gate."""
    monkeypatch.setattr(sys, "argv", ["verify"])
    assert _run(mod) == 0


def test_catches_a_tampered_artifact(mod, monkeypatch, tmp_path):
    """Integrity on its own: bytes edited, constants NOT re-pointed."""
    recs = _records(mod)
    recs[0]["fact_text"] = "edited"
    nd = tmp_path / "t.ndjson"
    nd.write_text("\n".join(json.dumps(r) for r in recs) + "\n", encoding="utf-8")
    monkeypatch.setattr(mod, "NDJSON", nd)
    monkeypatch.setattr(sys, "argv", ["verify"])
    assert _run(mod) == 1


def test_catches_a_row_arriving_approved(mod, monkeypatch, tmp_path, capsys):
    """The failure that would publish unreviewed immigration content on promotion."""
    recs = _records(mod)
    recs[0]["review_status"] = "approved"
    _repoint(mod, monkeypatch, tmp_path, recs)
    assert _run(mod) == 1
    out = capsys.readouterr().out
    assert "must all be 'pending'" in out
    assert "would publish unreviewed immigration content" in out


def test_catches_a_quote_marked_confirmed(mod, monkeypatch, tmp_path, capsys):
    recs = _records(mod)
    recs[4]["quote_verbatim_confirmed"] = True
    _repoint(mod, monkeypatch, tmp_path, recs)
    assert _run(mod) == 1
    assert "must all be false" in capsys.readouterr().out


def test_catches_a_counsel_flag_moved_between_facts(mod, monkeypatch, tmp_path, capsys):
    """The case a count-based check cannot see: still exactly 4 flags, wrong 4 facts.

    This is the one that matters. Three of the four flagged rows are the legally load-bearing
    ones; a flag drifting off `spanish_residence_does_not_grant_irish_entry` and onto a
    routine fact would let counsel approve the trap unreviewed.
    """
    recs = _records(mod)
    by_key = {r["topic_key"]: r for r in recs}
    by_key["spanish_residence_does_not_grant_irish_entry"]["needs_lawyer_review"] = False
    by_key["entry_d_visa_required_venezuela"]["needs_lawyer_review"] = True
    assert sum(1 for r in recs if r["needs_lawyer_review"]) == 4, "count must be unchanged"
    _repoint(mod, monkeypatch, tmp_path, recs)
    assert _run(mod) == 1
    out = capsys.readouterr().out
    assert "needs_lawyer_review mismatch" in out
    assert "spanish_residence_does_not_grant_irish_entry" in out


def test_catches_a_missing_fact(mod, monkeypatch, tmp_path, capsys):
    _repoint(mod, monkeypatch, tmp_path, _records(mod)[:8])
    assert _run(mod) == 1
    assert "expected exactly 9 facts, parsed 8" in capsys.readouterr().out


def test_catches_nationality_flipped_to_free_mover(mod, monkeypatch, tmp_path, capsys):
    """ES→IE would derive EEA. The subject is a Venezuelan national resident in Spain, and
    that residence does not carry over — an EEA row serves the free-mover track to someone who
    needs a visa before travel."""
    recs = _records(mod)
    recs[0]["applies_to_nationality_classes"] = ["EEA"]
    _repoint(mod, monkeypatch, tmp_path, recs)
    assert _run(mod) == 1
    assert "expected ['THIRD_COUNTRY']" in capsys.readouterr().out


def test_catches_a_family_domain_row_becoming_unmappable(mod, monkeypatch, tmp_path, capsys):
    """`mappings.resolve` accepts only domain_area='immigration'. Three rows are authored
    'family' and promote solely because staging normalises them; check 6b pins that set."""
    recs = _records(mod)
    for r in recs:
        if r["topic_key"] == "spouse_stamp_1g_right_to_work":
            r["domain_area"] = "immigration"
    _repoint(mod, monkeypatch, tmp_path, recs)
    assert _run(mod) == 1
    assert "domain_area='family' set changed" in capsys.readouterr().out
