# Activating the Claude Code agent lane (Feedback Autopilot — Phase 3)

The headless Haiku pipeline (`autofix-pipeline`) handles **Trivial/Low, single-file** fixes. The
**Claude Code agent lane** handles the slice it can't: **Medium/High complexity, 🟢/🟡 tier** tasks,
by running the `/relopass-dev-queue` skill end-to-end. It is shipped **inert** and cannot run until
the steps below are done — its runtime was **not** verifiable at build time (no Anthropic key in CI).

## What's already wired
- **Selector:** `scripts/notion_ready_queue.py --cc-next` → JSON `{aiq, page_id, title, url,
  autonomy_tier, complexity}` for the top eligible Ready-for-AI task (🟢/🟡, Medium/High), or `{}`.
- **Nightly workflow:** `.github/workflows/autopilot-cc-nightly.yml` (21:00 UTC + manual) → selects a
  task → `gh workflow run agent-dispatch.yml` → `claude-code-action` runs the skill → pushes an
  `autofix/**` branch → re-enters `autofix-validate.yml` (E2E → prod canary → merge; **Medium+ stays
  a draft PR for human review**, never auto-merged).
- **Gate:** the workflow is a no-op unless `vars.AGENT_DISPATCH_ENABLED == 'true'` **and**
  `secrets.ANTHROPIC_API_KEY` is set.

## Activation steps (all required)
1. **Add the secret** `ANTHROPIC_API_KEY` (repo → Settings → Secrets and variables → Actions).
   Both `agent-dispatch.yml` and this lane read it; both no-op while it's empty.
2. **Verify the action + skills** — in `agent-dispatch.yml`, confirm `anthropics/claude-code-action`
   is pinned to a working version and that the `relopass-*` skills (esp. `relopass-dev-queue` and
   the `relopass-fix-*` variants) are **available to the CI Claude Code** (skill install step or
   plugin config). Do a **manual `workflow_dispatch` dry-run of `agent-dispatch.yml`** with a
   throwaway prompt first — this is the single most likely failure point.
3. **Set the caps** — `AUTOPILOT_MAX_CC_TASKS_PER_NIGHT` (repo var, default `1`) and document/observe
   the `AUTOPILOT_CC_NIGHTLY_USD_CAP` budget. NOTE: precise per-run CC cost isn't auto-metered
   (claude-code-action doesn't report cost cleanly) — watch spend manually at first.
4. **Enable** `vars.AGENT_DISPATCH_ENABLED = 'true'` and (for the fix lane it merges into)
   `AUTOPILOT_FIX_ENABLED` per your governance. Also flip the backend/DB flags
   (`AUTOPILOT_ENABLED`, `AUTOPILOT_CC_ENABLED`) as the governor expects.
5. **Watch the first runs** on `/admin/autopilot-metrics` (Phase 4 dashboard) and in Notion.

## Known limitations
- **One task per nightly run** is safe today. The selector re-picks the same task until it leaves
  `Ready for AI` (dispatch is async), so the workflow stops on a repeat to avoid re-dispatching.
  Multi-per-night needs the selector to exclude in-flight tasks (e.g. mark `AI in Progress` on
  dispatch, which requires a Notion **write** token — `NOTION_QUEUE_TOKEN` here is read-only).
- The lane only progresses tasks; **it never auto-merges Medium+** — those land as draft PRs for a
  human, by design.
