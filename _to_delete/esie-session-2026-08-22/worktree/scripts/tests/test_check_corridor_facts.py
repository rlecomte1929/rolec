"""Meta-test for scripts/check_corridor_facts.py.

WHY EACH TEST PLANTS A VIOLATION. `migration-duplicate-main.yml` sat green for four months
while being structurally incapable of failing — it ran the drift checker in audit mode,
where duplicates print a warning and the process exits 0. It could not have caught the
three-way collision it names as its reason to exist. The lesson: a guard nobody has watched
go RED is decoration.

So every test below takes the known-good fixture, breaks exactly one thing, and asserts the
gate returns exit 1 AND names the responsible check. The first test asserts the unbroken
fixture passes, so a gate that failed everything could not fake its way through the rest.
"""
from __future__ import annotations

import copy
import hashlib
import io
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

REPO = Path(__file__).resolve().parents[2]
GUARD = REPO / "scripts" / "check_corridor_facts.py"
sys.path.insert(0, str(REPO))

# Import the guard as a module so tests can call check() directly, and pre-import the real
# classify_source so a tmp --root does not shadow the backend package.
import importlib.util  # noqa: E402

import backend.imports.otto.parsers  # noqa: F401,E402  (caches the module for tmp roots)

_spec = importlib.util.spec_from_file_location("check_corridor_facts", GUARD)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)

RUN_DATE = "2026-08-19"


def sha(text: str) -> str:
    return hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()


QUOTE_NO = ("Det kan avtales at leieren til sikkerhet for skyldig leie skal deponere et "
            "belop oppad begrenset til summen av seks maneders leie.")
QUOTE_IE = ("If you are aged 18 years or older you can apply for a PPS Number for yourself "
            "and your child online at MyWelfare.")


def good_packs():
    """One NO fact and one IE fact, bound by one corridor. Deliberately minimal."""
    return {
        "NO": {
            "jurisdiction": "NO", "catalog_country": "NORWAY",
            "default_purposes": ["employment"],
            "facts": [{
                "fact_key": "deposit_cap", "topic": "housing-husleieloven",
                "kind": "obligation", "status": "active", "pillar": "HOUSING",
                "title": "Deposit capped at six months", "fact_text": "A deposit may not exceed six months of rent.",
                "timing": "before signing", "non_obvious": True,
                "source": {
                    "url": "https://lovdata.no/lov/1999-03-26-17/x3-5",
                    "publisher_domain": "lovdata.no",
                    "published_date": "2026-06-12", "retrieved_at": "2026-08-19",
                    "evidence_quote": QUOTE_NO, "quote_sha256": sha(QUOTE_NO),
                },
                "last_verified_date": "2026-08-19", "depends_on": [],
                "pack_keys": ["FR-NO:housing-deposit-cap:deposit_cap"],
            }],
        },
        "IE": {
            "jurisdiction": "IE", "catalog_country": "IRELAND",
            "default_purposes": ["employment"],
            "facts": [{
                "fact_key": "pps_number", "topic": "registration-pps",
                "kind": "obligation", "status": "active", "pillar": "RESIDENCE",
                "title": "PPS number", "fact_text": "A PPS number is needed for employment and tax.",
                "timing": "on arrival", "non_obvious": True,
                "source": {
                    "url": "https://www.gov.ie/en/services/get-a-pps-number/",
                    "publisher_domain": "gov.ie",
                    "published_date": "2026-01-30", "retrieved_at": "2026-08-19",
                    "evidence_quote": QUOTE_IE, "quote_sha256": sha(QUOTE_IE),
                },
                "last_verified_date": "2026-08-19", "depends_on": [],
                "pack_keys": ["ES-IE:registration-pps:pps_number"],
            }],
        },
    }


def good_bindings():
    return {
        "ES_IE": {"corridor_id": "ES_IE", "origin_iso": "ES", "destination_iso": "IE",
                  "origin_facts": [],
                  "destination_facts": [{"ref": "IE:registration-pps:pps_number"}]},
        "FR_NO": {"corridor_id": "FR_NO", "origin_iso": "FR", "destination_iso": "NO",
                  "origin_facts": [],
                  "destination_facts": [{"ref": "NO:housing-husleieloven:deposit_cap"}]},
    }


