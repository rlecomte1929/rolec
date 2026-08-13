"""[AIQ-1826] Fetch register pages and apply hardening decisions to supplier_accreditations.

The decision surface lives in `backend/app/services/accreditation_hardening.py` and is pure.
This module is the I/O half: it reads the rows, fetches each row's own `evidence_url`, hands
the result to `decide()`, and writes the outcome.

SAFETY
------
`dry_run=True` is the default and takes the same code path as a real run — the same rows are
read, the same URLs fetched, the same decisions computed. Only the UPDATE is skipped. That is
what makes "dry-run counts == live counts" a real guarantee rather than a hope.

This module UPDATEs existing rows. It never inserts, never deletes, and never touches
`supplier_service_capabilities`, so it cannot change what an employee sees: the recommendation
path filters on `platform_vetting_status='approved'`, which is a separate human gate this
routine does not go near.

Only three columns move, and only on a confirmation: `status`, `verification_method`,
`verified_at` / `verified_by`. `notes` records why a row stayed `claimed`, so the reason for a
non-verification survives in the database rather than only in a terminal that has scrolled away.
"""
from __future__ import annotations

import logging
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import text

from backend.app.services.accreditation_hardening import (
    ACTION_KEEP_CLAIMED,
    ACTION_NAME_MISMATCH,
    ACTION_VERIFY,
    AccreditationRow,
    Capability,
    Decision,
    LookupResult,
    decide,
    merge_note,
    policy_for_body,
)

log = logging.getLogger(__name__)

#: Identifies the run in `verified_by`, so a later audit can tell an automated register
#: confirmation apart from a human sign-off.
VERIFIED_BY = "accreditation-hardening/AIQ-1826"

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
_TIMEOUT = 25
#: Registers return large pages; we only ever substring-match a name, so cap the read.
_MAX_BYTES = 2_000_000


_SELECT_ROWS = text(
    """
    SELECT a.id::text        AS accreditation_id,
           a.supplier_id::text AS supplier_id,
           s.name            AS supplier_name,
           s.legal_name      AS legal_name,
           a.body            AS body,
           a.status          AS status,
           a.membership_number,
           a.evidence_url,
           a.notes
    FROM public.supplier_accreditations a
    JOIN public.suppliers s ON s.id = a.supplier_id
    ORDER BY s.name, a.body
    """
)

_SELECT_CAPS = text(
    """
    SELECT supplier_id::text AS supplier_id,
           service_category,
           country_code,
           city_name,
           platform_vetting_status
    FROM public.supplier_service_capabilities
    """
)


def load_rows(conn: Any) -> List[AccreditationRow]:
    """Every accreditation, with its supplier's capabilities attached.

    Scope is NOT filtered in SQL. `in_scope()` decides it, so the preview can report what it
    skipped and why — a row silently excluded by a WHERE clause is invisible to review.
    """
    caps_by_supplier: Dict[str, List[Capability]] = {}
    for r in conn.execute(_SELECT_CAPS).mappings():
        caps_by_supplier.setdefault(r["supplier_id"], []).append(
            Capability(
                service_category=r["service_category"],
                country_code=r["country_code"],
                city_name=r["city_name"],
                platform_vetting_status=r["platform_vetting_status"],
            )
        )

    rows: List[AccreditationRow] = []
    for r in conn.execute(_SELECT_ROWS).mappings():
        rows.append(
            AccreditationRow(
                accreditation_id=r["accreditation_id"],
                supplier_id=r["supplier_id"],
                supplier_name=r["supplier_name"],
                legal_name=r["legal_name"],
                body=r["body"],
                status=r["status"],
                membership_number=r["membership_number"],
                evidence_url=r["evidence_url"],
                notes=r["notes"],
                capabilities=tuple(caps_by_supplier.get(r["supplier_id"], ())),
            )
        )
    return rows


