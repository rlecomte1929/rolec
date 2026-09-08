# Parker Framework Audit Pipeline

An automated, checkpointed pipeline that runs the 10 strategic recommendations
from `audit/parker-framework-audit.md` against the ReloPass codebase, one PR at
a time, with a human approval gate between each step.

## Why a pipeline (not "just paste 10 prompts")

Each step modifies real code: new tables, new migrations, new routers, new
frontend pages. Steps E, F, and I depend on **what step D actually shipped**
(table column names, route paths), not what was sketched in the audit doc.

The pipeline enforces:

- A **read-before-code** discipline (each step reads the prior steps' RESULT.md).
- A **plan-before-edit** discipline (each step writes PLAN.md before touching files).
- A **verify-before-advance** discipline (`pytest` + `tsc` + git diff captured
  before any step is marked complete).
- A **one-branch-per-PR** discipline matching CLAUDE.md's audit/stage-N convention.
- A **human-in-the-loop** discipline: no step auto-advances. You review each
  PR, you run `next`.

## Requirements

- `bash` ≥ 4
- `jq`
- `git`
- macOS (auto-clipboard via `pbcopy`) or any Linux (clipboard not required)

## Quickstart

You already launched step A externally. Initialise the pipeline to record that:

```bash
cd /Users/romainlecomte/Documents/GitHub/rolec
chmod +x audit/parker-pipeline/pipeline.sh
./audit/parker-pipeline/pipeline.sh init --launched-externally A
```

Once Claude Code finishes step A and pushes the PR, capture the result:

```bash
# 1. Drop Claude Code's RESULT.md into the run directory.
#    (Or ask Claude Code to write it there directly during step A — that's
#    what the wrapped prompt instructs for future steps.)
mkdir -p audit/parker-pipeline/runs/<run_id>/A
# place RESULT.md at audit/parker-pipeline/runs/<run_id>/A/RESULT.md

# 2. Verify.
./audit/parker-pipeline/pipeline.sh verify A

# 3. Read VERIFICATION.md, then advance.
./audit/parker-pipeline/pipeline.sh complete A
```

For subsequent steps (B onwards), use the wrapped prompt:

```bash
./audit/parker-pipeline/pipeline.sh prompt B   # prints + copies to clipboard
# paste into Claude Code, let it run
./audit/parker-pipeline/pipeline.sh verify B
./audit/parker-pipeline/pipeline.sh complete B
```

Or chain `verify → complete → show next prompt` in one command:

```bash
./audit/parker-pipeline/pipeline.sh next
```

## Commands

```
pipeline.sh init [--launched-externally <step>]   Bootstrap a new run.
pipeline.sh status                                 Show the board.
pipeline.sh prompt <step>                          Generate + clipboard the prompt.
pipeline.sh verify <step>                          Run tests, capture diff.
pipeline.sh complete <step>                        Mark step done, advance.
pipeline.sh next                                   verify + complete + next prompt.
pipeline.sh reset                                  Wipe state (asks to confirm).
pipeline.sh help                                   Show help.
```

## Where artifacts live

```
audit/parker-pipeline/
├── STATE.json                              Current run state.
├── pipeline.sh                             The orchestrator.
├── lib/
│   ├── preamble.md.tmpl                    Shared "read context, write plan" header.
│   └── closeout.md.tmpl                    Shared "write RESULT.md, open PR" footer.
├── prompts/                                10 task bodies.
│   ├── A-cox-survival.md
│   ├── B-benefit-optimizer.md
│   ├── C-cluster-tiering.md
│   ├── D-prompt-registry.md
│   ├── E-rlhf-lite.md
│   ├── F-passport-ocr-oss.md
│   ├── G-carbon-tco.md
│   ├── H-conjoint.md
│   ├── I-translation.md
│   └── J-nlg-variety.md
└── runs/<run_id>/<step>/                   Per-step artifacts.
    ├── PROMPT.md                           The wrapped prompt (preamble + body + closeout).
    ├── PREREQUISITES.md                    Auto-generated dependency list.
    ├── PLAN.md                             Claude Code writes this before coding.
    ├── RESULT.md                           Claude Code writes this at closeout.
    ├── VERIFICATION.md                     `pipeline.sh verify` writes this.
    └── BLOCKED.md                          Claude Code writes this only if blocked.
```

## How the prompts chain

The wrapped prompt for step **N** instructs Claude Code to:

1. Read `STATE.json` and the audit doc.
2. Read `PREREQUISITES.md` — auto-generated based on hard-coded per-step
   dependencies (see `step_deps()` in `pipeline.sh`).
3. For each named upstream step, read its `RESULT.md` to learn what was
   *actually* shipped — not what the original audit doc sketched.
4. Write `PLAN.md` before any file edit.
5. If a prerequisite is missing → write `BLOCKED.md` and stop.
6. Otherwise: branch, code, test, write `RESULT.md`, push, open the PR, stop.

The pipeline never auto-advances. You review the PR. You run `next`.

## Branch and PR conventions

Each step works on `audit/parker-step-<N>-<slug>` and opens a PR titled
`audit(parker-<N>): <slug>`. The `parker-audit` GitHub label is added to every PR.
This matches CLAUDE.md's existing `audit/stage-N-<slug>` convention.

PRs are **not** auto-merged. Render auto-deploys `main`, so an unreviewed merge
is a user-visible deploy.

## UI / UX reuse posture

The 10 main pipeline steps are deliberately backend-heavy. Most frontend work is
deferred to follow-up prompts you trigger manually after reviewing a UI
proposal.

| Step | UI impact | Significant? |
|------|-----------|--------------|
| A, B, C, F | None | — |
| D | One small admin table page | No |
| E | One column added to D's table | No |
| G | Backend only (panel deferred) | Yes (deferred) |
| H | Backend only (employee + HR pages deferred) | Yes (deferred) |
| I | One small wrapper + one settings field | No |
| J | In-place updates only | No |

Deferred follow-up prompts live at:
- `prompts/followups/G-frontend.md` — admin AI economics panel.
- `prompts/followups/H-frontend.md` — conjoint employee flow + HR results.

Run a follow-up by pasting it into Claude Code directly when you're ready —
the pipeline orchestrator does not auto-chain follow-ups.

The preamble template forces Claude Code to write `UI-PROPOSAL.md` and STOP
before any significant new UI surface. You approve the proposal, then re-run the
prompt to build the UI. That is your gate.

## Step dependency graph

```
A ──┐                     (Cox survival — independent)
B ──┤                     (Benefit optimizer — independent)
C ──┤                     (Cluster tiering — independent)
D ──┼──→ E (RLHF, reads D's prompt_versions schema)
    ├──→ F (Passport OCR OSS, reads D's router pattern)
    └──→ I (Translation, reads D + G)
G ──┘                     (Carbon TCO — independent)
H                         (Conjoint — independent)
J                         (NLG variety — independent)
```

Sequential A→J order respects D-before-E, D-before-F, D-before-I, G-before-I.

## Per-sprint groupings (from the audit doc)

| Sprint | Steps | Theme |
|--------|-------|-------|
| 1 | A, G | High leverage, low integration risk |
| 2 | B, H | Commercial artefacts (HR pitch) |
| 3 | D, E | Platform maturity (registry + RLHF loop) |
| 4 | C, F, I | Margin & coverage |
| 5 | J | NLG diversity |

The pipeline runs strictly sequentially (A→J), but you can re-order by
manually setting `current_step` in STATE.json if you prefer the sprint order.

## Recovering from a failed step

If Claude Code wrote `BLOCKED.md`:

```bash
cat audit/parker-pipeline/runs/<run_id>/<step>/BLOCKED.md
# fix the blocker (usually: complete the upstream dependency)
# then re-print the prompt for the blocked step:
./audit/parker-pipeline/pipeline.sh prompt <step>
```

If verification failed (pytest red, tsc red):

```bash
# Fix locally, push to the same branch, then re-verify:
./audit/parker-pipeline/pipeline.sh verify <step>
./audit/parker-pipeline/pipeline.sh complete <step>
```

## Safety checks built in

- `complete <step>` refuses to advance if RESULT.md is missing.
- Migrations are gated by CLAUDE.md's hard rules (RLS + policy + REVOKE FROM anon).
  Each prompt restates these rules in its preamble.
- `feature_key`-gated rollout flags are required on any new ML pathway
  (e.g. `PREDICTIONS_ENABLED`, `PASSPORT_OCR_OSS_SHARE`, `NLG_EXEC_SUMMARY_PROVIDER`).
- No step auto-merges PRs.

## When the pipeline is done

After step J completes, `pipeline.sh status` shows all 10 steps green and
`current_step = DONE`. You should have 10 merged PRs on `main` and 10 directories
under `runs/<run_id>/` documenting what shipped.

At that point the artefacts in `runs/<run_id>/` become the ReloPass AI/ML
architecture record-of-truth. Keep them. They are the evidence base for the next
Parker-style audit.
