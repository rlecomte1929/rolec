"""
[AIQ-236 / P3-1] Benefit comparison engine — service asks vs. tier policy caps.

Pure functions. The router in `backend/app/routers/comparison.py` is responsible
for auth and HTTP error translation; this module never raises HTTPException.

Data flow
─────────
1. Resolve the employee's *current* tier from `employee_tiers`
   (tier filter at SQL level: `end_date IS NULL`).
2. Resolve the company's currently published `policy_versions` row.
3. Fetch all `policy_values` for (active version × employee tier),
   joined with `policy_categories` for the CAT-XX code + display name.
4. Fetch the employee's selected services from `case_services` keyed off
   their most-recently-updated active/draft case in `cases`.
5. Merge by translating each CAT-XX code to a `cap_key` (housing, movers,
   schools, banking, insurance, travel) and matching against
   `case_services.category`. This bridge composes with the existing
   BENEFIT_KEY_TO_CAP_KEY taxonomy in `policy_adapter.py` — it does not
   parallel it.

Coverage rules (per Notion AIQ-236 + Dev Plan v1.0 §4.1)
- Covered  : ask <= cap (delta = 0)
- Partial  : ask  > cap (delta = ask - cap, always positive)
- Uncovered: category in ask, NOT in policy (delta = ask)
- Not applicable: neither in ask nor in policy → omitted entirely

Currency mismatch between ask and cap → `currency_warning=True`, NO conversion.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from ..schemas_comparison import ComparisonResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Errors — translated to HTTP by the router. Keeps the engine HTTP-agnostic.
# ---------------------------------------------------------------------------

class ComparisonEngineError(Exception):
    """Base error type so routers can `except ComparisonEngineError`."""


class NoActiveTierError(ComparisonEngineError):
    """Employee has no row in `employee_tiers` with `end_date IS NULL`."""


class NoPublishedPolicyError(ComparisonEngineError):
    """The employee's company has no `policy_versions` in `published` status."""


# ---------------------------------------------------------------------------
# CAT-XX → cap_key bridge.
# Composes with BENEFIT_KEY_TO_CAP_KEY (policy_adapter.py). See module docstring.
# Categories not present here have no matching service bucket today — they
# stay in the response only if they show up in the ask side, which they won't.
# ---------------------------------------------------------------------------

CAT_TO_CAP_KEY: Dict[str, str] = {
    "CAT-01": "housing",      # Housing Allowance
    "CAT-02": "movers",       # Relocation Lump Sum (compensation matrix: relocation_allowance → movers)
    "CAT-03": "movers",       # Transportation & Shipping (shipment → movers)
    "CAT-04": "housing",      # Temporary Accommodation (temporary_housing → housing)
    "CAT-05": "travel",       # Travel & Airfare
    "CAT-07": "schools",      # Schooling & Education
    "CAT-10": "insurance",    # Healthcare & Insurance
    "CAT-14": "travel",       # Repatriation Benefits — closest service bucket
    # CAT-06 (Language), CAT-08 (Spouse), CAT-09 (Tax), CAT-11 (Home sale),
    # CAT-12 (COLA), CAT-13 (Settling-in) have no service-catalogue counterpart.
    # They are still emitted as policy-only "Covered" rows when a cap exists,
    # to give the employee visibility into the benefit.
}


# ---------------------------------------------------------------------------
# Dialect helper — same pattern as policy_summary.py / employee_tiers.py.
# Lets the tests run against SQLite without schema prefixing.
# ---------------------------------------------------------------------------

def _t(db: Any, name: str) -> str:
    try:
        dialect_name = db.engine.dialect.name
    except Exception:
        dialect_name = "postgresql"
    return f"public.{name}" if dialect_name == "postgresql" else name


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def _fetch_active_tier(db: Any, conn: Any, employee_id: str) -> Optional[Dict[str, Any]]:
    """
    Return {policy_tier_id, company_id, tier_name} or None.

    The `end_date IS NULL` predicate is applied at SQL — never in Python —
    so a non-current tier can never leak through.
    """
    row = conn.execute(
        text(
            f"SELECT et.policy_tier_id, et.company_id, et.tier_name "
            f"FROM {_t(db, 'employee_tiers')} et "
            f"WHERE et.employee_id = :eid AND et.end_date IS NULL "
            f"LIMIT 1"
        ),
        {"eid": employee_id},
    ).mappings().first()
    return dict(row) if row else None


