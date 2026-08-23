# Task Authoring Standard — ReloPass AI Work Queue

**This is the single source of truth for what goes into a new Work Queue task.** Every skill
that creates a task (`relopass-bug-triage`, `notion-decomposition`, `relopass-interview-intake`,
`relopass-friday-digest`) MUST follow it. Do not re-define the task shape inline in a skill —
point here.

The goal is strict: **a task must be executable from the task alone.** An agent that picks it
up should never have to reverse-engineer intent, guess the approach, or invent an acceptance
test. If it would, the task is not `Ready for AI`.

---

## The six pillars (mandatory on every task)

Every task documents six things. Five map to dedicated Notion fields; **Plan** lives as a
section inside `Execution Prompt`.

| # | Pillar | What it answers | Where it lives (live Notion field) |
|---|--------|-----------------|------------------------------------|
| 1 | **Context** | *Why* this matters + background + current state | `Strategic Objective` (the why) + `Context Links` (refs) + Execution Prompt `## Context` |
| 2 | **Goals** | The concrete deliverable | `Expected Output` |
| 3 | **Plan** | The numbered steps to execute | Execution Prompt `## Plan` (numbered, each step with a `→ verify:`) |
| 4 | **Details** | Files, constraints, the exact code/pattern to follow | `Technical Constraints` / `UX Constraints` / `Files to Touch` + Execution Prompt `## Details` |
| 5 | **Metrics** | Machine-checkable acceptance criteria | `Validation Criteria` |
| 6 | **Verification** | The exact command / process to confirm it works end-to-end | `Test Command` (code) + Execution Prompt `## Verification` |

If any pillar is missing, the task is **not** ready — see the gate below.

---

## The hard gate — Definition of Ready

A task may be set to `Status = Ready for AI` **only when** `Definition of Ready = Vetted — ready`.
`Definition of Ready` is `Vetted — ready` **only when ALL of these hold**:

- [ ] **Context** — `Strategic Objective` is non-empty AND there is ≥1 `Context Link`.
- [ ] **Goals** — `Expected Output` is concrete and testable. ("Build the feature" / "fix the
      bug" is NOT concrete. "A `GET /api/cases/export` route returning CSV with columns X,Y,Z"
      is.)
- [ ] **Plan** — the `Execution Prompt` contains a numbered `## Plan` section (not a one-line
      "recommended approach").
- [ ] **Details** — `Technical Constraints` (and `UX Constraints` for frontend, `Files to
      Touch` for code) are populated where applicable; the Execution Prompt shows the pattern
      to follow.
- [ ] **Metrics** — ≥1 **machine-checkable** `Validation Criterion` (an HTTP status, a returned
      field, a passing assertion, a file that exists). Never subjective ("looks good",
      "works well"). Each criterion is **outcome-level**, not mechanism-level — see
      "Criteria describe outcomes" below.
- [ ] **Verification** — code tasks have a runnable `Test Command`; research/non-code tasks have
      an artifact-exists metric ("the file `X.md` exists and covers A, B, C").
- [ ] **Premise** *(Bug Fix / any task asserting a cause)* — `Failure Evidence` uses the
      `OBSERVED` / `HYPOTHESIS` / `REPRO` structure below, and no other field asserts a cause
      that `REPRO` does not establish.
- [ ] **Red-first** *(Bug Fix only)* — the `Test Command` **FAILS on current `origin/main`**, and
      the failing output is pasted into `## Verification`. A command that is already green
      cannot validate a fix.
- [ ] **Autonomy Tier** is set per `relopass-autopilot/SKILL.md` §A — including the
      diagnostic-confidence axis (an unreproduced cause is never 🟢/🟡).
- [ ] **Dependencies** are listed and either resolved or the task is `Blocked`.
- [ ] **Not already done** — searched for an existing branch/PR/commit solving this
      (`gh pr list --state all --search …`). Link it if found instead of duplicating.
- [ ] **Reachability** — name the **user path that reaches this change**, and the **query or
      request that proves the data it depends on exists in production**. If the answer is
      "nothing calls it yet" or "no row satisfies that condition yet", the task is not ready:
      it is blocked on the thing that would make it reachable. See below.

**If any box is unchecked:** set `Status = Needs Decomposition` and `Definition of Ready =
Needs info` (or `Draft` while still being written). **Never** create or leave a task at
`Ready for AI` with a missing pillar. This is not a soft preference — it is the gate.

### Merged is not live

`merged` → `migration applied` → `reachable by a user path` → `actually used`. CI proves the
first. The Reachability box exists because everything that went wrong on 2026-08-04 sat in the
second and third, and **every one of them had green tests**:

