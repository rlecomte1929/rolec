"""Characterise POST /api/hr/cases/{case_id}/tasks until WS1 Task 1.1 can resolve it.

The workstream plan treated this as two copies of one handler. They are not:

- Inline ``create_case_task_for_hr`` (``backend.main``) creates an *employee*
  task (``employee_id`` + ``task_type``). FastAPI first-match wins, so this is
  what production serves. Live client: ``api.client.addCaseTask`` /
  ``HrCaseTasksPanel``.
- Router ``assign_task`` (``hr_coordination``) creates a *provider* task
  (``provider_id``). Dead in prod. Client that expects it:
  ``hrCoordination.assignTask`` / provider coordination UI.

Unifying to a single definition needs a product choice (keep employee-task
on this path and move provider assign, or the reverse). Until that lands, these
tests pin the live contract so a "router wins" delete cannot ship silently.
"""
from backend.main import app

_PATH = "/api/hr/cases/{case_id}/tasks"


def _post_matches():
    return [
        r
        for r in app.routes
        if getattr(r, "path", None) == _PATH
        and "POST" in getattr(r, "methods", set())
    ]


def test_hr_case_tasks_post_live_handler_is_inline_employee_task():
    matches = _post_matches()
    assert matches, "POST /api/hr/cases/{case_id}/tasks is not registered"
    live = matches[0]
    assert live.endpoint.__name__ == "create_case_task_for_hr"
    assert live.endpoint.__module__ == "backend.main"


def test_hr_case_tasks_post_router_shadow_still_registered():
    matches = _post_matches()
    modules = [r.endpoint.__module__ for r in matches]
    assert "backend.main" in modules
    assert "backend.app.routers.hr_coordination" in modules
    assert len(matches) == 2, [r.endpoint.__name__ for r in matches]
