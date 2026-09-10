"""[AIQ-1788] Write planned candidate rows into vendor_curation_runs + vendor_candidates.

`plan_pair()` is pure: it decides which rows stage, which are duplicates and which are
rejected, and returns them with `run_id=""`. This is the half that opens the run and fills
that id in. Keeping them apart is why the entire decision surface is testable with no database.

SAFETY — two separate operations, and only one of them touches the directory:

    stage()    vendor_curation_runs -> vendor_candidates      suppliers untouched
    promote()  + suppliers, supplier_service_capabilities, supplier_accreditations

`promote()` is opt-in (`--promote`) and creates suppliers whose one capability is
`platform_vetting_status='pending'`, so they land in the admin vetting queue at
/admin/vetting-queue. **Nothing becomes visible to an employee**: `marketplace.py` and
`test_drive.py` both filter on `'approved'`, and approval stays a human action.

This departs from the harvester docstring's "suppliers READ ONLY", deliberately. That rule
assumed a dedicated candidates review surface, which does not exist — nothing in the product
reads `vendor_candidates` at all, so staged rows would have been invisible. Reusing the vetting
queue keeps ONE human gate instead of adding a third approval surface, and is exactly what
`admin_catalog.import_discovered` already does for scraper results. `vendor_candidates` remains
the audit and dedupe record, linked by `promoted_supplier_id`.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from sqlalchemy import text

from backend.app.services.vendor_harvester import (
    RUN_FAILED,
    RUN_STAGED,
    STATUS_PENDING,
    Candidate,
    PairResult,
    existing_dedupe_keys,
    plan_pair,
)

log = logging.getLogger(__name__)

# Nationally incorporated (or nationally licensed) entities that share a brand are
# distinct suppliers. Global networks (movers) are not — one Crown, many countries.
# Keep this set conservative; widening it is a follow-up, not this fix.
NATIONAL_ENTITY_CATEGORIES = frozenset({"banks", "legal_admin", "tax_finance"})

_INSERT_RUN = text(
    """
    INSERT INTO public.vendor_curation_runs
        (corridor, service_category, sources_searched, candidates_found, status)
    VALUES (:corridor, :service_category, CAST(:sources_searched AS jsonb), :candidates_found, :status)
    RETURNING id
    """
)

_INSERT_CANDIDATE = text(
    """
    INSERT INTO public.vendor_candidates
        (run_id, name, legal_name, website_url, email, phone, city, country_code,
         vat_number, corridor, service_category, source_url, source_name, source_tier,
         confidence_score, accreditation_body, accreditation_number, accreditation_expiry,
         bar_registered, dedupe_key, status, notes)
    VALUES
        (:run_id, :name, :legal_name, :website_url, :email, :phone, :city, :country_code,
         :vat_number, :corridor, :service_category, :source_url, :source_name, :source_tier,
         :confidence_score, :accreditation_body, :accreditation_number,
         CAST(:accreditation_expiry AS date),
         :bar_registered, :dedupe_key, :status, :notes)
    """
)


_STAGED_KEYS = text(
    "SELECT dedupe_key FROM public.vendor_candidates "
    "WHERE corridor = :corridor AND service_category = :category AND dedupe_key IS NOT NULL"
)


def _staged_keys(conn: Any, corridor: str, category: str) -> set:
    """Dedupe keys already present in vendor_candidates for this corridor+category."""
    return {
        k for (k,) in conn.execute(
            _STAGED_KEYS, {"corridor": corridor, "category": category}
        ) if k
    }


def group_by_pair(
    candidates: Sequence[Candidate],
) -> Dict[Tuple[str, str], List[Candidate]]:
    """(corridor, service_category) -> its candidates, in file order."""
    grouped: Dict[Tuple[str, str], List[Candidate]] = {}
    for cand in candidates:
        grouped.setdefault((cand.corridor, cand.service_category), []).append(cand)
    return grouped


def stage(
    conn: Any,
    candidates: Sequence[Candidate],
    *,
    dry_run: bool = True,
) -> Tuple[List[PairResult], List[str]]:
    """Plan every pair, and (unless dry_run) write the runs and rows.

    Returns (results, rejections). A dry run performs every read and every decision and
    writes nothing, so the numbers it prints are the numbers a real run will produce — the
    point of a preview is defeated if it takes a different code path.

    Takes a SQLAlchemy Connection inside a transaction the CALLER owns, so a partial failure
    rolls the whole import back rather than leaving half a corridor staged.
    """
    results: List[PairResult] = []
    rejections: List[str] = []

    for (corridor, category), pair_candidates in group_by_pair(candidates).items():
        # Re-read per corridor: the name-fallback key is corridor-scoped, and rows staged
        # earlier in THIS run must be visible to the next pair or a supplier appearing in two
        # categories would stage twice as 'pending'.
        known = existing_dedupe_keys(conn, corridor=corridor)
        rows, result, pair_rejections = plan_pair(corridor, category, pair_candidates, known)
        rejections.extend(pair_rejections)

        # Already-staged rows are not re-inserted. Without this a second run appends a full
        # duplicate set: every row matches the first run's dedupe keys, so it stages again as
        # 'duplicate' under a fresh run. That is not hypothetical — `--promote` implies
        # `--apply`, so running `--apply` and then `--promote` (the natural "stage, check,
        # then promote" sequence) did exactly that in production on 2026-08-11 and left 62
        # candidates and 16 runs where there should have been 31 and 8. The directory itself
        # was unharmed — the name index and add_capability's duplicate check absorbed it —
        # but the staging tables needed manual cleanup.
        already = _staged_keys(conn, corridor, category)
        skipped_existing = [r for r in rows if r["dedupe_key"] in already]
        rows = [r for r in rows if r["dedupe_key"] not in already]
        if skipped_existing:
            result.staged -= sum(
                1 for r in skipped_existing if r["status"] == STATUS_PENDING
            )
            result.suppressed_duplicates -= sum(
                1 for r in skipped_existing if r["status"] != STATUS_PENDING
            )
            log.info(
                "%s/%s: %d row(s) already staged, not re-inserted",
                corridor, category, len(skipped_existing),
            )

        if not dry_run and rows:
            try:
                run_id = conn.execute(
                    _INSERT_RUN,
                    {
                        "corridor": corridor,
                        "service_category": category,
                        "sources_searched": json.dumps(result.sources_searched),
                        "candidates_found": len(rows),
                        "status": RUN_STAGED,
                    },
                ).scalar_one()
                for row in rows:
                    conn.execute(_INSERT_CANDIDATE, {**row, "run_id": str(run_id)})
                result.run_id = str(run_id)
            except Exception as exc:                       # noqa: BLE001 — recorded, re-raised
                result.error = f"{type(exc).__name__}: {exc}"
                log.exception("staging %s/%s failed", corridor, category)
                raise

        results.append(result)

    return results, rejections


#: 'duplicate' is included on purpose. A duplicate means "we already hold this company" — it
#: does NOT mean the row is worthless. It is still evidence that the company serves this
#: corridor and category, and the right outcome is a new capability on the supplier we have,
#: not a discarded row. Excluding them silently dropped Expat Relocation's FR-NO housing
#: coverage, which is exactly the loss the duplicate status was meant to prevent.
_PROMOTABLE = text(
    """
    SELECT id, name, website_url, corridor, service_category, country_code, city,
           source_url, source_name, accreditation_body, accreditation_number,
           accreditation_expiry, notes
    FROM public.vendor_candidates
    WHERE status IN ('pending', 'duplicate') AND promoted_supplier_id IS NULL
    ORDER BY created_at
    """
)

#: [AIQ-1827] The same query, scoped to the runs a caller just staged.
#:
#: Unscoped promotion is a foot-gun that only shows up once the staging table has history.
#: Measured 2026-08-13: `vendor_candidates` held **233 unpromoted rows with corridor NULL**
#: from an earlier import, so a 16-row French harvest previewed as "promote: 235 suppliers".
#: A caller that stages a handful of rows and then promotes almost never means "and also
#: everything anyone ever staged and abandoned".
_PROMOTABLE_BY_RUN = text(
    """
    SELECT id, name, website_url, corridor, service_category, country_code, city,
           source_url, source_name, accreditation_body, accreditation_number,
           accreditation_expiry, notes
    FROM public.vendor_candidates
    WHERE status IN ('pending', 'duplicate') AND promoted_supplier_id IS NULL
      AND run_id = ANY(CAST(:run_ids AS uuid[]))
    ORDER BY created_at
    """
)

_LINK_CANDIDATE = text(
    "UPDATE public.vendor_candidates SET promoted_supplier_id = :sid, updated_at = now() "
    "WHERE id = :cid"
)

#: status stays 'claimed', not 'verified'. A registry listing is evidence that someone
#: published the membership, not that WE checked it — and the table's own CHECK requires
#: `verified_at` for 'verified'. The human who approves the capability is the verification.
_INSERT_ACCREDITATION = text(
    """
    INSERT INTO public.supplier_accreditations
        (supplier_id, body, membership_number, status, valid_until, evidence_url,
         verification_method, notes)
    VALUES
        (:supplier_id, :body, :membership_number, 'claimed', CAST(:valid_until AS date),
         :evidence_url, 'public_registry', :notes)
    ON CONFLICT (supplier_id, body, COALESCE(scheme, '')) DO NOTHING
    """
)


def _collapse_name_match(
    category: str,
    candidate_country: str,
    matched_countries: Set[str],
) -> bool:
    """Whether a `_name_key` hit is the same legal entity, not just the same brand.

    Movers (and every category outside NATIONAL_ENTITY_CATEGORIES) keep today's
    collapse: one supplier, per-country capabilities. Banks and licensed
    professions collapse only when the matched supplier already has a capability
    in the candidate's country — otherwise "Banco Santander, S.A." (ES) would
    attach to "Banco Santander (Brasil) S.A.".
    """
    if (category or "").strip().lower() not in NATIONAL_ENTITY_CATEGORIES:
        return True
    return bool(candidate_country) and candidate_country in matched_countries


def _capability_for(row: Any) -> Dict[str, Any]:
    """One capability per candidate row.

    `service_category` is lowercased here because `create_supplier` stores it RAW — the
    validator lowercases for its check but not for the value, and a stored 'Movers' would
    never match `search_by_service_destination`.
    """
    return {
        "service_category": (row["service_category"] or "").strip().lower(),
        "coverage_scope_type": "country",
        "country_code": (row["country_code"] or "").strip().upper()[:2],
        "city_name": row["city"],
        "platform_vetting_status": "pending",
        "notes": row["notes"],
    }


def _attach_accreditation(session: Any, supplier_id: str, row: Any) -> None:
    """Carry the registry evidence across. Dropping it at promotion would leave a supplier
    indistinguishable from a scrape, which is the whole thing this harvest exists to avoid."""
    if not row["accreditation_body"]:
        return
    session.execute(
        _INSERT_ACCREDITATION,
        {
            "supplier_id": supplier_id,
            "body": row["accreditation_body"],
            "membership_number": row["accreditation_number"],
            "valid_until": row["accreditation_expiry"],
            "evidence_url": row["source_url"],
            "notes": row["notes"],
        },
    )


def promote(
    session: Any,
    *,
    dry_run: bool = True,
    run_ids: Optional[Sequence[str]] = None,
) -> Tuple[int, int, List[str]]:
    """Promote pending candidates into the live directory as UNVETTED suppliers.

    Each becomes a `suppliers` row with exactly one capability at
    `platform_vetting_status='pending'`, so it lands in the admin vetting queue that already
    exists at /admin/vetting-queue. Nothing becomes visible to an employee: `marketplace` and
    `test_drive` both filter on `'approved'`.

    Chosen over building a third approval surface. `admin_catalog.import_discovered` already
    does exactly this for scraper results; a second promotion path would be a second thing to
    keep correct.

    Pass `run_ids` to promote ONLY what those runs staged. Omit it and every unpromoted
    candidate in the table is promoted, which is rarely what a caller means once the staging
    table has history — see `_PROMOTABLE_BY_RUN`.

    Returns (promoted, skipped, problems). Idempotent on `promoted_supplier_id`, so a re-run
    promotes nothing.
    """
    from backend.app.models import Supplier, SupplierServiceCapability
    from backend.app.services import supplier_registry
    from backend.app.services.supplier_registry import DuplicateSupplierError
    from backend.app.services.vendor_harvester import _name_key

    if run_ids is not None:
        if not run_ids:
            return 0, 0, []
        rows = session.execute(
            _PROMOTABLE_BY_RUN, {"run_ids": list(run_ids)}
        ).mappings().all()
    else:
        rows = session.execute(_PROMOTABLE).mappings().all()
    # Keyed by _name_key, not raw lowercase: it folds accents, strips legal form and drops
    # parenthetical asides, so "AGS France (SOFDI)" finds "AGS France (SOFDI – Société ...)".
    # Both name AND legal_name — a register reports the legal entity, and "Expat Relocation
    # Norway" is stored with legal_name "Expat Relocation AS", exactly what the harvest found.
    existing: Dict[str, str] = {}
    keys_by_sid: Dict[str, Set[str]] = {}
    for sid, sname, slegal in session.query(
        Supplier.id, Supplier.name, Supplier.legal_name
    ).all():
        for n in (sname, slegal):
            k = _name_key(n)
            if k:
                existing.setdefault(k, sid)
                keys_by_sid.setdefault(sid, set()).add(k)

    countries_by_sid: Dict[str, Set[str]] = {}
    existing_in_country: Dict[Tuple[str, str], str] = {}
    for cap_sid, cc in session.query(
        SupplierServiceCapability.supplier_id,
        SupplierServiceCapability.country_code,
    ).all():
        if not cc:
            continue
        code = str(cc).strip().upper()[:2]
        if not code:
            continue
        countries_by_sid.setdefault(cap_sid, set()).add(code)
        for k in keys_by_sid.get(cap_sid, ()):
            existing_in_country.setdefault((k, code), cap_sid)

    promoted = 0
    skipped = 0
    problems: List[str] = []

    for row in rows:
        name = (row["name"] or "").strip()
        key = _name_key(name)
        capability = _capability_for(row)
        category = capability["service_category"]
        country = capability["country_code"]

        def _remember(sid: str) -> None:
            if key:
                existing.setdefault(key, sid)
                if country:
                    existing_in_country[(key, country)] = sid
            if country:
                countries_by_sid.setdefault(sid, set()).add(country)

        # A company that serves both corridors — Grospiron and AGS France both do — is ONE
        # supplier with TWO capabilities, not two suppliers and not one dropped row. Skipping
        # the second would silently lose a corridor's coverage. National entities are the
        # exception: a name-key hit in a different country is a different legal entity.
        matched_id = None
        if key:
            matched_id = existing_in_country.get((key, country)) or existing.get(key)
        if matched_id and _collapse_name_match(
            category, country, countries_by_sid.get(matched_id, set())
        ):
            if dry_run:
                # Counted as PROMOTED, not skipped: a real run adds a capability to the
                # existing supplier, so counting it as a skip would make the preview
                # disagree with the run it is previewing.
                promoted += 1
                problems.append(
                    f"{name}: already a supplier — would add a capability to it, not a new row"
                )
                _remember(matched_id)
                continue
            try:
                supplier_registry.add_capability(session, matched_id, capability)
            except ValueError as exc:
                skipped += 1
                problems.append(f"{name}: capability not added — {exc}")
                continue
            _attach_accreditation(session, matched_id, row)
            session.execute(_LINK_CANDIDATE, {"sid": matched_id, "cid": row["id"]})
            session.commit()
            _remember(matched_id)
            promoted += 1
            continue

        if dry_run:
            promoted += 1
            _remember("(pending)")
            continue

        supplier_id = f"vc-{row['id']}"
        try:
            supplier_registry.create_supplier(
                session,
                {
                    "id": supplier_id,
                    "name": name,
                    "website": row["website_url"] or None,
                    "status": "active",
                    # CHECK allows admin_manual | customer_upload | scraper_discovery |
                    # directory_import. There is no 'harvester' value, and inventing one
                    # needs a migration — 'directory_import' is what the vendors migration
                    # uses for the same kind of provenance.
                    "source": "directory_import",
                    "source_url": row["source_url"],
                    "source_reference": f"vendor_candidates:{row['id']}",
                    "capabilities": [capability],
                },
            )
        except DuplicateSupplierError as exc:
            skipped += 1
            problems.append(f"{name}: {exc}")
            continue
        except ValueError as exc:
            skipped += 1
            problems.append(f"{name}: rejected by supplier validation — {exc}")
            continue

        _attach_accreditation(session, supplier_id, row)
        session.execute(_LINK_CANDIDATE, {"sid": supplier_id, "cid": row["id"]})
        session.commit()

        _remember(supplier_id)
        promoted += 1

    return promoted, skipped, problems


def summarise(results: Sequence[PairResult], rejections: Sequence[str]) -> str:
    """A short console summary. `render_report` in the harvester is the full markdown one."""
    staged = sum(r.staged for r in results)
    dupes = sum(r.suppressed_duplicates for r in results)
    lines = [
        f"pairs:      {len(results)}",
        f"staged:     {staged}   (status='pending')",
        f"duplicates: {dupes}   (status='duplicate', kept as history)",
        f"rejected:   {len(rejections)}",
    ]
    if rejections:
        lines.append("")
        lines.append("Rejected — this list is the re-sourcing worklist, not noise:")
        lines.extend(f"  - {r}" for r in rejections)
    return "\n".join(lines)