def _fetch_active_version(db: Any, conn: Any, company_id: str) -> Optional[Dict[str, Any]]:
    """
    Return the company's latest published `policy_versions` row, joined
    through `company_policies` for the tenant link.
    """
    row = conn.execute(
        text(
            f"SELECT pv.id, pv.version_number, pv.status, pv.effective_date, pv.published_at "
            f"FROM {_t(db, 'policy_versions')} pv "
            f"JOIN {_t(db, 'company_policies')} cp ON cp.id = pv.policy_id "
            f"WHERE cp.company_id = :cid "
            f"  AND pv.status = 'published' "
            f"ORDER BY pv.published_at DESC NULLS LAST "
            f"LIMIT 1"
        ).execution_options(),
        {"cid": company_id},
    ).mappings().first() if _is_postgres(db) else conn.execute(
        # SQLite has no "NULLS LAST" — same intent via COALESCE.
        text(
            f"SELECT pv.id, pv.version_number, pv.status, pv.effective_date, pv.published_at "
            f"FROM {_t(db, 'policy_versions')} pv "
            f"JOIN {_t(db, 'company_policies')} cp ON cp.id = pv.policy_id "
            f"WHERE cp.company_id = :cid "
            f"  AND pv.status = 'published' "
            f"ORDER BY COALESCE(pv.published_at, '') DESC "
            f"LIMIT 1"
        ),
        {"cid": company_id},
    ).mappings().first()
    return dict(row) if row else None


def _is_postgres(db: Any) -> bool:
    try:
        return db.engine.dialect.name == "postgresql"
    except Exception:
        return True


def _fetch_caps(
    db: Any, conn: Any, *, version_id: str, policy_tier_id: str,
) -> List[Dict[str, Any]]:
    """
    Cap rows for the active version + tier. Tier-scope is enforced in SQL
    (the `policy_tier_id = :pt OR IS NULL` allows tier-agnostic rows that
    apply to every tier — common pattern in the P1-5 schema).
    """
    rows = conn.execute(
        text(
            f"SELECT pv.id, pv.cap_value, pv.cap_unit, pv.cap_currency, "
            f"       c.code AS category_code, c.display_name AS category_name "
            f"FROM {_t(db, 'policy_values')} pv "
            f"JOIN {_t(db, 'policy_categories')} c ON c.id = pv.category_id "
            f"WHERE pv.version_id = :vid "
            f"  AND (pv.policy_tier_id = :pt OR pv.policy_tier_id IS NULL)"
        ),
        {"vid": version_id, "pt": policy_tier_id},
    ).mappings().all()
    return [dict(r) for r in rows]


def _has_active_case(db: Any, conn: Any, employee_id: str) -> bool:
    """True if the employee has at least one active/draft case row."""
    row = conn.execute(
        text(
            f"SELECT 1 FROM {_t(db, 'cases')} "
            f"WHERE employee_id = :eid AND status IN ('active', 'draft') "
            f"LIMIT 1"
        ),
        {"eid": employee_id},
    ).first()
    return row is not None


def _fetch_asks(db: Any, conn: Any, employee_id: str) -> List[Dict[str, Any]]:
    """
    Service asks for the employee — drawn from `case_services` joined to
    the employee's active/draft cases. Returns empty list when the employee
    has selected no services.
    """
    rows = conn.execute(
        text(
            f"SELECT cs.category, cs.service_key, cs.estimated_cost, cs.currency "
            f"FROM {_t(db, 'case_services')} cs "
            f"JOIN {_t(db, 'cases')} c ON CAST(c.id AS TEXT) = cs.case_id "
            f"WHERE c.employee_id = :eid "
            f"  AND c.status IN ('active', 'draft') "
            f"  AND cs.selected = :true_val "
            f"ORDER BY c.updated_at DESC"
        ),
        # SQLite uses 1/0 for booleans; Postgres accepts True. Pass the
        # native value so a parameter-bound cast handles either dialect.
        {"eid": employee_id, "true_val": True},
    ).mappings().all()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Pure merge — the part you actually want to test in isolation.
# ---------------------------------------------------------------------------

def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_effective_date(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value)
    return s if s else None


