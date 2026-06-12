# FRIDAY-005 · 1M-context policy ingestion spike — analysis (AIQ-648)

**Reconstructed: 2026-06-11.** The original Cowork spike was never committed
(`outputs/friday_005_policy_ingestion_spike.py` was claimed in AIQ-648's notes but
absent from the repo) and, per those same notes, **never run live** ("No API key in
Cowork sandbox … validated via manual prompt execution + cost/latency math"). This
document records the real, runnable reconstruction and an honest validation state.

## What it does
`friday_005_policy_ingestion_spike.py` ingests a full corporate mobility policy PDF
via Claude **Sonnet 4.6** (1M-token context, now GA — no chunking, no RAG) and
produces a personalised, **citation-grounded** one-page briefing for one employee in
a single API call, returning `{briefing, cost_usd, latency_ms, model}`. A second
verification call ("spot-check") fact-checks each `[Policy §X.Y]` citation against the
source — that second pass is **spike-only**; the production endpoint deliberately
omits it (FRIDAY-005 scope).

## Prompt design (the hallucination guards)
1. **Citation-first** — every factual claim ends with `[Policy §X.Y]` traceable to the source.
2. **Graceful uncertainty** — "The policy does not specify …" instead of inventing.
3. **One-page constraint** — bounded, skimmable output.
4. **Personalisation** — only provisions matching this employee's grade / assignment / route / dependants.

The `SYSTEM_PROMPT` + `build_user_prompt()` in the spike are the **source of truth**;
`backend/app/services/briefing.py` reuses them byte-for-byte.

## Validation state (honest)
| Criterion (AIQ-648) | Target | Status |
|---|---|---|
| Cost per briefing | < $2 | **Estimated ✅** — 80K-token policy + ~900-token briefing ≈ 80,000·$3/1M + 900·$15/1M ≈ **$0.25**. Confirm with a live run. |
| Latency | < 60s | **Estimated ✅** — single Sonnet-4.6 call on ~80K input ≈ 3–10s. Confirm with a live run. |
| Spot-check 5/5 cited facts traceable | 5/5 | **NOT yet measured** — needs a live run with `ANTHROPIC_API_KEY` + a real 50–80pg policy PDF. The spike's `spot_check()` automates this once a key is available. |

**Cannot be validated in this environment** (no `ANTHROPIC_API_KEY` in the run shell —
the same wall the Cowork sandbox hit). To close the GO/NO-GO and the endpoint's
validation criteria #1–#3, run the spike once where the key exists:
`python outputs/friday_005_policy_ingestion_spike.py <policy.pdf>`.

## Go / No-Go
**Conditional GO** — architecture and cost/latency math are favourable, but the
citation-fidelity criterion is unmeasured until a live run. Treat the endpoint as
shippable-pending-one-live-validation, not validated.

## Architecture fit (production endpoint)
- `pdf_to_text()` (`backend/app/utils/pdf_to_text.py`) → policy text from PDF bytes (`pypdf`; the repo's policy-intake path uses `pdfplumber` and is a heavier alternative).
- `generate_employee_briefing(policy_text, employee)` (`backend/app/services/briefing.py`) → reuses the spike prompts.
- `POST /api/hr/cases/{case_id}/employee-briefing` (`backend/app/routers/hr_case_detail.py`) → HR-auth + RLS, loads case + employee + active policy text, calls the service.

## Two integration seams flagged for the endpoint (brief premises that don't match the schema)
1. **Active policy text retrieval** — the brief assumes "the PDF is in Supabase storage"; the repo extracts policy text to `policy_documents` + clauses at intake (via `pdfplumber`), and the raw-PDF-in-storage retrieval path is unconfirmed. The endpoint exposes `load_active_policy_text(...)` as the single seam to wire once the storage/column is confirmed.
2. **Employee field mapping** — the brief's `case.assignment_type` / `origin_country` / `target_move_date` / `dependants` / `grade_band` are not columns; case data is in `relocation_cases.profile_json`. The endpoint maps from `profile_json` best-effort and flags the exact keys to confirm.

## Notes
- **PII / data governance**: this endpoint intentionally sends the employee's real
  name + the full policy to Anthropic to personalise the briefing — so the repo's
  `mask_pii`-before-egress pattern (used by the policy-assistant) is **not** applied
  here (masking would defeat personalisation). Flag for review: employee PII + policy
  text cross the Anthropic API boundary (30-day retention).
- **SDK**: `anthropic==0.39.0` is pinned in `backend/requirements.txt` — sufficient for
  `messages.create(model="claude-sonnet-4-6", …)`. The 1M-context beta header is only
  needed above ~200K tokens; an 80K-token policy doesn't require it.
