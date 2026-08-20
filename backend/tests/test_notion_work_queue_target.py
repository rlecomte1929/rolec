"""The AI Work Queue destination, and the defaults a feedback-born task carries.

WHY THIS EXISTS
---------------
The database the backend wrote to has been renamed "AI Work Queue (RETIRED)" in Notion; the live
queue is a different database. A stale id does not fail loudly — Notion happily accepts the
page-create and the task lands in a queue nobody reads. That is the failure mode these tests
guard: the destination is asserted explicitly, because nothing else would notice.

Two ids exist for one database: `database_id` (used by page-create here) and the data-source /
collection id (used by the Deno Edge Functions' /databases/<id>/query). Both must move together
or the backend and the autofix pipeline end up on different databases.
"""
from __future__ import annotations

import json
from typing import Any, Dict

import pytest

from backend.app.routers import admin_feedback
from backend.app.services import notion_work_queue

LIVE_DB_ID = "3bc887c6-4d48-8089-8188-fcf2dc3edc1b"
RETIRED_DB_ID = "7adc643a-c448-4a1a-ba80-e27e417f42d6"
RETIRED_DATA_SOURCE_ID = "75d7ed78-91f4-46b6-b805-12e43abbecce"


# ── destination ──────────────────────────────────────────────────────────────────────

def test_default_database_is_the_live_queue() -> None:
    assert notion_work_queue._DEFAULT_DB == LIVE_DB_ID


def test_default_database_is_not_the_retired_queue() -> None:
    """Named separately so a regression reads as 'went back to RETIRED', not 'wrong string'."""
    assert notion_work_queue._DEFAULT_DB != RETIRED_DB_ID


def test_page_create_targets_the_live_database(monkeypatch) -> None:
    """End of the wire: the POST body's parent.database_id is what actually decides the queue."""
    monkeypatch.setenv("NOTION_TOKEN", "secret_test")
    monkeypatch.delenv("NOTION_WORK_QUEUE_DB", raising=False)
    captured: Dict[str, Any] = {}

    class _Resp:
        status = 200
        def read(self): return json.dumps({"url": "https://notion.so/p/abc", "id": "abc"}).encode()
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def _fake_urlopen(req, timeout=None):
        captured["payload"] = json.loads(req.data.decode())
        return _Resp()

    monkeypatch.setattr(notion_work_queue.urllib.request, "urlopen", _fake_urlopen)
    notion_work_queue.create_work_queue_task(
        {"title": "t"}, failure_evidence="e", context_links="c"
    )
    assert captured["payload"]["parent"] == {"database_id": LIVE_DB_ID}


def test_env_override_still_wins(monkeypatch) -> None:
    """The constant is a fallback. Production sets NOTION_WORK_QUEUE_DB, and that must win —
    otherwise the deploy cannot be corrected without a code change."""
    monkeypatch.setenv("NOTION_TOKEN", "secret_test")
    monkeypatch.setenv("NOTION_WORK_QUEUE_DB", "11111111-2222-3333-4444-555555555555")
    captured: Dict[str, Any] = {}

    class _Resp:
        status = 200
        def read(self): return json.dumps({"url": "https://notion.so/p/abc", "id": "abc"}).encode()
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(
        notion_work_queue.urllib.request, "urlopen",
        lambda req, timeout=None: (captured.update(p=json.loads(req.data.decode())), _Resp())[1],
    )
    notion_work_queue.create_work_queue_task({"title": "t"}, failure_evidence="", context_links="")
    assert captured["p"]["parent"]["database_id"] == "11111111-2222-3333-4444-555555555555"


def test_no_retired_id_survives_in_executable_code() -> None:
    """Whole-repo sweep. The comment in notion_work_queue.py names the retired pair on purpose
    ('do not restore it'), so only ASSIGNMENTS and env fallbacks are checked, not prose."""
    import pathlib, re
    root = pathlib.Path(__file__).resolve().parents[2]
    offenders = []
    for path in list(root.glob("backend/**/*.py")) + list(root.glob("scripts/*.py")) \
            + list(root.glob("supabase/functions/**/*.ts")) + list(root.glob("lib/*.ts")):
        if ".claude" in str(path) or "__pycache__" in str(path) or "tests/" in str(path):
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("*") or stripped.startswith("//"):
                continue
            if RETIRED_DB_ID in line or RETIRED_DATA_SOURCE_ID in line:
                offenders.append(f"{path.relative_to(root)}:{n}: {stripped[:90]}")
    assert not offenders, "retired queue id still reachable at runtime:\n" + "\n".join(offenders)


# ── feedback-task defaults ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("engineer_choice", sorted(admin_feedback._IMPL_TASK_TYPES))
def test_a_confidently_diagnosed_bug_becomes_bug_fix(engineer_choice) -> None:
    task = {"task_type": engineer_choice}
    admin_feedback._apply_feedback_queue_defaults(task, category="bug")
    assert task["task_type"] == "Bug Fix"


def test_an_uncertain_bug_stays_research() -> None:
    """The safety property, and the reason this is not a blanket bug -> 'Bug Fix' map.

    feedback_task_engineer routes anything uncertain — a question, "I think", "I cannot see X" —
    to Research, because "a wrong impl task silently ships a broken change". Relabelling those as
    a confident Bug Fix would defeat that rule while looking like an improvement.
    """
    task = {"task_type": "Research"}
    admin_feedback._apply_feedback_queue_defaults(task, category="bug")
    assert task["task_type"] == "Research"


def test_an_idea_is_always_research() -> None:
    task = {"task_type": "Frontend Implementation"}
    admin_feedback._apply_feedback_queue_defaults(task, category="idea")
    assert task["task_type"] == "Research"


@pytest.mark.parametrize("category", ["bug", "idea", None, "", "other"])
def test_every_feedback_task_lands_in_needs_decomposition(category) -> None:
    """Raw user feedback is an unreviewed input; a human triages before an agent executes."""
    task = {"task_type": "Research", "status": "Ready for AI"}
    admin_feedback._apply_feedback_queue_defaults(task, category=category)
    assert task["status"] == "Needs Decomposition"


def test_the_shared_builder_default_is_untouched() -> None:
    """admin_work_items and autopilot_ingest share build_properties and must keep landing in
    'Ready for AI' — the new lane is set on the feedback path, not on the shared default."""
    props = notion_work_queue.build_properties(
        {"title": "t"}, failure_evidence="", context_links=""
    )
    assert props["Status"]["select"]["name"] == "Ready for AI"


def test_title_is_written_to_the_fable_property() -> None:
    """This database's title property is named `fable`, not Name/Title. A rename here silently
    creates untitled rows, which is why it is pinned rather than assumed."""
    props = notion_work_queue.build_properties(
        {"title": "Hello"}, failure_evidence="", context_links=""
    )
    assert props["fable"]["title"][0]["text"]["content"] == "Hello"


def test_a_feedback_task_is_self_consistent() -> None:
    """'Needs Decomposition' and 'Vetted — ready' cannot both be true of one row.

    Definition of Ready was hardcoded to 'Vetted — ready'. Once feedback tasks land in the
    decomposition lane that hardcode became a contradiction on every row, so it is now
    overridable — with the previous value still the default for every other caller.
    """
    task = {"title": "t", "task_type": "Research"}
    admin_feedback._apply_feedback_queue_defaults(task, category="bug")
    props = notion_work_queue.build_properties(task, failure_evidence="", context_links="")
    assert props["Status"]["select"]["name"] == "Needs Decomposition"
    assert props["Definition of Ready"]["select"]["name"] == "Draft"