def build(tmp_path, packs=None, bindings=None, allowlist=None, pathways=None):
    root = tmp_path / "repo"
    facts_dir = root / "backend" / "seeds" / "facts"
    facts_dir.mkdir(parents=True)
    for name, pack in (packs if packs is not None else good_packs()).items():
        (facts_dir / f"{name}.yaml").write_text(
            yaml.safe_dump(pack, allow_unicode=True, sort_keys=False), encoding="utf-8")
    for cid, binding in (bindings if bindings is not None else good_bindings()).items():
        d = root / "corridors" / cid
        d.mkdir(parents=True)
        (d / "facts.yaml").write_text(
            yaml.safe_dump(binding, allow_unicode=True, sort_keys=False), encoding="utf-8")
    for cid, steps in (pathways or {}).items():
        p = root / "corridors" / cid / "pathways" / "P_2026"
        p.mkdir(parents=True, exist_ok=True)
        (p / "v1.yaml").write_text(
            "step_graph:\n" + "".join(f"  - step_id: {s}\n    name: x\n" for s in steps),
            encoding="utf-8")
    if allowlist is not None:
        (root / "scripts").mkdir(parents=True, exist_ok=True)
        (root / "scripts" / "corridor_facts_allowlist.txt").write_text(allowlist, encoding="utf-8")
    return root


def run(root, run_date=RUN_DATE, max_age_days=365):
    import datetime as dt
    return guard.check(root, dt.date.fromisoformat(run_date), max_age_days)


def checks_fired(report):
    return {v["check"] for v in report["violations"]}


# ── the fixture itself must pass, or every test below is vacuous ─────────────────────────

def test_good_fixture_passes(tmp_path):
    code, report, text = run(build(tmp_path))
    assert code == 0, text
    assert report["verdict"] == "PASS"
    assert report["gate_bearing"] == 2


# ── (b) freshness ────────────────────────────────────────────────────────────────────────

def test_stale_publication_date_fails(tmp_path):
    packs = good_packs()
    packs["NO"]["facts"][0]["source"]["published_date"] = "2025-08-18"  # 366 days
    code, report, text = run(build(tmp_path, packs))
    assert code == 1
    assert "b-freshness" in checks_fired(report), text


def test_date_exactly_at_the_limit_passes(tmp_path):
    """365 days is inside the window; 366 is not. Pins the boundary against an off-by-one."""
    packs = good_packs()
    packs["NO"]["facts"][0]["source"]["published_date"] = "2025-08-19"
    code, _, text = run(build(tmp_path, packs))
    assert code == 0, text


def test_missing_publication_date_is_a_failure_not_a_skip(tmp_path):
    """The original TypeScript gate skipped nulls, so a pack with no dates reported PASS."""
    packs = good_packs()
    del packs["NO"]["facts"][0]["source"]["published_date"]
    code, report, text = run(build(tmp_path, packs))
    assert code == 1
    assert "b-freshness" in checks_fired(report), text


def test_future_publication_date_fails(tmp_path):
    packs = good_packs()
    packs["NO"]["facts"][0]["source"]["published_date"] = "2026-08-20"
    code, report, text = run(build(tmp_path, packs))
    assert code == 1
    assert "b-freshness" in checks_fired(report), text


def test_retrieved_before_published_fails(tmp_path):
    packs = good_packs()
    packs["NO"]["facts"][0]["source"]["retrieved_at"] = "2026-01-01"
    code, report, text = run(build(tmp_path, packs))
    assert code == 1
    assert "b-freshness" in checks_fired(report), text


# ── (c) completeness ─────────────────────────────────────────────────────────────────────

def test_edited_quote_breaks_the_hash(tmp_path):
    packs = good_packs()
    packs["NO"]["facts"][0]["source"]["evidence_quote"] = QUOTE_NO.replace("seks", "tolv")
    code, report, text = run(build(tmp_path, packs))
    assert code == 1
    assert "c-completeness" in checks_fired(report), text
    assert any("quote_sha256 mismatch" in v["message"] for v in report["violations"])


def test_stub_quote_fails(tmp_path):
    packs = good_packs()
    stub = "Stub content for https://lovdata.no/lov/1999-03-26-17/x3-5"
    packs["NO"]["facts"][0]["source"]["evidence_quote"] = stub
    packs["NO"]["facts"][0]["source"]["quote_sha256"] = sha(stub)
    code, report, text = run(build(tmp_path, packs))
    assert code == 1
    assert "c-completeness" in checks_fired(report), text


