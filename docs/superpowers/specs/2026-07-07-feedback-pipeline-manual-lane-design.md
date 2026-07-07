# Feedback pipeline — close the manual-lane gaps

**Date:** 2026-07-07
**Status:** Approved (design), pending implementation plan
**Source spec:** `docs/specs/feedback-pipeline-orchestration.md` (v1.0), reconciled against `origin/main` + the Feedback Autopilot merged 2026-07-06/07.

## Purpose

The admin feedback triage → dispatch → fix path (the human-driven `FeedbackTab`) has three gaps that the source spec identified. This design closes the high-ROI, low-risk subset of them, reusing the substrate the autonomous **Feedback Autopilot** already shares (`engineer_task`, Notion Work Queue, `feedback_status`, the diagnostics canary). This is the **human-lane counterpart** to the autopilot, not a competing design — both lanes now write one shared pipeline-state model.

Deliberately **out of scope** this round (deferred, no rework cost later): GitHub webhook state-sync (`feedback-status-sync.yml`, source §5.4) and PostHog post-deploy exception verification (source §5.5). The autopilot's diagnostics canary + funnel events already provide post-deploy signal.

## Verified premises (against `origin/main`, 2026-07-07)

These correct/confirm the source spec's §11 open questions:

- **PostHog is installed** — `posthog-js ^1.396.4`, initialized in `frontend/src/analytics.ts` with session replay on (AIQ-1434). Not a new dependency. (Not used in this round, but its premises hold for a later PostHog-verify layer.)
- **`client_context` is NOT fed into `engineer_task`** — `admin_feedback._load_product_fields` selects message/category/page_url/screenshot/reporter/report_id only. The captured reproduction signal never reaches spec generation. **Highest-value, zero-cost gap.**
- **`feedback_status.dispatch_status` is plain `text`, no CHECK** (added in `20260819000000_feedback_ticket_fields.sql`). The state machine is a purely additive migration.
- **The stale `admin_notes_browser` migration (source §0) does not exist** — `20260726000000` is an unrelated visa-permit seed. Nothing to drop.
- **Autonomy Tier** is read by the autopilot `--cc-next` selector but never written on dispatch (matches the read-only audit). Real Notion select values: `🟢 Green — auto` / `🟡 Yellow — self-validate + sample` / `🔴 Red — full human gate`.

## Scope decisions (user-approved)

- **Scope:** Reconciled core — 4 pieces below. Defer webhooks + PostHog-verify.
- **Integration:** Shared state, one source of truth. `feedback_status` is the pipeline-state mirror for **both** the manual lane and the autopilot.

---

## Piece 1 — Enrich `engineer_task` with the reproduction signal

**Problem:** Specs are written blind to the actual failure even though we capture it.

**Change:**
- Extract diagnostics from `client_context` jsonb: top `recentErrors[].{message,fingerprint}`, up to ~3 `recentFailedRequests[].{path,status,requestId}`, failing function. Format a compact **"Reproduction signal"** block.
  - In `_load_product_fields` (manual lane) — add `client_context` to the SELECT and parse.
  - In the autopilot ingest path — it already holds `client_context`; format the same block.
- `engineer_task(...)` gains optional `diagnostics: str`, appended to the LLM prompt **after `mask_pii` + the existing `_PII_RESIDUE` guard**. client_context is scrubbed at capture, but re-mask — never trust upstream.
- One extraction helper shared by both lanes (new small function; empty-safe — returns `""` when no diagnostics).

**Files:** `backend/app/services/feedback_task_engineer.py`, `backend/app/routers/admin_feedback.py`, `backend/app/services/autopilot_ingest.py`.

## Piece 2 — Compute + write Autonomy Tier on dispatch

**Change:**
- New deterministic `compute_autonomy_tier(task_type, complexity, product_area, layer) -> 'green'|'yellow'|'red'` in `feedback_task_engineer.py`.
  - **Red:** auth, billing/payments, migrations, security, RLS, access-control areas — regardless of complexity.
  - **Green:** trivial/low complexity AND copy/UI/content task types in non-sensitive areas.
  - **Yellow:** everything else (default-safe).
- `engineer_task` returns `autonomy_tier` in the task dict → preview surfaces it; admin can override before create.
- `notion_work_queue.build_properties` writes the `Autonomy Tier` select using the real option values above (matches what `scripts/notion_ready_queue.py --cc-next` reads — the two lanes finally agree).
- Persist to `feedback_status.autonomy_tier` on `dispatch_create`.

**Files:** `backend/app/services/feedback_task_engineer.py`, `backend/app/services/notion_work_queue.py`, `backend/app/routers/admin_feedback.py`.

## Piece 3 — Shared pipeline state on `feedback_status`

**Additive migration** (no CHECK exists today to fight):

