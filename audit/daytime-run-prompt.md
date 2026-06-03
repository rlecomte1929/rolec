# Daytime interactive PR merge run — Claude Code prompt

The human operator (Romain) is awake and present. Work through the plan one PR at a time. Pause for his approval at the points specified below. Ask questions when judgment is needed.

## Your task

Execute the plan in `audit/overnight-run-plan.md`, in the order listed there, but with **interactive checkpoints** rather than full autonomy.

## How to work

1. **First action:** read `audit/overnight-run-plan.md` and `CLAUDE.md` end-to-end. Summarize the queue and the first 3 PRs you'll attempt, then **wait for Romain's "go" before doing anything else.** This is your initial confirmation gate.

2. **Use the `relopass-dev-queue` skill** for each PR. Let it drive the recon/plan/implement/validate loop.

3. **Per-PR cadence (do this for every PR):**
   a. State the PR number, title, branch, and your one-paragraph plan for it.
   b. Run `gh pr view <N>`, check mergeable state and CI status.
   c. **Pause and ask: "Proceed with #N?"** Wait for Romain's confirmation before any push, merge, or branch-state-changing operation.
   d. On approval: rebase, push (`--force-with-lease`), wait for CI green, then `gh pr merge <N> --merge --delete-branch`.
   e. Watch the Render deploy. Poll `https://api.relopass.com/health` until 200, or report failure.
   f. **Pause and ask: "Continue to the next PR?"** before starting the next merge.

4. **Pause and ask immediately, do not proceed, on any of these:**
   - Any merge conflict beyond mechanical (registration files, additive lists, requirements dedup).
   - Any CI failure that isn't an obvious known flake.
   - Any TypeScript or test regression after rebase.
   - Any migration that's missing the RLS hard gates (ENABLE RLS + policy + REVOKE anon).
   - Any case where you'd otherwise mark the PR stuck in autonomous mode — surface it instead and ask.

5. **Between blocks:** after finishing each block (1 through 6 in the plan), summarize what landed, what's next, and explicitly ask Romain whether to continue, pause, or change course.

## Strict constraints (unchanged from overnight version)

- **No `git push --force`** without `-with-lease`. Ever.
- **No force-pushes to `main`.** Ever.
- **No editing `CLAUDE.md`, `.github/workflows/*`, `.githooks/*`, or `audit/REMEDIATION_PLAN.md`.**
- **No touching Supabase production** beyond what the PRs themselves carry.
- **No new Notion tasks** unless Romain asks for one.
- **Honor the hard stops** in the plan: main goes red after a merge → stop; Render deploy fails → stop; Supabase migration fails on remote → stop. In each case: report immediately, do not attempt rollback yourself, wait for instructions.

## Logging

Maintain these files as you go:

- `audit/daytime-run-summary-$(date +%Y%m%d).md` — one row per PR: number, title, merge SHA, elapsed time, notes. Update after each merge.
- `audit/daytime-run-stuck.md` — append-only, only for PRs that Romain asks you to skip after surfacing a blocker.

Do not write a final summary unless the whole plan completes or Romain asks for one — interactive mode means he's seeing each step as it happens.

## Begin

Start by reading the plan and CLAUDE.md, then propose the first 3 PRs you'll attempt and wait for go-ahead. Do not run any tool that modifies state (git push, gh pr merge, file edits) before that approval.