def test_placeholder_url_fails(tmp_path):
    packs = good_packs()
    packs["NO"]["facts"][0]["source"]["url"] = "https://example.com/deposit"
    code, report, text = run(build(tmp_path, packs))
    assert code == 1
    assert "c-completeness" in checks_fired(report), text


def test_missing_quote_fails(tmp_path):
    packs = good_packs()
    del packs["NO"]["facts"][0]["source"]["evidence_quote"]
    code, report, text = run(build(tmp_path, packs))
    assert code == 1
    assert "c-completeness" in checks_fired(report), text


def test_paraphrase_presented_as_capture_fails(tmp_path):
    """A 'quote' that is really our own summary is the failure a hash cannot catch."""
    packs = good_packs()
    fact = packs["NO"]["facts"][0]
    fact["source"]["evidence_quote"] = fact["fact_text"]
    fact["source"]["quote_sha256"] = sha(fact["fact_text"])
    code, report, text = run(build(tmp_path, packs))
    assert code == 1
    assert "c-completeness" in checks_fired(report), text


def test_preparation_item_may_not_grow_a_source(tmp_path):
    """The INVERSE check. These exist because no authority publishes them; attaching a page
    to one means attaching a citation to a claim that page does not make."""
    packs = good_packs()
    packs["NO"]["facts"].append({
        "fact_key": "bankid_friction", "topic": "registration-bankid",
        "kind": "preparation_item", "status": "staged", "pillar": "RESIDENCE",
        "title": "BankID friction", "fact_text": "Losing BankID cuts off online services.",
        "timing": "before departure", "non_obvious": True, "depends_on": [],
        "source": {"url": "https://lovdata.no/anything", "published_date": "2026-06-12"},
    })
    code, report, text = run(build(tmp_path, packs))
    assert code == 1
    assert "c-completeness" in checks_fired(report), text
    assert any("provenance must be ABSENT" in v["message"] for v in report["violations"])


def test_preparation_item_without_source_passes(tmp_path):
    packs = good_packs()
    packs["NO"]["facts"].append({
        "fact_key": "bankid_friction", "topic": "registration-bankid",
        "kind": "preparation_item", "status": "staged", "pillar": "RESIDENCE",
        "title": "BankID friction", "fact_text": "Losing BankID cuts off online services.",
        "timing": "before departure", "non_obvious": True, "depends_on": [],
    })
    code, _, text = run(build(tmp_path, packs))
    assert code == 0, text


# ── (a) official source and (a2) jurisdiction ────────────────────────────────────────────

def test_unofficial_host_fails(tmp_path):
    packs = good_packs()
    packs["NO"]["facts"][0]["source"]["url"] = "https://some-relocation-blog.com/norway-deposits"
    code, report, text = run(build(tmp_path, packs))
    assert code == 1
    assert {"a-official-source", "a2-jurisdiction-match"} & checks_fired(report), text


def test_semi_official_source_is_refused_at_active(tmp_path):
    """revenue.ie is good enough for `representative` and not for `active`. That distinction
    is the whole reason the two statuses exist."""
    packs = good_packs()
    packs["IE"]["facts"][0]["source"]["url"] = "https://www.revenue.ie/en/jobs/first-job.aspx"
    code, report, text = run(build(tmp_path, packs))
    assert code == 1
    assert "a-official-source" in checks_fired(report), text


def test_semi_official_source_is_accepted_at_representative(tmp_path):
    packs = good_packs()
    packs["IE"]["facts"][0]["status"] = "representative"
    packs["IE"]["facts"][0]["source"]["url"] = "https://www.revenue.ie/en/jobs/first-job.aspx"
    code, _, text = run(build(tmp_path, packs))
    assert code == 0, text


def test_fact_filed_under_the_wrong_jurisdiction_fails(tmp_path):
    """A gov.uk obligation in the Norway pack. This is the check that makes the
    origin/destination split structural rather than conventional."""
    packs = good_packs()
    packs["NO"]["facts"][0]["source"]["url"] = "https://www.gov.uk/tax-foreign-income/residence"
    code, report, text = run(build(tmp_path, packs))
    assert code == 1
    assert "a2-jurisdiction-match" in checks_fired(report), text


