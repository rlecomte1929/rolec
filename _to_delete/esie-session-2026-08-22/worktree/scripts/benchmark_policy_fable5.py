#!/usr/bin/env python3
"""
FD-2 / AIQ-994 — Policy-parsing benchmark: Claude Fable 5 vs Claude Sonnet 4.6.

Goal: justify (or reject) migrating HR-policy ingestion from Sonnet 4.6 to
Claude Fable 5's 1M-token context — process an entire policy manual in ONE call,
no chunking/RAG — by measuring **cost** and **accuracy** on real policy PDFs.

This is the runnable harness for the task; it must be run in an environment that
has a working ANTHROPIC_API_KEY (this repo's headless CI does not). The Sonnet→
Fable 5 switch in the router (POLICY_PARSING_FABLE5) stays OFF until this report
justifies it — Fable 5 is ~3.3x Sonnet's price ($10/$50 vs $3/$15 per 1M tokens).

────────────────────────────────────────────────────────────────────────────
Prerequisites
  pip install -U "anthropic>=0.40"     # repo pins 0.39.0, which predates Fable 5
  export ANTHROPIC_API_KEY=sk-ant-...  # org must allow 30-day data retention
                                       #   (Fable 5 is unavailable under ZDR)

Run
  python scripts/benchmark_policy_fable5.py \
      --pdf "docs/samples/GOPS 12102.pdf" \
      --pdf "docs/samples/Long Term Assignment Policy Summary.pdf" \
      --judge                          # optional: LLM-judge accuracy vs Sonnet
  # → writes audit/benchmarks/policy_fable5_<date>.md

Notes
  * Cost is computed from the API's real `usage` (input + output tokens) × the
    pricing in backend/relopass/llm/costs.yaml — not estimated.
  * Each PDF is sent whole as a single `document` block (no chunking) to exercise
    the 1M context. A 150k-token manual fits in one Fable 5 call.
  * Fable 5 API specifics handled: thinking is always-on (no `thinking` param),
    no sampling params, and `stop_reason == "refusal"` is surfaced, not crashed.
  * The 5 standard questions below are generic relocation-policy probes — EDIT
    them (and add the 3rd, larger PDF the task calls for) for your real eval.
"""
from __future__ import annotations

import argparse
import base64
import datetime as _dt
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

FABLE = "claude-fable-5"
SONNET = "claude-sonnet-4-6"
JUDGE = "claude-opus-4-8"

# USD per 1M tokens — keep in sync with backend/relopass/llm/costs.yaml.
PRICING = {
    FABLE: {"in": 10.00, "out": 50.00},
    SONNET: {"in": 3.00, "out": 15.00},
    JUDGE: {"in": 5.00, "out": 25.00},
}

# The 5 "standard policy questions" the task asks to run per PDF. Generic on
# purpose — replace with your real evaluation set + expected answers.
STANDARD_QUESTIONS = [
    "What is the maximum relocation/assignment allowance or budget this policy grants, and to whom?",
    "Who is eligible under this policy, and what assignment types or durations does it cover?",
    "What does the policy say about temporary/interim housing — is it covered, and for how long?",
    "What shipping, storage, or household-goods provisions are included (and any caps)?",
    "What tax, social-security, or payroll support does the policy provide?",
]

SYSTEM = (
    "You are an HR mobility policy analyst. Answer ONLY from the attached policy "
    "document. Quote the relevant clause. If the document does not address the "
    "question, say 'Not specified in this policy.' Be concise and precise."
)


def _usd(model: str, tin: int, tout: int) -> float:
    p = PRICING[model]
    return tin / 1_000_000 * p["in"] + tout / 1_000_000 * p["out"]


@dataclass
class Answer:
    text: str
    tokens_in: int
    tokens_out: int
    latency_s: float
    refused: bool = False
    error: Optional[str] = None


def _pdf_document_block(pdf_path: Path) -> dict:
    data = base64.standard_b64encode(pdf_path.read_bytes()).decode("utf-8")
    return {
        "type": "document",
        "source": {"type": "base64", "media_type": "application/pdf", "data": data},
    }


def _ask(client, model: str, doc_block: dict, question: str) -> Answer:
    """One whole-document call. No chunking. Returns answer + real usage."""
    t0 = time.monotonic()
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=2048,  # answers are short; input (the PDF) is the large part
            system=SYSTEM,
            messages=[{
                "role": "user",
                "content": [doc_block, {"type": "text", "text": question}],
            }],
            # No `thinking` param: Fable 5 thinking is always-on; Sonnet accepts the
            # omission too. No temperature/top_p — removed on Fable 5 (would 400).
        )
    except Exception as e:  # noqa: BLE001 — surface any API/SDK error per-cell
        return Answer("", 0, 0, time.monotonic() - t0, error=f"{type(e).__name__}: {e}")
    latency = time.monotonic() - t0

    # Fable 5 safety classifiers can decline with HTTP 200 + stop_reason "refusal".
    if getattr(resp, "stop_reason", None) == "refusal":
        return Answer("", resp.usage.input_tokens, resp.usage.output_tokens, latency, refused=True)

    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    return Answer(text, resp.usage.input_tokens, resp.usage.output_tokens, latency)


