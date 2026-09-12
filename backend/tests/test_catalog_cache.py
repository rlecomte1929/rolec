"""RP-MEM-001 / RP-MEM-003 — in-process catalog cache + write invalidation."""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from backend.app.services import requirement_catalog_cache as cache


def setup_function():
    cache.reset_for_tests()


def _row(country="NORWAY", title="Tax card", purpose="employment", **over):
    base = dict(
        id=f"id-{title}",
        country_code=country,
        purpose=purpose,
        pillar="RESIDENCE",
        title=title,
        description="orig",
        severity="WARN",
        owner="EMPLOYEE",
        required_fields_json="[]",
        citations_json="[]",
        applies_to_assignment_types_json=None,
        applies_to_nationality_classes_json=None,
        applies_to_regimes_json=None,
        verification_status="corpus_grounded",
        review_status="approved",
        attestation_status=None,
        attested_by=None,
        attested_at=None,
        non_obvious=False,
        timing=None,
        last_verified_at=datetime(2026, 8, 12),
    )
    base.update(over)
    return SimpleNamespace(**base)


def test_second_lookup_does_not_reload():
    calls = []

    def loader():
        calls.append(1)
        return [_row()]

    first = cache.get_catalog_rows("NORWAY", "employment", loader, now=1_000.0)
    second = cache.get_catalog_rows("NORWAY", "employment", loader, now=1_001.0)
    assert len(calls) == 1
    assert first[0].title == second[0].title == "Tax card"


def test_ttl_expiry_recompiles():
    calls = []

    def loader():
        calls.append(1)
        return [_row()]

    cache.get_catalog_rows("NORWAY", "employment", loader, now=1_000.0, ttl_seconds=10)
    cache.get_catalog_rows("NORWAY", "employment", loader, now=1_011.0, ttl_seconds=10)
    assert len(calls) == 2


def test_invalidate_country_is_a_miss_and_other_country_untouched():
    no_calls = []
    ie_calls = []

    cache.get_catalog_rows(
        "NORWAY", "employment", lambda: no_calls.append(1) or [_row(title="NO")], now=1_000.0
    )
    cache.get_catalog_rows(
        "IRELAND", "employment", lambda: ie_calls.append(1) or [_row(country="IRELAND", title="IE")], now=1_000.0
    )
    cache.invalidate_country("NORWAY", item_id="id-NO", reason="test")
    again_no = cache.get_catalog_rows(
        "NORWAY",
        "employment",
        lambda: no_calls.append(1) or [_row(title="NO-new", description="changed")],
        now=1_001.0,
    )
    again_ie = cache.get_catalog_rows(
        "IRELAND", "employment", lambda: ie_calls.append(1) or [_row(country="IRELAND", title="IE")], now=1_001.0
    )
    assert no_calls == [1, 1]
    assert ie_calls == [1]
    assert again_no[0].description == "changed"
    assert again_ie[0].title == "IE"


def test_create_requirement_item_invalidates_cache(db_session=None):
    """crud.create_requirement_item bumps generation so a prior hit cannot survive."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from backend.app import crud, models

    engine = create_engine("sqlite://", future=True)
    models.Base.metadata.create_all(
        engine,
        tables=[models.RequirementItem.__table__, models.RequirementItemChangelog.__table__],
    )
    Session = sessionmaker(bind=engine)
    with Session() as db:
        calls = []

        def loader():
            calls.append(1)
            return crud.list_requirements(db, "NORWAY", "employment", include_unapproved=True)

        crud.create_requirement_item(
            db,
            dict(
                id="id-1",
                country_code="NORWAY",
                purpose="employment",
                pillar="RESIDENCE",
                title="Tax card",
                description="orig",
                severity="WARN",
                owner="EMPLOYEE",
                required_fields_json="[]",
                citations_json="[]",
                verification_status="corpus_grounded",
                last_verified_at=datetime(2026, 8, 12),
                review_status="approved",
            ),
        )
        cache.get_catalog_rows("NORWAY", "employment", loader, now=1_000.0)
        crud.create_requirement_item(
            db,
            dict(
                id="id-1",
                country_code="NORWAY",
                purpose="employment",
                pillar="RESIDENCE",
                title="Tax card",
                description="rewritten",
                severity="WARN",
                owner="EMPLOYEE",
                required_fields_json="[]",
                citations_json="[]",
                verification_status="corpus_grounded",
                last_verified_at=datetime(2026, 8, 12),
                review_status="approved",
            ),
        )
        rows = cache.get_catalog_rows("NORWAY", "employment", loader, now=1_001.0)
        assert len(calls) == 2
        assert rows[0].description == "rewritten"
