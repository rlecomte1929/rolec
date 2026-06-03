# Overnight PR Merge Plan — 2026-06-01

**Generated:** 2026-05-31 (planning session in Cowork)
**Target start:** 2026-06-01 00:01 local time (fresh Claude budget cycle)
**Operator:** Claude Code in autonomous mode, executing this plan unattended.
**Author was asleep when this ran.** Do not ask questions. Log, decide, move on.

## Goal

Drain the 31-open-PR queue on `rlecomte1929/rolec` in dependency-correct, oldest-first order. Land the high-leverage merges first so even a partial run is useful.

## State of the queue at planning time

- **31 open PRs.** PR #211 (SEC-004 rate-limit coverage) is **already merged on main** — Parker integration was waiting for it.
- **Four streams:**
  1. Parker AI/ML pipeline (PRs #197–#210, 13 PRs, consolidated into #209).
  2. Migration / RLS hygiene (#179, #193, #194).
  3. C1 HR Dashboard chain (#181, #184, #182, #186, #189, #183, #187, #188, #195, #196).
  4. C2 rules / extraction + small fix (#176, #178, #191, #190).

## Dependency graph (real, not chronological)

```
                   ┌─ #179 (exception_requests migration fix) ────┐
                   │                                              ▼
SEC-004 (#211 ✓) ──► #209 Parker integration ─► closes #197–#208, #210

                   ┌─ #181 ─► #184 ─► #182 ─► #186  (C1-11 chain)
                   ├─ #189 ─► #183                  (C1-12 chain)
                   ├─ #187, #188, #195, #196        (parallel independents)
                   ├─ #194                          (SEC-RLSe, independent)
                   ├─ #190                          (intake hotfix)
                   └─ #176, #178, #191              (C2 stream)

#193 → diff against main first; if SEC-RLSa already in via #211, close as duplicate.
```

## Execution blocks (oldest-first within each tier)

### Block 1 — 00:01–01:00 · Unblock & big-bang Parker (highest leverage)

1. **#179** — `fix(migrations): make exception_requests RLS replayable from scratch`
   - Why first: it unblocks #209's §6 migration-replay gate, and fixes any future `supabase db reset` from scratch.
   - Acceptance: CI green, merge to main.

2. **#209** — `audit(parker): integration of steps A–J` (75 commits)
   - Rebase on the new `main` (post-#179).
   - Re-run mount-check before merge: `python3 -c "from backend.main import app; print(sorted(r.path for r in app.routes if any(p in r.path for p in ['/predicted-duration','/optimize-benefit-mix','/admin/prompts','/ai/feedback','/admin/ocr-shadow-comparison','/admin/ai-unit-economics','/conjoint','/translate','/exec-summary','/tldr'])))"` — expect 10 route families present.
   - Acceptance: CI green, TypeScript clean, mount-check shows all 10 families, merge to main, watch Render deploy go green.

3. **Close, do not merge: #197, #198, #199, #200, #201, #202, #203, #204, #205, #206, #207, #208, #210.**
   - These are individual Parker steps + reports + the hold marker. All obsoleted by #209.
   - Use `gh pr close <N> --comment "Superseded by #209 (parker integration A–J, merged $(date -I))"`.

**After Block 1: 31 open → 17 open.**

### Block 2 — 01:00–01:30 · SEC cleanup

4. **#193** — `SEC-RLSa · Tenant-scoped RLS for the cases domain (AIQ-658)`
   - Diff against main: `git fetch origin && git diff origin/main...origin/audit/stage-1-rls-a-cases-aiq658 -- supabase/migrations/ backend/`
   - If commit `b737700` (SEC-RLSa) is already in main via #211, close as duplicate with a comment.
   - Otherwise merge if CI green.

5. **#194** — `SEC-RLSe — RLS triage for audit / system-only tables (AIQ-662)`
   - Independent. Merge if CI green.

### Block 3 — 01:30–03:00 · C1-11 case detail stack (dependency-strict)

6. **#181** — `feat(backend): C1-11c-be — case detail endpoints (6 reads, RLS-scoped)` — foundational.
7. **#184** — `feat(hr-dashboard): C1-11c — Case detail page (5 sections + viewer Sheet)` — sits on #181.
8. **#182** — `feat(hr-dashboard): C1-11d + C1-11e — pdf.js viewer + bbox overlay` — sits on #184.
9. **#186** — `docs(audit): C1-11A — WCAG 2.1 AA audit on HR Dashboard` — docs only, fast.

Rebase each on main after the previous merge. Run `npm --prefix frontend run build` + `cd frontend && npx tsc --noEmit` before merging anything that touches the frontend.

### Block 4 — 03:00–03:45 · Contradiction Resolution + small hotfix

10. **#189** — `feat(backend): C1-12-be — resolve + escalate POST endpoints`.
11. **#183** — `feat(hr-dashboard): C1-12 — Contradiction Resolution UI` — sits on #189.
12. **#190** — `fix(intake): _destination_payload signature + wizard city hydration` — independent, small.

### Block 5 — 03:45–05:00 · Independent backend / AI work

13. **#187** — `feat(agents): C1-07 — entity resolver (5-stage deterministic-first)`.
14. **#188** — `feat(backend): C1-16 — case audit endpoint (chronological lineage)`.
15. **#196** — `feat(ai): AIQ-626 / P1-01a — immigration_retriever wrapper`.
16. **#195** — `feat(admin): PDF coordinate mapper — click-to-assign field positions (AIQ-174)`.

### Block 6 — 05:00–06:00 · C2 stream (oldest-first, deferrable)

17. **#176** — `feat(C2-06-FOLLOWUP): policy-gap adapter + rce.case_artefacts + endpoint` — **oldest open PR**, finally drained.
18. **#178** — `feat(extraction): C2-02b — FR/DE/NO tax_cert agents + runtime validators`.
19. **#191** — `feat(rules): C2-04 rule scraper + RuleChangeProposal queue (AIQ-555)`.

## Hard rules (do not violate)

- **Dual-layer routing.** Per `CLAUDE.md`: every new router must be registered in **both** `backend/main.py` AND `backend/app/main.py`. Verify with the `python3 -c "from backend.main import app..."` check before merging anything that adds a route.
- **Migration RLS gates.** Per `CLAUDE.md`: any new `public.*` table needs `ENABLE ROW LEVEL SECURITY` + at least one `CREATE POLICY` + `REVOKE ALL ... FROM anon`. If a migration in a PR is missing any of these, **stop and log to the stuck file** — do not patch on the fly.
- **CI gating.** Do not merge any PR with a failing CI check unless the failure is identified as a pre-existing main flake (cross-check against current main's CI). Pre-existing flakes are documented in `audit/parker-pipeline/PRE_MERGE_AUDIT.md` if useful.
- **No force-pushes to main.** Ever.
- **No force-pushes to other people's branches.** All these are yours, but still — `git push --force-with-lease`, never bare `--force`.
- **Render deploy watch.** After each merge to main, watch the Render deploy: `gh run watch` or poll `gh pr checks --watch`. If the deploy fails, **stop the entire run**, log everything, and surface the failure — do not compound failures.
- **One Supabase migration per merge cycle.** If a PR carries a migration, let it apply and verify `/health` returns 200 from prod before starting the next merge.
- **Never merge if main is currently broken.** Check `gh run list --branch main --limit 5` before each merge.

## Stuck-PR protocol

For any PR you cannot merge cleanly, **do not retry indefinitely**. Once per PR:

1. Try to rebase on current main.
2. If conflict: attempt to resolve only mechanical/registration conflicts (CLAUDE.md dual-layer additive stack — see `audit/parker-pipeline/PRE_MERGE_AUDIT.md` §8 for the union-merge pattern). Anything semantic — code logic, schema design, copy choices — **do not resolve**.
3. If CI fails after rebase: re-trigger once. If it still fails, log and move on.
4. Append a row to `audit/overnight-run-stuck.md` with: PR number, title, failure mode (CI / merge conflict / migration error / Render deploy / unknown), exact command that failed, the next action for the human reviewer, and the commit SHA on main at the time of the attempt.
5. **Move to the next PR.** Do not block the run on a single stuck PR.

## Hard stops (abort the entire run)

- **Main goes red after a merge:** stop immediately, document, do not merge anything else.
- **3 consecutive PR failures in the same block:** stop and document — something systemic is wrong.
- **Render deploy fails on a merge:** stop, document, surface for morning review.
- **Supabase migration fails to apply on remote:** stop, document, do not attempt rollback yourself.

## End-of-run deliverables

Write to the repo:

1. `audit/overnight-run-summary-YYYYMMDD.md` — what merged, what didn't, what's still on the queue, total elapsed time, recommended morning actions.
2. `audit/overnight-run-stuck.md` — append-only log of PRs that need human input.
3. `audit/overnight-run-YYYYMMDD-HHMMSS.log` — full transcript of the session (this is the launcher's job, you just need to not suppress output).

## Out of scope (do not do)

- Do not work on PRs outside this list.
- Do not refactor adjacent code in the PRs you merge.
- Do not "improve" the audit/ docs.
- Do not generate new tasks in Notion.
- Do not touch Supabase production via the Supabase MCP unless a PR specifically requires it.
- Do not change CI workflows, the pre-push hook, or `CLAUDE.md`.
