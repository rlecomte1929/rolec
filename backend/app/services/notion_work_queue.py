"""notion_work_queue.py — create an AI Work Queue page in Notion from an
engineered feedback task.

Mirrors the NOTION_TOKEN + urllib pattern in routers/support.py, adding
POST /v1/pages. Requires the backend Notion integration to be shared with the
AI Work Queue database and NOTION_WORK_QUEUE_DB set (defaults to the known id).
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from .feedback_task_engineer import _TIER_LABELS

_NOTION_PAGES_API = "https://api.notion.com/v1/pages"
_NOTION_VERSION = "2022-06-28"
# AI Work Queue. NOTE (DB-id reconciliation): this database id `7adc643a…` and the
# `75d7ed78…` the autofix Edge Function uses as NOTION_DATABASE_ID are the SAME database —
# `75d7ed78…` is this database's data-source/collection id. Page-create (parent.database_id
# = 7adc643a…) and the edge fn's /databases/75d7ed78…/query both resolve to one queue, so
# tasks the backend dispatches ARE the tasks the pipeline fixes. Keep both ids pointing here.
_DEFAULT_DB = "7adc643a-c448-4a1a-ba80-e27e417f42d6"
_MAX_CHUNK = 1900  # Notion caps a single text object at 2000 chars

# Final Validation Result select options (must match the Notion DB exactly).
VALIDATION_RESULTS = ("Pending", "Passed", "Partial", "Failed")


class NotionNotConfigured(RuntimeError):
    """NOTION_TOKEN missing — the create call cannot proceed."""


class NotionApiError(RuntimeError):
    """Notion API returned an error (surfaced to the admin, never a silent 500)."""


def _rich(text: Optional[str]) -> Dict[str, Any]:
    text = (text or "").strip()
    if not text:
        return {"rich_text": []}
    chunks = [text[i:i + _MAX_CHUNK] for i in range(0, len(text), _MAX_CHUNK)]
    return {"rich_text": [{"text": {"content": c}} for c in chunks[:25]]}


def _select(name: Optional[str]) -> Dict[str, Any]:
    return {"select": {"name": name}} if name else {"select": None}


def build_properties(task: Dict[str, Any], *, failure_evidence: str, context_links: str) -> Dict[str, Any]:
    """Map an engineered task dict to AI Work Queue Notion properties.

    Split out so tests can assert the payload without a live Notion call.
    """
    return {
        "fable": {"title": [{"text": {"content": (task.get("title") or "Untitled feedback task")[:200]}}]},
        "Strategic Objective": _rich(task.get("strategic_objective")),
        "Execution Prompt": _rich(task.get("execution_prompt")),
        "Expected Output": _rich(task.get("expected_output")),
        "Validation Criteria": _rich(task.get("validation_criteria")),
        "Test Command": _rich(task.get("test_command")),
        "Technical Constraints": _rich(task.get("technical_constraints")),
        "Files to Touch": _rich(task.get("files_to_touch")),
        "Risk & Rollback": _rich(task.get("risk_rollback")),
        "Failure Evidence": _rich(failure_evidence),
        "Context Links": _rich(context_links),
        "Priority": _select(task.get("priority")),
        "Estimated Complexity": _select(task.get("complexity")),
        "Task Type": _select(task.get("task_type")),
        "Layer": _select(task.get("layer")),
        "Product Area": _select(task.get("product_area")),
        "Status": _select(task.get("status") or "Ready for AI"),
        "Definition of Ready": _select("Vetted — ready"),
        "Autonomy Tier": _select(_TIER_LABELS.get(task.get("autonomy_tier"))),
    }


def create_work_queue_task(task: Dict[str, Any], *, failure_evidence: str, context_links: str) -> str:
    """Create the Notion page and return its URL. Raises NotionNotConfigured or
    NotionApiError (both surfaced to the caller as a clear 4xx/5xx — never a
    silent success)."""
    token = os.getenv("NOTION_TOKEN", "").strip()
    if not token:
        raise NotionNotConfigured(
            "NOTION_TOKEN is not set — share the AI Work Queue DB with the backend "
            "Notion integration and set NOTION_TOKEN / NOTION_WORK_QUEUE_DB."
        )
    db_id = os.getenv("NOTION_WORK_QUEUE_DB", _DEFAULT_DB).strip() or _DEFAULT_DB

    payload = {
        "parent": {"database_id": db_id},
        "properties": build_properties(task, failure_evidence=failure_evidence, context_links=context_links),
    }
    req = urllib.request.Request(
        _NOTION_PAGES_API,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": _NOTION_VERSION,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:  # noqa: PERF203
        detail = exc.read().decode("utf-8", "replace")[:600]
        raise NotionApiError(f"Notion API {exc.code}: {detail}") from exc
    except Exception as exc:  # noqa: BLE001
        raise NotionApiError(f"Notion request failed: {exc}") from exc

    return data.get("url") or f"https://notion.so/{(data.get('id') or '').replace('-', '')}"


# ── Fix-trigger layer: read/flip a task's status by page id ───────────────────
# `dispatch_create` stores the Notion page URL as feedback_status.dispatch_ref but
# discards the page id. These helpers recover the id from the URL and let the
# "Trigger fix" / "Auto-attempt" endpoints read the task's fields and flip Status.


def _token() -> str:
    token = os.getenv("NOTION_TOKEN", "").strip()
    if not token:
        raise NotionNotConfigured(
            "NOTION_TOKEN is not set — share the AI Work Queue DB with the backend "
            "Notion integration and set NOTION_TOKEN / NOTION_WORK_QUEUE_DB."
        )
    return token


def _notion_api(method: str, url: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        method=method,
        headers={
            "Authorization": f"Bearer {_token()}",
            "Notion-Version": _NOTION_VERSION,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:600]
        raise NotionApiError(f"Notion API {exc.code}: {detail}") from exc
    except Exception as exc:  # noqa: BLE001
        raise NotionApiError(f"Notion request failed: {exc}") from exc


def page_id_from_ref(ref: Optional[str]) -> Optional[str]:
    """Recover a Notion page id (dashed uuid) from a stored dispatch_ref URL.

    Notion page URLs end in a 32-char dashless hex id (optionally after a slug);
    a raw id (dashed or not) is also accepted. Returns None if no id is present.
    """
    if not ref:
        return None
    tail = ref.split("?")[0].split("#")[0].rstrip("/").rsplit("/", 1)[-1]
    hexs = re.sub(r"[^0-9a-fA-F]", "", tail)
    if len(hexs) < 32:
        hexs = re.sub(r"[^0-9a-fA-F]", "", ref)
    if len(hexs) < 32:
        return None
    h = hexs[-32:]
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def get_task_meta(page_id: str) -> Dict[str, Optional[str]]:
    """Read the select fields + AIQ id of a Work Queue page (source of truth for
    the auto-attempt guard and the /relopass-dev-queue command)."""
    data = _notion_api("GET", f"{_NOTION_PAGES_API}/{page_id}")
    props = data.get("properties") or {}

    def _sel(name: str) -> Optional[str]:
        return ((props.get(name) or {}).get("select") or {}).get("name")

    uid = (props.get("ID") or {}).get("unique_id") or {}
    number = uid.get("number")
    aiq_id = f"{uid.get('prefix') or 'AIQ'}-{number}" if number is not None else None

    return {
        "status": _sel("Status"),
        "complexity": _sel("Estimated Complexity"),
        "autonomy_tier": _sel("Autonomy Tier"),
        "aiq_id": aiq_id,
        "url": data.get("url"),
    }


def set_task_status(page_id: str, status: str, notes: Optional[str] = None) -> None:
    """Flip a Work Queue page's Status (optionally appending an Execution Note)."""
    props: Dict[str, Any] = {"Status": _select(status)}
    if notes:
        props["Execution Notes"] = _rich(notes)
    _notion_api("PATCH", f"{_NOTION_PAGES_API}/{page_id}", {"properties": props})


def set_validation_result(page_id: str, result: str, notes: Optional[str] = None) -> None:
    """Write the `Final Validation Result` select (Pending/Passed/Partial/Failed) and,
    optionally, append validation evidence to `Execution Notes`. Used by the post-deploy
    canary to record whether the recorded diagnostic signal was resolved before Done."""
    if result not in VALIDATION_RESULTS:
        raise ValueError(f"invalid Final Validation Result {result!r}; expected one of {VALIDATION_RESULTS}")
    props: Dict[str, Any] = {"Final Validation Result": _select(result)}
    if notes:
        props["Execution Notes"] = _rich(notes)
    _notion_api("PATCH", f"{_NOTION_PAGES_API}/{page_id}", {"properties": props})
