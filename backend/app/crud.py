import json
from datetime import datetime, date
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from . import models
from .services import verification_guard


def get_case(db: Session, case_id: str) -> Optional[models.Case]:
    return db.query(models.Case).filter(models.Case.id == case_id).first()


def create_case(db: Session, case_id: str, draft: Dict[str, Any]) -> models.Case:
    case = models.Case(
        id=case_id,
        draft_json=json.dumps(draft),
        status="created",
        flags_json=json.dumps({}),
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def update_case(db: Session, case: models.Case, draft: Dict[str, Any], derived: Dict[str, Any], flags: Dict[str, Any]) -> models.Case:
    case.draft_json = json.dumps(draft)
    case.origin_country = derived.get("origin_country")
    case.origin_city = derived.get("origin_city")
    case.dest_country = derived.get("dest_country")
    case.dest_city = derived.get("dest_city")
    case.purpose = derived.get("purpose")
    case.target_move_date = _parse_date(derived.get("target_move_date"))
    case.flags_json = json.dumps(flags)
    case.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(case)
    return case


def _parse_date(value: Any) -> Optional[date]:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        raw = value.strip()
        try:
            return date.fromisoformat(raw)
        except ValueError:
            pass
        # Fallbacks for common UI formats: DD.MM.YYYY or DD/MM/YYYY
        try:
            if len(raw) == 10 and raw[2] in (".", "/") and raw[5] in (".", "/"):
                d1, d2, y = raw[:2], raw[3:5], raw[6:]
                day = int(d1)
                month = int(d2)
                year = int(y)
                # If month looks invalid, swap
                if month > 12 and day <= 12:
                    day, month = month, day
                return date(year, month, day)
        except Exception:
            return None
        return None
    return None


# Upper bound on list endpoints that used to return .all() unbounded.
# Callers that genuinely need more should paginate with offset/limit params.
_DEFAULT_LIST_LIMIT = 500


def list_country_profiles(db: Session, limit: int = _DEFAULT_LIST_LIMIT, offset: int = 0) -> List[models.CountryProfile]:
    return (
        db.query(models.CountryProfile)
        .order_by(models.CountryProfile.country_code.asc())
        .offset(max(0, offset))
        .limit(max(1, min(limit, 1000)))
        .all()
    )


def get_country_profile(db: Session, country_code: str) -> Optional[models.CountryProfile]:
    return db.query(models.CountryProfile).filter(models.CountryProfile.country_code == country_code).first()


def upsert_country_profile(db: Session, payload: Dict[str, Any]) -> models.CountryProfile:
    existing = get_country_profile(db, payload["country_code"])
    if existing:
        existing.last_updated_at = payload.get("last_updated_at")
        existing.confidence_score = payload.get("confidence_score")
        existing.notes = payload.get("notes")
        db.commit()
        db.refresh(existing)
        return existing
    record = models.CountryProfile(**payload)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def create_source_record(db: Session, payload: Dict[str, Any]) -> models.SourceRecord:
    existing = db.query(models.SourceRecord).filter(models.SourceRecord.content_hash == payload["content_hash"]).first()
    if existing:
        return existing
    record = models.SourceRecord(**payload)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def list_sources(db: Session, country_code: str, limit: int = _DEFAULT_LIST_LIMIT, offset: int = 0) -> List[models.SourceRecord]:
    return (
        db.query(models.SourceRecord)
        .filter(models.SourceRecord.country_code == country_code)
        .order_by(models.SourceRecord.id.desc())
        .offset(max(0, offset))
        .limit(max(1, min(limit, 1000)))
        .all()
    )


def _has_citations(value: Any) -> bool:
    """True when `value` carries at least one citation.

    citations_json is stored as a JSON string but callers pass lists too, and prod holds
    three interchangeable citation FORMATS (raw URLs, source_records uuids,
    immigration_rule.* corpus refs) — so this deliberately counts entries and never
    inspects their shape.
    """
    if value is None:
        return False
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return bool(value.strip())
    return bool(value)


#: The natural key every requirement-item import matches on. The database enforces it
#: too (uq_requirement_items_country_purpose_title — models.RequirementItem /
#: migration 20261118000000), so the ON CONFLICT insert below is pinned to exactly
#: this index and a duplicate corridor import inserts ZERO rows.
REQUIREMENT_ITEM_NATURAL_KEY = ("country_code", "purpose", "title")


def _find_requirement_item(db: Session, payload: Dict[str, Any]) -> Optional[models.RequirementItem]:
    return (
        db.query(models.RequirementItem)
        .filter(models.RequirementItem.country_code == payload["country_code"])
        .filter(models.RequirementItem.purpose == payload["purpose"])
        .filter(models.RequirementItem.title == payload["title"])
        .first()
    )


def _apply_requirement_item_update(db: Session, existing: models.RequirementItem, payload: Dict[str, Any]) -> models.RequirementItem:
    from .services.requirement_item_changelog import record_field_diff, snapshot_item

    previous = snapshot_item(existing)
    existing.description = payload["description"]
    existing.severity = payload["severity"]
    existing.owner = payload["owner"]
    existing.required_fields_json = payload["required_fields_json"]
    # citations_json follows the SAME rule as review_status below: curated provenance is
    # an editorial fact about the row, not a property of the seed file. Never replace a
    # citation with nothing.
    #
    # run_country_research() rebuilds these rows on every backend startup — so on every
    # Render deploy — with citations_json = json.dumps(source_ids[:1]). source_ids is
    # EMPTY whenever the StubResearchProvider returns nothing that passes
    # _is_official_domain for that country, which is every SINGAPORE and UNITED STATES
    # run. On 2026-08-20 that silently blanked a verified ICA citation applied hours
    # earlier, and only the requirement-provenance guard caught it.
    #
    # An incoming citation still wins — this exempts nothing from legitimate updates, it
    # only refuses the downgrade to empty.
    if _has_citations(payload["citations_json"]) or not _has_citations(existing.citations_json):
        existing.citations_json = payload["citations_json"]
    # AIQ-1349: keep the assignment-type applicability in sync on re-load.
    if "applies_to_assignment_types_json" in payload:
        existing.applies_to_assignment_types_json = payload["applies_to_assignment_types_json"]
    if "applies_to_nationality_classes_json" in payload:
        existing.applies_to_nationality_classes_json = payload["applies_to_nationality_classes_json"]
    if "applies_to_regimes_json" in payload:
        existing.applies_to_regimes_json = payload["applies_to_regimes_json"]
    if "verification_status" in payload:
        existing.verification_status = payload["verification_status"]
    # non_obvious / timing were added by 20261103000000 and this update branch never
    # learned about them: they were set on INSERT and silently dropped on every re-load,
    # so correcting a deadline in a seed file changed nothing for an existing row.
    # Guarded with `in payload` like the two above, so a caller that does not manage
    # these columns cannot blank them.
    if "non_obvious" in payload:
        existing.non_obvious = payload["non_obvious"]
    if "timing" in payload:
        existing.timing = payload["timing"]
    # review_status is deliberately NOT synced here. It is an admin decision about an
    # existing row, not a property of the seed file, and re-running any YAML seed would
    # otherwise silently un-approve live content — germany.yaml alone owns 16 rows. Set on
    # insert (below), carried on update. Same rule as _CARRIED_COLUMNS in
    # admin_form_templates.py.
    existing.last_verified_at = payload["last_verified_at"]
    record_field_diff(
        db,
        existing,
        previous,
        changed_by="system:create_requirement_item",
    )
    db.commit()
    db.refresh(existing)
    return existing


def _insert_requirement_item_ignore_conflict(db: Session, payload: Dict[str, Any]) -> int:
    """INSERT ... ON CONFLICT (country_code, purpose, title) DO NOTHING. Returns rows inserted.

    THE corridor-import idempotency guard (the 2026-08-15 FR→NO double-import
    incident): re-importing a requirement that already exists — including one a
    concurrent import committed after this session's pre-select ran — inserts ZERO
    rows instead of a duplicate. The conflict target is pinned to the natural-key
    unique index, so a genuine primary-key collision still fails loudly rather than
    being swallowed. Dialect-aware because production runs Postgres and the CI suite
    runs SQLite; both compile a native ON CONFLICT DO NOTHING clause.
    """
    table = models.RequirementItem.__table__
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as dialect_insert
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as dialect_insert
    else:
        # No ON CONFLICT support known for this dialect: plain insert. The unique
        # constraint still refuses a duplicate loudly rather than storing it.
        return db.execute(table.insert().values(**payload)).rowcount or 0
    stmt = (
        dialect_insert(table)
        .values(**payload)
        .on_conflict_do_nothing(index_elements=list(REQUIREMENT_ITEM_NATURAL_KEY))
    )
    return db.execute(stmt).rowcount or 0


def create_requirement_item(db: Session, payload: Dict[str, Any]) -> models.RequirementItem:
    """Upsert on the natural key (country_code, purpose, title). Fully idempotent.

    Every caller of this funnel is an automated producer (Otto promote, YAML
    seed, research stub), so the generator/verifier separation guard runs on
    BOTH branches: a payload claiming 'expert_verified', carrying the
    guard-owned verified_by/verified_at columns, or rewriting a human-verified
    row's provenance is rejected (VerificationWriteError) before anything is
    written. Flipping a row to 'expert_verified' has exactly one path:
    services/verification_guard.mark_expert_verified, behind the admin router.

    Idempotency is enforced in the DATABASE, not just here: the insert runs
    ON CONFLICT (country_code, purpose, title) DO NOTHING against the natural-key
    unique index, so running the same corridor import N times — sequentially or
    concurrently — produces the same row set as running it once. A duplicate
    import inserts zero new rows (see test_corridor_import_idempotency.py; the
    2026-08-15 FR→NO corridor import ran twice and duplicated requirement rows
    because nothing below the application-level pre-select enforced the key).
    """
    existing = _find_requirement_item(db, payload)
    verification_guard.assert_generator_verification_write(
        payload,
        existing_status=existing.verification_status if existing else None,
        context="create_requirement_item",
    )
    if existing:
        return _apply_requirement_item_update(db, existing, payload)

    insert_payload = dict(payload)
    # Catalog rows default to 'approved' in the ORM/server default. Automated inserts
    # (Otto, research stub, YAML that omitted the column) must wait for a human.
    insert_payload.setdefault("review_status", "pending")
    inserted = _insert_requirement_item_ignore_conflict(db, insert_payload)
    db.commit()
    if inserted:
        item = _find_requirement_item(db, payload)
        assert item is not None  # just inserted and committed
        from .services.requirement_item_changelog import CHANGE_ADDED, record_change, snapshot_item

        record_change(
            db,
            requirement_id=item.id,
            country_code=item.country_code,
            change_type=CHANGE_ADDED,
            previous_value=None,
            new_value=snapshot_item(item),
            changed_by="system:create_requirement_item",
            commit=True,
        )
        return item

    # ON CONFLICT DO NOTHING fired: a concurrent import of the same requirement won the
    # race between our pre-select and our insert. Zero rows were inserted — re-read the
    # row that won, re-run the guard against its actual status, and converge on the
    # update branch so N imports end in exactly the state one import produces.
    raced = _find_requirement_item(db, payload)
    if raced is None:  # pragma: no cover — the conflicting row must exist
        raise RuntimeError(
            "requirement_items insert conflicted on (country_code, purpose, title) but "
            "the winning row could not be re-read; refusing to guess."
        )
    verification_guard.assert_generator_verification_write(
        payload,
        existing_status=raced.verification_status,
        context="create_requirement_item",
    )
    return _apply_requirement_item_update(db, raced, payload)


def create_research_candidate(db: Session, payload: Dict[str, Any]) -> models.ResearchSourceCandidate:
    existing = (
        db.query(models.ResearchSourceCandidate)
        .filter(models.ResearchSourceCandidate.content_hash == payload["content_hash"])
        .first()
    )
    if existing:
        return existing
    record = models.ResearchSourceCandidate(**payload)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def list_research_candidates(
    db: Session,
    destination_country: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = _DEFAULT_LIST_LIMIT,
    offset: int = 0,
) -> List[models.ResearchSourceCandidate]:
    query = db.query(models.ResearchSourceCandidate)
    if destination_country:
        query = query.filter(
            (models.ResearchSourceCandidate.destination_country == destination_country)
            | (models.ResearchSourceCandidate.country_code == destination_country)
        )
    if status:
        query = query.filter(models.ResearchSourceCandidate.status == status)
    return (
        query.order_by(models.ResearchSourceCandidate.created_at.desc())
        .offset(max(0, offset))
        .limit(max(1, min(limit, 1000)))
        .all()
    )


def update_research_candidate_status(db: Session, candidate_id: str, status: str) -> Optional[models.ResearchSourceCandidate]:
    candidate = db.query(models.ResearchSourceCandidate).filter(models.ResearchSourceCandidate.id == candidate_id).first()
    if not candidate:
        return None
    candidate.status = status
    db.commit()
    db.refresh(candidate)
    return candidate


def create_ingest_job(db: Session, payload: Dict[str, Any]) -> models.KnowledgeDocIngestJob:
    job = models.KnowledgeDocIngestJob(**payload)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def update_ingest_job(
    db: Session,
    job_id: str,
    status: str,
    doc_id: Optional[str] = None,
    error: Optional[str] = None,
) -> Optional[models.KnowledgeDocIngestJob]:
    job = db.query(models.KnowledgeDocIngestJob).filter(models.KnowledgeDocIngestJob.id == job_id).first()
    if not job:
        return None
    job.status = status
    if doc_id:
        job.doc_id = doc_id
    job.error = error
    if status in ("running", "done", "failed"):
        job.started_at = job.started_at or datetime.utcnow()
    if status in ("done", "failed"):
        job.finished_at = datetime.utcnow()
    db.commit()
    db.refresh(job)
    return job


def list_ingest_jobs(
    db: Session,
    status: Optional[str] = None,
    limit: int = _DEFAULT_LIST_LIMIT,
    offset: int = 0,
) -> List[models.KnowledgeDocIngestJob]:
    query = db.query(models.KnowledgeDocIngestJob)
    if status:
        query = query.filter(models.KnowledgeDocIngestJob.status == status)
    return (
        query.order_by(models.KnowledgeDocIngestJob.created_at.desc())
        .offset(max(0, offset))
        .limit(max(1, min(limit, 1000)))
        .all()
    )


def list_requirements(
    db: Session,
    country_code: str,
    purpose: Optional[str] = None,
    limit: int = _DEFAULT_LIST_LIMIT,
    offset: int = 0,
    include_unapproved: bool = False,
) -> List[models.RequirementItem]:
    """Requirements for a destination, filtered to what an admin has approved.

    THE publication gate, and deliberately the only one. Both readers come through here —
    `requirements_builder` (employee dossier) and `public_corridor` (unauthenticated) — so
    withholding unreviewed content is one change rather than two, and there is no second seam
    to forget. Before this filter existed, a row was live to anonymous internet traffic the
    instant it was inserted.

    `include_unapproved=True` is for the admin review surface, which must obviously see the
    rows it is being asked to approve.

    A `needs_lawyer_review`-flagged, un-attested row is NOT withheld here — it is served with a
    caveat instead. #2131 withheld it; that removed real, grounded content from users. The
    serving layer now sets `legalReviewPending=True` on such a row (see
    `services/lawyer_review_gate.legal_review_pending`, computed in `public_corridor._base_items`
    and `requirements_builder`), and the UI badges it "Legal review pending — not independently
    legal-reviewed." Honest (the flag means exactly that) and higher coverage than a blank.
    Approval still blocks on the same flag at `admin.py`; only the *serving* treatment changed
    from withhold to badge. See `docs/compliance/counsel-attestation-lane-2026-08-30.md`.
    """
    query = db.query(models.RequirementItem).filter(models.RequirementItem.country_code == country_code)
    if purpose:
        query = query.filter(models.RequirementItem.purpose == purpose)
    if not include_unapproved:
        query = query.filter(models.RequirementItem.review_status == "approved")
    return (
        query.order_by(models.RequirementItem.id.desc())
        .offset(max(0, offset))
        .limit(max(1, min(limit, 1000)))
        .all()
    )


def create_snapshot(db: Session, payload: Dict[str, Any]) -> models.CaseRequirementsSnapshot:
    snapshot = models.CaseRequirementsSnapshot(**payload)
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot
