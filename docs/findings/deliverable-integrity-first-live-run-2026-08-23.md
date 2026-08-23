# Deliverable integrity: the first live run, and what "110 phantom deliverables" actually was

**Date:** 2026-08-23 · **Guard:** `scripts/check_deliverable_integrity.py`

---

# ⚠️ CORRECTION — 2026-08-23, second pass

**Most of what the first version of this document said was wrong, and two of its claims were
alarming as well as wrong.**

## The retraction that matters: the GDPR alarm was false

The first version flagged three adjacent privacy obligations as marked Done with nothing
shipped, and urged a deliberate check. All three had shipped. Verified against production:

| capability | state in prod |
|---|---|
| IMM-16 — immutable data-access audit log | `data_access_log`: **3,858 rows**, 1 active trigger |
| IMM-17 — right-to-access export | `erasure_requests` table exists (0 rows: no requests yet) |
| IMM-18 — retention automation | `fn_case_close_set_retention`, `fn_immigration_retention_cleanup` |

Plus routers `gdpr.py`, `immigration_gdpr.py`, `admin_dsar.py`. The IMM-17 and IMM-18 migrations
are on `main` under later timestamps than the cards recorded — this repo re-stamps migrations by
policy, so a card written before its file lands is wrong **by construction**.

Notes claiming otherwise were written onto those three Notion cards. They have been retracted
there.

## Corrected numbers

The guard could not see git history at all (fixed in #2055 — `actions/checkout` leaves a PR build
on a detached HEAD, and `--all` enumerated no refs, so `paths_ever_added` returned the **empty
set**). Every conclusion drawn before that fix was drawn from a blind guard.

With history visible, the original 110 claims resolve as:

| category | count |
|---|---:|
| added at some point, later renamed or removed — **shipped** | ~70 |
| a migration re-stamped before it landed — **the file exists** | 6 |
| Notion ate the underscores of `__init__.py` / `__tests__` — **exists** | 13 |
| **never added anywhere in this repo's history** | **20** |

Not 46. **26 allowlist entries were removed, and 16 Notion cards that had been flipped to
`Rejected` were restored to `Done`.**

## What actually went wrong, four times

1. `git log --all --diff-filter=A -- <path>` **per path** — applies history simplification, misses
   files added on merged side branches. Gave 62/10/25.
2. Rebuilt the list from a **truncated** `gh run view --log` capture — produced the wrong 23.
3. Took CI's next failure list as "the answer" when it was only *what remained after the previous
   23 were suppressed*. The union was 46.
4. Concluded migration re-stamping was unhandled by grepping `_MANGLE_RULES` — while
   `resolve_restamped_migration` already existed 70 lines below.

Every one is the same mistake: **reasoning about what the tool would say instead of running it and
reading the answer.** Number 4 is the sharpest, because "search for the capability, not the name"
is the rule this very document was written to illustrate.

## Standing caveat

The 20 remaining are absent **by path**. That is filename evidence, not capability evidence — and
capability checks on four clusters found three had shipped under different names
(`feedback_to_gold.py` for correction→gold promotion; `extraction_agents_storage.py` +
`rce_extraction_agents.sql` for the extraction runtime; `run_judge_calibration.py` +
`run_rag_triad.py` for LLM-as-judge). Only AI-W3.4's Promptfoo **PR gate** was confirmed genuinely
absent — `eval-llm-reports.yml` says in its own header that it "never gates a PR".

Assume the 20 over-report. Check the capability before acting on any of them.


---

# Original document (superseded — read the correction above first)

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

Taken from the guard's own output on a full-history checkout. The 110 claims account for exactly:

| category | count | what it means |
|---|---:|---|
| existed once, later renamed or removed | **51** | the work **shipped**; the path went stale |
| underscore-mangled by Notion | **13** | **the file exists** — `backend/eval/init.py` is really `backend/eval/__init__.py` |
| never existed in any commit on any branch | **46** | the real phantom set, across **26** tasks |
| | **110** | reconciles exactly against the original run |

**~58% were not phantom Done at all** — still the majority, but far short of the 76% an earlier pass claimed. They were the guard asking the wrong question: *"is this a
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


> **Three reconstruction errors, all the same class of mistake, all recorded.**
>
> 1. A first pass ran `git log --all --diff-filter=A -- <path>` **per path** and reported
>    62/10/25. That form applies history simplification and misses a file added on a merged side
>    branch: two migrations returned 0 commits that way but 1 under `--full-history`, and their
>    adding commit `ded8c5e5` is an ancestor of `origin/main`. They shipped.
> 2. A second pass rebuilt the list from a **truncated** `gh run view --log` capture and produced
>    23 findings that were the wrong 23 — task `541` actually fails on
>    `.github/workflows/ai-eval-gate.yml`, not the single path the partial log had shown.
> 3. A third pass then took CI's next failure list as "the answer", when it was only *what
>    remained after the previous 23 were suppressed*. The complete set is the union: **46**.
>
> Each error was caught by running the guard and reading its output, and each time the
> correction came from the tool rather than from reasoning about the tool. That is the whole
> lesson: **51 + 13 + 46 = 110** reconciles against the original run exactly, and nothing short
> of that did.

## The 46 that never existed

Each is allowlisted under an `<aiq>:<path>` key scoped to the task that made the claim, so the
suppression cannot leak to another task claiming the same path. The Notion cards are flipped off
`Done` separately.

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

### 575 · AI-W6.2 — Correction-to-gold-fixture promotion script

<https://app.notion.com/p/AI-W6-2-Correction-to-gold-fixture-promotion-script-da5887c64d488375ad5301d509ebf307>

Claimed 5 deliverable(s), none of which ever existed:

- `backend/app/services/correction_anonymizer.py`
- `backend/app/services/correction_promotion.py`
- `backend/scripts/promote_correction_to_gold.py`
- `backend/tests/fixtures/pilot/promoted/README.md`
- `backend/tests/test_promote_correction.py`

### 541 · AI-W3.4 — Promptfoo PR-gate CI workflow

<https://app.notion.com/p/AI-W3-4-Promptfoo-PR-gate-CI-workflow-551887c64d488341b82e012254891375>

Claimed 3 deliverable(s), none of which ever existed:

- `.github/test-events/sample-pr.json`
- `.github/workflows/ai-eval-gate.yml`
- `backend/prompts/promptfooconfig.yaml`

### 552 · AI-W5.1 — Extraction Agent runtime + versioning semantics

<https://app.notion.com/p/AI-W5-1-Extraction-Agent-runtime-versioning-semantics-69e887c64d488372b28e010000bdafa8>

Claimed 3 deliverable(s), none of which ever existed:

- `backend/app/services/extraction_agent.py`
- `backend/tests/test_extraction_agent_runtime.py`
- `supabase/migrations/20260601000000_extraction_agents.sql`

### 111 · IMM-10 · Frontend — wire Step 4 'Immigration' in employee journey wizard

<https://app.notion.com/p/IMM-10-Frontend-wire-Step-4-Immigration-in-employee-journey-wizard-fa7887c64d4883f996b481423ade90c5>

Claimed 2 deliverable(s), none of which ever existed:

- `backend/tests/test_immigration_requirements_summary.py`
- `frontend/src/features/immigration/ImmigrationStep.tsx`

### 188 · IMM-16 · Backend — immutable data access audit log (DB trigger)

<https://app.notion.com/p/IMM-16-Backend-immutable-data-access-audit-log-DB-trigger-8ec887c64d488315b54401b17798b408>

Claimed 2 deliverable(s), none of which ever existed:

- `docs/privacy/immigration-data-access-log.md`
- `supabase/migrations/20260605500000_imm16_profile_access_audit_trigger.sql`

### 545 · AI-W7.1 — Eligibility-reasoning LLM node (Claude Sonnet via Bedrock Frankfurt)

<https://app.notion.com/p/AI-W7-1-Eligibility-reasoning-LLM-node-Claude-Sonnet-via-Bedrock-Frankfurt-019887c64d488255934f8160b560b67e>

Claimed 2 deliverable(s), none of which ever existed:

