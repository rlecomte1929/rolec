"""Unit tests for the corridor fact loader's pure half. No database.

The write loop is a thin wrapper; everything that decides WHAT gets written lives in
`build_payloads`, so that is what is pinned here — including the two things that would do
real damage if they regressed: citing bare URLs instead of source-record ids, and writing a
fact whose title lands beside an approved row instead of updating it.
"""
from __future__ import annotations

import json

import pytest

from backend.scripts.seed_corridor_facts import (
    HOLD,
    build_payloads,
    content_hash_for,
    load_destination_bound,
    load_packs,
    overlap_hint,
    quote_digest,
    requirement_id_for,
    significant_tokens,
    source_id_for,
)

ROOT = "."


@pytest.fixture(scope="module")
def plan():
    facts = load_packs(ROOT)
    return facts, build_payloads(facts, load_destination_bound(ROOT))


# ── the shape of the load ────────────────────────────────────────────────────────────────

def test_only_destination_bound_facts_become_requirements(plan):
    """requirement_items.country_code is the DESTINATION.

    An obligation a Norwegian authority imposes on someone LEAVING Norway is not a French
    requirement, so origin-side and EU-level facts must never produce a row here.
    """
    facts, p = plan
    bound = load_destination_bound(ROOT)
    produced = {r["_key"] for r in p["requirements"]}
    assert produced <= set(bound), "a fact with no destination binding produced a row"
    # the EU-level A1 fact is bound origin-side only, and must not appear
    assert not any(k.startswith("EU:") for k in produced)


def test_every_promoted_fact_gets_a_source_record_even_when_origin_side(plan):
    """Origin-side evidence still has to be addressable — it just is not a requirement."""
    facts, p = plan
    promoted = [f for f in facts.values()
                if f.get("kind") != "preparation_item" and f["status"] in ("active", "representative")]
    assert len(promoted) == 21
    # 21 facts, de-duplicated on (url, quote); no two share BOTH
    assert len(p["sources"]) == 21


def test_preparation_items_are_never_written(plan):
    """They carry no source at all — writing one would attach a citation to a claim no
    authority makes."""
    facts, p = plan
    prep = [k for k, f in facts.items() if f.get("kind") == "preparation_item"]
    assert len(prep) == 4
    assert set(prep) <= set(p["skipped_unpromoted"])
    assert not any(r["_key"] in prep for r in p["requirements"])


# ── the two failures that would matter ───────────────────────────────────────────────────

def test_citations_are_source_record_ids_never_urls(plan):
    """THE POINT OF THIS LOADER.

    seed_requirements.py writes bare URLs; requirements_builder resolves citations against a
    source_records map and silently drops what does not resolve — measured at 90 items with
    citations, 27 resolving. A URL here would reproduce that bug exactly.
    """
    _, p = plan
    ids = {s["id"] for s in p["sources"]}
    for requirement in p["requirements"]:
        citations = json.loads(requirement["citations_json"])
        assert citations, f"{requirement['title']} has no citation"
        for citation in citations:
            assert not citation.startswith("http"), f"bare URL cited by {requirement['title']}"
            assert citation in ids, f"citation {citation} resolves to no source record"


def test_held_facts_are_not_written_and_are_reported(plan):
    """Ireland already holds an approved row conflating PPSN and emergency tax.

    The natural key has no unique index behind it, so these titles would INSERT beside that
    row rather than update it, and there is no delete path to undo it.
    """
    _, p = plan
    held_keys = {h["key"] for h in p["held"]}
    assert held_keys == set(HOLD)
    assert not any(r["_key"] in held_keys for r in p["requirements"])
    for entry in p["held"]:
        assert entry["reason"], "a held fact must say why"


def test_everything_lands_pending(plan):
    """review_status defaults to 'approved' and requirements_builder serves only approved
    rows, so an omitted column publishes unreviewed facts the moment it applies."""
    _, p = plan
    assert {r["review_status"] for r in p["requirements"]} == {"pending"}


def test_loader_never_produces_expert_verified(plan):
    """Raising a requirement to verified is a human act (otto/executor.py)."""
    _, p = plan
    assert "verified" not in {r["verification_status"] for r in p["requirements"]}
    assert {r["verification_status"] for r in p["requirements"]} <= {
        "corpus_grounded", "representative"}


def test_non_obvious_and_timing_are_written(plan):
    """The columns 20261103000000 added that no seeder ever populated."""
    _, p = plan
    assert any(r["non_obvious"] for r in p["requirements"])
    assert any(r["timing"] for r in p["requirements"])


def test_last_verified_is_the_facts_own_date_not_now(plan):
    """When a human checked the source is a property of the evidence, not of this run."""
    _, p = plan
    assert {r["last_verified_at"].date().isoformat() for r in p["requirements"]} == {"2026-08-19"}


# ── identity and de-duplication ──────────────────────────────────────────────────────────

def test_requirement_id_matches_the_yaml_seeder(plan):
    """Same namespace and natural key as seed_requirements.py, so the two writers converge on
    one row instead of racing. Otto's promote() imports _SEED_NS for the same reason."""
    _, p = plan
    for requirement in p["requirements"]:
        assert requirement["id"] == requirement_id_for(
            requirement["country_code"], requirement["purpose"], requirement["title"])


def test_content_hash_keys_on_url_AND_quote(plan):
    """source_records.content_hash is UNIQUE, and four of these pages back two facts each
    with DIFFERENT quotes. A url-only hash collides and drops half the evidence."""
    url = "https://www.gov.ie/en/services/get-a-pps-number/"
    assert content_hash_for(url, quote_digest("first")) != content_hash_for(url, quote_digest("second"))
    _, p = plan
    hashes = [s["content_hash"] for s in p["sources"]]
    assert len(hashes) == len(set(hashes)), "two source records share a content_hash"


def test_one_page_two_quotes_yields_two_source_records(plan):
    """The inverse of de-duplication, and the case that actually occurs."""
    _, p = plan
    by_url = {}
    for source in p["sources"]:
        by_url.setdefault(source["url"], []).append(source)
    multi = {u: v for u, v in by_url.items() if len(v) > 1}
    assert multi, "expected at least one page backing two distinct quotes"
    for sources in multi.values():
        assert len({s["snippet"] for s in sources}) == len(sources)


def test_identical_url_and_quote_share_one_source_record():
    assert source_id_for("https://x.example/a", "d") == source_id_for("https://x.example/a", "d")
    assert source_id_for("https://x.example/a", "d") != source_id_for("https://x.example/a", "e")


# ── the hint is a hint ───────────────────────────────────────────────────────────────────

def test_overlap_hint_surfaces_the_known_collision():
    live = ["PPSN (Personal Public Service Number) — application and emergency tax"]
    assert overlap_hint("A PPS number is required for employment and tax administration", live)
    assert overlap_hint("Emergency tax applies until the job is registered, rising to 40%", live)


def test_overlap_hint_is_documented_as_insufficient():
    """It MISSES the third Ireland collision. Pinned so nobody promotes it to a gate.

    "Proof of address for a PPS application ..." shares only `application` with the row it
    duplicates. The loader's real protection is the HOLD list plus printing every live title;
    if this ever starts passing, the docstring and the report both need revisiting.
    """
    live = ["PPSN (Personal Public Service Number) — application and emergency tax"]
    assert overlap_hint(
        "Proof of address for a PPS application must be under three months old", live) == []


def test_significant_tokens_drops_noise():
    assert significant_tokens("The employer must file the DPAE") == {"employer", "file", "dpae"}
