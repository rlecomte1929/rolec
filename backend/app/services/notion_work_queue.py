"""notion_work_queue.py — create an AI Work Queue page in Notion from an
engineered feedback task.

Mirrors the NOTION_TOKEN + urllib pattern in routers/support.py, adding
POST /v1/pages. Requires the backend Notion integration to be shared with the
AI Work Queue database and NOTION_WORK_QUEUE_DB set (defaults to the known id).
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

_NOTION_PAGES_API = "https://api.notion.com/v1/pages"
_NOTION_VERSION = "2022-06-28"
_DEFAULT_DB = "7adc643a-c448-4a1a-ba80-e27e417f42d6"  # AI Work Queue
_MAX_CHUNK = 1900  # Notion caps a single text object at 2000 chars


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