- `backend/relopass/agents/eligibility_reasoner.py`
- `backend/tests/test_eligibility_reasoner.py`

### 592 · C1-07P · Prompt engineering: LLM entity-resolution fallback (structured output)

<https://app.notion.com/p/C1-07P-Prompt-engineering-LLM-entity-resolution-fallback-structured-output-4a1887c64d488382a65981e62b8e8a36>

Claimed 2 deliverable(s), none of which ever existed:

- `prompts/entity/resolver_v1.eval.md`
- `prompts/entity/resolver_v1.txt`

### 617 · AI-W2.2 — Adapter: ai_trace_logger.TraceSession → agent_runs writer

<https://app.notion.com/p/AI-W2-2-Adapter-ai_trace_logger-TraceSession-agent_runs-writer-b5d887c64d4883babd2c813f21190d51>

Claimed 2 deliverable(s), none of which ever existed:

- `backend/app/services/agent_run_writer.py`
- `backend/tests/test_agent_run_writer.py`

### 714 · P3-01b · Build context-precision evaluator

<https://app.notion.com/p/P3-01b-Build-context-precision-evaluator-b3e887c64d4883b8910601a238b0a800>

Claimed 2 deliverable(s), none of which ever existed:

- `scripts/eval_context_precision.py`
- `scripts/rag_eval_harness.py`

### 144 · IMM-17 · Backend — right-to-access data export endpoint

<https://app.notion.com/p/IMM-17-Backend-right-to-access-data-export-endpoint-a30887c64d4882fab84901f8dabaaa41>

Claimed 1 deliverable(s), none of which ever existed:

- `supabase/migrations/20260605600000_imm17_erasure_requests.sql`

### 145 · IMM-18 · Backend — data erasure workflow + retention automation

<https://app.notion.com/p/IMM-18-Backend-data-erasure-workflow-retention-automation-7de887c64d488382990381e959c2e128>

Claimed 1 deliverable(s), none of which ever existed:

- `supabase/migrations/20260605700000_imm18_retention_automation.sql`

### 319 · FOUNDATION-1A · Design & create events + daily_summaries schema

<https://app.notion.com/p/FOUNDATION-1A-Design-create-events-daily_summaries-schema-f66887c64d488399a69381da9881b67c>

Claimed 1 deliverable(s), none of which ever existed:

- `supabase/migrations/20260523000000_analytics_events_and_daily_summaries.sql`

### 332 · [P4-3] 'Add document' — ad-hoc forms outside the registry

<https://app.notion.com/p/P4-3-Add-document-ad-hoc-forms-outside-the-registry-4be887c64d48821595b2014ba6c9d1c6>

Claimed 1 deliverable(s), none of which ever existed:

- `supabase/migrations/20260605600000_case_forms_adhoc.sql`

### 540 · Test runner: stop sending invite emails to fake @testco.com domains (kills Resend sender reputation)

<https://app.notion.com/p/Test-runner-stop-sending-invite-emails-to-fake-testco-com-domains-kills-Resend-sender-reputation-85e887c64d488276973d01b8d6d1d33f>

Claimed 1 deliverable(s), none of which ever existed:

- `scripts/relopass_api_runner.js`

### 555 · AI-W5.2 — PASSPORT_TD3 extraction agent (deterministic MRZ + LLM for non-MRZ fields)

<https://app.notion.com/p/AI-W5-2-PASSPORT_TD3-extraction-agent-deterministic-MRZ-LLM-for-non-MRZ-fields-d05887c64d4883a58f4b010551924d8b>

Claimed 1 deliverable(s), none of which ever existed:

- `backend/tests/test_passport_td3_agent.py`

### 565 · C2-06 · Policy-versus-reality gap detector (entitlement gaps with clause citations)

<https://app.notion.com/p/C2-06-Policy-versus-reality-gap-detector-entitlement-gaps-with-clause-citations-fd8887c64d4882fcad4881c5567949ae>

Claimed 1 deliverable(s), none of which ever existed:

- `backend/relopass/policy_evidence/models.py`

