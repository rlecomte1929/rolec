from backend.app.services.feedback_task_engineer import format_diagnostics


def test_format_diagnostics_extracts_error_and_requests():
    ctx = {
        "recentErrors": [{"message": "TypeError: x is undefined", "fingerprint": "abc123"}],
        "recentFailedRequests": [
            {"status": 500, "path": "/api/cases/42", "requestId": "req-1"},
            {"status": 404, "path": "/api/policy/9", "requestId": "req-2"},
        ],
    }
    out = format_diagnostics(ctx)
    assert "abc123" in out and "/api/cases/42" in out and "500" in out


def test_format_diagnostics_empty_safe():
    assert format_diagnostics(None) == ""
    assert format_diagnostics({}) == ""
    assert format_diagnostics("not json") == ""


def test_format_diagnostics_parses_json_string():
    out = format_diagnostics('{"recentErrors":[{"message":"boom","fingerprint":"f1"}]}')
    assert "boom" in out and "f1" in out
