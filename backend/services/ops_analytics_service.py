"""
Ops Analytics Service: SLA, queue, reviewer, destination, and notification metrics.
Admin-only. Used by the SLA reporting dashboard.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .supabase_client import get_supabase_admin_client


def _get_supabase():
    return get_supabase_admin_client()


def _parse_dt(s: Optional[str]):
    if not s:
        return None
    try:
        return datetime.fromisoformat((s or "").replace("Z", "+00:00"))
    except Exception:
        return None


def get_sla_overview(
    country_code: Optional[str] = None,
    days: int = 30,
) -> Dict[str, Any]:
    """SLA overview KPIs for review queue items."""
    supabase = _get_supabase()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    items = (
        supabase.table("review_queue_items")
        .select("id, status, priority_band, created_at, assigned_at, resolved_at, sla_target_at, trust_tier")
        .gte("created_at", since)
        .execute()
    ).data or []

    open_items = (
        supabase.table("review_queue_items")
        .select("id, country_code, sla_target_at, due_at, status, resolved_at, priority_band")
        .in_("status", ["new", "triaged", "assigned", "in_progress", "blocked", "waiting"])
        .execute()
    ).data or []

    if country_code:
        items = [i for i in items if i.get("country_code") == country_code]
        open_items = [i for i in open_items if i.get("country_code") == country_code]

    now = datetime.now(timezone.utc)
    resolved = [i for i in items if i.get("status") in ("resolved", "rejected")]

    times_to_resolve: List[float] = []
    for i in resolved:
        created = _parse_dt(i.get("created_at"))
        resolved_dt = _parse_dt(i.get("resolved_at"))
        if created and resolved_dt:
            times_to_resolve.append((resolved_dt - created).total_seconds() / 3600)

    overdue_count = 0
    breached_count = 0
    for i in open_items:
        sla = _parse_dt(i.get("sla_target_at") or i.get("due_at"))
        if sla and now > sla:
            overdue_count += 1
            breached_count += 1

    for i in resolved:
        sla = _parse_dt(i.get("sla_target_at"))
        if sla:
            res = _parse_dt(i.get("resolved_at"))
            if res and res > sla:
                breached_count += 1

    total_with_sla = len([i for i in items if i.get("sla_target_at")])
    on_time = total_with_sla - breached_count if total_with_sla else 0
    on_time_rate = (on_time / total_with_sla * 100) if total_with_sla else 100

    times_to_assign: List[float] = []
    for i in resolved:
        created = _parse_dt(i.get("created_at"))
        assigned = _parse_dt(i.get("assigned_at"))
        if created and assigned:
            times_to_assign.append((assigned - created).total_seconds() / 3600)

    avg_resolve = sum(times_to_resolve) / len(times_to_resolve) if times_to_resolve else 0
    avg_assign = sum(times_to_assign) / len(times_to_assign) if times_to_assign else 0

    critical_resolved = len([i for i in resolved if i.get("priority_band") == "critical"])
    critical_breached = 0
    for i in open_items:
        if i.get("priority_band") == "critical":
            sla = _parse_dt(i.get("sla_target_at") or i.get("due_at"))
            if sla and now > sla:
                critical_breached += 1
    for i in resolved:
        if i.get("priority_band") == "critical":
            sla = _parse_dt(i.get("sla_target_at"))
            res_dt = _parse_dt(i.get("resolved_at"))
            if sla and res_dt and res_dt > sla:
                critical_breached += 1

    return {
        "open_count": len(open_items),
        "overdue_count": overdue_count,
        "breached_count": breached_count,
        "on_time_resolution_rate_pct": round(on_time_rate, 1),
        "avg_time_to_assign_hours": round(avg_assign, 2),
        "avg_time_to_resolve_hours": round(avg_resolve, 2),
        "resolved_count": len(resolved),
        "created_count": len(items),
        "critical_resolved": critical_resolved,
        "critical_breach_count": critical_breached,
    }


def get_queue_backlog(
    country_code: Optional[str] = None,
) -> Dict[str, Any]:
    """Queue backlog metrics by status and priority."""
    supabase = _get_supabase()
    q = (
        supabase.table("review_queue_items")
        .select("id, status, priority_band, queue_item_type, created_at")
        .in_("status", ["new", "triaged", "assigned", "in_progress", "blocked", "waiting"])
    )
    if country_code:
        q = q.eq("country_code", country_code)
    items = q.execute().data or []

    by_status: Dict[str, int] = {}
    by_priority: Dict[str, int] = {}
    by_type: Dict[str, int] = {}
    for i in items:
        s = i.get("status", "unknown")
        by_status[s] = by_status.get(s, 0) + 1
        p = i.get("priority_band", "medium")
        by_priority[p] = by_priority.get(p, 0) + 1
        t = i.get("queue_item_type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1

    return {
        "total": len(items),
        "by_status": by_status,
        "by_priority": by_priority,
        "by_queue_item_type": by_type,
    }


def get_queue_breaches(
    country_code: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """List queue items that have breached SLA (open past due/sla_target)."""
    supabase = _get_supabase()
    now = datetime.now(timezone.utc)
    q = (
        supabase.table("review_queue_items")
        .select("*")
        .in_("status", ["new", "triaged", "assigned", "in_progress", "blocked", "waiting"])
        .limit(limit * 2)
    )
    if country_code:
        q = q.eq("country_code", country_code)
    all_items = q.execute().data or []
    breached = []
    for i in all_items:
        sla = _parse_dt(i.get("sla_target_at") or i.get("due_at"))
        if sla and now > sla:
            breached.append(i)
            if len(breached) >= limit:
                break
    return {"items": breached, "total": len(breached)}


def get_reviewer_workload() -> Dict[str, Any]:
    """Workload by assignee."""
    supabase = _get_supabase()
    items = (
        supabase.table("review_queue_items")
        .select("id, assigned_to_user_id, status, priority_band, due_at")
        .in_("status", ["assigned", "in_progress", "blocked", "waiting"])
        .execute()
    ).data or []

    by_assignee: Dict[str, Dict[str, Any]] = {}
    now = datetime.now(timezone.utc)
    for i in items:
        aid = i.get("assigned_to_user_id") or "_unassigned"
        if aid not in by_assignee:
            by_assignee[aid] = {"total": 0, "in_progress": 0, "blocked": 0, "overdue": 0, "critical": 0}
        by_assignee[aid]["total"] += 1
        if i.get("status") == "in_progress":
            by_assignee[aid]["in_progress"] += 1
        if i.get("status") == "blocked":
            by_assignee[aid]["blocked"] += 1
        if i.get("priority_band") == "critical":
            by_assignee[aid]["critical"] += 1
        due = _parse_dt(i.get("due_at"))
        if due and now > due:
            by_assignee[aid]["overdue"] += 1

    return {"by_assignee": by_assignee}


def get_destination_ops_metrics() -> Dict[str, Any]:
    """Metrics by country/city."""
    supabase = _get_supabase()
    items = (
        supabase.table("review_queue_items")
        .select("id, country_code, city_name, status, priority_band")
        .in_("status", ["new", "triaged", "assigned", "in_progress", "blocked", "waiting"])
        .execute()
    ).data or []

    by_dest: Dict[str, Dict[str, Any]] = {}
    for i in items:
        key = f"{i.get('country_code') or 'unknown'}:{i.get('city_name') or ''}"
        if key not in by_dest:
            by_dest[key] = {"country_code": i.get("country_code"), "city_name": i.get("city_name"), "total": 0, "critical": 0}
        by_dest[key]["total"] += 1
        if i.get("priority_band") == "critical":
            by_dest[key]["critical"] += 1

    return {"items": list(by_dest.values())}


def get_notification_ops_metrics(days: int = 7) -> Dict[str, Any]:
    """Notification metrics."""
    supabase = _get_supabase()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    items = (
        supabase.table("ops_notifications")
        .select("id, status, severity, notification_type, created_at, acknowledged_at, resolved_at")
        .gte("created_at", since)
        .execute()
    ).data or []

    by_type: Dict[str, int] = {}
    open_count = 0
    resolved_count = 0
    for i in items:
        t = i.get("notification_type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1
        if i.get("status") in ("open", "acknowledged"):
            open_count += 1
        elif i.get("status") == "resolved":
            resolved_count += 1

    return {
        "created_count": len(items),
        "open_count": open_count,
        "resolved_count": resolved_count,
        "by_type": by_type,
    }


def get_ops_bottlenecks() -> Dict[str, Any]:
    """Identify operational bottlenecks."""
    backlog = get_queue_backlog()
    by_dest = get_destination_ops_metrics()
    items = by_dest.get("items", [])
    top_dest = max(items, key=lambda x: x.get("total", 0)) if items else None

    return {
        "top_backlog_destination": top_dest,
        "total_backlog": backlog.get("total", 0),
        "unassigned_count": backlog.get("by_status", {}).get("new", 0) + backlog.get("by_status", {}).get("triaged", 0),
    }


# Common country-name → ISO 3166-1 alpha-2 mapping. Covers the names we see
# in Supabase `case_assignments.destination_country` (full names like
# "Germany") so the API always returns a canonical 2-letter code the frontend
# can pass to flagcdn.com.
_COUNTRY_NAME_TO_ISO2: Dict[str, str] = {
    # Europe
    "norway": "NO", "germany": "DE", "france": "FR", "spain": "ES", "italy": "IT",
    "netherlands": "NL", "the netherlands": "NL", "holland": "NL",
    "united kingdom": "GB", "uk": "GB", "great britain": "GB", "britain": "GB", "england": "GB",
    "ireland": "IE", "belgium": "BE", "luxembourg": "LU",
    "switzerland": "CH", "austria": "AT", "denmark": "DK", "sweden": "SE", "finland": "FI",
    "iceland": "IS", "poland": "PL", "portugal": "PT", "greece": "GR", "czech republic": "CZ",
    "czechia": "CZ", "slovakia": "SK", "hungary": "HU", "romania": "RO", "bulgaria": "BG",
    "croatia": "HR", "slovenia": "SI", "estonia": "EE", "latvia": "LV", "lithuania": "LT",
    "ukraine": "UA", "turkey": "TR", "türkiye": "TR", "russia": "RU", "cyprus": "CY",
    "malta": "MT", "serbia": "RS",
    # Americas
    "united states": "US", "united states of america": "US", "usa": "US", "u.s.": "US", "u.s.a.": "US",
    "america": "US",
    "canada": "CA", "mexico": "MX", "brazil": "BR", "argentina": "AR", "chile": "CL",
    "colombia": "CO", "peru": "PE", "uruguay": "UY", "costa rica": "CR", "panama": "PA",
    # Asia / Pacific
    "japan": "JP", "china": "CN", "south korea": "KR", "korea": "KR", "republic of korea": "KR",
    "north korea": "KP", "india": "IN", "pakistan": "PK", "bangladesh": "BD", "sri lanka": "LK",
    "singapore": "SG", "malaysia": "MY", "indonesia": "ID", "thailand": "TH", "vietnam": "VN",
    "philippines": "PH", "hong kong": "HK", "taiwan": "TW", "australia": "AU", "new zealand": "NZ",
    "israel": "IL", "saudi arabia": "SA", "uae": "AE", "united arab emirates": "AE",
    "qatar": "QA", "kuwait": "KW", "bahrain": "BH", "oman": "OM", "jordan": "JO",
    "lebanon": "LB", "egypt": "EG",
    # Africa
    "south africa": "ZA", "morocco": "MA", "tunisia": "TN", "kenya": "KE", "nigeria": "NG",
    "ghana": "GH", "ethiopia": "ET",
}


def _normalize_country_to_iso2(raw: Optional[str]) -> Optional[str]:
    """Normalize a country string to an ISO 3166-1 alpha-2 code.

    Accepts already-canonical codes ("DE", "de"), full names ("Germany",
    "United States"), or 3-letter codes (best-effort by stripping the trailing
    char). Returns None when input is empty/unmappable so the caller can
    decide whether to drop the row or keep the raw value.
    """
    if not raw:
        return None
    s = raw.strip()
    if not s:
        return None
    # Already 2-letter code (case-insensitive).
    if len(s) == 2 and s.isalpha():
        return s.upper()
    lower = s.lower()
    if lower in _COUNTRY_NAME_TO_ISO2:
        return _COUNTRY_NAME_TO_ISO2[lower]
    # 3-letter (alpha-3) — not standard ISO mapping, but a few common cases.
    alpha3 = {
        "deu": "DE", "fra": "FR", "esp": "ES", "ita": "IT", "gbr": "GB",
        "usa": "US", "can": "CA", "mex": "MX", "bra": "BR", "nor": "NO",
        "swe": "SE", "fin": "FI", "dnk": "DK", "nld": "NL", "che": "CH",
        "aut": "AT", "bel": "BE", "irl": "IE", "prt": "PT", "pol": "PL",
        "jpn": "JP", "chn": "CN", "kor": "KR", "ind": "IN", "sgp": "SG",
        "aus": "AU", "nzl": "NZ", "are": "AE", "sau": "SA", "zaf": "ZA",
    }
    if len(s) == 3 and lower in alpha3:
        return alpha3[lower]
    return None


def get_top_destinations_by_request(limit: int = 5) -> Dict[str, Any]:
    """Top destination countries selected by users across all relocation requests.

    Sources `destination_country` from Supabase `case_assignments` — the
    canonical store for relocation requests. Falls back to the local
    `relocation_cases.host_country` for environments where Supabase isn't
    populated (dev), so the card still has data when running off SQLite.

    All raw values are normalized to ISO 3166-1 alpha-2 codes so the frontend
    can render a flag without worrying about whether the row stored "Germany"
    or "DE". Unrecognized values are kept as an uppercased raw string so they
    still appear in the list (the frontend falls back to a generic globe).

    Returns the top `limit` countries ordered by request volume.
    """
    counts: Dict[str, int] = {}

    def _add(raw: Optional[str]) -> None:
        iso = _normalize_country_to_iso2(raw)
        if iso:
            counts[iso] = counts.get(iso, 0) + 1
            return
        # Keep unmappable rows so the card isn't silently lossy — just label
        # them with the raw value (uppercased) and let the UI render a globe.
        key = (raw or "").strip().upper()
        if key:
            counts[key] = counts.get(key, 0) + 1

    # Primary source: Supabase case_assignments.
    try:
        supabase = _get_supabase()
        page = (
            supabase.table("case_assignments")
            .select("destination_country")
            .neq("status", "archived")
            .limit(10000)
            .execute()
        )
        for row in (page.data or []):
            _add(row.get("destination_country"))
    except Exception:
        # Swallow — fall back to local DB below.
        pass

    # Fallback: local relocation_cases (dev environments without Supabase data).
    if not counts:
        try:
            from ..database import db  # type: ignore
            assignments = db.list_admin_assignments(status=None) or []
            for a in assignments:
                _add(a.get("destination_country") or a.get("host_country"))
        except Exception:
            pass

    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    items = [{"country_code": code, "total": cnt} for code, cnt in ranked[:limit]]
    return {
        "items": items,
        "total_requests": sum(counts.values()),
        "unique_countries": len(counts),
    }
