"""C2-04 · Tests for the UDI/BAMF/dejure rule-change scraper (AIQ-555).

Covers every Validation Criterion from the Notion task:

1. A simulated rule change (v1 -> v2 fixture HTML) produces a
   rce.rule_change_proposals row with a non-empty diff_summary.
2. Re-running the scraper on unchanged HTML is a no-op (no duplicate rows).
3. Each proposal records captured_at + source_url + a sha256 hash.
4. SEC-003 hard gate on the new table — verified statically against the
   migration file (RLS + policy + REVOKE FROM anon).
5. The 2026 BGBl thresholds page and the German Blue Card §18g page are both
   seeded sources.
6. The UDI 'viktige meldinger' feed parses the September 2025 salary-adjustment
   announcement correctly (archived fixture).

PLUS the load-bearing guarantee: the scraper NEVER auto-promotes. Every proposal
it writes is status='pending'; there is no code path to 'promoted'/'rejected'.

Fully hermetic and offline: HTTP is a stub fetcher reading fixture files, the
store is in-memory, and no LLM is called (deterministic diff summary).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.relopass.jobs import (
    RULE_SCRAPER_SOURCES,
    InMemoryProposalStore,
    RuleScraper,
    RuleSource,
    normalize_text,
    sha256_hex,
)
from backend.relopass.jobs.rule_scraper import PENDING, RuleChangeProposal

FIXTURES = Path(__file__).parent / "fixtures" / "rule_scraper"


# ─────────────────────────────────────────────────────────────────────────────
# Stub fetcher — maps a URL to fixture HTML. NEVER hits the network.
# ─────────────────────────────────────────────────────────────────────────────


class StubFetcher:
    def __init__(self, url_to_fixture: dict[str, str]) -> None:
        self._map = url_to_fixture
        self.calls: list[str] = []

    def __call__(self, url: str) -> str:
        self.calls.append(url)
        fixture = self._map.get(url)
        if fixture is None:
            raise RuntimeError(f"no fixture mapped for {url} (network is forbidden in tests)")
        return (FIXTURES / fixture).read_text(encoding="utf-8")


UDI_URL = "https://www.udi.no/en/important-messages/"
DEJURE_18G_URL = "https://dejure.org/gesetze/AufenthG/18g.html"

UDI_SOURCE = RuleSource(
    source_id="UDI_VIKTIGE_MELDINGER",
    url=UDI_URL,
    rule_ids=("NO_UTL_SKILLED_WORKER_SALARY",),
)


# ─────────────────────────────────────────────────────────────────────────────
# 1 + 3. A simulated change produces a proposal with non-empty diff_summary,
#         captured_at, source_url, and a sha256 hash.
# ─────────────────────────────────────────────────────────────────────────────


def test_simulated_change_creates_pending_proposal_with_diff_summary():
    store = InMemoryProposalStore()
    # Baseline = v1 normalised text (what the last RuleVersion.body source captured).
    v1_text = normalize_text((FIXTURES / "udi_viktige_meldinger_v1.html").read_text())
    store.set_baseline("NO_UTL_SKILLED_WORKER_SALARY", v1_text)

    # Live page now serves v2.
    fetcher = StubFetcher({UDI_URL: "udi_viktige_meldinger_v2.html"})
    scraper = RuleScraper(fetcher=fetcher, store=store, sources=[UDI_SOURCE])

    result = scraper.run()

    assert result.proposals_created == 1
    assert len(store.proposals) == 1
    p = store.proposals[0]

    # Criterion 1: non-empty diff_summary.
    assert p.diff_summary
    assert p.diff_summary != "No change detected."
    # Criterion 3: captured_at + source_url + sha256 hash.
    assert p.source_url == UDI_URL
    assert p.captured_at is not None
    assert len(p.captured_html_hash) == 64  # sha256 hex
    assert p.captured_html_hash == sha256_hex(p.captured_text)
    # The load-bearing invariant: it lands pending, never promoted.
    assert p.status == PENDING


# ─────────────────────────────────────────────────────────────────────────────
# 6. UDI September 2025 salary-adjustment announcement is parsed (the new
#    thresholds appear in the captured text, the old ones don't).
# ─────────────────────────────────────────────────────────────────────────────


def test_udi_september_2025_salary_announcement_parsed():
    store = InMemoryProposalStore()
    v1_text = normalize_text((FIXTURES / "udi_viktige_meldinger_v1.html").read_text())
    store.set_baseline("NO_UTL_SKILLED_WORKER_SALARY", v1_text)

    fetcher = StubFetcher({UDI_URL: "udi_viktige_meldinger_v2.html"})
    scraper = RuleScraper(fetcher=fetcher, store=store, sources=[UDI_SOURCE])
    scraper.run()

    captured = store.proposals[0].captured_text
    assert "1 September 2025" in captured
    assert "472 300" in captured  # new bachelor threshold
    assert "493 500" in captured  # new master threshold
    assert "448 900" not in captured  # the superseded 2024 figure is gone


# ─────────────────────────────────────────────────────────────────────────────
# 2. Re-running on UNCHANGED HTML is a no-op.
# ─────────────────────────────────────────────────────────────────────────────


def test_unchanged_page_is_a_noop():
    store = InMemoryProposalStore()
    v1_text = normalize_text((FIXTURES / "udi_viktige_meldinger_v1.html").read_text())
    store.set_baseline("NO_UTL_SKILLED_WORKER_SALARY", v1_text)

    # Live page still serves v1 — identical to the baseline.
    fetcher = StubFetcher({UDI_URL: "udi_viktige_meldinger_v1.html"})
    scraper = RuleScraper(fetcher=fetcher, store=store, sources=[UDI_SOURCE])

    result = scraper.run()

    assert result.proposals_created == 0
    assert result.pages_unchanged == 1
    assert store.proposals == []


def test_cosmetic_only_change_is_a_noop():
    """Whitespace/comment churn must not raise a false proposal — the hash is
    over the normalised text, not raw HTML."""
    store = InMemoryProposalStore()
    raw_v1 = (FIXTURES / "udi_viktige_meldinger_v1.html").read_text()
    store.set_baseline("NO_UTL_SKILLED_WORKER_SALARY", normalize_text(raw_v1))

    # Same visible text, different indentation + an extra comment.
    cosmetic = raw_v1.replace("<main>", "<main>\n\n   <!-- reflowed -->   ")
    fetcher = StubFetcher({UDI_URL: "_inline_"})
    fetcher._map[UDI_URL] = "udi_viktige_meldinger_v1.html"  # keep file map sane

    # Patch fetcher to return the cosmetic variant directly.
    scraper = RuleScraper(fetcher=lambda url: cosmetic, store=store, sources=[UDI_SOURCE])
    result = scraper.run()

    assert result.proposals_created == 0
    assert result.pages_unchanged == 1


def test_rerun_after_proposal_does_not_duplicate():
    """Criterion 2 continued: a second run before the human resolves the
    proposal must not create a duplicate (UNIQUE rule_id, captured_html_hash)."""
    store = InMemoryProposalStore()
    v1_text = normalize_text((FIXTURES / "udi_viktige_meldinger_v1.html").read_text())
    store.set_baseline("NO_UTL_SKILLED_WORKER_SALARY", v1_text)

    fetcher = StubFetcher({UDI_URL: "udi_viktige_meldinger_v2.html"})
    scraper = RuleScraper(fetcher=fetcher, store=store, sources=[UDI_SOURCE])

    first = scraper.run()
    assert first.proposals_created == 1

    # Baseline NOT advanced (human hasn't promoted yet); page still v2.
    second = scraper.run()
    assert second.proposals_created == 0
    assert second.duplicates_skipped == 1
    assert len(store.proposals) == 1  # still exactly one row


# ─────────────────────────────────────────────────────────────────────────────
# First-seen source (no baseline) raises a pending proposal for triage.
# ─────────────────────────────────────────────────────────────────────────────


def test_first_seen_source_raises_pending_proposal():
    store = InMemoryProposalStore()  # no baseline seeded
    fetcher = StubFetcher({DEJURE_18G_URL: "dejure_aufenthg_18g_v2.html"})
    source = RuleSource(
        source_id="DEJURE_AUFENTHG_18G",
        url=DEJURE_18G_URL,
        rule_ids=("DE_AUFENTHG_18G",),
    )
    scraper = RuleScraper(fetcher=fetcher, store=store, sources=[source])

    result = scraper.run()
    assert result.proposals_created == 1
    assert store.proposals[0].status == PENDING
    assert store.proposals[0].diff_summary


# ─────────────────────────────────────────────────────────────────────────────
# NO AUTO-PROMOTION — the load-bearing guarantee.
# ─────────────────────────────────────────────────────────────────────────────


def test_scraper_never_writes_non_pending_status():
    store = InMemoryProposalStore()
    store.set_baseline(
        "DE_AUFENTHG_18G",
        normalize_text((FIXTURES / "dejure_aufenthg_18g_v1.html").read_text()),
    )
    fetcher = StubFetcher({DEJURE_18G_URL: "dejure_aufenthg_18g_v2.html"})
    source = RuleSource("DEJURE_AUFENTHG_18G", DEJURE_18G_URL, ("DE_AUFENTHG_18G",))
    scraper = RuleScraper(fetcher=fetcher, store=store, sources=[source])

    scraper.run()

    # Every proposal the scraper produced is pending — never promoted/rejected.
    assert all(p.status == "pending" for p in store.proposals)
    assert not any(p.status in ("promoted", "rejected") for p in store.proposals)


def test_proposal_construction_rejects_non_pending_status():
    """Defence-in-depth: even constructing a non-pending proposal from the
    scraper path is forbidden, so auto-promotion can't sneak in via a bug."""
    with pytest.raises(ValueError):
        RuleChangeProposal(
            source_id="X",
            source_url="https://x",
            captured_html_hash="h",
            captured_text="t",
            diff_summary="s",
            status="promoted",
        )