def _judge(client, question: str, doc_block: dict, fable: Answer, sonnet: Answer) -> str:
    """Optional LLM-judge: do the two answers materially agree + stay grounded?"""
    prompt = (
        f"Question: {question}\n\n"
        f"Answer A (Fable 5):\n{fable.text or '[no answer]'}\n\n"
        f"Answer B (Sonnet 4.6):\n{sonnet.text or '[no answer]'}\n\n"
        "Using ONLY the attached policy document as ground truth, reply with exactly "
        "one of: AGREE (both materially correct and consistent), A_BETTER, B_BETTER, "
        "or BOTH_WRONG — then one short sentence why."
    )
    try:
        resp = client.messages.create(
            model=JUDGE,
            max_tokens=300,
            messages=[{"role": "user", "content": [doc_block, {"type": "text", "text": prompt}]}],
        )
        return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
    except Exception as e:  # noqa: BLE001
        return f"[judge error: {type(e).__name__}: {e}]"


def main() -> int:
    ap = argparse.ArgumentParser(description="Benchmark policy parsing: Fable 5 vs Sonnet 4.6")
    ap.add_argument("--pdf", action="append", required=True, help="Path to an HR policy PDF (repeatable)")
    ap.add_argument("--judge", action="store_true", help="LLM-judge accuracy (extra cost)")
    ap.add_argument("--out", default=None, help="Output markdown path")
    args = ap.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY is not set. See the module docstring.", file=sys.stderr)
        return 2
    try:
        import anthropic
    except ImportError:
        print("ERROR: pip install -U 'anthropic>=0.40'", file=sys.stderr)
        return 2

    client = anthropic.Anthropic()
    today = _dt.date.today().isoformat()
    out_path = Path(args.out or f"audit/benchmarks/policy_fable5_{today}.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [
        f"# Policy-parsing benchmark — Fable 5 vs Sonnet 4.6 ({today})",
        "",
        "FD-2 / AIQ-994. Each PDF sent whole in a single call (no chunking). Cost from real `usage`.",
        "",
    ]
    totals = {FABLE: {"in": 0, "out": 0, "cost": 0.0, "lat": 0.0, "refusals": 0},
              SONNET: {"in": 0, "out": 0, "cost": 0.0, "lat": 0.0, "refusals": 0}}

    for pdf in args.pdf:
        pdf_path = Path(pdf)
        if not pdf_path.exists():
            lines.append(f"## {pdf} — MISSING, skipped\n")
            continue
        doc = _pdf_document_block(pdf_path)
        size_kb = pdf_path.stat().st_size / 1024
        lines.append(f"## {pdf_path.name}  ({size_kb:.0f} KB)\n")
        for q in STANDARD_QUESTIONS:
            fa = _ask(client, FABLE, doc, q)
            so = _ask(client, SONNET, doc, q)
            for model, a in ((FABLE, fa), (SONNET, so)):
                t = totals[model]
                t["in"] += a.tokens_in; t["out"] += a.tokens_out
                t["cost"] += _usd(model, a.tokens_in, a.tokens_out)
                t["lat"] += a.latency_s
                t["refusals"] += 1 if a.refused else 0
            verdict = _judge(client, q, doc, fa, so) if args.judge else "(judge off)"
            lines += [
                f"### Q: {q}",
                f"- **Fable 5** ({fa.tokens_in}→{fa.tokens_out} tok, "
                f"${_usd(FABLE, fa.tokens_in, fa.tokens_out):.4f}, {fa.latency_s:.1f}s)"
                + (f" — ERROR {fa.error}" if fa.error else (" — REFUSED" if fa.refused else "")),
                f"  > {(fa.text or '').strip()[:600]}",
                f"- **Sonnet 4.6** ({so.tokens_in}→{so.tokens_out} tok, "
                f"${_usd(SONNET, so.tokens_in, so.tokens_out):.4f}, {so.latency_s:.1f}s)"
                + (f" — ERROR {so.error}" if so.error else (" — REFUSED" if so.refused else "")),
                f"  > {(so.text or '').strip()[:600]}",
                f"- **Judge:** {verdict}",
                "",
            ]

    lines += ["## Totals", ""]
    for model in (FABLE, SONNET):
        t = totals[model]
        lines.append(
            f"- **{model}**: {t['in']:,} in / {t['out']:,} out tokens · "
            f"**${t['cost']:.4f}** · {t['lat']:.0f}s total · {t['refusals']} refusal(s)"
        )
    if totals[SONNET]["cost"] > 0:
        ratio = totals[FABLE]["cost"] / totals[SONNET]["cost"]
        lines += ["", f"- **Fable 5 / Sonnet 4.6 cost ratio: {ratio:.2f}×**",
                  "", "## Recommendation (fill in after reviewing answers above)",
                  "- [ ] Accuracy parity or improvement? (judge verdicts + manual read)",
                  "- [ ] Is the cost ratio justified by the accuracy gain for *this* call path?",
                  "- [ ] Which calls (if any) move to Fable 5 vs stay on Sonnet?",
                  "- [ ] If yes: set POLICY_PARSING_FABLE5=1 on Render; keep chunking fallback.",
                  ""]
    out_path.write_text("\n".join(lines))
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
