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

Taken from the guard's own output on a full-history checkout, which classified **87** claims:

| category | count | what it means |
|---|---:|---|
| existed once, later renamed or removed | **51** | the work **shipped**; the path went stale |
| underscore-mangled by Notion | **13** | **the file exists** — `backend/eval/init.py` is really `backend/eval/__init__.py` |
| never existed in any commit on any branch | **23** | the real phantom set, across **12** tasks |

**~74% were not phantom Done at all.** They were the guard asking the wrong question: *"is this a
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


> **Two reconstruction errors, both recorded because they are the same class of mistake.**
>
> 1. A first pass ran `git log --all --diff-filter=A -- <path>` **per path** and reported
>    62/10/25. That form applies history simplification and misses a file added on a merged side
>    branch: two migrations returned 0 commits that way but 1 under `--full-history`, and their
>    adding commit `ded8c5e5` is an ancestor of `origin/main`. They shipped.
> 2. A second pass rebuilt the list by parsing a **truncated** CI log, and produced 23 findings
>    that were the wrong 23 — task `541`, for instance, actually fails on
>    `.github/workflows/ai-eval-gate.yml`, not the path the partial log showed.
>
> The numbers in this document are taken **verbatim from the guard's own output** on a
> full-history checkout. Reconstructing what a tool would say, instead of running it and reading
> the answer, is what produced both errors.

## The 23 that never existed

Each is allowlisted under an `<aiq>:<path>` key scoped to the task that made the claim, so the
suppression cannot leak to another task claiming the same path. The Notion cards were flipped off
`Done` the same day.

The largest cluster is an entire eval workstream marked Done with nothing shipped.

### 575 · AI-W6.2 — Correction-to-gold-fixture promotion script

<https://app.notion.com/p/AI-W6-2-Correction-to-gold-fixture-promotion-script-da5887c64d488375ad5301d509ebf307>

Claimed 5 deliverable(s), none of which ever existed:

- `backend/app/services/correction_anonymizer.py`
- `backend/app/services/correction_promotion.py`
- `backend/scripts/promote_correction_to_gold.py`
- `backend/tests/fixtures/pilot/promoted/README.md`
- `backend/tests/test_promote_correction.py`

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

### 541 · AI-W3.4 — Promptfoo PR-gate CI workflow

<https://app.notion.com/p/AI-W3-4-Promptfoo-PR-gate-CI-workflow-551887c64d488341b82e012254891375>

Claimed 2 deliverable(s), none of which ever existed:

- `.github/test-events/sample-pr.json`
- `.github/workflows/ai-eval-gate.yml`

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

### 332 · [P4-3] 'Add document' — ad-hoc forms outside the registry

<https://app.notion.com/p/P4-3-Add-document-ad-hoc-forms-outside-the-registry-4be887c64d48821595b2014ba6c9d1c6>

Claimed 1 deliverable(s), none of which ever existed:

- `supabase/migrations/20260605600000_case_forms_adhoc.sql`

### 555 · AI-W5.2 — PASSPORT_TD3 extraction agent (deterministic MRZ + LLM for non-MRZ fields)

<https://app.notion.com/p/AI-W5-2-PASSPORT_TD3-extraction-agent-deterministic-MRZ-LLM-for-non-MRZ-fields-d05887c64d4883a58f4b010551924d8b>

Claimed 1 deliverable(s), none of which ever existed:

- `backend/tests/test_passport_td3_agent.py`

### 574 · C2-01 · FamilyMember + spouse/child document types (MARRIAGE_CERT, BIRTH_CERT, FOSTER_CARE_ORDER)

<https://app.notion.com/p/C2-01-FamilyMember-spouse-child-document-types-MARRIAGE_CERT-BIRTH_CERT-FOSTER_CARE_ORDER-fa5887c64d488398857e01d287b0c57a>

Claimed 1 deliverable(s), none of which ever existed:

- `supabase/migrations/20260602000000_rce_family_document_types_seed.sql`

### 620 · AI-W3.5 — Nightly full-corpus eval job + Langfuse leaderboard

<https://app.notion.com/p/AI-W3-5-Nightly-full-corpus-eval-job-Langfuse-leaderboard-366887c64d4882bb99b6815310fbd134>

Claimed 1 deliverable(s), none of which ever existed:

- `.github/workflows/ai-eval-nightly.yml`

### 627 · AI-W5.4 — DIPLOMA extraction agent

<https://app.notion.com/p/AI-W5-4-DIPLOMA-extraction-agent-1e6887c64d4882059782011d1981145d>

Claimed 1 deliverable(s), none of which ever existed:

- `prompts/extraction/diploma_v1.txt`

## What this does not say

These 23 are **historical** — May–June 2026 workstreams (`AI-W*`, `C2-*`, `IMM-*`, `P3-*`,
`FOUNDATION-*`). Recording that they did not ship is not a judgement that they still should. That
is a product call, and deliberately not made here.

Nor does it say the other 74 were well-authored. The 10 underscore cases are real authoring bugs —
CLAUDE.md tells authors to wrap paths in backticks precisely because Notion renders a bare
`__tests__` as bold and eats the underscores. The guard now resolves them **and warns**, naming
each card, so they get fixed instead of being quietly absorbed forever.