def test_unmappable_host_cannot_silently_pass(tmp_path):
    packs = good_packs()
    packs["NO"]["facts"][0]["source"]["url"] = "https://www.bundesregierung.de/norway"
    code, report, text = run(build(tmp_path, packs))
    assert code == 1
    assert "a2-jurisdiction-match" in checks_fired(report), text


# ── (a3) binding direction ───────────────────────────────────────────────────────────────

def test_destination_binding_citing_a_foreign_authority_fails(tmp_path):
    bindings = good_bindings()
    bindings["FR_NO"]["destination_facts"] = [{"ref": "IE:registration-pps:pps_number"}]
    code, report, text = run(build(tmp_path, bindings=bindings))
    assert code == 1
    assert "a3-binding-direction" in checks_fired(report), text


def test_eu_fact_may_be_bound_origin_side(tmp_path):
    packs = good_packs()
    packs["EU"] = {
        "jurisdiction": "EU", "catalog_country": None, "default_purposes": ["employment"],
        "facts": [{
            "fact_key": "a1_posting", "topic": "social_security-posting", "kind": "obligation",
            "status": "representative", "pillar": "SOCIAL_SECURITY", "title": "PD A1",
            "fact_text": "The PD A1 certifies home-country social security during a posting.",
            "timing": "before posting", "non_obvious": True,
            "source": {"url": "https://europa.eu/youreurope/business/posting-staff-abroad/",
                       "publisher_domain": "europa.eu", "published_date": "2026-03-12",
                       "retrieved_at": "2026-08-19", "evidence_quote": "The PD A1 confirms registration.",
                       "quote_sha256": sha("The PD A1 confirms registration.")},
            "last_verified_date": "2026-08-19", "depends_on": [], "pack_keys": ["NO-FR:ss-a1:a1"],
        }],
    }
    bindings = good_bindings()
    bindings["FR_NO"]["origin_facts"] = [{"ref": "EU:social_security-posting:a1_posting"}]
    code, _, text = run(build(tmp_path, packs, bindings))
    assert code == 0, text


def test_binding_reference_to_an_unknown_fact_fails(tmp_path):
    bindings = good_bindings()
    bindings["FR_NO"]["destination_facts"].append({"ref": "NO:housing-husleieloven:does_not_exist"})
    code, report, text = run(build(tmp_path, bindings=bindings))
    assert code == 1
    assert "d-consistency" in checks_fired(report), text


def test_invented_step_id_fails(tmp_path):
    bindings = good_bindings()
    bindings["FR_NO"]["destination_facts"] = [
        {"ref": "NO:housing-husleieloven:deposit_cap", "step_id": "NO_SUCH_STEP"}]
    code, report, text = run(build(tmp_path, bindings=bindings,
                                   pathways={"FR_NO": ["TRAVEL_TO_NO", "BANK_ACCOUNT"]}))
    assert code == 1
    assert "d-consistency" in checks_fired(report), text


def test_real_step_id_passes(tmp_path):
    bindings = good_bindings()
    bindings["FR_NO"]["destination_facts"] = [
        {"ref": "NO:housing-husleieloven:deposit_cap", "step_id": "BANK_ACCOUNT"}]
    code, _, text = run(build(tmp_path, bindings=bindings,
                              pathways={"FR_NO": ["TRAVEL_TO_NO", "BANK_ACCOUNT"]}))
    assert code == 0, text


# ── (d) consistency ──────────────────────────────────────────────────────────────────────

def test_promoted_fact_depending_on_a_staged_one_fails(tmp_path):
    packs = good_packs()
    packs["NO"]["facts"].append({
        "fact_key": "lease_terms", "topic": "housing-husleieloven", "kind": "obligation",
        "status": "staged", "pillar": "HOUSING", "title": "Lease terms",
        "fact_text": "Fixed-term leases run three years.", "timing": "before signing",
        "non_obvious": True, "depends_on": [],
    })
    packs["NO"]["facts"][0]["depends_on"] = ["NO:housing-husleieloven:lease_terms"]
    code, report, text = run(build(tmp_path, packs))
    assert code == 1
    assert "d-consistency" in checks_fired(report), text
    assert any("nobody has verified" in v["message"] for v in report["violations"])


def test_dependency_cycle_fails(tmp_path):
    packs = good_packs()
    packs["NO"]["facts"][0]["depends_on"] = ["IE:registration-pps:pps_number"]
    packs["IE"]["facts"][0]["depends_on"] = ["NO:housing-husleieloven:deposit_cap"]
    code, report, text = run(build(tmp_path, packs))
    assert code == 1
    assert "d-consistency" in checks_fired(report), text
    assert any("cycle" in v["message"] for v in report["violations"])