- **AIQ-1756** shipped an EN/NO label toggle gated on `hasNbLabels = fields.some(f => !!f.label_nb)`.
  Zero production templates have `label_nb` on any field, because the seed migration
  (`20261015000000`) was never applied. The toggle **never rendered for a single user**. Its
  219-line test suite passed throughout — the fixtures set `label_nb`; no real row does.
- **AIQ-1749** added a `feasibility` block to `GET /api/hr/cases/{id}/overview`. Correct,
  tested, deployed — and **nothing in the SPA called that endpoint**. In fact none of that
  router's six endpoints had a frontend consumer.
- **AIQ-1758** built an endpoint to register a prefilled data-sheet that does not exist in
  production, for the same unapplied-seed reason.

**Green tests prove the fixture, not the data.** When a feature is gated on a column value, a
row count, or a caller existing, assert that thing is true in production *before* the task is
`Ready for AI` — not after a reviewer wonders why nothing happens.

Cheapest form of the check, usually one line:

```sql
-- AIQ-1756 would have failed this instantly
SELECT count(*) FROM form_templates ft
  CROSS JOIN LATERAL jsonb_array_elements(ft.fields) f
  WHERE NULLIF(f->>'label_nb','') IS NOT NULL;   -- returns 0 → the toggle cannot render
```

```bash
# AIQ-1749 would have failed this instantly
git grep -rn "hr/cases/.*overview" -- frontend/src   # no hits → nothing consumes the field
```

Corollary for anything touching the DB: **assume a merged migration is unapplied until the
ledger says otherwise.** 147 are pending as of 2026-08-04. Check
`supabase_migrations.schema_migrations` for a *gap*, not just the tip — one missing version
mid-run is the tell.

Executors trust the gate: `relopass-autopilot` §B and `relopass-dev-queue` Phase 1 treat
`Definition of Ready = Vetted — ready` as the eligibility signal.

> **The gate checks completeness, not truth.** All six pillars can be present, confident, and
> wrong — that is exactly how AIQ-1687 and AIQ-1689 both reached an executor with false root
> causes on 2026-07-23. The rules below exist to close that hole; the executor's
> falsification step (`relopass-dev-queue` Phase 2.5) is the backstop.

---

## Separate what was OBSERVED from what you THINK caused it

The single most expensive failure mode in this queue is a **hypothesis written as fact**. Once a
guessed cause lands in `Strategic Objective`, `Files to Touch`, or `## Plan`, the executor reads
it as an instruction and implements it — even when the real cause is elsewhere.

Any task asserting a cause (all `Bug Fix` tasks) MUST structure `Failure Evidence` as:

```
OBSERVED:   [verbatim, what was actually seen. Status codes, DB rows, the literal UI state.
             NO interpretation, NO cause. Preserve the exact symptom wording.]
HYPOTHESIS: [the suspected cause, explicitly labelled as a guess.]
REPRO:      [the command / query / steps that reproduce it, AND their output.
             Write "none" if you did not reproduce it — do not leave this blank.]
```

**The hard rule:** `Strategic Objective`, `Files to Touch`, and `Execution Prompt ## Plan` may
assert a cause **only** when `REPRO` establishes it. With `REPRO: none`, they must be phrased as
"hypothesis — verify before implementing".

**Preserve symptom wording exactly.** AIQ-1689's evidence said "**NO** 'Request quotations'
button"; its title said the button "stays **disabled**". Those are different failures with
different causes — a missing render gate vs. an unmet condition — and that one word was the
entire answer. Paraphrasing a symptom destroys the most diagnostic thing in the report.

### Criteria describe outcomes, not mechanisms

A `Validation Criterion` states what a user or API can observe end-to-end. It must never name the
function or file expected to change — otherwise the criterion silently encodes the hypothesis,
and becomes unsatisfiable if the hypothesis is wrong.

| ❌ Mechanism-level (encodes a guess) | ✅ Outcome-level (survives a wrong guess) |
|---|---|
| "the fixture writes the shortlist so the button is ENABLED" | "a staged session can submit an RFQ end-to-end" |
| "`require_case_access` resolves assignment ids" | "`GET /api/payment/status/{assignment_id}` returns 200 with the real tier" |

AIQ-1689's criteria 1–2 were mechanism-level and **unsatisfiable by any fixture change** — the
task could not pass no matter what was built. That is only discoverable before the work if the
criteria are written against the outcome.

### Severity claims need a compensating-control check

Before asserting "leak", "exposure", "bypass", or revenue impact, name the controls you checked
and what they returned. AIQ-1687 was filed as a revenue leak; a server-side backstop
(`assert_roadmap_access`) meant the real impact was UI-only. An overstated severity mis-ranks
the whole queue.

---

