# Deliverable integrity: the first live run, and what "110 phantom deliverables" actually was

**Date:** 2026-08-23 · **Guard:** `scripts/check_deliverable_integrity.py`

## Why this run was the first

`NOTION_QUEUE_TOKEN` had been stale since **2026-06-04**. Every query 404'd, and the script
converted any Notion error into `exit 0` — so the guard reported **pass** on every PR for nearly
three months while examining nothing. That swallow was removed in #2035 (exit 3 = "did not
measure"), a canary bug in that change was fixed in #2052, and the secret was refreshed on
2026-08-23. This is what it found when it could finally see.

```
Scanned 481 Done file-producing task(s).
[FAIL] 110 claimed deliverable(s) marked Done but NOT in the repo
```

## "110 phantom deliverables" was the wrong headline

The 110 double-counts across tasks: **97 unique paths**. Classifying every one against git
history:

| category | count | what it means |
|---|---:|---|
| existed once, later renamed or removed | **64** | the work **shipped**; the path went stale |
| underscore-mangled by Notion | **10** | **the file exists** — `backend/eval/init.py` is really `backend/eval/__init__.py` |
| never existed in any commit on any branch | **23** | the real phantom set, across **15** tasks |

**~76% were not phantom Done at all.** They were the guard asking the wrong question: *"is this a
tracked file today"* rather than *"did this deliverable ever ship"*. Files legitimately move, and a
refactor three months later does not retroactively make a shipped deliverable a lie.

Both first two categories are now resolved **in the guard**, not the allowlist — see the change
that accompanies this document. Baselining them would have grown the allowlist from 150 to 247
entries and left every future refactor tripping the same way.

## Method, and a mistake worth recording

The classification uses **one** sweep over the whole repo:

```
git log --all --diff-filter=A --name-only --format=
```

24,983 paths, 1.3s.

The first pass instead ran `git log --all --diff-filter=A -- <path>` per path and reported
62/10/25. That form applies **history simplification** and silently misses a file added on a
merged side branch. Two migrations — `20260529160000_rce_policy_gaps.sql` and
`20260529161000_rce_case_artefacts.sql` — returned 0 commits that way but 1 under
`--full-history`, and their adding commit `ded8c5e5` **is** an ancestor of `origin/main`. They
shipped. The corrected split is 64/10/23.

⚠️ The check needs full history. On a shallow clone `git log --all` returns almost nothing and
**every** deliverable would be classified as never-existing — 97 confident false phantoms. The
job's checkout now sets `fetch-depth: 0`, and the script refuses to run shallow (exit 3) rather
than trust a truncated history.

## The 23 that never existed

Each is allowlisted under an `<aiq>:<path>` key scoped to the task that made the claim, so the
suppression cannot leak to another task claiming the same path. The Notion cards were flipped off
`Done` the same day.

The largest cluster is an entire eval workstream marked Done with nothing shipped.

### 623 · AI-W7.2 — LLM-as-judge for assistant tone, groundedness, actionability

<https://app.notion.com/p/AI-W7-2-LLM-as-judge-for-assistant-tone-groundedness-actionability-402887c64d4883479c2a019f6fb2db7e>

Claimed 7 deliverable(s), none of which ever existed:

- `backend/eval/judges/base.py`
- `backend/eval/judges/calibration.py`
- `backend/eval/judges/groundedness.py`
- `backend/eval/judges/init.py`
- `backend/eval/judges/tone.py`
- `backend/tests/fixtures/judges/labelled_examples.json`
- `backend/tests/test_judges.py`

### 714 · P3-01b · Build context-precision evaluator

<https://app.notion.com/p/P3-01b-Build-context-precision-evaluator-b3e887c64d4883b8910601a238b0a800>

Claimed 2 deliverable(s), none of which ever existed:

- `scripts/eval_context_precision.py`
- `scripts/rag_eval_harness.py`

### 617 · AI-W2.2 — Adapter: ai_trace_logger.TraceSession → agent_runs writer

<https://app.notion.com/p/AI-W2-2-Adapter-ai_trace_logger-TraceSession-agent_runs-writer-b5d887c64d4883babd2c813f21190d51>

Claimed 2 deliverable(s), none of which ever existed:

- `backend/app/services/agent_run_writer.py`
- `backend/tests/test_agent_run_writer.py`

### 698 · [BUG-A] Fix GET /api/company/branding-config returning 500 — missing branding_config column

<https://app.notion.com/p/BUG-A-Fix-GET-api-company-branding-config-returning-500-missing-branding_config-column-81b887c64d4883efae9c0190e1d53d8c>

Claimed 1 deliverable(s), none of which ever existed:

- `supabase/migrations/20260527_add_company_branding_config.sql`