# ─────────────────────────────────────────────────────────────────────────────
# 5. Seeded source list contains the BGBl thresholds page and the §18g page.
# ─────────────────────────────────────────────────────────────────────────────


def test_seeded_sources_include_bgbl_and_blue_card_18g():
    source_ids = {s.source_id for s in RULE_SCRAPER_SOURCES}
    assert "BMI_THRESHOLD_BULLETIN" in source_ids  # 2026 BGBl thresholds
    assert "DEJURE_AUFENTHG_18G" in source_ids     # German Blue Card §18g
    assert "BAMF_BLUE_CARD" in source_ids
    assert "UDI_VIKTIGE_MELDINGER" in source_ids
    # All six Cohort-2 sources present.
    assert len(RULE_SCRAPER_SOURCES) == 6
    # Every source carries at least one rule_id and an https URL.
    for s in RULE_SCRAPER_SOURCES:
        assert s.rule_ids
        assert s.url.startswith("https://")


# ─────────────────────────────────────────────────────────────────────────────
# 4. SEC-003 hard gate — verified statically against the migration file.
# ─────────────────────────────────────────────────────────────────────────────


def test_migration_has_rls_policy_and_revoke_anon():
    migration = (
        Path(__file__).parents[2]
        / "supabase"
        / "migrations"
        / "20260604000000_rce_rule_change_proposals.sql"
    )
    sql = migration.read_text(encoding="utf-8")
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "CREATE POLICY" in sql
    assert "REVOKE ALL ON rce.rule_change_proposals FROM anon" in sql
    # Admin-only / service-role scoping (not a permissive USING (true)).
    assert "admin_allowlist" in sql
    assert "auth.role() = 'service_role'" in sql
    # No-auto-promotion contract is documented in the schema CHECK + comment.
    assert "status IN ('pending','promoted','rejected')" in sql
    assert "DEFAULT 'pending'" in sql
    # Daily 03:00 UTC cron registration present.
    assert "rce-rule-scraper-daily" in sql
    assert "0 3 * * *" in sql