def test_same_page_with_different_quotes_is_allowed(tmp_path):
    """One gov.ie page legitimately backs two facts. Only an identical quote is duplication."""
    packs = good_packs()
    second = copy.deepcopy(packs["IE"]["facts"][0])
    second["fact_key"] = "pps_proof_of_address"
    other = "The document must show your name and address and not be older than 3 months."
    second["source"]["evidence_quote"] = other
    second["source"]["quote_sha256"] = sha(other)
    second["pack_keys"] = ["ES-IE:registration-pps:pps_proof_of_address"]
    packs["IE"]["facts"].append(second)
    code, _, text = run(build(tmp_path, packs))
    assert code == 0, text


def test_identical_url_and_quote_is_duplication(tmp_path):
    packs = good_packs()
    second = copy.deepcopy(packs["IE"]["facts"][0])
    second["fact_key"] = "pps_number_again"
    second["pack_keys"] = ["ES-IE:registration-pps:dupe"]
    packs["IE"]["facts"].append(second)
    code, report, text = run(build(tmp_path, packs))
    assert code == 1
    assert "d-consistency" in checks_fired(report), text
    assert any("one fact filed twice" in v["message"] for v in report["violations"])


def test_pack_key_claimed_twice_fails(tmp_path):
    packs = good_packs()
    packs["IE"]["facts"][0]["pack_keys"] = ["FR-NO:housing-deposit-cap:deposit_cap"]
    code, report, text = run(build(tmp_path, packs))
    assert code == 1
    assert "d-consistency" in checks_fired(report), text


# ── invalid runs are exit 2, never a pass ────────────────────────────────────────────────

def test_zero_facts_is_exit_2_not_a_pass(tmp_path):
    """'no violations' and 'nothing was examined' print identically. check_rls_coverage.py
    learned this the hard way."""
    packs = {"NO": {"jurisdiction": "NO", "catalog_country": "NORWAY", "facts": []}}
    with pytest.raises(guard.GateError):
        run(build(tmp_path, packs, bindings={}))


def test_unparseable_pack_is_exit_2(tmp_path):
    root = build(tmp_path)
    (root / "backend" / "seeds" / "facts" / "NO.yaml").write_text(
        "jurisdiction: 'NO'\nfacts:\n  - [unclosed\n", encoding="utf-8")
    with pytest.raises(guard.GateError):
        run(root)


def test_unknown_status_is_exit_2(tmp_path):
    packs = good_packs()
    packs["NO"]["facts"][0]["status"] = "published"
    with pytest.raises(guard.GateError):
        run(build(tmp_path, packs))


def test_missing_facts_directory_is_exit_2(tmp_path):
    with pytest.raises(guard.GateError):
        run(tmp_path / "nope")


# ── the allowlist is verified, not trusted ───────────────────────────────────────────────

def test_allowlist_suppresses_a_real_violation(tmp_path):
    packs = good_packs()
    packs["NO"]["facts"][0]["source"]["published_date"] = "2024-01-01"
    root = build(tmp_path, packs,
                 allowlist="NO:housing-husleieloven:deposit_cap  b-freshness  # under re-sourcing\n")
    code, report, text = run(root)
    assert code == 0, text
    assert len(report["suppressed"]) == 1


def test_allowlist_entry_that_no_longer_reproduces_fails(tmp_path):
    """The file must DRAIN. A stale entry is a blindfold nobody removed."""
    root = build(tmp_path,
                 allowlist="NO:housing-husleieloven:deposit_cap  b-freshness  # long fixed\n")
    code, report, text = run(root)
    assert code == 1, text
    assert report["stale_allowlist"], text


# ── the real repository state ────────────────────────────────────────────────────────────

def test_repository_packs_pass_the_gate():
    """The committed packs must pass at the run-date they were verified on."""
    result = subprocess.run(
        [sys.executable, str(GUARD), "--root", str(REPO), "--run-date", RUN_DATE],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_host_jurisdiction_table_agrees_with_parsers():
    """Guards the one place two host tables could silently drift apart."""
    from backend.imports.otto.parsers import classify_source
    assert guard._selftest_hosts(classify_source) == []