### 665 · P3-01c · Build factual-consistency evaluator

<https://app.notion.com/p/P3-01c-Build-factual-consistency-evaluator-f10887c64d48828d87d001690d624308>

Claimed 1 deliverable(s), none of which ever existed:

- `scripts/eval_factual_consistency.py`

### 601 · P1-04a · Build specialist_review_events analytics schema + ETL view

<https://app.notion.com/p/P1-04a-Build-specialist_review_events-analytics-schema-ETL-view-90a887c64d488228abde818681bd3d68>

Claimed 1 deliverable(s), none of which ever existed:

- `supabase/migrations/20260604120000_specialist_review_calibration_view.sql`

### 750 · AI-W2.1 — Migration: unified agent_runs table with RLS

<https://app.notion.com/p/AI-W2-1-Migration-unified-agent_runs-table-with-RLS-18c887c64d4883809486012e7de21c71>

Claimed 1 deliverable(s), none of which ever existed:

- `supabase/migrations/20260531000000_agent_runs.sql`

### 565 · C2-06 · Policy-versus-reality gap detector (entitlement gaps with clause citations)

<https://app.notion.com/p/C2-06-Policy-versus-reality-gap-detector-entitlement-gaps-with-clause-citations-fd8887c64d4882fcad4881c5567949ae>

Claimed 1 deliverable(s), none of which ever existed:

- `backend/relopass/policy_evidence/models.py`

### 580 · AI-I.5 — Remove/avoid LangGraph dependency; commit FastAPI + Pydantic pipeline pattern

<https://app.notion.com/p/AI-I-5-Remove-avoid-LangGraph-dependency-commit-FastAPI-Pydantic-pipeline-pattern-65d887c64d4882e4815c814156a821fe>

Claimed 1 deliverable(s), none of which ever existed:

- `audit/ADR-001-no-langgraph.md`

### 541 · AI-W3.4 — Promptfoo PR-gate CI workflow

<https://app.notion.com/p/AI-W3-4-Promptfoo-PR-gate-CI-workflow-551887c64d488341b82e012254891375>

Claimed 1 deliverable(s), none of which ever existed:

- `backend/prompts/promptfooconfig.yaml`

### 540 · Test runner: stop sending invite emails to fake @testco.com domains (kills Resend sender reputation)

<https://app.notion.com/p/Test-runner-stop-sending-invite-emails-to-fake-testco-com-domains-kills-Resend-sender-reputation-85e887c64d488276973d01b8d6d1d33f>

Claimed 1 deliverable(s), none of which ever existed:

- `scripts/relopass_api_runner.js`

### 577 · C2-02b-FOLLOWUP · Agent wiring + AgentRegistry registration (tax_cert_{fr,de,no}.py)

<https://app.notion.com/p/C2-02b-FOLLOWUP-Agent-wiring-AgentRegistry-registration-tax_cert_-fr-de-no-py-831887c64d488350a374819a77d8c95e>

Claimed 1 deliverable(s), none of which ever existed:

- `backend/relopass/agents/extraction/tax_cert_findings.py`

### 319 · FOUNDATION-1A · Design & create events + daily_summaries schema

<https://app.notion.com/p/FOUNDATION-1A-Design-create-events-daily_summaries-schema-f66887c64d488399a69381da9881b67c>

Claimed 1 deliverable(s), none of which ever existed:

- `supabase/migrations/20260523000000_analytics_events_and_daily_summaries.sql`

### 145 · IMM-18 · Backend — data erasure workflow + retention automation

<https://app.notion.com/p/IMM-18-Backend-data-erasure-workflow-retention-automation-7de887c64d488382990381e959c2e128>

Claimed 1 deliverable(s), none of which ever existed:

- `supabase/migrations/20260605700000_imm18_retention_automation.sql`

### 144 · IMM-17 · Backend — right-to-access data export endpoint

<https://app.notion.com/p/IMM-17-Backend-right-to-access-data-export-endpoint-a30887c64d4882fab84901f8dabaaa41>

Claimed 1 deliverable(s), none of which ever existed:

- `supabase/migrations/20260605600000_imm17_erasure_requests.sql`
## What this does not say

These 23 are **historical** — May–June 2026 workstreams (`AI-W*`, `C2-*`, `IMM-*`, `P3-*`,
`FOUNDATION-*`). Recording that they did not ship is not a judgement that they still should. That
is a product call, and deliberately not made here.

Nor does it say the other 74 were well-authored. The 10 underscore cases are real authoring bugs —
CLAUDE.md tells authors to wrap paths in backticks precisely because Notion renders a bare
`__tests__` as bold and eats the underscores. The guard now resolves them **and warns**, naming
each card, so they get fixed instead of being quietly absorbed forever.
