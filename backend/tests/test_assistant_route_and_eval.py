"""
Slice 5 backend — the /api/assistant/route endpoint + the routing eval acting as a
CI regression guard: the real classifier must keep meeting the gate on the gold
set, and the gold must be a real guard (a mislabel drops the score).
"""
from pathlib import Path

from backend.app.routers.assistant_router import RouteBody, route_assistant_question
from backend.eval.routing_metrics import score_routing
from backend.eval.run_routing_eval import load_gold

_GOLD = Path(__file__).resolve().parent / "fixtures/eval/routing/domain_gold.jsonl"


def test_route_handler_returns_classification():
    out = route_assistant_question(RouteBody(question="Does my company cover housing?"), user={"id": "e"})
    assert out["domain"] == "policy"
    out2 = route_assistant_question(RouteBody(question="What documents do I need for my visa?"), user={"id": "e"})
    assert out2["domain"] == "immigration"


def test_route_registered_in_both_apps():
    # Dual-registration rule (CLAUDE.md): the router MUST be wired into BOTH
    # backend/app/main.py and backend/main.py, else it 405s in prod. Verified
    # statically (importing backend.main under pytest re-attaches the query-counter
    # listener to the conftest's mock engine). Runtime mount confirmed out-of-band:
    # `python -c "from backend.main import app; ..."` resolves /api/assistant/route.
    backend_dir = Path(__file__).resolve().parents[1]
    app_main = (backend_dir / "app/main.py").read_text()
    assert "assistant_router," in app_main, "router not imported in app/main.py"
    assert "app.include_router(assistant_router.router)" in app_main, "router not registered in app/main.py"
    prod_main = (backend_dir / "main.py").read_text()
    assert "import assistant_router as assistant_router_router" in prod_main, "router not imported in main.py"
    assert "app.include_router(assistant_router_router.router)" in prod_main, "router not registered in main.py"


def test_real_classifier_meets_gate_on_gold():
    report = score_routing(load_gold(_GOLD))
    assert report["accuracy"] >= 0.90, report["confusion"]


def test_gold_is_a_real_guard():
    gold = load_gold(_GOLD)
    poisoned = [dict(c) for c in gold]
    first = poisoned[0]
    first["expected_domain"] = "policy" if first["expected_domain"] != "policy" else "immigration"
    assert score_routing(poisoned)["accuracy"] < 1.0
