"""[AIQ-2271] Per-benefit_key drawdown of approved expense lines against policy caps.

Serving path — no LLM, no live FX HTTP. Uses amounts snapshotted at submit
(``amount_in_cap_currency``). Cross-currency lines with no stored conversion
are ``not_comparable``, never invented.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import text

from .policy_config_cap_compare import NORMALIZED_CURRENCY_AMOUNT

COUNTED_STATUSES = ("approved", "paid")


def _dec(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _status(
    cap_amount: Optional[float],
    claimed: Optional[float],
    comparable: bool,
) -> str:
    if cap_amount is None:
        return "no_cap"
    if not comparable:
        return "not_comparable"
    if claimed is None:
        return "within_budget"
    if float(claimed) <= float(cap_amount):
        return "within_budget"
    return "over_budget"


def drawdown_for_case(
    conn: Any,
    case_id: str,
    caps: Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Return one drawdown row per published currency cap plus orphan claimed keys.

    Remaining = cap − Σ approved/paid ``amount_in_cap_currency`` when the line
    is comparable. Draft/submitted/rejected lines do not count.
    """
    caps_by_key: Dict[str, Dict[str, Any]] = {}
    for cap in caps or []:
        key = str(cap.get("benefit_key") or "").strip()
        if not key:
            continue
        ntype = cap.get("normalized_cap_type") or cap.get("cap_type")
        if ntype != NORMALIZED_CURRENCY_AMOUNT:
            continue
        amount = cap.get("normalized_amount")
        if amount is None:
            amount = cap.get("amount")
        caps_by_key[key] = {
            "benefit_key": key,
            "cap_amount": float(amount) if amount is not None else None,
            "currency": (cap.get("currency_code") or cap.get("currency") or "") or None,
            "name": cap.get("benefit_label") or cap.get("name") or key,
        }

    claimed_by_key: Dict[str, Dict[str, Any]] = {}
    try:
        rows = conn.execute(
            text(
                """
                SELECT l.benefit_key, l.amount, l.currency, l.cap_currency,
                       l.fx_rate_to_cap, l.amount_in_cap_currency
                FROM expense_claim_lines l
                JOIN expense_claims c ON c.id = l.claim_id
                WHERE c.case_id = :case_id AND c.status IN ('approved', 'paid')
                """
            ),
            {"case_id": case_id},
        ).mappings().all()
    except Exception:
        rows = []

    for row in rows:
        key = str(row.get("benefit_key") or "").strip()
        if not key:
            continue
        bucket = claimed_by_key.setdefault(
            key,
            {"claimed": Decimal("0"), "comparable": True, "currency": None},
        )
        cap_meta = caps_by_key.get(key)
        cap_ccy = (cap_meta or {}).get("currency")
        line_ccy = str(row.get("currency") or "").strip().upper() or None
        stored_ccy = str(row.get("cap_currency") or "").strip().upper() or None
        in_cap = _dec(row.get("amount_in_cap_currency"))
        rate = row.get("fx_rate_to_cap")

        if cap_meta is None:
            # Orphan key: still surface, never as a fabricated 0 remaining against a cap.
            if in_cap is not None:
                bucket["claimed"] += in_cap
            continue

        if cap_ccy and line_ccy and line_ccy != str(cap_ccy).upper():
            if in_cap is None or rate is None:
                bucket["comparable"] = False
                continue
            bucket["claimed"] += in_cap
            bucket["currency"] = cap_ccy
            continue

        # Same currency (or cap currency missing): prefer snapshotted amount, else raw.
        if in_cap is not None:
            bucket["claimed"] += in_cap
        else:
            raw = _dec(row.get("amount"))
            if raw is not None:
                bucket["claimed"] += raw
        bucket["currency"] = cap_ccy or stored_ccy or line_ccy

    keys = list(dict.fromkeys([*caps_by_key.keys(), *claimed_by_key.keys()]))
    out: List[Dict[str, Any]] = []
    for key in keys:
        cap_meta = caps_by_key.get(key)
        claimed_meta = claimed_by_key.get(key) or {
            "claimed": Decimal("0"),
            "comparable": True,
            "currency": None,
        }
        cap_amount = cap_meta["cap_amount"] if cap_meta else None
        comparable = bool(claimed_meta["comparable"]) if cap_meta else False
        claimed_f: Optional[float]
        if not claimed_by_key.get(key):
            claimed_f = 0.0 if cap_meta else None
            comparable = True if cap_meta else False
        else:
            claimed_f = float(claimed_meta["claimed"])
        remaining: Optional[float] = None
        if cap_amount is not None and comparable and claimed_f is not None:
            remaining = float(Decimal(str(cap_amount)) - Decimal(str(claimed_f)))
        out.append(
            {
                "benefit_key": key,
                "name": (cap_meta or {}).get("name") or key,
                "cap_amount": cap_amount,
                "currency": (cap_meta or {}).get("currency")
                or claimed_meta.get("currency"),
                "claimed_approved": claimed_f,
                "remaining": remaining,
                "status": _status(cap_amount, claimed_f, comparable if cap_meta else False),
            }
        )
    return out