- **Widen `dispatch_status`** to lifecycle values: `new → triaged → spec_drafted → dispatched → in_progress → in_review → deployed → done`, plus terminal `verify_failed | dismissed | wont_fix`. Add a permissive `CHECK` for exactly those values.
- **New columns:** `autonomy_tier text`, `pr_url text`, `pr_number int`, `branch_name text`, and timestamps `triaged_at, spec_drafted_at, dispatched_at, in_progress_at, deployed_at, done_at`.
- **Writers:**
  - `dispatch_create` → `dispatched` + `dispatched_at` + `dispatch_ref` (existing) + `autonomy_tier` (new).
  - The autopilot's existing `POST /api/crons/autopilot-event` endpoint is extended so `merged / canary_passed / task_done` events also advance `feedback_status` (`in_progress → deployed → done`) when the entity maps to a feedback item — reuses the `autofix-validate.yml` funnel wiring, **no new GitHub webhook**.
  - Manual transitions from the button strip (Piece 4).
- **Security:** altering an existing table (not creating one), so the existing `feedback_status` RLS/anon posture is inherited. Confirm existing policies cover the new columns (they do — column-level grants aren't scoped per-column here). No new hard-gate table.
- **Migration timestamp:** must be greater than the true directory max (repo contains future-dated migrations, e.g. `20260819000000`). Compute `max+1` at implementation time via `git ls-tree origin/main supabase/migrations | sort | tail`. Validate via rollback-tx.

**Files:** `supabase/migrations/<computed-ts>_feedback_status_pipeline.sql`, `backend/app/routers/admin_feedback.py`, `backend/app/routers/crons.py`.

## Piece 4 — Progressive Button Strip in `FeedbackTab`

**Change:**
- New `ProgressStrip.tsx`: horizontal stepper of the current `dispatch_status`, showing only the valid next action(s) for that state (`new → [Triage]`, `triaged → [Draft spec]`, `spec_drafted → [Create task]`, `dispatched → [Mark in progress]`, `deployed → [Mark done] [Verify failed]`), plus `Dismiss / Won't fix` escapes.
- New endpoint `PATCH /api/admin/feedback/{stream}/{id}/state` (`require_admin`): validates the transition against an allowed-transitions map, stamps the matching timestamp, returns 409 on illegal jump.
- The existing 2-step dispatch (Draft → Create) stays; the strip wraps it so the full lifecycle lives in one place. Autonomy Tier renders as a colored chip per row.

**Files:** `frontend/src/components/admin/ProgressStrip.tsx` (new), `frontend/src/components/admin/FeedbackTab.tsx`, `frontend/src/api/feedback.ts` (or existing admin feedback API wrapper), `backend/app/routers/admin_feedback.py`.

## Data flow

```
submit → public.feedback (+ client_context) → feedback_status (new)
  │
  ├─ manual lane: admin triages (Piece 4 strip) → dispatch/preview
  │     └─ engineer_task( + diagnostics [P1], returns autonomy_tier [P2] )
  │     └─ dispatch/create → Notion (Autonomy Tier written [P2]) + feedback_status=dispatched [P3]
  │     └─ admin advances state via PATCH /state [P4]
  │
  └─ autopilot lane: ingest (dedup) → engineer_task( + diagnostics [P1] ) → Notion + feedback_status=dispatched
        └─ autofix-validate.yml funnel events → autopilot-event → feedback_status in_progress/deployed/done [P3]
```

## Error handling

- Diagnostics extraction is empty-safe (no client_context → `""`, engineer_task unchanged).
- `engineer_task` LLM failure already surfaces as 502 (unchanged).
- Illegal state transition → 409 (validator), never a silent write.
- Migration is idempotent (`add column if not exists`), validated by rollback-tx before commit.
- `autopilot-event → feedback_status` bridge is best-effort: if the entity doesn't map to a feedback item, it no-ops (funnel event still emitted).

## Testing

- **Backend (`.venv311`):** `compute_autonomy_tier` boundaries; diagnostics extraction (jsonb→block, empty-safe, PII re-masked); state-transition validator (legal/illegal/terminal); `autopilot-event → feedback_status` bridge.
- **Frontend:** `vitest` ProgressStrip (correct next-actions per state; no `api/supabase` import → jsdom trap) + `tsc --noEmit` + `build`.
- **Migration:** rollback-tx (inline DDL + seed + asserts, end `RAISE EXCEPTION 'ALL_TESTS_PASSED'`).

## Rollout

- No feature flag needed — additive and human-driven; the strip only exposes states that already exist. Autonomy Tier + diagnostics enrichment improve every dispatch immediately.
- Dual-register any new router surface per the repo rule (both `backend/main.py` and `backend/app/main.py`). The new `PATCH /state` lives on the existing `admin_feedback` router (already dual-registered) — no new registration.
- New `/api/crons/*` behavior is an extension of the existing `autopilot-event` route — already allowlisted.
- Migration applied out-of-band per repo migration discipline; ledger reconciled by committing the matching file.

## Out of scope (deferred, no rework cost)

- GitHub webhook `feedback-status-sync.yml` (source §5.4) — autopilot funnel events cover the automated lane.
- PostHog post-deploy exception verification (source §5.5) — diagnostics canary already gives post-deploy signal; PostHog-verify can layer on later.