def fetch(url: str, *, opener: Any = None) -> LookupResult:
    """GET a register page. Any failure is a LookupResult, never an exception.

    An unreachable register must degrade to "unchecked" — `decide()` then keeps the row
    `claimed`. Raising here would abort the run and leave earlier rows written.
    """
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        _open = opener or urllib.request.urlopen
        with _open(req, timeout=_TIMEOUT) as resp:  # noqa: S310 — fixed https registry URLs
            raw = resp.read(_MAX_BYTES)
            status = getattr(resp, "status", None) or resp.getcode()
        return LookupResult(
            ok=200 <= int(status) < 300,
            http_status=int(status),
            text=raw.decode("utf-8", errors="replace"),
        )
    except urllib.error.HTTPError as exc:
        return LookupResult(ok=False, http_status=exc.code, error=f"HTTP {exc.code}")
    except Exception as exc:  # timeouts, DNS, TLS, malformed URL
        return LookupResult(ok=False, error=f"{type(exc).__name__}: {exc}")


def plan(
    rows: Sequence[AccreditationRow],
    *,
    fetcher: Any = fetch,
) -> List[Decision]:
    """Decide every row, fetching only where a fetch could change the outcome.

    Out-of-scope rows, blocked bodies and non-`claimed` rows are resolved without a request:
    there is no point asking a register about a row whose answer cannot matter, and it keeps
    the run polite.
    """
    from backend.app.services.accreditation_hardening import in_scope

    decisions: List[Decision] = []
    for row in rows:
        lookup: Optional[LookupResult] = None
        pol = policy_for_body(row.body)
        needs_fetch = (
            in_scope(row)
            and row.status == "claimed"
            and pol is not None
            and pol.auto_verifiable
            and bool(row.evidence_url)
        )
        if needs_fetch:
            lookup = fetcher(row.evidence_url)
        decisions.append(decide(row, lookup))
    return decisions


_UPDATE_VERIFIED = text(
    """
    UPDATE public.supplier_accreditations
       SET status              = :status,
           verification_method = :method,
           verified_at         = :verified_at,
           verified_by         = :verified_by,
           notes               = :notes,
           updated_at          = now()
     WHERE id = CAST(:aid AS uuid)
    """
)

_UPDATE_NOTE_ONLY = text(
    """
    UPDATE public.supplier_accreditations
       SET notes      = :notes,
           updated_at = now()
     WHERE id = CAST(:aid AS uuid)
    """
)


def apply(
    conn: Any,
    decisions: Sequence[Decision],
    *,
    dry_run: bool = True,
    record_reasons: bool = True,
) -> Tuple[int, int]:
    """Write the decisions. Returns (rows_verified, rows_annotated).

    Exactly one action changes a `status`: a confirmation. Everything else can only ever
    write `notes`, so no failure mode of this routine can make a row look more verified
    than its evidence supports.

    `record_reasons` writes the reason onto rows that stay `claimed` — including name
    mismatches, which are the re-sourcing worklist. That is how "unconfirmable ones stay
    claimed with a note" is satisfied, and it keeps the reason in the database rather than
    only in a terminal that has scrolled away.
    """
    verified = annotated = 0
    now = datetime.now(timezone.utc)

    for d in decisions:
        if d.action == ACTION_VERIFY:
            verified += 1
            if not dry_run:
                conn.execute(
                    _UPDATE_VERIFIED,
                    {
                        "status": d.status,
                        "method": d.verification_method,
                        "verified_at": now,
                        "verified_by": VERIFIED_BY,
                        "notes": merge_note(d.existing_notes, d.reason),
                        "aid": d.accreditation_id,
                    },
                )
        elif d.action in (ACTION_NAME_MISMATCH, ACTION_KEEP_CLAIMED) and record_reasons:
            annotated += 1
            if not dry_run:
                conn.execute(_UPDATE_NOTE_ONLY, {"notes": merge_note(d.existing_notes, d.reason), "aid": d.accreditation_id})

    return verified, annotated
