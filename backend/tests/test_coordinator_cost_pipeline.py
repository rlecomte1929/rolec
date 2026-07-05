"""AIQ-1414 — cost-accounting pipeline for the coordinator (criterion #2 runtime side).

Verifies (a) a coordinator TraceSession prices BOTH its reasoning (sonnet-4-6) and its
summary-fold (haiku-4-5) calls — a regression guard for the costs.yaml haiku fix — and
(b) `compute_unit_economics_rollup` aggregates `feature_key='ai_coordinator'` cost. No key.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.app.services.ai_trace_logger import TraceSession
from backend.app.services.ai_unit_economics import compute_unit_economics_rollup

_SONNET = (5000, 800)   # a typical coordinator turn (bounded ~5k in / 0.8k out)
_HAIKU = (4000, 300)    # a summary fold
# sonnet 3/15, haiku 1/5 per M
_EXPECTED = round((5000 * 3 + 800 * 15) / 1e6 + (4000 * 1 + 300 * 5) / 1e6, 6)


def test_trace_prices_reasoning_and_fold():
    t = TraceSession(session_id="c-1", query="q", company_id="acme",
                     feature_key="ai_coordinator", customer_id="acme")
    t.record_llm_call(model="claude-sonnet-4-6", input_tokens=_SONNET[0], output_tokens=_SONNET[1], latency_ms=100)
    t.record_llm_call(model="claude-haiku-4-5", input_tokens=_HAIKU[0], output_tokens=_HAIKU[1], latency_ms=50)
    econ = t._compute_unit_economics()
    assert econ["cost_usd_estimated"] == _EXPECTED
    assert econ["tokens_in"] == _SONNET[0] + _HAIKU[0]


def test_haiku_fold_is_priced_not_zero():
    """Regression guard: before the costs.yaml fix, the haiku fold priced to $0."""
    t = TraceSession(session_id="c-1", query="q", company_id="acme", feature_key="ai_coordinator")
    t.record_llm_call(model="claude-haiku-4-5", input_tokens=4000, output_tokens=300, latency_ms=50)
    assert t._compute_unit_economics()["cost_usd_estimated"] > 0


def test_rollup_aggregates_ai_coordinator_feature():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE policy_assistant_traces ("
            "id TEXT PRIMARY KEY, company_id TEXT, customer_id TEXT, feature_key TEXT, "
            "tokens_in INTEGER, tokens_out INTEGER, cost_usd_estimated REAL, "
            "co2e_grams_estimated REAL, created_at TEXT)"
        ))
        for i, (fk, cost) in enumerate(
            [("ai_coordinator", 0.0325), ("ai_coordinator", 0.0055), ("policy_assistant", 0.02)]
        ):
            conn.execute(text(
                "INSERT INTO policy_assistant_traces "
                "(id, company_id, customer_id, feature_key, tokens_in, tokens_out, "
                "cost_usd_estimated, co2e_grams_estimated, created_at) "
                "VALUES (:id,'acme','acme',:fk,100,20,:c,0.1,'2026-07-05T00:00:00')"
            ), {"id": f"t{i}", "fk": fk, "c": cost})

    with Session(engine) as s:
        rollup = compute_unit_economics_rollup(feature_key="ai_coordinator", session=s)
    # only the two ai_coordinator rows aggregate
    assert round(rollup["totals"]["total_cost_usd"], 6) == 0.038
    assert rollup["totals"]["n_calls"] == 2
