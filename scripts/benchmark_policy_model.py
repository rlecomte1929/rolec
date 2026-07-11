#!/usr/bin/env python3
"""AIQ-1488 — benchmark the policy LLM (parsing ingestion + RAG Q&A) on the
active model, and compute latency / tokens / cost per parse.

REVIEWER-RUN: this makes real Anthropic calls, so it needs ANTHROPIC_API_KEY. It is
NOT run in CI or by the dev-queue agent (the key is unset there). With the key unset
it prints the exact command and exits 0 — no mock benchmark, which would be
misleading.

Usage (reviewer):
    ANTHROPIC_API_KEY=sk-... \\
    RELOPASS_LLM_ASSISTANT_MODEL=claude-sonnet-5 \\
    python scripts/benchmark_policy_model.py

    # parsing path model comes from RELOPASS_LLM_POLICY_MODEL; override either with --model.
    python scripts/benchmark_policy_model.py --model claude-sonnet-5 --fixture <path>

Compares numbers by re-running with the model env vars set to the current models
(claude-sonnet-4-6 / claude-fable-5) vs claude-sonnet-5.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_DEFAULT_FIXTURE = _REPO_ROOT / "backend/tests/fixtures/policy_comp_allowance_templates_golden.json"

# Representative policy Q&A spot-check (the task's "5 specific questions").
_QA_QUESTIONS = [
    "What is the maximum housing allowance and how is it calculated?",
    "Is a rental car covered during the temporary accommodation period?",
    "What relocation expenses require pre-approval, and by whom?",
    "How long is the temporary accommodation benefit provided?",
    "Are dependents' school fees reimbursed, and up to what cap?",
]


def _load_fixture_text(path: Path) -> str:
    raw = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        try:
            return json.dumps(json.loads(raw), ensure_ascii=False)  # flatten to text
        except ValueError:
            return raw
    return raw


def _bench_one(client, model: str, system: str, user_message: str, max_tokens: int):
    from backend.app.services.policy_assistant_llm_client import LlmRequest, estimate_cost_usd

    req = LlmRequest(system=system, user_message=user_message, model=model, max_tokens=max_tokens)
    t0 = time.perf_counter()
    resp = client.complete(req)
    wall = time.perf_counter() - t0
    usage = resp.get("usage") or {}
    cost = estimate_cost_usd(usage, model)
    return {
        "latency_s": round(wall, 2),
        "input_tokens": int(usage.get("input_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or 0),
        "cost_usd": round(cost, 6),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark the policy LLM (AIQ-1488).")
    parser.add_argument("--fixture", default=str(_DEFAULT_FIXTURE), help="Large policy doc to ingest.")
    parser.add_argument("--model", default=None, help="Override model id (else the env-resolved default).")
    parser.add_argument("--qa", type=int, default=len(_QA_QUESTIONS), help="Number of Q&A spot-checks.")
    args = parser.parse_args(argv)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "ANTHROPIC_API_KEY is not set — this benchmark makes real Anthropic calls "
            "and will not run against the mock client.\n\n"
            "Run it as the reviewer, e.g.:\n"
            "  ANTHROPIC_API_KEY=sk-... RELOPASS_LLM_ASSISTANT_MODEL=claude-sonnet-5 \\\n"
            "    python scripts/benchmark_policy_model.py\n\n"
            "Then re-run with RELOPASS_LLM_ASSISTANT_MODEL=claude-sonnet-4-6 to compare.\n"
        )
        return 0

    from backend.app.services.policy_assistant_llm_client import DEFAULT_MODEL, get_default_client

    model = args.model or DEFAULT_MODEL
    client = get_default_client()
    fixture = Path(args.fixture)
    doc = _load_fixture_text(fixture)

    print(f"# Policy LLM benchmark (AIQ-1488)\n")
    print(f"- model: `{model}`")
    print(f"- fixture: `{fixture}` ({len(doc):,} chars)\n")

    rows = []
    # 1) Parsing/ingestion proxy — single-pass ingest of the whole doc.
    rows.append(("parse (single-pass ingest)", _bench_one(
        client, model,
        system="Extract the structured relocation-policy facts from the document.",
        user_message=doc, max_tokens=4000,
    )))
    # 2) RAG Q&A spot-check.
    for i, q in enumerate(_QA_QUESTIONS[: args.qa], 1):
        rows.append((f"qa#{i}", _bench_one(
            client, model,
            system="Answer the policy question using only the document. Cite the section.",
            user_message=f"POLICY:\n{doc}\n\nQUESTION: {q}", max_tokens=500,
        )))

    print("| workload | latency_s | input_tok | output_tok | cost_usd |")
    print("|---|---|---|---|---|")
    tot_in = tot_out = 0
    tot_cost = 0.0
    for name, r in rows:
        print(f"| {name} | {r['latency_s']} | {r['input_tokens']:,} | {r['output_tokens']:,} | ${r['cost_usd']} |")
        tot_in += r["input_tokens"]; tot_out += r["output_tokens"]; tot_cost += r["cost_usd"]
    print(f"| **total** | | {tot_in:,} | {tot_out:,} | **${round(tot_cost, 6)}** |")
    print(f"\nCost per full parse+5Q at this model: ${round(tot_cost, 6)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
