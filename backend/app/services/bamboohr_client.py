"""
BambooHR API v1 client.  (AIQ-38-A / AIQ-38-B)

Auth: HTTP Basic — base64("{api_key}:x") in the Authorization header.
      BambooHR ignores the password field; "x" is the conventional placeholder.

Base URL: https://api.bamboohr.com/api/gateway.php/{subdomain}/v1/

Rate limit: BambooHR enforces ~100 req/min and 1 000 req/day per API key.
  - Full sync (fetch_employees): 1 req per 200 employees.
  - Incremental sync (fetch_changed_employees): 1 req for IDs + 1 req per changed
    employee.  At 10-min polling with typical small-company churn, this stays well
    inside the 1 000 req/day budget.
  - We apply a 0.6-second inter-page delay and a 60-second back-off on 429.
"""
from __future__ import annotations

import base64
import logging
import time
from typing import Any, Dict, List, Optional

import requests as http_requests

log = logging.getLogger(__name__)

_RATE_LIMIT_DELAY = 0.6   # seconds between paginated calls
_REQUEST_TIMEOUT  = 15    # seconds per request


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

def _basic_auth_header(api_key: str) -> str:
    """Return the Authorization header value for BambooHR Basic Auth."""
    credentials = base64.b64encode(f"{api_key}:x".encode()).decode()
    return f"Basic {credentials}"


def _common_headers(api_key: str) -> Dict[str, str]:
    return {
        "Authorization": _basic_auth_header(api_key),
        "Accept":        "application/json",
        "User-Agent":    "ReloPass/1.0",
    }


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