# ─────────────────────────────────────────────────────────────────────────────
# Multi-source / multi-rule run sanity (and offline-only confirmation).
# ─────────────────────────────────────────────────────────────────────────────


def test_full_run_is_offline_and_mixed():
    store = InMemoryProposalStore()
    # UDI unchanged, dejure changed.
    store.set_baseline(
        "NO_UTL_SKILLED_WORKER_SALARY",
        normalize_text((FIXTURES / "udi_viktige_meldinger_v1.html").read_text()),
    )
    store.set_baseline(
        "DE_AUFENTHG_18G",
        normalize_text((FIXTURES / "dejure_aufenthg_18g_v1.html").read_text()),
    )
    fetcher = StubFetcher(
        {
            UDI_URL: "udi_viktige_meldinger_v1.html",       # unchanged
            DEJURE_18G_URL: "dejure_aufenthg_18g_v2.html",  # changed
        }
    )
    sources = [
        RuleSource("UDI_VIKTIGE_MELDINGER", UDI_URL, ("NO_UTL_SKILLED_WORKER_SALARY",)),
        RuleSource("DEJURE_AUFENTHG_18G", DEJURE_18G_URL, ("DE_AUFENTHG_18G",)),
    ]
    scraper = RuleScraper(fetcher=fetcher, store=store, sources=sources)
    result = scraper.run()

    assert result.proposals_created == 1
    assert result.pages_unchanged == 1
    assert result.fetch_errors == 0
    # Confirm only the two fixture URLs were ever fetched (no live calls).
    assert set(fetcher.calls) == {UDI_URL, DEJURE_18G_URL}
