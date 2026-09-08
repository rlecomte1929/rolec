# 2-hour autonomous burst — operator stepping away

**Operator:** Romain is offline for ~2 hours. Decide and act. Use the rules below — don't pause for confirmation on cases that meet the auto-merge criteria, and do skip-and-log cases that don't.

## Auto-merge — do not ask, just do

A PR is auto-merge eligible if **ALL** of these are true on the rebased branch:

1. CI is green (every job ✓ or skipped, no failures, durations > 10s — not the billing fast-fail pattern).
2. **No Supabase migration in the diff** (no new file under `supabase/migrations/`).
3. **No new `public.*` table** created by this PR.
4. **No file touched** under `.github/workflows/`, `.githooks/`, or `audit/REMEDIATION_PLAN.md`. CLAUDE.md is also off-limits.
5. `cd frontend && npx tsc --noEmit` returns 0 (if frontend changed).
6. Dual-layer routing rule satisfied: if the PR adds a new router, mount-check confirms every new route is reachable on `backend.main:app`. The check command from CLAUDE.md is the authority.
7. No merge conflicts beyond mechanical (registration files, additive requirements lists, allowlist appends with no semantic disagreement).
8. `curl -s -o /dev/null -w "%{http_code}" https://api.relopass.com/health` returns 200 immediately before AND 15 seconds after merge.

If all 8 hold: `gh pr merge <N> --merge --delete-branch`, watch the deploy via 3 health-poll samples 15 seconds apart, log to `audit/daytime-run-summary-20260601.md`, move to the next PR. **No pause, no question.**

## Skip-and-log — do not attempt, write to stuck file

A PR is skip-and-log if **ANY** of these are true:

- Carries a Supabase migration (Romain decides apply-or-defer when he's back).
- Creates a new `public.*` table (RLS hard-gate review needed by Romain).
- Has a real merge conflict (semantic, not mechanical).
- CI fails for a non-billing reason after rebase + one re-trigger.
- Mount-check shows a new route missing from `backend.main:app`.
- Touches CLAUDE.md, workflows, hooks, or REMEDIATION_PLAN.md.
- Anything that would normally trigger a "pause for confirmation" under the interactive prompt.

For each skip: write one entry to `audit/daytime-run-stuck.md` with PR number, title, exact blocker (one paragraph), and the next action required from Romain. Then **continue to the next PR.**

## Hard stops — stop the run entirely, do not continue

Stop and do not start the next PR if **ANY** of these happen:

- A merge to main causes `/health` to drop below 200 for >60 seconds.
- A merge to main causes the next CI on main to fail with a non-billing failure.
- Three consecutive PRs land in `stuck.md` (suggests something systemic is wrong).
- The Anthropic API returns rate-limit or quota errors.
- You discover a force-push or other irreversible bad action would be needed to proceed.

When a hard stop fires: write `audit/daytime-run-HALT.md` with the timestamp, the PR that triggered it, the exact failure, and the state of main + open PRs. Then exit cleanly.

## What to work through (in order, oldest dependency first)

Block 3 — C1-11 chain (#181 → #184 → #182 → #186)
Block 4 — Contradiction Resolution + intake hotfix (#189 → #183, then #190)
Block 5 — Independent backend/AI (#187, #188, #196, #195)
Block 6 — C2 stream (#176, #178, #191)

Skip #209 entirely (in tomorrow's separate sitting). For #197–#208 + #210, only close them as superseded *if* #209 lands today — otherwise leave them open.

## Deliverables at end of the 2-hour window

When Romain comes back, he should be able to read three files and know everything:

1. `audit/daytime-run-summary-20260601.md` — table of every PR you touched, outcome, merge SHA, elapsed time, one-line note.
2. `audit/daytime-run-stuck.md` — every PR you deferred, with the specific reason and the next action needed.
3. `audit/daytime-run-HALT.md` — only present if a hard stop fired; otherwise absent.

Plus a final summary message in this conversation: total PRs landed, total skipped, queue size now vs at start, and your top recommendation for what Romain should look at first when he's back.

## Final rule

If you're unsure whether a PR is auto-merge or skip-and-log, **skip and log.** False-negatives (skipping a PR that could have merged) cost nothing — Romain handles it when he's back. False-positives (auto-merging something that breaks main) cost a rollback. Bias hard toward skipping when ambiguous.

## Begin

Continue from where you are — Block 3, #181. Apply these rules from the next action onward. No need to re-acknowledge; just start.