def test_connection(api_key: str, subdomain: str) -> bool:
    """
    Return True if the credentials are valid.

    Calls GET /employees/directory?limit=1 — the lightest authenticated
    endpoint available.  Returns False (does not raise) on auth failure
    so callers can return a clean 400 to the frontend.
    """
    url = f"https://api.bamboohr.com/api/gateway.php/{subdomain}/v1/employees/directory"
    try:
        resp = http_requests.get(
            url,
            headers=_common_headers(api_key),
            params={"limit": 1},
            timeout=_REQUEST_TIMEOUT,
        )
        if resp.status_code in (200, 206):
            return True
        log.warning(
            "[bamboohr] test_connection failed: subdomain=%s status=%s",
            subdomain, resp.status_code,
        )
        return False
    except http_requests.RequestException as exc:
        log.error("[bamboohr] test_connection request error: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Employee fetch
# ---------------------------------------------------------------------------

def fetch_employees(
    api_key: str,
    subdomain: str,
    fields: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch all employees via the BambooHR employee directory endpoint.

    BambooHR does not support server-side filtering by updated_since on the
    directory endpoint; we fetch all and let the caller diff if needed.

    Returns a flat list of employee dicts.
    """
    if fields is None:
        fields = [
            "id", "firstName", "lastName", "workEmail",
            "hireDate", "department", "location",
            "country", "nationality",
        ]

    url = (
        f"https://api.bamboohr.com/api/gateway.php"
        f"/{subdomain}/v1/employees/directory"
    )
    employees: List[Dict[str, Any]] = []
    page = 1

    while True:
        params: Dict[str, Any] = {
            "fields": ",".join(fields),
            "limit":  200,
            "offset": (page - 1) * 200,
        }

        try:
            resp = http_requests.get(
                url,
                headers=_common_headers(api_key),
                params=params,
                timeout=_REQUEST_TIMEOUT,
            )
        except http_requests.RequestException as exc:
            log.error("[bamboohr] fetch_employees request error: %s", exc)
            break

        if resp.status_code == 429:
            log.warning("[bamboohr] Rate-limited — backing off 60 s")
            time.sleep(60)
            continue   # retry same page

        if not resp.ok:
            log.error(
                "[bamboohr] employees API %s: %s",
                resp.status_code, resp.text[:200],
            )
            break

        data  = resp.json()
        batch = data.get("employees", [])
        employees.extend(batch)

        # BambooHR returns totalCount in the envelope; stop when we have all.
        total = data.get("totalCount", len(employees))
        if len(employees) >= int(total) or len(batch) < 200:
            break

        page += 1
        time.sleep(_RATE_LIMIT_DELAY)

    return employees


# ---------------------------------------------------------------------------
# Relocation flag
# ---------------------------------------------------------------------------

def is_relocation_required(employee: Dict[str, Any]) -> bool:
    """
    Return True when the employee should trigger a draft relocation case.

    BambooHR has no standard "relocation_required" field; we check for a
    custom field by convention ('customRelocationRequired') and fall back
    to a non-empty 'customRelocationStatus' value.
    """
    flag = (employee.get("customRelocationRequired") or "").strip().lower()
    if flag in ("yes", "true", "1"):
        return True
    status = (employee.get("customRelocationStatus") or "").strip()
    return bool(status)


def extract_fields(employee: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise a BambooHR employee record into ReloPass-friendly fields."""
    return {
        "bamboohr_id":        str(employee.get("id", "")),
        "first_name":         employee.get("firstName") or "",
        "last_name":          employee.get("lastName") or "",
        "email":              employee.get("workEmail") or "",
        "start_date":         employee.get("hireDate"),
        "nationality":        employee.get("nationality"),
        "destination_office": employee.get("location"),
        "home_country":       employee.get("country") or "",
        "host_country":       employee.get("location") or "",
    }


# ---------------------------------------------------------------------------
# Incremental sync helpers  (AIQ-38-B)
# ---------------------------------------------------------------------------

_INCREMENTAL_FIELDS = [
    "id", "firstName", "lastName", "workEmail",
    "hireDate", "department", "location",
    "country", "nationality",
    "customRelocationRequired", "customRelocationStatus",
]


def fetch_changed_employee_ids(
    api_key: str,
    subdomain: str,
    since: str,
) -> List[str]:
    """
    Return a list of employee IDs that changed since *since* (ISO 8601).

    Calls GET /employees/changed?since=<since>&type=inserted,updated
    BambooHR returns a flat ``{"employees": [{"id": "123"}, ...]}`` envelope.

    Returns an empty list on any error so the caller can fall back to a
    full fetch.
    """
    url = (
        f"https://api.bamboohr.com/api/gateway.php"
        f"/{subdomain}/v1/employees/changed"
    )
    try:
        resp = http_requests.get(
            url,
            headers=_common_headers(api_key),
            params={"since": since, "type": "inserted,updated"},
            timeout=_REQUEST_TIMEOUT,
        )
    except http_requests.RequestException as exc:
        log.error("[bamboohr] fetch_changed_employee_ids request error: %s", exc)
        return []

    if resp.status_code == 429:
        log.warning("[bamboohr] Rate-limited on /employees/changed — returning []")
        return []

    if not resp.ok:
        log.error(
            "[bamboohr] /employees/changed %s: %s",
            resp.status_code, resp.text[:200],
        )
        return []

    data = resp.json()
    # The response wraps IDs in {"employees": [{"id": "123"}, ...]}
    employees = data.get("employees") or []
    return [str(e["id"]) for e in employees if e.get("id")]


def fetch_employee_by_id(
    api_key: str,
    subdomain: str,
    emp_id: str,
    fields: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Fetch a single employee by BambooHR ID.

    Calls GET /employees/{id}?fields=...
    Returns None on 404 or any error.
    """
    if fields is None:
        fields = _INCREMENTAL_FIELDS

    url = (
        f"https://api.bamboohr.com/api/gateway.php"
        f"/{subdomain}/v1/employees/{emp_id}"
    )
    try:
        resp = http_requests.get(
            url,
            headers=_common_headers(api_key),
            params={"fields": ",".join(fields)},
            timeout=_REQUEST_TIMEOUT,
        )
    except http_requests.RequestException as exc:
        log.error("[bamboohr] fetch_employee_by_id(%s) request error: %s", emp_id, exc)
        return None

    if resp.status_code == 404:
        log.debug("[bamboohr] employee %s not found", emp_id)
        return None

    if resp.status_code == 429:
        log.warning("[bamboohr] Rate-limited fetching employee %s — backing off 60 s", emp_id)
        time.sleep(60)
        # One retry
        try:
            resp = http_requests.get(
                url,
                headers=_common_headers(api_key),
                params={"fields": ",".join(fields)},
                timeout=_REQUEST_TIMEOUT,
            )
            if not resp.ok:
                return None
        except http_requests.RequestException:
            return None

    if not resp.ok:
        log.error(
            "[bamboohr] fetch_employee_by_id(%s) %s: %s",
            emp_id, resp.status_code, resp.text[:200],
        )
        return None

    return resp.json()


def fetch_changed_employees(
    api_key: str,
    subdomain: str,
    since: str,
    fields: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Incremental sync: return full employee records for all employees that
    changed since *since* (ISO 8601 datetime string).

    Two-step:
      1. GET /employees/changed?since=<since> → list of IDs
      2. GET /employees/{id}?fields=... for each ID

    Rate-limit budget: 1 (changed-IDs call) + N (employee detail calls).
    At 10-min polling cadence and typical SME churn, this stays within
    the 1 000 req/day BambooHR limit.  A 0.6 s inter-request delay
    keeps the per-minute rate safe.

    Falls back to an empty list on error (caller should decide whether
    to fall back to a full fetch or skip the cycle).
    """
    ids = fetch_changed_employee_ids(api_key, subdomain, since)
    if not ids:
        return []

    log.info("[bamboohr] %d employees changed since %s", len(ids), since)

    employees: List[Dict[str, Any]] = []
    for emp_id in ids:
        emp = fetch_employee_by_id(api_key, subdomain, emp_id, fields)
        if emp:
            employees.append(emp)
        time.sleep(_RATE_LIMIT_DELAY)

    return employees
