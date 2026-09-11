"""[AIQ-2271] Authoring-layer FX snapshot writer.

Fetches public ECB rates via Frankfurter (EU-hosted, no API key, no PII) and
upserts ``fx_rates`` as a dated USD-cross table matching ``fx_service.USD_TO``.

Must NEVER be imported from the serving/drawdown path — only from cron.
"""
from __future__ import annotations

import json
import logging
import uuid
import urllib.request
from datetime import date
from typing import Any, Dict, Optional

from sqlalchemy import text

from .fx_service import USD_TO

log = logging.getLogger(__name__)

FRANKFURTER_URL = "https://api.frankfurter.app/latest?from=USD"
_TIMEOUT_SEC = 15


def fetch_usd_rates(url: str = FRANKFURTER_URL) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "ReloPass-fx-refresh/1.0"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT_SEC) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload


def persist_usd_snapshot(conn: Any, payload: Dict[str, Any], source: str = "frankfurter") -> int:
    """Write 1 USD = rate quote rows. Idempotent on (as_of_date, USD, quote)."""
    as_of_raw = payload.get("date") or date.today().isoformat()
    as_of = str(as_of_raw)[:10]
    rates = payload.get("rates") or {}
    if not isinstance(rates, dict):
        rates = {}
    merged = {**{k: float(v) for k, v in USD_TO.items() if k != "USD"}}
    for code, value in rates.items():
        try:
            merged[str(code).upper()] = float(value)
        except (TypeError, ValueError):
            continue
    merged["USD"] = 1.0
    written = 0
    for quote, rate in merged.items():
        conn.execute(
            text(
                """
                INSERT INTO fx_rates (id, as_of_date, base_currency, quote_currency, rate, source)
                VALUES (:id, :d, 'USD', :q, :r, :src)
                ON CONFLICT (as_of_date, base_currency, quote_currency)
                DO UPDATE SET rate = excluded.rate, source = excluded.source
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "d": as_of,
                "q": quote,
                "r": rate,
                "src": source,
            },
        )
        written += 1
    return written


def refresh_fx_rates(conn: Any, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Fetch (unless payload given) and persist. ``payload`` keeps tests offline."""
    fetched = payload if payload is not None else fetch_usd_rates()
    count = persist_usd_snapshot(conn, fetched)
    return {
        "ok": True,
        "as_of": str(fetched.get("date") or "")[:10],
        "rows": count,
        "source": "frankfurter" if payload is None else "injected",
    }
