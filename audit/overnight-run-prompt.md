# Overnight autonomous merge run — Claude Code prompt

You are running unattended overnight starting 2026-06-01 00:01. The human author is asleep and cannot be reached. Do not ask questions. Decide, log, move on.

## Your task

Execute the plan in `audit/overnight-run-plan.md` end-to-end. That file is the authoritative instruction set: read it first, then follow it block by block.

## How to work

1. Read `audit/overnight-run-plan.md` in full before doing anything.
2. Read `CLAUDE.md` for the dual-layer routing rule, RLS migration gates, and pre-push hook details.
3. Use the `relopass-dev-queue` skill — it knows this codebase's conventions, the TypeScript strict-mode gotchas, the mandatory git-commit pattern, and the dual-layer routing trap. Invoke it when you start a PR; let it drive the recon/plan/implement/validate loop.
4. For each PR in the plan, in order:
   - `gh pr view <N> --json title,headRefName,baseRefName,mergeable,statusCheckRollup` to assess state.
   - Checkout the branch, rebase on current `origin/main`.
   - If clean rebase: push (`--force-with-lease`), wait for CI.
   - If conflict: only resolve mechanical conflicts (registration files, additive lists, requirements.txt deduping). For anything semantic, log to `audit/overnight-run-stuck.md` and skip.
   - Run local validations: `cd frontend && npx tsc --noEmit` for frontend-touching PRs; `cd backend && pytest -x` for backend-touching PRs (skip if too slow, rely on CI).
   - Wait for CI: `gh pr checks <N> --watch`.
   - If CI green: `gh pr merge <N> --merge --delete-branch` (use `--merge`, not `--squash` — these are stacked branches, history matters).
   - After merge: pull main, watch Render deploy with `gh run watch` or by polling Render's deploy endpoint. Curl `https://api.relopass.com/health` until 200 OK.
   - Smoke-test the new routes only if the PR added routes (see plan §"Hard rules" for the mount-check command).
5. After each merge, append a one-line summary to `audit/overnight-run-summary-$(date +%Y%m%d).md`: PR number, title, merge SHA, elapsed time, any notes.

## Strict constraints

- **No questions.** If you genuinely cannot decide, log the PR to `audit/overnight-run-stuck.md` and move to the next.
- **No `git push --force`** (without `-with-lease`). Ever.
- **No force-pushes to `main`.** Ever.
- **No editing `CLAUDE.md`, `.github/workflows/*`, `.githooks/*`, or `audit/REMEDIATION_PLAN.md`.**
- **No touching Supabase production** beyond what the PRs themselves carry.
- **No new Notion tasks.** This run only closes work; it doesn't create work.
- **No scope creep.** Only the PRs listed in the plan, in the order given.
- **Honor the hard stops** in the plan's "Hard stops" section. If any trigger, stop the run and write the summary file immediately.

## What "stuck" means

Be liberal about marking a PR stuck. The goal is throughput across the whole queue, not heroics on any single PR. If a PR needs more than ~10 minutes of attention, it's stuck — log it and move on. The human will look at it in the morning.

## End of run

When you reach the end of the plan (or hit a hard stop), write `audit/overnight-run-summary-$(date +%Y%m%d).md` with:

- Total elapsed time.
- PRs merged (number, title, merge SHA).
- PRs closed without merge (number, reason).
- PRs stuck (number, link to `overnight-run-stuck.md` entry).
- PRs not attempted (if the run stopped early).
- Final state of main (last commit SHA, CI status, Render deploy status).
- Recommended first action for the human at the start of the next session.

Then exit cleanly. Do not start unrelated work.

## Begin

Start with Block 1 of the plan. The first action is to assess and merge PR #179.
