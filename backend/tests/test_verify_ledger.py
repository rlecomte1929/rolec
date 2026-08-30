"""Corridor Verifier Service P1 — V0-V3 gates and the landing contract.

⚠️ THE REAL US->EC FIXTURE IS NOT PRESENT. The P1 brief names
`backend/imports/otto/fixtures/us_ec/` (from `us_ec_corridor_batch.zip`) as the
acceptance fixture. That archive does not exist on this machine or in this repo, so the
brief's acceptance run has NOT been performed — see the PR body, which marks it FAILED.

These tests therefore use a small SYNTHETIC batch built inline. It is deliberately NOT
written to `fixtures/us_ec/`: a fabricated file sitting at the path reserved for real
delivered research would be indistinguishable from the real thing to the next reader,
and inventing sources is precisely what this service exists to refuse.

Network is never touched: `run_gates` takes an injectable `fetcher`, and every test
here passes a stub.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# `scripts/` is not a package, and `backend/scripts/` also exists — the shared conftest
# puts `backend/` on sys.path, so a plain `import scripts.verify_ledger` resolves to the
# WRONG `scripts` package and fails collection in a full-suite run while passing
# standalone. Import by path, the idiom the rest of backend/tests already uses
# (test_b3_corridor_facts_conversion.py:29-35).
_SCRIPT = _REPO_ROOT / "scripts" / "verify_ledger.py"
_spec = importlib.util.spec_from_file_location("verify_ledger", _SCRIPT)
assert _spec and _spec.loader
_vl = importlib.util.module_from_spec(_spec)
sys.modules["verify_ledger"] = _vl
_spec.loader.exec_module(_vl)

VERDICT_FLAG = _vl.VERDICT_FLAG
VERDICT_PASS = _vl.VERDICT_PASS
VERDICT_REJECT = _vl.VERDICT_REJECT
entity_uuid = _vl.entity_uuid
fact_uuid = _vl.fact_uuid
land = _vl.land
load_batch = _vl.load_batch
normalise_source_url = _vl.normalise_source_url
run_gates = _vl.run_gates

# A real page body the quote must be found inside. `check_evidence` needs >=200 chars of
# source before it will return anything but NO_SOURCE.
PAGE = (
    "Immigration Service Delivery. First-time registration must be completed within 90 "
    "days of arrival in the State. The registration fee is EUR 300 and is payable at the "
    "time of registration. Your Irish Residence Permit card will be delivered within 10 "
    "working days to the address you provide. You must attend in person and bring your "
    "passport and evidence of your permission to remain."
)
GOOD_QUOTE = "The registration fee is EUR 300"


def _stub_fetcher(text=PAGE, ok=True, reason="fetched"):
    def _f(url, robots=None, limiter=None):
        return {"ok": ok, "reason": reason, "text": text, "blocked": False, "ua": None}
    return _f


def _entity(**over):
    d = {"entity_uid": "ent-1", "destination_country": "IE", "domain_area": "immigration",
         "topic_key": "first_registration", "title": "First-time registration"}
    d.update(over)
    return d


def _fact(**over):
    d = {"fact_uid": "fact-1", "entity_uid": "ent-1", "fact_type": "fee",
         "fact_key": "registrationFee", "fact_text": "The registration fee is EUR 300.",
         "source_url": "https://www.irishimmigration.ie/registration/",
         "evidence_quote": GOOD_QUOTE, "confidence": "high"}
    d.update(over)
    return d


def _write_batch(tmp_path: Path, entities, facts, name: str = "batch") -> Path:
    d = tmp_path / name
    d.mkdir(exist_ok=True)
    (d / "01_requirement_entities_TEST.ndjson").write_text(
        "\n".join(json.dumps(e) for e in entities), encoding="utf-8")
    (d / "02_requirement_facts_TEST.ndjson").write_text(
        "\n".join(json.dumps(f) for f in facts), encoding="utf-8")
    return d


# ── V0: URL normalisation ────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ('https://x.gov.ie/a%22', "https://x.gov.ie/a"),
    ('https://x.gov.ie/a"', "https://x.gov.ie/a"),
    ("www.irishimmigration.ie/reg", "https://www.irishimmigration.ie/reg"),
    ("https://x.gov.ie/a#frag#frag", "https://x.gov.ie/a#frag"),
    ("https://x.gov.ie/a).", "https://x.gov.ie/a"),
    ("  https://x.gov.ie/ok  ", "https://x.gov.ie/ok"),
])
def test_normalise_source_url_repairs_known_garble(raw, expected):
    assert normalise_source_url(raw) == expected


def test_normalise_source_url_leaves_a_clean_url_alone():
    url = "https://www.irishimmigration.ie/registering-your-permission/"
    assert normalise_source_url(url) == url


# ── V0: loading ──────────────────────────────────────────────────────────────

def test_dry_run_parses_every_record(tmp_path):
    d = _write_batch(tmp_path, [_entity()], [_fact(), _fact(fact_uid="fact-2")])
    entities, facts, problems = load_batch(d)
    assert problems == []
    assert len(entities) == 1 and len(facts) == 2


def test_load_batch_reports_a_missing_file(tmp_path):
    d = tmp_path / "batch"
    d.mkdir()
    (d / "01_requirement_entities_TEST.ndjson").write_text("{}", encoding="utf-8")
    _, _, problems = load_batch(d)
    assert any("02_requirement_facts" in p for p in problems)


def test_a_single_unparseable_line_loses_only_that_record(tmp_path):
    d = tmp_path / "batch"
    d.mkdir()
    (d / "01_requirement_entities_TEST.ndjson").write_text(
        json.dumps(_entity()), encoding="utf-8")
    (d / "02_requirement_facts_TEST.ndjson").write_text(
        json.dumps(_fact()) + "\n{ NOT JSON\n" + json.dumps(_fact(fact_uid="fact-3")),
        encoding="utf-8")
    _, facts, _ = load_batch(d)
    assert [f.fact_uid for f in facts] == ["fact-1", "fact-3"]


# ── V1: schema / enum gate ───────────────────────────────────────────────────

@pytest.mark.parametrize("bad_field,value,needle", [
    ("fact_type", "not_a_type", "fact_type"),
    ("confidence", "very-sure", "confidence"),
    ("fact_key", "", "fact_key"),
    ("fact_text", "", "fact_text"),
])
def test_v1_rejects_a_fact_outside_the_live_vocabulary(tmp_path, bad_field, value, needle):
    d = _write_batch(tmp_path, [_entity()], [_fact(**{bad_field: value})])
    entities, facts, worklist = run_gates(*load_batch(d)[:2], fetcher=_stub_fetcher())
    assert facts[0].verdict == VERDICT_REJECT
    assert any(needle in r for item in worklist for r in item["reasons"])


def test_v1_rejects_an_entity_with_a_country_name_in_the_country_code(tmp_path):
    d = _write_batch(tmp_path, [_entity(destination_country="Ireland")], [_fact()])
    entities, facts, worklist = run_gates(*load_batch(d)[:2], fetcher=_stub_fetcher())
    assert entities == []
    assert any("alpha-2" in r for item in worklist for r in item["reasons"])


def test_v1_rejects_a_fact_whose_entity_does_not_exist(tmp_path):
    d = _write_batch(tmp_path, [_entity()], [_fact(entity_uid="ent-missing")])
    _, facts, worklist = run_gates(*load_batch(d)[:2], fetcher=_stub_fetcher())
    assert facts[0].verdict == VERDICT_REJECT
    assert any("no matching entity" in r for item in worklist for r in item["reasons"])


def test_v1_rejects_a_duplicate_fact_uid(tmp_path):
    d = _write_batch(tmp_path, [_entity()], [_fact(), _fact()])
    _, facts, worklist = run_gates(*load_batch(d)[:2], fetcher=_stub_fetcher())
    assert facts[1].verdict == VERDICT_REJECT
    assert any("duplicate fact_uid" in r for item in worklist for r in item["reasons"])


# ── V2: source gate ──────────────────────────────────────────────────────────

def test_v2_rejects_an_unofficial_host(tmp_path):
    d = _write_batch(tmp_path, [_entity()],
                     [_fact(source_url="https://some-relocation-blog.com/ireland")])
    _, facts, worklist = run_gates(*load_batch(d)[:2], fetcher=_stub_fetcher())
    assert facts[0].verdict == VERDICT_REJECT
    assert any("unofficial" in r for item in worklist for r in item["reasons"])


def test_v2_rejects_plain_http(tmp_path):
    d = _write_batch(tmp_path, [_entity()],
                     [_fact(source_url="http://www.irishimmigration.ie/reg")])
    _, facts, worklist = run_gates(*load_batch(d)[:2], fetcher=_stub_fetcher())
    assert facts[0].verdict == VERDICT_REJECT
    assert any("not https" in r for item in worklist for r in item["reasons"])


def test_v2_rejects_a_dead_source(tmp_path):
    d = _write_batch(tmp_path, [_entity()], [_fact()])
    _, facts, worklist = run_gates(*load_batch(d)[:2],
                                   fetcher=_stub_fetcher(text="", ok=False, reason="http_404"))
    assert facts[0].verdict == VERDICT_REJECT
    assert any("did not resolve" in r for item in worklist for r in item["reasons"])


def test_v2_accepts_an_official_host_and_ranks_it(tmp_path):
    d = _write_batch(tmp_path, [_entity()], [_fact()])
    _, facts, _ = run_gates(*load_batch(d)[:2], fetcher=_stub_fetcher())
    assert facts[0].authority_rank == 1


# ── V3: evidence grounding ───────────────────────────────────────────────────

def test_v3_verifies_a_quote_that_is_on_the_page(tmp_path):
    d = _write_batch(tmp_path, [_entity()], [_fact()])
    _, facts, worklist = run_gates(*load_batch(d)[:2], fetcher=_stub_fetcher())
    assert facts[0].evidence_verified is True
    assert facts[0].evidence_offset is not None
    assert facts[0].verdict == VERDICT_PASS
    assert worklist == []


def test_v3_flags_a_quote_that_is_not_on_the_page_and_does_not_land_it(tmp_path):
    d = _write_batch(tmp_path, [_entity()],
                     [_fact(evidence_quote="The registration fee is EUR 9999")])
    _, facts, worklist = run_gates(*load_batch(d)[:2], fetcher=_stub_fetcher())
    assert facts[0].evidence_verified is False
    # FLAG, not REJECT: a human decides. But it is still not landed.
    assert facts[0].verdict == VERDICT_FLAG
    assert any("evidence" in r for item in worklist for r in item["reasons"])


def test_v3_does_not_condemn_a_quote_in_another_language(tmp_path):
    """TRANSLATED must not read as 'the quote is absent'.

    The quote here is deliberately long. `fact_evidence._language_of` needs >=6
    word-characters-only tokens before it will name a language, and digits do not count
    — so a short quote like "The stamp duty is 225 euros" (5 tokens) cannot be detected
    and falls through to UNVERIFIED rather than TRANSLATED. That is the existing
    behaviour, not a defect introduced here, but it means the translated-source escape
    hatch only protects reasonably long quotes.
    """
    french_page = (
        "Service-public.fr. Vous devez effectuer votre demande de titre de sejour dans "
        "les trois mois suivant votre arrivee en France. Le montant du droit de timbre "
        "est de 225 euros. Votre carte vous sera remise en main propre a la prefecture "
        "de votre departement de residence apres instruction de votre dossier complet."
    )
    d = _write_batch(tmp_path, [_entity(destination_country="FR")],
                     [_fact(source_url="https://www.service-public.fr/particuliers",
                            evidence_quote="You must submit your residence permit "
                                           "application within the three months that "
                                           "follow your arrival, and the stamp duty for "
                                           "the card is 225 euros")])
    _, facts, _ = run_gates(*load_batch(d)[:2], fetcher=_stub_fetcher(text=french_page))
    assert facts[0].evidence_verified is None       # check did not apply
    assert facts[0].verdict == VERDICT_FLAG          # not rejected


def test_checks_json_records_every_gate(tmp_path):
    d = _write_batch(tmp_path, [_entity()], [_fact()])
    _, facts, _ = run_gates(*load_batch(d)[:2], fetcher=_stub_fetcher())
    assert set(facts[0].checks) == {"v1_schema", "v2_source", "v3_evidence"}


# ── idempotency ──────────────────────────────────────────────────────────────

def test_ids_are_stable_across_runs():
    """A re-run must compute the same uuid, or ON CONFLICT (id) creates duplicates."""
    assert fact_uuid("fact-1") == fact_uuid("fact-1")
    assert entity_uuid("IE", "immigration", "x") == entity_uuid("IE", "immigration", "x")
    assert fact_uuid("fact-1") != fact_uuid("fact-2")
    assert entity_uuid("IE", "immigration", "x") != entity_uuid("FR", "immigration", "x")


class _RecordingSession:
    """Captures executed statements instead of touching a database."""

    def __init__(self):
        self.calls = []
        self.committed = False

    def execute(self, stmt, params=None):
        self.calls.append((str(stmt), params or {}))

    def commit(self):
        self.committed = True


def _land_once(tmp_path, name: str = "batch"):
    d = _write_batch(tmp_path, [_entity()], [_fact()], name=name)
    entities, facts, _ = run_gates(*load_batch(d)[:2], fetcher=_stub_fetcher())
    s = _RecordingSession()
    n = land(s, entities, [f for f in facts if f.verdict == VERDICT_PASS], batch_id="t")
    return s, n


def test_landing_writes_pending_and_never_approved(tmp_path):
    s, n = _land_once(tmp_path)
    assert n == {"entities": 1, "facts": 1}
    statuses = [p.get("status") for _, p in s.calls if "status" in p]
    assert statuses and all(v == "pending" for v in statuses)
    assert not any("approved" in sql for sql, _ in s.calls)
    assert s.committed


def test_landing_never_writes_a_verification_status(tmp_path):
    """`requirement_facts` has no verification_status column, and the machine ceiling is
    'representative' — never 'verified'."""
    s, _ = _land_once(tmp_path)
    blob = " ".join(sql for sql, _ in s.calls) + json.dumps(
        [{k: str(v) for k, v in p.items()} for _, p in s.calls])
    assert "verified'" not in blob.replace("evidence_verified", "")
    assert "verification_status" not in blob


def test_landing_is_idempotent_on_id(tmp_path):
    """Two identical runs emit identical ids, so ON CONFLICT (id) updates in place."""
    s1, _ = _land_once(tmp_path, "run1")
    s2, _ = _land_once(tmp_path, "run2")
    ids1 = [p["id"] for _, p in s1.calls]
    ids2 = [p["id"] for _, p in s2.calls]
    assert ids1 == ids2
    assert all("ON CONFLICT (id)" in sql for sql, _ in s1.calls)


def test_landing_does_not_overwrite_a_reviewer_decision(tmp_path):
    """The UPDATE branch must not touch status/reviewed_by/reviewed_at."""
    s, _ = _land_once(tmp_path)
    for sql, _ in s.calls:
        update = sql.split("DO UPDATE SET", 1)[1] if "DO UPDATE SET" in sql else ""
        assert "status" not in update
        assert "reviewed_by" not in update
        assert "reviewed_at" not in update


def test_an_entity_with_no_clean_fact_is_not_landed(tmp_path):
    d = _write_batch(tmp_path, [_entity(), _entity(entity_uid="ent-2", topic_key="other")],
                     [_fact()])
    entities, facts, _ = run_gates(*load_batch(d)[:2], fetcher=_stub_fetcher())
    s = _RecordingSession()
    n = land(s, entities, [f for f in facts if f.verdict == VERDICT_PASS], batch_id="t")
    assert n["entities"] == 1
