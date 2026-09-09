"""Knowledge-layer scorecard bars — FR→NO seed is pending-only, so not ready."""
from __future__ import annotations

from types import SimpleNamespace

from backend.app.services.knowledge_layer_scorecard import (
    NOT_READY_CITATIONS,
    NOT_READY_EMPTY,
    NOT_READY_PILLARS,
    score_catalog,
    score_requirement_rows,
)


def test_empty_catalog_is_not_ready():
    card = score_catalog(
        approved_count=0,
        pending_count=4,
        citation_resolved_approved=0,
        pillars=[],
    )
    assert card.catalog_ready is False
    assert card.not_ready_reason == NOT_READY_EMPTY
    assert card.citation_resolve_pct == 0.0


def test_cited_multi_pillar_catalog_is_ready():
    card = score_catalog(
        approved_count=4,
        pending_count=1,
        citation_resolved_approved=3,
        pillars=("IDENTITY", "RESIDENCE", "HOUSING"),
    )
    assert card.catalog_ready is True
    assert card.not_ready_reason is None
    assert card.citation_resolve_pct == 75.0


def test_uncited_approved_rows_fail_the_citation_bar():
    card = score_catalog(
        approved_count=4,
        pending_count=0,
        citation_resolved_approved=1,
        pillars=("IDENTITY", "RESIDENCE"),
    )
    assert card.catalog_ready is False
    assert card.not_ready_reason == NOT_READY_CITATIONS


def test_single_pillar_is_not_a_dossier():
    card = score_catalog(
        approved_count=3,
        pending_count=0,
        citation_resolved_approved=3,
        pillars=("RESIDENCE",),
    )
    assert card.catalog_ready is False
    assert card.not_ready_reason == NOT_READY_PILLARS


def test_score_rows_uses_employee_citation_resolver():
    record = SimpleNamespace(
        id="src-1",
        url="https://www.udi.no/en/",
        title="UDI",
        publisher_domain="www.udi.no",
        retrieved_at=None,
        snippet=None,
    )
    rows = [
        SimpleNamespace(
            review_status="approved",
            pillar="RESIDENCE",
            citations_json='["src-1"]',
            reviewed_at=None,
        ),
        SimpleNamespace(
            review_status="approved",
            pillar="IDENTITY",
            citations_json='["https://www.skatteetaten.no/en/"]',
            reviewed_at=None,
        ),
        SimpleNamespace(
            review_status="pending",
            pillar="HOUSING",
            citations_json="[]",
            reviewed_at=None,
        ),
    ]
    card = score_requirement_rows(rows, {"src-1": record})
    assert card.approved_count == 2
    assert card.pending_count == 1
    assert card.citation_resolved_approved == 2
    assert card.catalog_ready is True