## Canonical Execution Prompt template

Write this into the `Execution Prompt` field. Two variants — pick by task type. The six `##`
sections are mandatory and appear in this order.

### Code / implementation variant

```
## AI Brief — generated [YYYY-MM-DD] by <skill-name>

## Context
[Why this task exists, the background, and the CURRENT state of the code/data — what is true
today that makes this necessary. Link the originating evidence.]

## Goals
[The single concrete deliverable. Mirrors Expected Output. What exists when this is done that
did not before.]

## Plan
1. [Step] → verify: [how you'll know this step is done]
2. [Step] → verify: [...]
3. [Step] → verify: [...]

## Details
**Files to touch:**
- `path/to/file.ext` lines X–Y — [why relevant]

**Pattern to follow / code excerpt:**
[10–30 lines: the exact section to change or the pattern to copy — e.g. a sibling migration,
a similar route, an existing component]

**Constraints:** [hard rules — mirrors Technical/UX Constraints. Violating = failure.]

## Metrics
[The machine-checkable acceptance criteria — mirrors Validation Criteria. Each must be
verifiable by a command or an inspection, not a judgement.]

## Verification
**Test command:** [exact tsc / pytest / jest / curl command that proves it works]
**Process:** [how to confirm end-to-end beyond the command — e.g. "hit the route as an
employee, confirm 200 + the roadmap step advances"]

**Schema state:** [No DB changes] OR [migration file + version]
**Snapshot date:** [YYYY-MM-DD] — re-verify if >7 days old before executing.
```

### Research / non-code variant

```
## AI Brief — generated [YYYY-MM-DD] by <skill-name>

## Context
[Why this research/analysis is needed now, and what decision it informs.]

## Goals
[The concrete artifact — e.g. "a markdown report at /path comparing X vs Y across dimensions
A–F". Mirrors Expected Output.]

## Plan
1. [Research step] → verify: [source gathered / question answered]
2. [Synthesis step] → verify: [...]
3. [Write-up step] → verify: [...]

## Details
**Starting sources / context:** [URLs, prior docs, who to talk to]
**Constraints:** [scope bounds, tone, what NOT to include, compliance rules e.g. never claim a
compliance status]

## Metrics
[Machine-checkable: "artifact exists at <path> and covers A, B, C", "every claim carries a
source URL", "≥3 actionable recommendations".]

## Verification
**Process:** [how to confirm the artifact meets the metrics — checklist against the Goals.]
**Snapshot date:** [YYYY-MM-DD] — re-verify if >7 days old before executing.
```

The **Plan** section is the material upgrade over the old templates (which had only a 1–3
sentence "Recommended approach"). A real numbered plan with per-step verification is what lets
an agent execute — and self-correct — without coming back to ask.

---

## Canonical field names & values (end the drift)

The Notion **title property is `fable`** (not `Name`, `Title`, or `Task Title` — those names
appear in older skill text and are wrong). When creating via `notion-create-pages`, set the
title; do not invent a `Name`/`Task Title` property.

Live select values (use exactly):

- **Status:** `Needs Decomposition` · `Ready for AI` · `Blocked` · `AI in Progress` ·
  `Human Review` · `Validation` · `Done` · `Rejected` · `Archived` · `Parked`
- **Definition of Ready:** `Draft` · `Vetted — ready` · `Needs info`
- **Autonomy Tier:** `🟢 Green — auto` · `🟡 Yellow — self-validate + sample` ·
  `🔴 Red — full human gate` (rubric: `relopass-autopilot/SKILL.md` §A)
- **Priority:** `P0` · `P1` · `P2` · `P3`
- **Estimated Complexity:** `Trivial` · `Low` · `Medium` · `High` · `Very High` · `S`
- **Task Type:** `Frontend Implementation` · `Backend Implementation` · `UX Redesign` ·
  `Database Migration` · `Prompt Engineering` · `RAG Improvement` ·
  `Performance Optimization` · `Research` · `Competitive Analysis` · `Bug Fix`
- **Product Area:** `Core Product` · `AI Layer` · `Integrations` · `UX` · `Infrastructure` ·
  `GTM` · `Admin`
- **Layer:** `UI` · `API` · `Isolation` · `Feature` · `Infrastructure`
- **Final Validation Result:** `Pending` · `Passed` · `Partial` · `Failed`

Free-text pillar fields: `Strategic Objective`, `Expected Output`, `Technical Constraints`,
`UX Constraints`, `Validation Criteria`, `Dependencies`, `Context Links`, `Execution Prompt`,
`Files to Touch`, `Failure Evidence`, `Test Command`, `Risk & Rollback`. Date field:
`Recon Snapshot Date`.

### Population rules