### 574 · C2-01 · FamilyMember + spouse/child document types (MARRIAGE_CERT, BIRTH_CERT, FOSTER_CARE_ORDER)

<https://app.notion.com/p/C2-01-FamilyMember-spouse-child-document-types-MARRIAGE_CERT-BIRTH_CERT-FOSTER_CARE_ORDER-fa5887c64d488398857e01d287b0c57a>

Claimed 1 deliverable(s), none of which ever existed:

- `supabase/migrations/20260602000000_rce_family_document_types_seed.sql`

### 577 · C2-02b-FOLLOWUP · Agent wiring + AgentRegistry registration (tax_cert_{fr,de,no}.py)

<https://app.notion.com/p/C2-02b-FOLLOWUP-Agent-wiring-AgentRegistry-registration-tax_cert_-fr-de-no-py-831887c64d488350a374819a77d8c95e>

Claimed 1 deliverable(s), none of which ever existed:

- `backend/relopass/agents/extraction/tax_cert_findings.py`

### 580 · AI-I.5 — Remove/avoid LangGraph dependency; commit FastAPI + Pydantic pipeline pattern

<https://app.notion.com/p/AI-I-5-Remove-avoid-LangGraph-dependency-commit-FastAPI-Pydantic-pipeline-pattern-65d887c64d4882e4815c814156a821fe>

Claimed 1 deliverable(s), none of which ever existed:

- `audit/ADR-001-no-langgraph.md`

### 601 · P1-04a · Build specialist_review_events analytics schema + ETL view

<https://app.notion.com/p/P1-04a-Build-specialist_review_events-analytics-schema-ETL-view-90a887c64d488228abde818681bd3d68>

Claimed 1 deliverable(s), none of which ever existed:

- `supabase/migrations/20260604120000_specialist_review_calibration_view.sql`

### 620 · AI-W3.5 — Nightly full-corpus eval job + Langfuse leaderboard

<https://app.notion.com/p/AI-W3-5-Nightly-full-corpus-eval-job-Langfuse-leaderboard-366887c64d4882bb99b6815310fbd134>

Claimed 1 deliverable(s), none of which ever existed:

- `.github/workflows/ai-eval-nightly.yml`

### 627 · AI-W5.4 — DIPLOMA extraction agent

<https://app.notion.com/p/AI-W5-4-DIPLOMA-extraction-agent-1e6887c64d4882059782011d1981145d>

Claimed 1 deliverable(s), none of which ever existed:

- `prompts/extraction/diploma_v1.txt`

### 665 · P3-01c · Build factual-consistency evaluator

<https://app.notion.com/p/P3-01c-Build-factual-consistency-evaluator-f10887c64d48828d87d001690d624308>

Claimed 1 deliverable(s), none of which ever existed:

- `scripts/eval_factual_consistency.py`

### 698 · [BUG-A] Fix GET /api/company/branding-config returning 500 — missing branding_config column

<https://app.notion.com/p/BUG-A-Fix-GET-api-company-branding-config-returning-500-missing-branding_config-column-81b887c64d4883efae9c0190e1d53d8c>

Claimed 1 deliverable(s), none of which ever existed:

- `supabase/migrations/20260527_add_company_branding_config.sql`

### 750 · AI-W2.1 — Migration: unified agent_runs table with RLS

<https://app.notion.com/p/AI-W2-1-Migration-unified-agent_runs-table-with-RLS-18c887c64d4883809486012e7de21c71>

Claimed 1 deliverable(s), none of which ever existed:

- `supabase/migrations/20260531000000_agent_runs.sql`

## What this does not say

These 23 are **historical** — May–June 2026 workstreams (`AI-W*`, `C2-*`, `IMM-*`, `P3-*`,
`FOUNDATION-*`). Recording that they did not ship is not a judgement that they still should. That
is a product call, and deliberately not made here.

Nor does it say the other 74 were well-authored. The 10 underscore cases are real authoring bugs —
CLAUDE.md tells authors to wrap paths in backticks precisely because Notion renders a bare
`__tests__` as bold and eats the underscores. The guard now resolves them **and warns**, naming
each card, so they get fixed instead of being quietly absorbed forever.
