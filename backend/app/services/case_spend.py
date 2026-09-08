"""[AIQ-2089] Real committed spend per case — derived, not a ledger, and never an estimate.

There is no spend ledger in the platform. `case_budget_lines` is estimate-only and empty; the old
`hr_analytics` spend figure was hardcoded zeros (removed in AIQ-1527 rather than faked). But there
IS real committed-cost data: when HR validates an RFQ quote, `rfqs.validated_quote_id` points at
the accepted `quotes` row (`total_amount`, `currency`, `vendor_id`) and `rfqs.validated_at` stamps
it. This module reads exactly that — a derivation, no schema change.

Two traps it refuses, because both are how a fabricated number gets shipped:
  * It does NOT total `case_services.estimated_cost`. That column mixes an *agreed* cost (after
    acceptance) with an *estimate* or NULL, indistinguishably — totalling it reports guesses as
    commitments. Committed spend comes only from the explicit validation state on `rfqs`.
  * It does NOT sum across currencies. EUR, NOK and USD all appear with no FX source in the schema,
    so a cross-currency total would be invented. Spend is reported per currency; a caller that
    wants one number must bring a conversion policy this module deliberately does not have.

A case (or company) with no validated quote returns `has_spend=False` and an empty `by_currency`,
which the surfaces render as an honest empty state — never a 0 that reads as a measurement.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from ...database import db as main_db


def committed_spend_for_case(case_id: str) -> Dict[str, Any]:
    """Committed spend for ONE case, from its validated RFQ quotes. Per-currency subtotals only.

    `case_id` must be the canonical case id — the id `rfqs.case_id` carries. The budget-summary
    caller resolves it (`_canonical_case_id_or_404`) before calling, so a stale/assignment id can
    never silently read an empty selection here.
    """
    sql = text(
        """
        SELECT r.validated_quote_id AS quote_id, q.vendor_id, q.total_amount, q.currency,
               r.validated_at
        FROM rfqs r
        JOIN quotes q ON q.id = r.validated_quote_id
        WHERE r.case_id = :cid AND r.validated_quote_id IS NOT NULL
        ORDER BY r.validated_at
        """
    )
    with main_db.engine.connect() as conn:
        rows = conn.execute(sql, {"cid": str(case_id)}).mappings().all()
    return _summarise(rows)


def committed_spend_for_company(company_id: str) -> Dict[str, Any]:
    """Committed spend across a company's cases, tenant-scoped by `relocation_cases.company_id`.

    The scope is the authority: a validated quote on another company's case can never appear here
    (asserted by a negative test). `relocation_cases.id` is not text and `rfqs.case_id` is, hence
    the CAST — mirroring the existing HR case-scoping in `main.py`.
    """
    if not company_id:
        return _summarise([], include_cases=True)
    sql = text(
        """
        SELECT r.case_id, r.validated_quote_id AS quote_id, q.vendor_id, q.total_amount,
               q.currency, r.validated_at
        FROM rfqs r
        JOIN quotes q ON q.id = r.validated_quote_id
        JOIN relocation_cases rc ON CAST(rc.id AS TEXT) = r.case_id
        WHERE rc.company_id = :company AND r.validated_quote_id IS NOT NULL
        ORDER BY r.validated_at
        """
    )
    with main_db.engine.connect() as conn:
        rows = conn.execute(sql, {"company": str(company_id)}).mappings().all()
    return _summarise(rows, include_cases=True)


def _summarise(rows: List[Any], *, include_cases: bool = False) -> Dict[str, Any]:
    by_currency: Dict[str, Decimal] = {}
    lines: List[Dict[str, Any]] = []
    case_ids: set = set()
    for r in rows:
        amount = _to_decimal(r["total_amount"])
        if amount is None:
            # A validated quote with no amount is not a committed NUMBER. Skip it rather than
            # coerce to 0 — a 0 would read as "this cost nothing", a different and false claim.
            continue
        currency = (r["currency"] or "").strip().upper() or "UNKNOWN"
        by_currency[currency] = by_currency.get(currency, Decimal("0")) + amount
        line: Dict[str, Any] = {
            "quote_id": str(r["quote_id"]) if r["quote_id"] else None,
            "vendor_id": str(r["vendor_id"]) if r["vendor_id"] else None,
            "amount": str(amount),
            "currency": currency,
            "validated_at": _iso(r["validated_at"]),
        }
        if include_cases:
            line["case_id"] = str(r["case_id"])
            case_ids.add(str(r["case_id"]))
        lines.append(line)

    out: Dict[str, Any] = {
        # Per-currency subtotals, sorted for a stable payload. NO cross-currency total by design.
        "by_currency": {c: str(v) for c, v in sorted(by_currency.items())},
        "lines": lines,
        "has_spend": bool(lines),
    }
    if include_cases:
        out["case_count"] = len(case_ids)
    return out


def _to_decimal(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    iso = getattr(value, "isoformat", None)
    return iso() if callable(iso) else str(value)
