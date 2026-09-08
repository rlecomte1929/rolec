"""Single-definition gate for HR case-task POSTs (WS1 Task 1.1 follow-up).

``POST /api/hr/cases/{case_id}/tasks`` stays the inline employee-task creator
(``backend.main.create_case_task_for_hr``). Provider assign lives at
``POST /api/hr/cases/{case_id}/provider-tasks`` (``hr_coordination.assign_task``).
"""
from backend.main import app


def _post_matches(path: str):
    return [
        r
        for r in app.routes
        if getattr(r, "path", None) == path
        and "POST" in getattr(r, "methods", set())
    ]


def test_hr_case_task_posts_are_single_definition():
    employee = _post_matches("/api/hr/cases/{case_id}/tasks")
    provider = _post_matches("/api/hr/cases/{case_id}/provider-tasks")

    assert len(employee) == 1, [r.endpoint.__module__ for r in employee]
    assert employee[0].endpoint.__module__ == "backend.main"

    assert len(provider) == 1, [r.endpoint.__module__ for r in provider]
    assert provider[0].endpoint.__module__ == "backend.app.routers.hr_coordination"
