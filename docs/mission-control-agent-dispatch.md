# Mission Control P3c — the multi-file coding agent (design + wiring)

**Status: greenfield + inert.** The workflow ships but cannot run until the activation
checklist below is complete. This is the final hop of the Mission Control loop
(`see → triage → plan → execute`): turning an **approved plan** into a real multi-file
PR via `claude-code-action`, reusing the existing autofix safety pipeline.

## The loop (end-to-end)

```
work_item (triaged)  → work_item_planner.build_plan() → human approves plan_json
  → POST /api/admin/work-items/{id}/dispatch            (Mission Control P2)
  → autofix-pipeline edge fn fires a workflow_dispatch on agent-dispatch.yml
  → agent-dispatch.yml: claude-code-action edits multiple files + writes tests
  → push to autofix/bug-*                                (this workflow)
  → autofix-validate.yml: blocklist → Playwright E2E → squash-merge → deploy → auto-revert
  → run-callback updates work_item_runs status in the console
```

The single-file nightly path (`processBug`) is unchanged; this is an additive,
plan-driven, multi-file path.

## What exists vs. what is greenfield

| Piece | State |
|---|---|
| `work_item_planner.build_plan()` (the approved plan) | **Exists** (PR #1233) |
| `POST .../dispatch` + `autofix_dispatch.py` (backend → edge fn) | **Exists** (PR #1232, unmerged) |
| `autofix-validate.yml` (E2E → merge → deploy on `autofix/**`) | **Exists** |
| `ANTHROPIC_API_KEY` repo secret | Exists (used by `eval-llm-reports.yml`) |
| **`.github/workflows/agent-dispatch.yml`** | **This PR** (inert) |
| Edge-fn branch that fires `workflow_dispatch` on this workflow | **Greenfield** (see below) |
| `claude-code-action` anywhere in CI | **Greenfield** — version + input names unverified |

## The edge-fn → `workflow_dispatch` trigger (greenfield)

`supabase/functions/autofix-pipeline/index.ts` already holds a vault `GITHUB_TOKEN` and a
generic `ghPost` helper. The multi-file path replaces the single-file branch+PR block with:

```ts
// inputs.prompt = the approved plan_json (stringified); branch = autofix/bug-<id>
await ghPost(
  `/repos/${owner}/${repo}/actions/workflows/agent-dispatch.yml/dispatches`,
  { ref: "main", inputs: { prompt, work_item_id, branch } },
  env.githubToken,
);
```

Note: `workflow_dispatch` returns **204 No Content** (no PR url), so the run-status comes
back via `autofix-validate.yml` → the existing `run-callback` endpoint, not the dispatch
response.

## Safety

- **Inert by default:** the job is gated on `vars.AGENT_DISPATCH_ENABLED == 'true'` — it
  will not run even if dispatched until that repo variable is set.
- **Injection-hardened:** untrusted `workflow_dispatch` inputs are passed via `env:`
  (never inlined as `${{ }}` in a shell), and the branch is charset-restricted to
  `autofix/<safe>`.
- **Same gates as the nightly loop:** because the agent pushes to `autofix/*`,
  `autofix-validate.yml` runs the blocklist + Playwright E2E and only squash-merges on a
  green run (auto-revert on deploy failure). The human plan-approval step upstream is the
  first gate.

## Activation checklist (do all before flipping the variable)

1. Confirm the `claude-code-action` **version** and **input names** (`anthropic_api_key`,
   `prompt`) against the action's current release — they are a best-effort pin here.
2. Restore **GitHub Actions billing** (runs are blocked until then).
3. Ensure the vault `GITHUB_TOKEN` (or a dedicated token) carries **`actions:write`** so
   the edge fn can call the `dispatches` API.
4. Land the P2 edge-fn change and add the multi-file `workflow_dispatch` branch above.
5. **Dry run first:** dispatch with a trivial plan (e.g. "add a comment to one file") and
   confirm the `autofix/*` branch + `autofix-validate.yml` chain behaves before opening it
   to real plans.
6. Set repo **Variables → `AGENT_DISPATCH_ENABLED = true`**.