- **Backtick every file path** in `Execution Prompt` / `Files to Touch` (`` `backend/main.py` ``).
  A bare path containing `__tests__` renders as bold and silently drops the underscores — the
  deliverable-integrity CI guard then fails on every PR.
- **Metrics must be machine-checkable.** If the only acceptance you can write is subjective,
  the task is `🔴 Red` (needs human judgement) — say so; do not pretend it is auto-checkable.
- **Titles are imperative** ("Add…", "Fix…", "Retire…", "Research…").
- **Always search before creating** — dedupe by ID/title against the existing queue.
- **Never invent premises.** State only what recon verified; if a claim is unconfirmed, mark it
  as an assumption in `## Context`, don't assert it. Use the `OBSERVED` / `HYPOTHESIS` / `REPRO`
  structure above — it is the enforceable form of this rule. (Generated tasks have shipped false
  premises repeatedly — AIQ-1687 and AIQ-1689 both did, on the same day — which is what this
  standard exists to stop.)

---

## Closing a task: the metrics trailer

Every executor ends `Execution Notes` with this single line. It is the only source of data on how
often the queue sends agents after phantoms, and it costs one line:

```
PREMISE: Confirmed|Refuted|Partial   DUPLICATE: yes|no   OUTCOME: code|docs|no-op
```

- `PREMISE` — did the stated cause survive Phase 2.5 falsification?
- `DUPLICATE` — was this already fixed/PR'd elsewhere when picked up?
- `OUTCOME` — what actually shipped: production code, docs/guardrail only, or nothing.

Read these in bulk periodically and compute **false-premise rate by authoring skill**
(`relopass-bug-triage` vs `notion-review-validator` vs Audos run reports). Fix the worst upstream
generator rather than patching individual tasks. A skill whose tasks are frequently `Refuted` is
producing hypotheses it has not tested.

---

## Worked example — before / after

**Before** (thin, would be blocked): a `relopass-friday-digest` task with only
`fable = "Add CSV export for HR cases"`, `Status = Ready for AI`, `Expected Output = "let HR
export cases"`. No Plan, no machine-checkable metric, no Test Command, no Context Link,
`Definition of Ready` unset. → An agent picking this up cannot tell the route, the columns, the
auth, or how to prove it works.

**After** (passes the gate):
- `fable`: `Add CSV export endpoint for HR cases`
- `Status`: `Ready for AI` · `Definition of Ready`: `Vetted — ready` · `Priority`: `P2` ·
  `Task Type`: `Backend Implementation` · `Product Area`: `Core Product` · `Layer`: `API` ·
  `Autonomy Tier`: `🟡 Yellow — self-validate + sample` · `Assigned AI Agent`: `Claude Code`
- `Strategic Objective`: "HR asked repeatedly for a spreadsheet of their cases; without export
  they re-key data by hand — a top-3 friction point in the Mar interviews."
- `Context Links`: interview note URL + `backend/app/routers/cases_read.py`
- `Expected Output`: "A `GET /api/hr/cases/export` route (HR/admin only) returning `text/csv`
  with columns: case_id, employee_name, origin, destination, status, created_at — scoped to the
  caller's company."
- `Technical Constraints`: "FastAPI; reuse `require_admin_or_hr` from `backend.app.auth_deps`;
  company-scope via `hr_company_ids()`; stream CSV, don't build in memory."
- `Files to Touch`: `` `backend/app/routers/cases_read.py` ``, register in both `backend/main.py`
  and `backend/app/main.py`.
- `Validation Criteria`: "curl as HR → 200 + `Content-Type: text/csv`; row count == that HR's
  case count; curl as employee → 403; curl cross-company → 0 foreign rows."
- `Test Command`: `` curl -s -H "Authorization: Bearer $HR" https://api.relopass.com/api/hr/cases/export -o /tmp/c.csv && head -1 /tmp/c.csv ``
- `Execution Prompt`: the six-section code template above, with a numbered Plan
  (add route → scope query → CSV stream → register both apps → test), the reuse pattern, and
  the verification process.

Every pillar is present; the gate passes; an agent can execute it cold.

---

## Provenance of this file

Tracked in the repo on **2026-08-23**. Until then it existed only at
`~/.claude/skills/relopass-dev-queue/references/task-authoring-standard.md` on one laptop —
not in this repo, not in any repo. Two `--strict` CI guards
(`check_deliverable_integrity.py`, `check_queue_status_hygiene.py`) and four skills
(`relopass-bug-triage`, `notion-decomposition`, `relopass-interview-intake`,
`relopass-friday-digest`) depend on the rules below, and none of them could read it.

**This copy is the source of truth.** The skills' `references/` copy should point here.
