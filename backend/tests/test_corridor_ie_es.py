"""IE→ES (Dublin→Madrid) corridor — data integrity, load shape, and registry wiring.

The 25 requirement records are the corridor's asset. These tests pin the properties that
make them trustworthy rather than merely present: that the committed file is byte-identical
to the batch its manifest describes, that every record is source-attributed, that the two
records whose claim outruns their source stay flagged, and — the one that would hurt most if
it broke — that nothing lands in a state the deterministic engine will serve before a human
has approved it.

No database required. The load is generated from the NDJSON by
`scripts/gen_ie_es_corridor_load.py`, so asserting against the generated SQL asserts against
what production will actually receive.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "corridors" / "IE_ES" / "data"
NDJSON = DATA / "ie_es_requirement_facts.ndjson"
MANIFEST = DATA / "manifest.json"
REPORT = DATA / "validation_report.json"
MIGRATION = REPO / "supabase" / "migrations" / "20261107000000_ie_es_requirement_items.sql"
CORRIDOR_YAML = REPO / "corridors" / "IE_ES" / "corridor.yaml"
PATHWAY_YAML = REPO / "corridors" / "IE_ES" / "pathways" / "ES_FREEMOVE_2026" / "v1.yaml"

ALLOWED_DOMAINS = {
    "registration", "tax", "social_security", "healthcare", "housing", "immigration", "other",
}
EXPECTED_DOMAINS = {
    "registration": 8, "tax": 4, "social_security": 4,
    "healthcare": 3, "housing": 3, "immigration": 1, "other": 2,
}
#: The platform's canonical pillar vocabulary — the values requirement_items actually holds.
CANONICAL_PILLARS = {
    "RESIDENCE", "IDENTITY", "EMPLOYMENT", "HOUSING", "SOCIAL_SECURITY", "TIMELINE", "HEALTHCARE",
}
TREATY_RECORDS = {"tax_residency_183_days", "tax_ie_es_double_taxation"}


@pytest.fixture(scope="module")
def records():
    return [json.loads(line) for line in NDJSON.read_text().splitlines() if line.strip()]


@pytest.fixture(scope="module")
def manifest():
    return json.loads(MANIFEST.read_text())


@pytest.fixture(scope="module")
def migration_sql():
    return MIGRATION.read_text()


# ---------------------------------------------------------------------------
# Provenance — is this the batch that was verified?
# ---------------------------------------------------------------------------


def test_the_committed_file_is_the_batch_the_manifest_describes(manifest):
    """The whole trust chain hangs off this. If the bytes drift from the sha256 the batch
    was verified under, every downstream claim about lawyer review and sourcing is about a
    different file."""
    actual = hashlib.sha256(NDJSON.read_bytes()).hexdigest()
    assert actual == manifest["sha256"]
    assert NDJSON.stat().st_size == manifest["file_bytes"]


def test_the_manifest_describes_this_corridor(manifest):
    assert manifest["corridor"] == "IE-ES"
    assert manifest["origin_country_code"] == "IE"
    assert manifest["destination_country_code"] == "ES"
    assert manifest["record_count"] == 25


# ---------------------------------------------------------------------------
# Structural gate.
# ---------------------------------------------------------------------------


def test_there_are_exactly_twenty_five_records(records):
    assert len(records) == 25


def test_every_record_is_source_attributed(records):
    """A requirement decides whether someone legally has the right to work. One without a
    source is not a requirement, it is a rumour."""
    unsourced = [r["fact_uid"] for r in records if not r.get("source_url")]
    assert unsourced == []


def test_every_record_has_fact_text(records):
    assert [r["fact_uid"] for r in records if not r.get("fact_text")] == []


def test_the_domain_profile_matches_the_batch(records):
    assert dict(Counter(r["domain_area"] for r in records)) == EXPECTED_DOMAINS


def test_every_domain_is_in_the_enum(records):
    assert {r["domain_area"] for r in records} <= ALLOWED_DOMAINS


def test_the_corridor_is_consistent_on_every_record(records):
    assert {r["corridor"] for r in records} == {"IE-ES"}
    assert {r["origin_country_code"] for r in records} == {"IE"}
    assert {r["destination_country_code"] for r in records} == {"ES"}


def test_fact_uids_are_unique_and_well_formed(records):
    uids = [r["fact_uid"] for r in records]
    assert len(set(uids)) == len(uids)
    for r in records:
        assert r["fact_uid"] == f"ES:IE-ES:{r['topic_key']}"


# ---------------------------------------------------------------------------
# The moat metric.
# ---------------------------------------------------------------------------


def test_fifteen_records_are_flagged_non_obvious(records):
    assert sum(1 for r in records if r.get("non_obvious")) == 15


def test_every_non_obvious_record_explains_why(records):
    """The note IS the relief moment. A non_obvious flag with no explanation cannot be
    surfaced to a user, so it cannot be measured either."""
    missing = [r["fact_uid"] for r in records if r.get("non_obvious") and not r.get("non_obvious_note")]
    assert missing == []


def test_the_non_obvious_note_reaches_the_served_description(migration_sql, records):
    """Carried into requirement_items.description, because that is the field the roadmap
    renders. Left only on the NDJSON it would be invisible to the user and to the eval."""
    assert "Why this is easy to miss:" in migration_sql
    noted = sum(1 for r in records if r.get("non_obvious"))
    assert migration_sql.count("Why this is easy to miss:") == noted


# ---------------------------------------------------------------------------
# Trust gate.
# ---------------------------------------------------------------------------


def test_the_two_treaty_records_stay_flagged_for_a_lawyer(migration_sql):
    """Both claim something about the Ireland–Spain treaty tie-breaker while citing the
    AEAT residency page, not the treaty. The gap is real; flagging it is how the
    verification gate stays honest instead of laundering an unsourced claim as settled."""
    assert migration_sql.count("needs_lawyer_review") == 2
    for topic in TREATY_RECORDS:
        assert f"ES:IE-ES:{topic}" in migration_sql


def test_nothing_lands_pre_approved(migration_sql):
    """requirement_items.review_status DEFAULTS to 'approved' and requirements_builder
    serves only approved rows — so an INSERT that forgot this column would publish 25
    unreviewed REPRESENTATIVE facts to real users the moment it applied."""
    assert "'pending'" in migration_sql
    assert migration_sql.count("review_status") >= 1
    # And a rebuild must never silently re-open a row a human has since approved.
    assert "review_status = EXCLUDED.review_status" not in migration_sql


def test_the_load_is_marked_representative_not_verified(migration_sql):
    assert "'representative'" in migration_sql
    assert "'verified'" not in migration_sql


# ---------------------------------------------------------------------------
# Load shape.
# ---------------------------------------------------------------------------


def test_the_load_targets_requirement_items_not_requirement_facts(migration_sql):
    """requirement_facts has no fact_uid and two NOT NULL uuid FKs the NDJSON cannot
    supply; requirement_items is what the deterministic engine reads."""
    assert "INSERT INTO public.requirement_items" in migration_sql
    assert "INSERT INTO public.requirement_facts" not in migration_sql


def test_the_upsert_key_is_the_fact_uid(migration_sql):
    assert "ON CONFLICT (id) DO UPDATE" in migration_sql
    assert migration_sql.count("'ES:IE-ES:") >= 25


def test_every_record_appears_in_the_load(records, migration_sql):
    for r in records:
        assert f"'{r['fact_uid']}'" in migration_sql


def test_every_pillar_is_in_the_canonical_vocabulary(migration_sql):
    used = set(re.findall(r"'(RESIDENCE|IDENTITY|EMPLOYMENT|HOUSING|SOCIAL_SECURITY|TIMELINE|HEALTHCARE)'", migration_sql))
    assert used
    assert used <= CANONICAL_PILLARS


def test_free_movement_steps_are_scoped_to_eu_nationals(migration_sql):
    """A returning Spanish national holds a DNI and cannot be issued a certificado de
    registro. Scoping the registration items prevents the engine serving them a document
    that does not exist for them."""
    assert '["EU_EEA"]' in migration_sql


# ---------------------------------------------------------------------------
# Registry wiring.
# ---------------------------------------------------------------------------


def test_the_corridor_is_registered():
    profile = yaml.safe_load(CORRIDOR_YAML.read_text())["corridor"]
    assert profile["id"] == "IE_ES"
    assert profile["origin_iso"] == "IE"
    assert profile["destination_iso"] == "ES"
    assert "IE-ES" in profile["aliases"]


def test_the_pathway_models_free_movement_not_a_permit():
    """IE→ES is an EU free mover. If this ever grows a salary floor or a visa gate, it has
    been copied from the wrong corridor."""
    agent = yaml.safe_load(PATHWAY_YAML.read_text())["corridor_agent"]
    assert agent["corridor_id"] == "IE_ES_2026"
    assert agent["origin_country_iso3"] == "IRL"
    assert agent["destination_country_iso3"] == "ESP"
    assert agent["salary_thresholds_eur"] == {}


def test_the_step_graph_encodes_the_padron_before_extranjeria_dependency():
    """The padrón certificate is an input to the Extranjería appointment and neither page
    says so. Modelling the edge is what turns a week-7 ambush into a week-1 warning."""
    steps = {s["step_id"]: s for s in yaml.safe_load(PATHWAY_YAML.read_text())["corridor_agent"]["step_graph"]}
    assert "EMPADRONAMIENTO" in steps["NIE_CERTIFICADO_REGISTRO"]["prerequisite_step_ids"]


def test_housing_depends_on_the_nie():
    """The NIE↔lease↔padrón circularity is the most-reported IE→ES surprise."""
    steps = {s["step_id"]: s for s in yaml.safe_load(PATHWAY_YAML.read_text())["corridor_agent"]["step_graph"]}
    assert "NIE_CERTIFICADO_REGISTRO" in steps["HOUSING_LEASE"]["prerequisite_step_ids"]


# ---------------------------------------------------------------------------
# The report is the proof-of-verification artifact.
# ---------------------------------------------------------------------------


def test_the_validation_report_is_committed_and_green():
    report = json.loads(REPORT.read_text())
    assert report["all_pass"] is True
    assert report["record_count"] == 25
    assert report["non_obvious_count"] == 15
    assert sorted(report["needs_lawyer_review"]) == sorted(TREATY_RECORDS)
    assert report["target_table"] == "public.requirement_items"
    failed = [g["gate"] for g in report["gates"] if not g["pass"]]
    assert failed == []