def merge_caps_and_asks(
    *,
    caps: List[Dict[str, Any]],
    asks: List[Dict[str, Any]],
    policy_version_label: Optional[str],
    policy_effective_date: Optional[str],
    fallback_currency: str = "EUR",
) -> List[ComparisonResult]:
    """
    Pure function — no IO. Combines cap rows (CAT-XX coded) with ask rows
    (cap_key coded via `case_services.category`) and emits one
    `ComparisonResult` per relevant category.

    Returns a list in the order the underlying caps were seen, with any
    Uncovered asks appended at the end.
    """
    asks_by_cap_key: Dict[str, Dict[str, Any]] = {}
    for a in asks:
        cap_key = (a.get("category") or "").strip().lower()
        if not cap_key:
            continue
        # Keep the first ask with an estimated_cost; otherwise the first row.
        prev = asks_by_cap_key.get(cap_key)
        ask_amt = _coerce_float(a.get("estimated_cost"))
        if prev is None:
            asks_by_cap_key[cap_key] = a
            continue
        if _coerce_float(prev.get("estimated_cost")) is None and ask_amt is not None:
            asks_by_cap_key[cap_key] = a

    results: List[ComparisonResult] = []
    matched_cap_keys: set = set()

    for cap in caps:
        cat_code = str(cap.get("category_code") or "").strip()
        cat_name = str(cap.get("category_name") or cat_code or "Unnamed")
        cap_amount = _coerce_float(cap.get("cap_value"))
        cap_currency = (cap.get("cap_currency") or fallback_currency) or fallback_currency
        unit = cap.get("cap_unit")

        cap_key = CAT_TO_CAP_KEY.get(cat_code)
        ask = asks_by_cap_key.get(cap_key) if cap_key else None
        if cap_key:
            matched_cap_keys.add(cap_key)

        ask_amount = _coerce_float(ask.get("estimated_cost")) if ask else None
        ask_currency = (ask.get("currency") if ask else None) or cap_currency

        # Not applicable — no ask, no cap. Skip per spec.
        if cap_amount is None and ask_amount is None:
            continue

        currency_warning = bool(
            ask_amount is not None
            and cap_amount is not None
            and ask_currency
            and cap_currency
            and ask_currency.upper() != cap_currency.upper()
        )

        if ask_amount is not None and cap_amount is not None:
            if ask_amount > cap_amount:
                status = "Partial"
                delta = ask_amount - cap_amount
            else:
                status = "Covered"
                delta = 0.0
        elif cap_amount is not None and ask_amount is None:
            # Policy promises a cap but the employee hasn't asked for this
            # service yet — surface it as Covered (delta 0) so they know.
            status = "Covered"
            delta = 0.0
        else:
            # Should not reach here given the early-skip above.
            continue

        results.append(
            ComparisonResult(
                category_code=cat_code or "UNCLASSIFIED",
                category_name=cat_name,
                policy_cap=cap_amount,
                ask_value=ask_amount,
                currency=cap_currency,
                unit=unit,
                coverage_status=status,
                delta=delta,
                policy_version=policy_version_label,
                policy_effective_date=policy_effective_date,
                currency_warning=currency_warning,
            )
        )

    # Uncovered: asks that have no matching cap.
    for cap_key, a in asks_by_cap_key.items():
        if cap_key in matched_cap_keys:
            continue
        ask_amount = _coerce_float(a.get("estimated_cost"))
        if ask_amount is None:
            continue
        results.append(
            ComparisonResult(
                category_code=f"ASK-{cap_key.upper()}",
                category_name=cap_key.replace("_", " ").title(),
                policy_cap=None,
                ask_value=ask_amount,
                currency=(a.get("currency") or fallback_currency),
                unit=None,
                coverage_status="Uncovered",
                delta=ask_amount,  # full amount is out-of-pocket
                policy_version=policy_version_label,
                policy_effective_date=policy_effective_date,
                currency_warning=False,
            )
        )

    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_comparison(db: Any, employee_id: str) -> List[ComparisonResult]:
    """
    Compute the comparison between the employee's selected services and their
    active tier's policy caps. Raises:

    - NoActiveTierError       — employee has no current `employee_tiers` row
    - NoPublishedPolicyError  — company has no `published` policy_versions

    Both are translated to HTTP 404 / 409 by the router.
    """
    with db.engine.connect() as conn:
        tier = _fetch_active_tier(db, conn, employee_id)
        if not tier:
            raise NoActiveTierError(f"No active tier for employee {employee_id}")

        version = _fetch_active_version(db, conn, str(tier["company_id"]))
        if not version:
            raise NoPublishedPolicyError(
                f"No published policy for company {tier['company_id']}"
            )

        # Per AIQ-236 spec: when the employee has no case at all, the
        # comparison response is the empty list (no asks → "Not applicable"
        # for every category). Short-circuit before any cap work happens.
        if not _has_active_case(db, conn, employee_id):
            return []

        caps = _fetch_caps(
            db,
            conn,
            version_id=str(version["id"]),
            policy_tier_id=str(tier["policy_tier_id"]),
        )
        asks = _fetch_asks(db, conn, employee_id)

    policy_version_label = (
        f"v{version['version_number']}"
        if version.get("version_number") is not None
        else None
    )
    policy_effective_date = _format_effective_date(version.get("effective_date"))

    return merge_caps_and_asks(
        caps=caps,
        asks=asks,
        policy_version_label=policy_version_label,
        policy_effective_date=policy_effective_date,
    )
