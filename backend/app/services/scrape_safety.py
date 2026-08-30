"""
Cost-control surface for the catalog scraper (Phase 2b-secured).

Layered protection — see docs/RECOMMENDATIONS_CATALOG_ROUTINE.md:
  L1: pre-check inside populate_destination_catalog (skip LLM when rows exist)
  L2: HR endpoint /api/hr/catalog/populate-with-ai goes through this module
  L3: per-company per-day quota — DEFAULT_DAILY_QUOTA distinct calls
  L4: destination allowlist — admin gates which (city, country) pairs scrape
  L7: audit row on every dispatch + every allowlist add

This module is purely the data layer. The HTTP endpoints in
backend/app/routers/hr_catalog.py + admin_catalog.py call into here.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import date, datetime
from typing import Any, Dict, FrozenSet, List, Optional, Set

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from ...database import db
from . import destination_key
from .audit_log_service import (
    ACTION_INSERT,
    ACTION_UPDATE,
    ACTOR_HUMAN,
    insert_audit_log,
)

log = logging.getLogger(__name__)

DEFAULT_DAILY_QUOTA = 20


# ---------------------------------------------------------------------------
# Allowlist (L4)
# ---------------------------------------------------------------------------


def _norm(s: Optional[str]) -> str:
    return (s or "").strip()


# AIQ-1325c: the allowlist was seeded with ReloPass-internal tags in `notes`
# ('AIQ-28-A seed', 'B14 seed', 'aiq-28-a-backfill original countries') that leak
# ticket IDs into the admin /catalog-queue UI. Normalise those to a clean label at
# read time (display-only; the stored row is untouched). Genuine HR-entered notes
# pass through unchanged.
_SEED_NOTE_LABEL = "ReloPass curated"
_SEED_NOTE_RE = re.compile(r"^(aiq|b\d+ seed)", re.IGNORECASE)


def _clean_seed_note(note: Optional[str]) -> Optional[str]:
    """Return a clean label for ReloPass-internal seed tags; pass real notes
    (and None/empty) through unchanged."""
    if not note:
        return note
    return _SEED_NOTE_LABEL if _SEED_NOTE_RE.match(note.strip()) else note


def allowlist_index() -> FrozenSet[destination_key.DestinationKey]:
    """One query -> every canonical key the allowlist currently answers to.

    Batch callers (list_demand_gaps, list_intake_corridors) build this ONCE and pass it
    to is_destination_allowlisted, instead of one full-table read per row.

    Deliberately NOT a memoised/TTL cache. Under multiple workers a cache in worker A
    would not see an add_allowlist_entry in worker B, so an admin who had just approved
    a destination would see it intermittently refused. A parameter removes the N+1 with
    no staleness at all.
    """
    with db.engine.connect() as conn:
        rows = conn.execute(
            text("SELECT city, country FROM catalog_destination_allowlist")
        ).all()
    keys: Set[destination_key.DestinationKey] = set()
    for city, country in rows:
        keys |= destination_key.destination_keys(city, country)
    return frozenset(keys)


def is_destination_allowlisted(
    city: str,
    country: Optional[str],
    *,
    index: Optional[FrozenSet[destination_key.DestinationKey]] = None,
) -> bool:
    """L4 gate: may we spend money scraping this destination?

    Canonical comparison — case, whitespace, diacritics, and ISO-2-vs-full-name all
    describe the SAME destination. Before this, a raw `=` meant the allowlist's
    'France' could never answer a demand row's 'FR', so every gap row read
    "not allowlisted" while the writer happily minted a duplicate.

    FAILS CLOSED. An unusable city or country — empty, whitespace-only, or a string
    that is not a country at all — yields no keys and therefore matches nothing. There
    is no wildcard: `None` does not match `None`.

    `index` is an optimisation for callers gating many rows in one request. `None` means
    "read the table now"; an explicitly-passed EMPTY index means "the allowlist is
    empty" and correctly returns False rather than silently re-querying.

    A database error PROPAGATES. Do not catch it into a `return True` — an unreadable
    allowlist must never open the gate.
    """
    probe = destination_key.destination_keys(city, country)
    if not probe:
        return False
    idx = allowlist_index() if index is None else index
    return not probe.isdisjoint(idx)


def list_allowlist() -> List[Dict[str, Any]]:
    with db.engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT city, country, approved_by, approved_at, notes "
                "FROM catalog_destination_allowlist ORDER BY country, city"
            )
        ).mappings().all()
    out: List[Dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        v = d.get("approved_at")
        if hasattr(v, "isoformat"):
            d["approved_at"] = v.isoformat()
        d["notes"] = _clean_seed_note(d.get("notes"))  # AIQ-1325c
        out.append(d)
    return out


def _house_country_spelling(
    rows: List[Any], iso: Optional[str]
) -> Optional[str]:
    """The spelling this table already uses for `iso`, or None if it holds none.

    Deliberately self-referential: NO new country map. The allowlist already knows how
    it spells every country it holds, and the only ISO-2 writer is fill_demand_gap,
    whose eight countries all already have a full-name row. So ('Berlin','DE') adopts
    'Germany' from the existing ('Munich','Germany') instead of minting a 'DE' variant.

    Preference mirrors dedupe_destination_allowlist's scoring so the writer and the
    cleanup script agree on which spelling wins:
      1. not a bare 2-letter code   ('France' over 'FR')
      2. initial uppercase          ('France' over 'france')
      3. most frequent in the table
      4. lexicographic              (determinism across processes)
    """
    if not iso:
        return None
    counts: Dict[str, int] = {}
    for _city, country in rows:
        if destination_key.canon_country(country) == iso:
            counts[country] = counts.get(country, 0) + 1
    if not counts:
        return None

    def score(name: str) -> tuple:
        return (
            0 if len(name.strip()) != 2 else 1,   # full name beats a bare code
            0 if name[:1].isupper() else 1,        # 'France' beats 'france'
            -counts[name],                          # most frequent
            name,                                   # deterministic tiebreak
        )

    return sorted(counts, key=score)[0]


def add_allowlist_entry(
    *,
    city: str,
    country: str,
    approved_by_user_id: str,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Admin/HR-only. CANONICALLY idempotent.

    A destination already allowlisted under ANY equivalent spelling is not inserted a
    second time. This is the fix for the regenerating ('Paris','FR') / ('Paris','France')
    pair that PR #2020 deleted from the data and that this writer immediately recreated
    on the next click.

    Returns the row that is IN FORCE — the existing spelling on a canonical match, the
    newly-stored spelling otherwise — plus `created`. It still never raises for an
    existing entry: `fill_demand_gap` and `resolve_destination_request` catch ValueError
    and pass, and ValueError stays reserved for EMPTY input.
    """
    city_n, country_n = _norm(city), _norm(country)
    if not city_n or not country_n:
        raise ValueError("city and country are both required")

    probe = destination_key.destination_keys(city_n, country_n)
    now = datetime.utcnow().isoformat()
    created = False
    stored_city, stored_country = city_n, country_n

    with db.engine.begin() as conn:
        rows = conn.execute(
            text("SELECT city, country FROM catalog_destination_allowlist")
        ).all()

        twin = None
        if probe:
            for row_city, row_country in rows:
                if not probe.isdisjoint(
                    destination_key.destination_keys(row_city, row_country)
                ):
                    twin = (row_city, row_country)
                    break

        if twin:
            stored_city, stored_country = twin
        else:
            # City verbatim — never title-cased. `.title()` mangles 'The Hague',
            # "'s-Hertogenbosch" and 'Sant Cugat del Vallès', and since #2023 the input
            # comes from a picker rather than a free-text box.
            house = _house_country_spelling(rows, destination_key.canon_country(country_n))
            if house:
                stored_country = house
            # else: keep the caller's spelling. For a country the table has never held
            # this is the normal path (the picker supplies a full name); a bare ISO-2
            # would be the only row for that country, so no duplicate is possible and
            # the canonical reader still matches a later 'Japan' against a stored 'JP'.
            try:
                conn.execute(
                    text(
                        "INSERT INTO catalog_destination_allowlist "
                        "(city, country, approved_by, approved_at, notes) "
                        "VALUES (:city, :country, :actor, :now, :notes)"
                    ),
                    {
                        "city": stored_city,
                        "country": stored_country,
                        "actor": approved_by_user_id,
                        "now": now,
                        "notes": notes,
                    },
                )
                created = True
            except IntegrityError:
                # Two concurrent fills of a brand-new destination derive the same
                # spelling from the same deterministic rule, so the PK collides. The
                # other writer won; treat it as the idempotent case.
                created = False

    # Audit only a REAL insert. This used to fire on every call, so the log claimed
    # inserts that never happened.
    if created:
        _audit(
            entity_type="catalog_destination_allowlist",
            entity_id=f"{stored_city}|{stored_country}",
            action=ACTION_INSERT,
            actor_id=approved_by_user_id,
            new_value={"city": stored_city, "country": stored_country, "notes": notes},
        )
    return {
        "city": stored_city,
        "country": stored_country,
        "notes": notes,
        "created": created,
    }


