from backend.app.services.notion_work_queue import build_properties


def test_build_properties_writes_autonomy_tier():
    props = build_properties({"title": "t", "strategic_objective": "s", "execution_prompt": "e",
                              "expected_output": "o", "validation_criteria": "v",
                              "priority": "P2", "complexity": "Low", "task_type": "UX Redesign",
                              "layer": "UI", "product_area": "UX", "status": "Ready for AI",
                              "autonomy_tier": "green"},
                             failure_evidence="fe", context_links="cl")
    assert props["Autonomy Tier"]["select"]["name"] == "🟢 Green — auto"


def test_build_properties_omits_tier_when_absent():
    props = build_properties({"title": "t", "strategic_objective": "s", "execution_prompt": "e",
                              "expected_output": "o", "validation_criteria": "v", "priority": "P2",
                              "complexity": "Low", "task_type": "UX Redesign", "layer": "UI",
                              "product_area": "UX", "status": "Ready for AI"},
                             failure_evidence="fe", context_links="cl")
    assert props["Autonomy Tier"]["select"] is None
