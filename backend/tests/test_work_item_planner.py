"""
Mission Control P3 — the planner turns a triaged demand into a structured,
human-reviewable plan via the masked LlmClient (PII-safe by construction). Tested
with MockClient: assert the prompt carries the demand+triage, the JSON is parsed,
and malformed output fails safe (risk=high, never crashes).
"""
import json

from backend.app.services.policy_assistant_llm_client import MockClient
from backend.app.services.work_item_planner import build_plan


def test_parses_a_structured_plan():
    plan_json = json.dumps({
        "summary": "Fix the mislabeled button",
        "affected_files": ["frontend/src/pages/Dashboard.tsx"],
        "approach": "Rename the label string",
        "test_plan": "Snapshot test asserts the new label",
        "risk": "low",
        "confidence": "high",
    })
    client = MockClient(default_response=plan_json)
    out = build_plan("Wrong button label", "It says Recieve", {"kind": "bug", "priority": "P3", "complexity": "trivial"}, client=client)

    assert out["summary"] == "Fix the mislabeled button"
    assert out["affected_files"] == ["frontend/src/pages/Dashboard.tsx"]
    assert out["risk"] == "low"
    assert out["confidence"] == "high"
    assert out["approved"] is False


def test_prompt_includes_demand_and_triage():
    client = MockClient(default_response='{"summary":"x"}')
    build_plan("My title", "My body", {"kind": "idea", "priority": "P2", "complexity": "medium"}, client=client)
    user = client.calls[0].user_message
    assert "My title" in user and "My body" in user
    assert "idea" in user and "P2" in user


def test_malformed_output_fails_safe():
    client = MockClient(default_response="sorry, I can't do that")
    out = build_plan("t", "b", {"kind": "bug"}, client=client)
    assert out["risk"] == "high"          # unparseable → conservative
    assert out["affected_files"] == []
    assert out["approved"] is False


def test_handles_json_in_markdown_fences():
    fenced = "```json\n{\"summary\": \"ok\", \"risk\": \"medium\"}\n```"
    client = MockClient(default_response=fenced)
    out = build_plan("t", "b", {"kind": "bug"}, client=client)
    assert out["summary"] == "ok"
    assert out["risk"] == "medium"