# ---------------------------------------------------------------------------
# Quota (L3)
# ---------------------------------------------------------------------------


def _today_iso() -> str:
    return date.today().isoformat()


def get_quota_state(company_id: str) -> Dict[str, Any]:
    today = _today_iso()
    with db.engine.begin() as conn:
        row = conn.execute(
            text(
                "SELECT calls_made FROM catalog_scrape_quota "
                "WHERE company_id = :co AND day = :day"
            ),
            {"co": company_id, "day": today},
        ).mappings().first()
    used = int(row["calls_made"]) if row else 0
    return {"day": today, "used": used, "limit": DEFAULT_DAILY_QUOTA, "remaining": max(0, DEFAULT_DAILY_QUOTA - used)}


def check_and_increment_quota(company_id: str) -> Dict[str, Any]:
    """
    Atomically check + increment the per-day counter. Returns the post-increment
    state plus an `allowed` flag. Caller bails when allowed=False.
    """
    today = _today_iso()
    with db.engine.begin() as conn:
        existing = conn.execute(
            text(
                "SELECT calls_made FROM catalog_scrape_quota "
                "WHERE company_id = :co AND day = :day"
            ),
            {"co": company_id, "day": today},
        ).mappings().first()
        used = int(existing["calls_made"]) if existing else 0
        if used >= DEFAULT_DAILY_QUOTA:
            return {"allowed": False, "day": today, "used": used, "limit": DEFAULT_DAILY_QUOTA, "remaining": 0}
        new_used = used + 1
        if existing:
            conn.execute(
                text(
                    "UPDATE catalog_scrape_quota SET calls_made = :n "
                    "WHERE company_id = :co AND day = :day"
                ),
                {"n": new_used, "co": company_id, "day": today},
            )
        else:
            conn.execute(
                text(
                    "INSERT INTO catalog_scrape_quota (company_id, day, calls_made) "
                    "VALUES (:co, :day, :n)"
                ),
                {"co": company_id, "day": today, "n": new_used},
            )
    return {
        "allowed": True,
        "day": today,
        "used": new_used,
        "limit": DEFAULT_DAILY_QUOTA,
        "remaining": DEFAULT_DAILY_QUOTA - new_used,
    }


