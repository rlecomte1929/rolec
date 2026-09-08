"""AIQ-1516 — best-value recommendation for an RFQ's quotes.

HR is the payer. The employee ran the RFQ; HR sees every offer and validates one. This produces
the recommendation HR reads before signing: a NARRATIVE, never a bare score, grounded ONLY in
signals that actually exist for the quotes in hand. When a signal has no data, its weight is zero
and the narrative says so — we never impute a number nobody quoted.

What the data model actually supports (verified 2026-07-15):
  * PRICE   — quotes.total_amount + currency, compared to vendor_metric_snapshots.avg_cost_eur.
  * QUALITY — vendor_metric_snapshots.avg_rating × log10(review_count+1), when review_count >= 5.
  * CAP     — the policy cap for the service (passed in; already computed for the HR cap view).
  * DELIVERY / budget-variance — assignment_outcomes, currently 0 rows -> omitted, degrade to LOW.

What it deliberately does NOT do: per-line scope coverage. quote_lines carry no rfq_item_id, so
"quote B is missing the customs-clearance line" cannot be determined honestly. Comparability is
therefore total-level only (currency + presence of a total); the coarse line-vs-item verdict already
shown on the HR cap view is the honest ceiling.

This module is a PURE function over already-fetched rows so it is trivially testable and cannot
touch the DB. The caller fetches quotes, snapshots, and the cap and passes them in.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

# Confidence levels, most→least trustworthy.
HIGH = "HIGH"
MEDIUM = "MEDIUM"
LOW = "LOW"
REFUSED = "REFUSED"

_QUALITY_MIN_REVIEWS = 5  # below this, review-based quality is noise — treat as absent.


def _to_float(v: Any) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _quality_index(avg_rating: Optional[float], review_count: Optional[int]) -> Optional[float]:
    """avg_rating (0–5 or 0–100) normalised × log10(reviews+1). None when reviews are too few."""
    if avg_rating is None or not review_count or review_count < _QUALITY_MIN_REVIEWS:
        return None
    # snapshots store avg_rating on a 0–5 scale; normalise defensively if a 0–100 slips in.
    norm = avg_rating / 100.0 if avg_rating > 5 else avg_rating / 5.0
    return norm * math.log10(review_count + 1)


def recommend(
    quotes: List[Dict[str, Any]],
    snapshot_by_vendor: Dict[str, Dict[str, Any]],
    *,
    cap_amount: Optional[float] = None,
) -> Dict[str, Any]:
    """Return a recommendation snapshot for the quotes of one RFQ.

    quotes: rows from list_quotes_for_rfq (need id, vendor_id, total_amount, currency, and an
            optional supplier_name).
    snapshot_by_vendor: vendor_id -> the latest vendor_metric_snapshots row (avg_cost_eur,
            avg_rating, review_count) for this service. Missing vendor => no price/quality signal.
    cap_amount: the policy cap for the service in the quote currency, or None.

    Shape: {recommended_quote_id, confidence, headline, reasons[], trade_offs[], refused_reason?}.
    Every reason cites its source. Never a bare score.
    """
    priced = [q for q in quotes if _to_float(q.get("total_amount")) is not None]

    # --- Comparability gate (total-level; scope coverage is not knowable — see module docstring) ---
    if not priced:
        return _refuse("No quote carries a total amount to compare.")

    currencies = {(q.get("currency") or "").upper() for q in priced}
    if len(currencies) > 1:
        return _refuse(
            "Currency mismatch across offers ("
            + ", ".join(sorted(c for c in currencies if c))
            + ") with no exchange rate — ranking by price would be misleading."
        )

    # --- Single comparable offer: no comparison possible ---
    if len(priced) == 1:
        q = priced[0]
        return {
            "recommended_quote_id": q.get("id"),
            "confidence": LOW,
            "headline": f"Only one offer received ({_name(q)}) — no comparison possible.",
            "reasons": [f"{_name(q)} quoted {_money(q)} (quotes.total_amount)."],
            "trade_offs": ["No competing offer to weigh this against."],
        }

    # --- Score each comparable offer on the signals that exist ---
    scored = []
    any_quality = False
    for q in priced:
        total = _to_float(q.get("total_amount"))
        snap = snapshot_by_vendor.get(str(q.get("vendor_id"))) or {}
        bench = _to_float(snap.get("avg_cost_eur"))
        qi = _quality_index(_to_float(snap.get("avg_rating")), snap.get("review_count"))
        if qi is not None:
            any_quality = True
        # price signal: cheaper vs the field, and vs market benchmark when we have one.
        price_vs_bench = None if bench in (None, 0) else (bench - total) / bench * 100.0
        scored.append({"q": q, "total": total, "bench": bench,
                       "price_vs_bench": price_vs_bench, "quality": qi})

    cheapest = min(scored, key=lambda s: s["total"])

    # Winner: best composite of price (always) + quality (when present). We keep it explainable —
    # rank by price, then let a clear quality edge break a near-tie. No hidden number is surfaced.
    def _key(s: Dict[str, Any]):
        return (s["total"], -(s["quality"] or 0.0))

    winner = sorted(scored, key=_key)[0]
    q = winner["q"]

    reasons: List[str] = []
    reasons.append(f"{_name(q)} quoted {_money(q)} — "
                   + ("the lowest total" if winner is cheapest else "competitive on price")
                   + " (quotes.total_amount).")
    trade_offs: List[str] = []
    if winner["price_vs_bench"] is not None:
        pct = winner["price_vs_bench"]
        bench_txt = (f"the market benchmark of {winner['bench']:.0f} EUR "
                     "(vendor_metric_snapshots.avg_cost_eur)")
        # Below/at market is a reason FOR the pick; above market is a trade-off AGAINST it —
        # never dress an above-benchmark price up as a positive.
        if pct >= 0:
            reasons.append(f"{pct:.0f}% below {bench_txt}.")
        else:
            trade_offs.append(f"{abs(pct):.0f}% above {bench_txt}.")
    if winner["quality"] is not None:
        snap = snapshot_by_vendor.get(str(q.get("vendor_id"))) or {}
        reasons.append(f"Rated {snap.get('avg_rating')} over {snap.get('review_count')} reviews "
                       f"(vendor_metric_snapshots).")

    if winner is not cheapest:
        trade_offs.append(f"{_name(cheapest['q'])} is cheaper at {_money(cheapest['q'])}, "
                          "but scored lower on the available signals.")
    if not any_quality:
        trade_offs.append("Quality signals unavailable for these suppliers — price is the only "
                          "comparable signal.")
    if cap_amount is not None and winner["total"] is not None and winner["total"] > cap_amount:
        trade_offs.append(f"Over the policy cap by {winner['total'] - cap_amount:.0f} "
                          f"{(q.get('currency') or 'EUR')} — HR may override with a reason.")

    # Confidence: price+quality present -> MEDIUM (no delivery data yet keeps us off HIGH);
    # price only -> LOW, said plainly.
    if any_quality:
        confidence = MEDIUM
    else:
        confidence = LOW
        reasons.append("Quality and delivery history are unavailable — this ranking rests on "
                       "price alone.")

    headline = f"{_name(q)} is the best-value offer at {_money(q)}"
    if winner["price_vs_bench"] is not None and winner["price_vs_bench"] > 0:
        headline += f", {winner['price_vs_bench']:.0f}% below market"
    headline += "."

    return {
        "recommended_quote_id": q.get("id"),
        "confidence": confidence,
        "headline": headline,
        "reasons": reasons,
        "trade_offs": trade_offs,
    }


def _refuse(reason: str) -> Dict[str, Any]:
    return {
        "recommended_quote_id": None,
        "confidence": REFUSED,
        "headline": "Ranking not possible.",
        "reasons": [],
        "trade_offs": [],
        "refused_reason": reason,
    }


def _name(q: Dict[str, Any]) -> str:
    return q.get("supplier_name") or q.get("vendor_name") or str(q.get("vendor_id") or "A supplier")


def _money(q: Dict[str, Any]) -> str:
    total = _to_float(q.get("total_amount"))
    cur = (q.get("currency") or "EUR").upper()
    return f"{total:.0f} {cur}" if total is not None else f"— {cur}"