# ---------------------------------------------------------------------------
# Ticket queue (L4 + L6)
# ---------------------------------------------------------------------------


def open_destination_request(
    *,
    city: str,
    country: str,
    category: str,
    requested_by_user_id: str,
    company_id: str,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    city_n, country_n = _norm(city), _norm(country)
    if not city_n or not country_n or not _norm(category):
        raise ValueError("city, country, and category are required")
    row_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    with db.engine.begin() as conn:
        # Dedup: if there's already a pending request for the same triple, return that.
        existing = conn.execute(
            text(
                "SELECT * FROM catalog_destination_requests "
                "WHERE city = :city AND country = :country "
                "AND category = :cat AND status = 'pending' AND company_id = :co "
                "ORDER BY created_at DESC LIMIT 1"
            ),
            {"city": city_n, "country": country_n, "cat": category, "co": company_id},
        ).mappings().first()
        if existing:
            return _ticket_to_dict(existing)
        conn.execute(
            text(
                "INSERT INTO catalog_destination_requests "
                "(id, city, country, category, requested_by, company_id, "
                " status, notes, created_at, updated_at) "
                "VALUES (:id, :city, :country, :cat, :req, :co, "
                " 'pending', :notes, :now, :now)"
            ),
            {
                "id": row_id, "city": city_n, "country": country_n, "cat": category,
                "req": requested_by_user_id, "co": company_id, "notes": notes,
                "now": now,
            },
        )
        new_row = conn.execute(
            text("SELECT * FROM catalog_destination_requests WHERE id = :id"),
            {"id": row_id},
        ).mappings().first()
    _audit(
        entity_type="catalog_destination_requests",
        entity_id=row_id,
        action=ACTION_INSERT,
        actor_id=requested_by_user_id,
        new_value={"city": city_n, "country": country_n, "category": category, "company_id": company_id},
    )
    # AIQ-1602: email admins that a NEW gap request was opened (only reached for
    # fresh rows — the dedup branch above returns early, so duplicates don't spam).
    # Fail-soft: a notification failure must never break the request.
    try:
        from .admin_notify import notify_admins_gap_request

        notify_admins_gap_request(
            city=city_n,
            country=country_n,
            category=category,
            company_id=company_id,
            requested_by=requested_by_user_id,
        )
    except Exception:  # noqa: BLE001 — notification must never break the request
        log.warning("open_destination_request: admin gap-request email failed (suppressed)")
    return _ticket_to_dict(new_row)


def list_destination_requests(
    *,
    status: Optional[str] = None,
    company_id: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    where = []
    params: Dict[str, Any] = {"limit": int(max(1, min(limit, 500)))}
    if status:
        where.append("status = :status")
        params["status"] = status
    if company_id:
        where.append("company_id = :co")
        params["co"] = company_id
    sql = "SELECT * FROM catalog_destination_requests"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC LIMIT :limit"
    with db.engine.begin() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    return [_ticket_to_dict(r) for r in rows]


def resolve_destination_request(
    *,
    request_id: str,
    new_status: str,
    actor_user_id: str,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    if new_status not in ("approved", "rejected"):
        raise ValueError("new_status must be 'approved' or 'rejected'")
    now = datetime.utcnow().isoformat()
    with db.engine.begin() as conn:
        existing = conn.execute(
            text("SELECT * FROM catalog_destination_requests WHERE id = :id"),
            {"id": request_id},
        ).mappings().first()
        if not existing:
            raise LookupError("Request not found")
        if existing["status"] != "pending":
            raise ValueError(f"Request already {existing['status']}")
        conn.execute(
            text(
                "UPDATE catalog_destination_requests "
                "SET status = :s, resolved_by = :actor, resolved_at = :now, "
                "    updated_at = :now, notes = COALESCE(:notes, notes) "
                "WHERE id = :id"
            ),
            {"s": new_status, "actor": actor_user_id, "now": now, "notes": notes, "id": request_id},
        )
        row = conn.execute(
            text("SELECT * FROM catalog_destination_requests WHERE id = :id"),
            {"id": request_id},
        ).mappings().first()
    _audit(
        entity_type="catalog_destination_requests",
        entity_id=request_id,
        action=ACTION_UPDATE,
        actor_id=actor_user_id,
        old_value={"status": existing["status"]},
        new_value={"status": new_status, "notes": notes},
    )
    return _ticket_to_dict(row)


def _ticket_to_dict(row: Any) -> Dict[str, Any]:
    d = dict(row)
    for k in ("id", "company_id", "requested_by"):
        if k in d and d[k] is not None:
            d[k] = str(d[k])
    for k in ("created_at", "updated_at", "resolved_at"):
        v = d.get(k)
        if hasattr(v, "isoformat"):
            try:
                d[k] = v.isoformat()
            except Exception:
                d[k] = str(v)
    return d


# ---------------------------------------------------------------------------
# Audit helper — never raises
# ---------------------------------------------------------------------------


def _audit(
    *,
    entity_type: str,
    entity_id: str,
    action: str,
    actor_id: str,
    new_value: Optional[Dict[str, Any]] = None,
    old_value: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        with db.engine.begin() as conn:
            insert_audit_log(
                conn,
                entity_type=entity_type,
                entity_id=entity_id,
                action_type=action,
                old_value=old_value,
                new_value=new_value,
                actor_type=ACTOR_HUMAN,
                actor_id=actor_id,
            )
    except Exception:
        log.exception("audit_log write failed entity_type=%s entity_id=%s", entity_type, entity_id)
