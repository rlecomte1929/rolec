# Feedback-to-Fix Pipeline — Product Specification
**Version:** 1.0  
**Author:** Product (Romain + Claude)  
**Status:** Ready for implementation  
**Target:** Claude Code with repo mounted on `origin/main`

---

## 0. Prerequisites — Before Writing Any Code

The local workspace may contain stale edits applied to the wrong version of the files. Claude Code must run the following before implementing anything:

```bash
# Check for stale edits
git diff origin/main -- frontend/src/components/FeedbackWidget.tsx
git diff origin/main -- frontend/src/components/admin/FeedbackTab.tsx
```

**If diffs are found:** Review each change against the audit findings. Any edits that assume a direct Supabase insert in `FeedbackWidget.tsx` (instead of `submitProductFeedback()` via `POST /api/feedback`) or assume a simple `FeedbackRow` interface in `FeedbackTab.tsx` (instead of `UnifiedFeedbackItem` from `GET /api/admin/feedback`) are incorrect — revert them.

**Check the stale migration:**

```bash
ls supabase/migrations/ | grep 20260726
```

If `20260726000000_feedback_admin_notes_browser.sql` exists, it adds `admin_notes TEXT` and `browser TEXT` to `public.feedback`. These columns are wrong: browser is already in `client_context` JSONB; admin notes belong in `feedback_status.triage_notes` (see §4.3 of this spec). Do NOT apply this migration. Drop or `.skip` it.

**Canonical source of truth for the existing backend:** `backend/app/routers/admin_feedback.py`, `backend/app/routers/feedback.py`, `backend/app/services/feedback_task_engineer.py`. The frontend should match the API contracts those files expose.

---

## 1. Problem Statement

The current feedback loop has three disconnected phases:

1. **Triage** — admin reads a flat inbox, manually sets severity, has no pre-assembled context
2. **Dispatch** — spec generation exists but Autonomy Tier is never written, so agents can't route themselves correctly
3. **Execution to close** — once dispatched, the admin must manually check Notion, GitHub, and Render to know what happened; nothing flows back to the feedback row

The result: high admin cognitive load, variable spec quality, wasted agent tokens on under-specified tasks, and no automated verification that a fix actually worked.

This spec defines the complete system that closes all three gaps.

---

## 2. Goals

### 2.1 Primary goals
| Goal | Target | How measured |
|------|--------|--------------|
| Reduce admin time per bug (submission → dispatched) | < 3 minutes | `triage_at` − `created_at` where admin is present |
| Reduce wall-clock time to fix (Green tier bugs) | < 8 hours | `done_at` − `created_at` |
| Increase agent session success rate | > 65% Green, > 45% Yellow | dispatched items reaching `done` without `verify_failed` |
| Reduce tokens per agent session | ≤ 80k avg (Green) | logged from Claude Code session metadata |

### 2.2 Secondary goals
- Admin never needs to open Notion, GitHub, or Render to check fix status
- Every dispatched Notion task has Autonomy Tier set on creation
- PostHog session context is included in every spec automatically

### 2.3 Non-goals (explicitly out of scope)
- Linear / Jira / Sentry integration
- Multi-admin triage support
- Public changelog or status page
- Mobile push notifications
- SLA timers or escalation rules

---

## 3. Personas

**Romain (sole admin / founder)** — the only person triaging, reviewing specs, and verifying fixes. Spends currently 10–20 min per bug on context-gathering. Target: < 3 min, with no tool-switching.

**Pilot users (HR managers, employees)** — submit feedback via the in-app widget. They see a confirmation with a reference ID. They are not exposed to any pipeline state.

---

## 4. State Machine

This is the heart of the system. Every feature is a consequence of these states and transitions.

### 4.1 States

| State | Label shown to admin | Meaning |
|-------|---------------------|---------|
| `new` | New | Submitted, not yet reviewed |
| `triaged` | Triaged | Admin set severity/area; ready for spec |
| `spec_drafted` | Spec Ready | Preview generated; admin reviewing |
| `dispatched` | Dispatched | Notion task created; waiting for agent |
| `in_progress` | Agent Working | GitHub PR opened by agent |
| `in_review` | In Review | PR ready; admin or CI reviewing |
| `deployed` | Deployed | PR merged; Render deploy succeeded |
| `done` | Done ✓ | PostHog verified fix, or admin manually confirmed |
| `verify_failed` | Verify Failed | PostHog saw no improvement post-deploy |
| `dismissed` | Dismissed | Not worth fixing now; soft close |
| `wont_fix` | Won't Fix | Explicit rejection with reason |

### 4.2 Transitions

```
new ──[admin triages]──────────────────────► triaged
triaged ──[admin drafts spec]──────────────► spec_drafted
spec_drafted ──[admin confirms dispatch]───► dispatched
dispatched ──[GitHub webhook: PR opened]───► in_progress
in_progress ──[GitHub webhook: PR review]──► in_review
in_review ──[GitHub webhook: PR merged
             + Render deploy success]──────► deployed
deployed ──[PostHog verify: pass]──────────► done
deployed ──[PostHog verify: fail]──────────► verify_failed
deployed ──[admin clicks Verify Fix]───────► done  (manual override)
verify_failed ──[admin re-dispatches]──────► dispatched
any state ──[admin dismisses]──────────────► dismissed
any state ──[admin clicks Won't Fix]───────► wont_fix
```

### 4.3 DB changes required

Current `feedback_status` table (check existing schema before altering):

```sql
-- Extend dispatch_status enum to cover the full state machine.
-- Check the existing CHECK constraint first:
-- SELECT column_default, check_constraints FROM information_schema for dispatch_status
-- Then alter or replace the constraint to include all states below.

-- New valid values for feedback_status.dispatch_status:
-- 'new' | 'triaged' | 'spec_drafted' | 'dispatched' | 'in_progress'
-- | 'in_review' | 'deployed' | 'done' | 'verify_failed' | 'dismissed' | 'wont_fix'

-- Add columns to feedback_status:
ALTER TABLE public.feedback_status
  ADD COLUMN IF NOT EXISTS triage_notes     TEXT,           -- admin notes during triage
  ADD COLUMN IF NOT EXISTS pr_url           TEXT,           -- GitHub PR URL from webhook
  ADD COLUMN IF NOT EXISTS pr_number        INTEGER,        -- GitHub PR number
  ADD COLUMN IF NOT EXISTS branch_name      TEXT,           -- e.g. fix/BUG-260617-A1B2
  ADD COLUMN IF NOT EXISTS triaged_at       TIMESTAMPTZ,    -- when triage completed
  ADD COLUMN IF NOT EXISTS spec_drafted_at  TIMESTAMPTZ,    -- when preview generated
  ADD COLUMN IF NOT EXISTS dispatched_at    TIMESTAMPTZ,    -- when Notion task created
  ADD COLUMN IF NOT EXISTS in_progress_at   TIMESTAMPTZ,    -- when PR opened
  ADD COLUMN IF NOT EXISTS deployed_at      TIMESTAMPTZ,    -- when Render deploy fired
  ADD COLUMN IF NOT EXISTS done_at          TIMESTAMPTZ,    -- when verified/closed
  ADD COLUMN IF NOT EXISTS posthog_session_url TEXT,        -- session replay link
  ADD COLUMN IF NOT EXISTS posthog_verified    BOOLEAN,     -- true if auto-verified
  ADD COLUMN IF NOT EXISTS autonomy_tier       TEXT         -- 'green' | 'yellow' | 'red'
    CHECK (autonomy_tier IN ('green', 'yellow', 'red'));
```

**Migration file:** `supabase/migrations/20260729000000_feedback_status_pipeline.sql`

---

## 5. Feature Specifications

### 5.1 Progressive Button Strip

#### What it is
A horizontal action strip in the expanded feedback row. It replaces the current single Dispatch column with a full pipeline view. The admin always sees where the bug is and what single action is available next.

#### Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ✓ Triaged  │  [Draft Spec ▶]  │  Create Task (muted)  │  Agent  │  Review │ Done │
│  2h ago     │                  │                        │ waiting │ waiting │      │
└─────────────────────────────────────────────────────────────────────────────┘
```

Always visible, always full-width inside the expanded row. No steps are hidden.

#### Button states

| State | Visual | Behaviour |
|-------|--------|-----------|
| `complete` | ✓ green chip, label + relative time | Non-interactive; hover shows absolute timestamp |
| `active` | Navy (#0b2b43) filled button, label + ▶ | Clickable; shows spinner while async in-flight |
| `pending` | Grey (#94a3b8), 40% opacity | Disabled; has `title="Complete [previous step] first"` |
| `auto` | Animated pulse indicator | System is waiting for external signal (GitHub, Render, PostHog) |

**Rule:** Only one button is `active` at any time. Everything to its left is `complete`. Everything to its right is `pending` or `auto`.

#### Individual button definitions

**Step 1 — Triage**
- Active when: `dispatch_status === 'new'`
- Click action: expand an inline severity/area picker (two dropdowns: severity: critical/high/medium/low; area: ui/api/isolation/feature/other) + optional `triage_notes` textarea
- Save action: `PATCH /api/admin/feedback/{stream}/{id}` with `{ severity, area, dispatch_status: 'triaged', triage_notes, triaged_at }`
- On success: button becomes complete ✓, "Draft Spec" activates
- Keyboard: Enter to save when picker is open

**Step 2 — Draft Spec**
- Active when: `dispatch_status === 'triaged'`
- Click action: `POST /api/admin/feedback/{stream}/{id}/dispatch/preview` — existing endpoint
- While loading: button shows spinner; disable all other buttons
- On success: spec preview panel opens below the button strip; `dispatch_status` updated to `spec_drafted`; `spec_drafted_at` recorded
- The "Create Task" button activates ONLY after the spec panel has been open for ≥ 3 seconds AND the admin has scrolled or focused any field in it (anti-double-click guard)
- Admin can edit spec fields (title, execution_prompt, validation_criteria) inline before proceeding

**Step 3 — Create Task**
- Active when: `dispatch_status === 'spec_drafted'` AND spec acknowledgement guard passed
- Click action: `POST /api/admin/feedback/{stream}/{id}/dispatch/create` with the (possibly edited) spec
- On success: Notion link shown; `dispatch_status` → `dispatched`; `dispatched_at` recorded
- "In Progress" step switches to `auto` pulse state with label "Waiting for agent"

**Step 4 — In Progress** (auto-advancing)
- Transitions to `active` pulse: when `dispatch_status === 'dispatched'`
- Label: "Waiting for agent" with subtle animation
- Advances to `complete` automatically: GitHub Actions webhook fires `pr_opened`
- On complete: shows PR link (e.g. `#42 ↗`); `in_progress_at` recorded

**Step 5 — In Review** (auto-advancing)
- Transitions to `auto` pulse when `dispatch_status === 'in_progress'`
- Advances to `complete` automatically: GitHub Actions webhook fires `pr_merged`
- On complete: `in_review_at` recorded; "Deployed" step transitions to auto

**Step 6 — Done**
- Transitions to `auto` pulse when `dispatch_status === 'deployed'`
- Label: "Verifying…" — PostHog verification job will run 30 min after deploy
- Auto-advances to `complete` if PostHog confirms fix
- If PostHog returns `verify_failed`: step shows red warning icon; "Verify Fix" manual button activates
- Admin can always click "Verify Fix" manually regardless of PostHog result
- On done: entire strip collapses to a single green "Done ✓ [timestamp]" line

#### Dismiss / Won't Fix controls
Two small text buttons, always visible below the strip (not in the step sequence):
- "Dismiss" — soft close; shows reason dropdown (duplicate / not reproducible / low priority / test data)
- "Won't Fix" — hard close; requires a one-sentence reason (textarea, required)
Both available from any state after `triaged`. Before triage, only "Dismiss" is available.

---

### 5.2 PostHog Context Enrichment

#### Purpose
When the admin clicks "Draft Spec," the backend fetches the submitter's PostHog event history and injects it into the `engineer_task()` LLM prompt. The LLM then produces a spec with specific reproduction steps rather than a rephrasing of the feedback text.

#### Step A — Capture PostHog distinct_id at submission

In `diagnostics.ts` (the `collectDiagnostics()` function called by FeedbackWidget), add:

```typescript
posthog_id: (() => {
  try { return (window as any).posthog?.get_distinct_id?.() ?? null; }
  catch { return null; }
})(),
```

This stores the PostHog distinct_id in `client_context.posthog_id`. No other widget changes needed.

#### Step B — New service module: `posthog_context.py`

**File:** `backend/app/services/posthog_context.py`

```python
"""
posthog_context.py — Fetch user session context from PostHog for spec enrichment.

Called by engineer_task() before the LLM prompt is assembled.
Returns a formatted string safe to inject into the prompt.
All output is sanitised: no PII beyond what's already in the feedback text.
"""
```

**Function signature:**
```python
def fetch_session_context(
    posthog_id: str | None,
    feedback_created_at: datetime,
    page_url: str,
    window_minutes: int = 10,
) -> dict:
    """
    Returns:
      {
        "event_timeline": str,   # numbered list of events, empty string if unavailable
        "session_replay_url": str | None,
        "user_properties": dict,  # role, plan, feature flags — no names/emails
        "error_count": int,       # JS errors in the window
        "fetch_ok": bool,
      }
    """
```

**Implementation rules:**
1. Use `POSTHOG_API_KEY` (personal API key, not the project API key) and `POSTHOG_PROJECT_ID` env vars
2. Call `GET https://app.posthog.com/api/projects/{project_id}/events/?distinct_id={id}&after={t-window}&before={t+2min}&limit=30`
3. Format each event as: `  {+Ns} {event_name} [{properties.$pathname or properties.url or ''}]`  
   where `{+Ns}` is seconds before submission (e.g. `−120s`)
4. Filter out internal PostHog events (`$feature_flag_called`, `$identify`, `$set`) — keep page views, button clicks, custom captures, `$exception`
5. For session replay URL: look for `$session_id` in any event's properties, then construct `https://app.posthog.com/replay/{session_id}`
6. For user properties: call `GET /api/projects/{id}/persons/?distinct_id={id}` — extract `role`, `company_id`, `plan` from `properties`. Never include `email`, `name`, or PII.
7. **Always fail gracefully**: if PostHog is unreachable, returns `{"event_timeline": "", "session_replay_url": None, "user_properties": {}, "error_count": 0, "fetch_ok": False}` — spec generation proceeds without timeline. Log the failure at WARNING level.
8. Apply `safe_log_text()` to any event property values before logging.
9. Do NOT apply `mask_pii()` to the event timeline before injecting into the prompt — the event data (pathnames, event names) is not PII. Only the feedback `message` text is masked (already done in `engineer_task()`).

#### Step C — Inject into `engineer_task()`

In `feedback_task_engineer.py`, call `fetch_session_context()` before the LLM call:

```python
posthog = fetch_session_context(
    posthog_id=client_context.get("posthog_id"),
    feedback_created_at=created_at,
    page_url=page_url,
)
```

Add to the user message section of the engineer_task prompt:

```
User session context (PostHog, {N} events in the 10 min before submission):
{posthog.event_timeline or "Not available"}

Session replay: {posthog.session_replay_url or "Not available"}
User role: {posthog.user_properties.get("role", "unknown")}
JS errors in session: {posthog.error_count}
```

Add `session_replay_url` to the task output JSON so it gets written to the Notion task's "Context Links" field.

#### Step D — Spec preview indicator

In the spec preview panel (frontend), show a small badge: 
- `"📊 {N} PostHog events included"` if `fetch_ok` is true
- `"📊 Session context unavailable"` in muted grey if `fetch_ok` is false

This builds admin trust that the spec is enriched.

---

### 5.3 Autonomy Tier Computation

**The gap:** `engineer_task()` returns `priority`, `complexity`, `task_type`, `layer`, `product_area` — but never computes Autonomy Tier. Dispatched tasks land in Notion with the tier blank, breaking `relopass-autopilot`.

#### Tier mapping rules (deterministic — no LLM needed)

Add a pure function `compute_autonomy_tier(task: dict, area: str) -> str` in `feedback_task_engineer.py`:

```python
def compute_autonomy_tier(task: dict, area: str) -> str:
    """
    Returns 'green' | 'yellow' | 'red' based on task properties.
    Rules applied in order — first match wins.
    """
    layer = (task.get("layer") or "").lower()
    complexity = (task.get("complexity") or "").lower()
    task_type = (task.get("task_type") or "").lower()

    # RED — always require human gate before any code is written
    if any(kw in layer for kw in ["isolation", "rls", "auth", "security"]):
        return "red"
    if any(kw in task_type for kw in ["migration", "schema"]) and "isolation" in (task.get("technical_constraints") or "").lower():
        return "red"
    if area in ("isolation",):
        return "red"

    # YELLOW — agent runs but creates plan for review before executing
    if complexity in ("high", "very high"):
        return "yellow"
    if layer in ("api", "infrastructure"):
        return "yellow"
    if area in ("api",):
        return "yellow"
    if any(kw in task_type for kw in ["migration", "schema", "data"]):
        return "yellow"

    # GREEN — agent executes autonomously
    return "green"
```

#### Where to call it

1. In `engineer_task()`, after parsing the LLM JSON response, call `compute_autonomy_tier(task, area)` and add `autonomy_tier` to the returned dict.
2. In the spec preview panel (frontend), show the tier prominently:
   - 🟢 Green — "Agent will execute automatically"
   - 🟡 Yellow — "Agent will present plan for your approval"
   - 🔴 Red — "Agent waits for your explicit go-ahead before writing code"
3. In `dispatch/create`, write the tier to Notion using the existing `build_properties` mechanism.
4. Write the tier to `feedback_status.autonomy_tier` at dispatch time.

#### Notion property name
`Autonomy Tier` — value: `"🟢 Green Autonomy"` | `"🟡 Yellow Autonomy"` | `"🔴 Red Autonomy"`
(Match the exact string format that `relopass-autopilot` reads — verify in the autopilot skill before implementing.)

---

### 5.4 GitHub Actions Webhooks

#### Purpose
Automate the `dispatched → in_progress → in_review → deployed` transitions without admin polling.

#### Branch naming convention (enforce this)
Claude Code must name fix branches: `fix/{report_id}` (e.g. `fix/BUG-260617-A1B2`).  
Add this rule to the `relopass-dev-queue` skill's Phase 1 (codebase recon step): "Name the branch `fix/{report_id}` where report_id comes from the Notion task's 'report_id' or 'source_ref' field."

The backend webhook handler uses the branch name to look up the feedback row via `feedback_status.source_ref = report_id`.

#### New backend endpoint

**File:** `backend/app/routers/github_webhook.py`  
**Register in both** `backend/app/main.py` and `backend/main.py` (CLAUDE.md dual-layer rule).

```
POST /api/internal/github-webhook
Auth: HMAC-SHA256 signature header (X-Hub-Signature-256), secret = GITHUB_WEBHOOK_SECRET env var
No user session required.
```

Payload events handled:

| GitHub event | Action | Backend action |
|-------------|--------|----------------|
| `pull_request` | `opened` or `reopened` | Extract branch name → lookup report_id → PATCH feedback_status: `in_progress`, `pr_url`, `pr_number`, `branch_name`, `in_progress_at` |
| `pull_request` | `review_requested` or `ready_for_review` | → PATCH: `in_review`, `in_review_at` |
| `push` | to `main` | → PATCH all `in_review` items matching commits in push: `deployed`, `deployed_at`; schedule PostHog verify job |

**Signature verification (mandatory):**
```python
import hmac, hashlib
def verify_github_signature(payload_bytes: bytes, header: str, secret: str) -> bool:
    expected = "sha256=" + hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header)
```
Return 403 and log if verification fails. Never process the payload on auth failure.

#### GitHub Actions workflow file

**File:** `.github/workflows/feedback-status-sync.yml`

```yaml
name: Sync feedback status
on:
  pull_request:
    types: [opened, reopened, review_requested, ready_for_review]
  push:
    branches: [main]

jobs:
  notify:
    runs-on: ubuntu-latest
    steps:
      - name: Notify ReloPass
        run: |
          curl -s -X POST "${{ secrets.RELOPASS_API_URL }}/api/internal/github-webhook" \
            -H "Content-Type: application/json" \
            -H "X-Hub-Signature-256: sha256=$(echo -n '${{ toJSON(github.event) }}' | \
                openssl dgst -sha256 -hmac '${{ secrets.GITHUB_WEBHOOK_SECRET }}' | cut -d' ' -f2)" \
            -d '${{ toJSON(github.event) }}'
```

**GitHub secrets to add:** `RELOPASS_API_URL`, `GITHUB_WEBHOOK_SECRET`

---

### 5.5 PostHog Post-Deploy Verification

#### Purpose
30 minutes after a deploy event, automatically check whether the bug's error rate dropped. If yes, mark done. If no, surface to admin.

#### Verification logic

**New service function:** `posthog_context.verify_fix(page_url, deployed_at, feedback_id) -> dict`

```python
"""
Compares $exception event counts for page_url in:
  - window_before: deployed_at - 24h → deployed_at
  - window_after:  deployed_at → deployed_at + 24h (or now if < 24h)
Returns { resolved: bool, before_count: int, after_count: int, confidence: float }
"""
```

Resolution threshold: `after_count < 0.1 * before_count` (90% reduction).  
If `before_count == 0`: skip verification, mark done (no baseline to compare).  
If `window_after` is < 1 hour: defer — reschedule for later.

#### Trigger mechanism

In the GitHub webhook handler, when `deployed` state is set:
- Schedule a verification task: write a row to a `scheduled_jobs` table (or use an existing scheduling mechanism in the codebase — check if one exists, e.g. a `pg_cron` job or a Supabase Edge Function scheduler).
- Job payload: `{ job_type: "posthog_verify", feedback_id, page_url, deployed_at, run_after: deployed_at + 30min }`

If no scheduler exists, use `asyncio.create_task` with a background coroutine in the FastAPI app (acceptable for now; note this does not survive server restarts — a proper scheduler should replace it in a future sprint).

**New endpoint for manual verify:**

```
POST /api/admin/feedback/{stream}/{id}/verify
Auth: admin
Body: {} (empty — manual override, no PostHog check needed)
Action: set dispatch_status = 'done', done_at = now(), posthog_verified = false
```

---

## 6. API Contract Changes

### Existing endpoints — changes required

**`PATCH /api/admin/feedback/{stream}/{id}`** (admin_feedback.py)
- Currently updates: `status`, `owner`, `resolution`, `severity`, `area`, `dispatch_context`
- Add to accepted body fields: `dispatch_status`, `triage_notes`, `triaged_at`, `autonomy_tier`
- Add validation: `dispatch_status` must be a valid state (see §4.1)

**`POST /api/admin/feedback/{stream}/{id}/dispatch/preview`** (admin_feedback.py)
- Before calling `engineer_task()`, call `fetch_session_context()` and include result in context
- After response: update `feedback_status.dispatch_status = 'spec_drafted'`, `spec_drafted_at = now()`
- Response body: add `{ autonomy_tier, posthog_fetch_ok, posthog_event_count, session_replay_url }`

**`POST /api/admin/feedback/{stream}/{id}/dispatch/create`** (admin_feedback.py)
- After creating Notion task: write `autonomy_tier` to Notion task properties
- Write `feedback_status.autonomy_tier`, `dispatch_status = 'dispatched'`, `dispatched_at = now()`

### New endpoints

| Method | Path | File | Description |
|--------|------|------|-------------|
| `POST` | `/api/internal/github-webhook` | `github_webhook.py` | GitHub Actions event handler |
| `POST` | `/api/admin/feedback/{stream}/{id}/verify` | `admin_feedback.py` | Manual verify/close |

---

## 7. Frontend Changes

### 7.1 Files to modify
- `frontend/src/components/admin/FeedbackTab.tsx` — replace the Dispatch column with the progressive button strip; add spec preview panel; add Triage inline picker
- `frontend/src/api/adminFeedback.ts` — add `verifyFeedback()`, `triageFeedback()` API wrappers
- `frontend/src/components/admin/` — add `ProgressStrip.tsx` (new component, extracted from FeedbackTab for testability)

### 7.2 `ProgressStrip` component

```typescript
interface ProgressStripProps {
  item: UnifiedFeedbackItem;
  onTriage: (severity: string, area: string, notes: string) => Promise<void>;
  onDraftSpec: () => Promise<EngineeredTask>;
  onCreateTask: (task: EngineeredTask) => Promise<void>;
  onVerify: () => Promise<void>;
  onDismiss: (reason: string) => Promise<void>;
  onWontFix: (reason: string) => Promise<void>;
}
```

The component is purely presentational — it receives callbacks for each action and renders state based on `item.dispatch_status`. It does not fetch data itself.

### 7.3 State → button strip rendering

```typescript
const STEPS = ['triaged', 'spec_drafted', 'dispatched', 'in_progress', 'in_review', 'deployed', 'done'];

function stepState(step: string, currentStatus: string): 'complete' | 'active' | 'auto' | 'pending' {
  const currentIdx = STEPS.indexOf(currentStatus);
  const stepIdx = STEPS.indexOf(step);
  if (stepIdx < currentIdx) return 'complete';
  if (stepIdx === currentIdx) return currentStatus === 'dispatched' || currentStatus === 'deployed' ? 'auto' : 'active';
  return 'pending';
}
```

Auto states (pulse animation): `dispatched` (waiting for agent PR), `deployed` (waiting for PostHog verify).

### 7.4 Spec preview panel

Rendered below the button strip when `dispatch_status === 'spec_drafted'`.  
Editable fields: title, execution_prompt, validation_criteria, test_command.  
Read-only chips: priority, complexity, task_type, layer, autonomy_tier (prominent, with color 🟢/🟡/🔴).  
PostHog badge: "📊 {N} events" or "📊 Session unavailable."  
Session replay link: clickable if present.

The panel stores edits in local component state. The edited task is what gets sent to `dispatch/create`.

### 7.5 Design tokens
Follow DESIGN.md strictly. Use navy `#0b2b43` for active buttons, teal `#1f8e8b` for complete chips, `#94a3b8` for pending. No purple. 8px grid. Inter font. No gradients.

---

## 8. Metrics & Instrumentation

### 8.1 Events to track (PostHog custom events from the frontend)

| Event | When | Properties |
|-------|------|------------|
| `feedback_triage_started` | Admin opens expanded row | `{ report_id, stream, severity }` |
| `feedback_spec_drafted` | Spec preview loads | `{ report_id, posthog_events_count, autonomy_tier }` |
| `feedback_task_created` | Notion task confirmed | `{ report_id, autonomy_tier, time_since_triage_ms }` |
| `feedback_done` | Status reaches done | `{ report_id, autonomy_tier, time_to_done_ms, posthog_verified }` |
| `feedback_verify_failed` | PostHog verify returns negative | `{ report_id, before_count, after_count }` |

Track these via `posthog.capture()` in the frontend. No PII in properties — only IDs, tiers, and timings.

### 8.2 Server-side metrics (log structured JSON)

In `admin_feedback.py`, log at INFO level after each state transition:

```python
logger.info("feedback_state_transition", extra={
    "report_id": report_id,
    "from_state": old_status,
    "to_state": new_status,
    "stream": stream,
    "autonomy_tier": autonomy_tier,
    "elapsed_ms": (datetime.utcnow() - created_at).total_seconds() * 1000,
})
```

### 8.3 Targets (review at 30-day mark)

| Metric | Target |
|--------|--------|
| P50 time_to_triage | < 5 min (admin online) |
| P50 time_to_dispatch | < 3 min (from triage) |
| P50 time_to_done (Green) | < 8 hours wall clock |
| P50 time_to_done (Yellow) | < 24 hours wall clock |
| Agent success rate (Green) | ≥ 65% |
| Agent success rate (Yellow) | ≥ 45% |
| PostHog context fetch success | ≥ 90% of spec requests |
| PostHog verify accuracy | ≥ 80% (manual override rate < 20%) |

---

## 9. Verification Plan — Acceptance Criteria

Every feature must pass its AC before being marked Done in Notion.

### 9.1 State machine and DB

- [ ] All 11 states exist as valid values in `feedback_status.dispatch_status`
- [ ] All timestamp columns (`triaged_at`, `spec_drafted_at`, `dispatched_at`, `in_progress_at`, `deployed_at`, `done_at`) are populated at the correct transitions
- [ ] Invalid state transitions are rejected (e.g. cannot go from `new` to `deployed` directly)
- [ ] `autonomy_tier` column exists and accepts only `green | yellow | red`

### 9.2 Progressive button strip

- [ ] When status is `new`: only "Triage" button is navy/active; all others are muted
- [ ] After triage: "Triage" shows ✓ + timestamp; "Draft Spec" is navy
- [ ] Hovering a complete step shows its absolute timestamp in a tooltip
- [ ] "Draft Spec" shows a spinner while the preview request is in-flight; no other buttons are clickable during this time
- [ ] "Create Task" is disabled for ≥ 3 seconds after the spec panel opens, even if you click immediately
- [ ] When dispatch_status is `dispatched`: "In Progress" shows pulsing animation with "Waiting for agent"
- [ ] When GitHub webhook fires `pr_opened`: UI updates to show PR link and "In Progress ✓" without page reload (poll every 30s or use realtime subscription)
- [ ] "Dismiss" and "Won't Fix" are visible at all states post-triage; clicking each requires confirmation
- [ ] On `done`: entire strip collapses to "Done ✓ [timestamp]" with a subtle green background

### 9.3 PostHog enrichment

- [ ] `client_context.posthog_id` is populated in submitted feedback rows (check DB for a test submission)
- [ ] Draft Spec call takes < 8 seconds (PostHog fetch should not add > 3s)
- [ ] Spec preview shows "📊 N events included" badge when PostHog returns data
- [ ] If PostHog env vars are missing, spec generation proceeds and badge shows "📊 Session unavailable"
- [ ] PostHog event timeline appears in the spec's `execution_prompt` (check server logs or the preview text)
- [ ] Session replay URL appears in "Context Links" field of the created Notion task
- [ ] No user email, name, or raw PII appears in the event timeline (manual review of a sample spec)

### 9.4 Autonomy Tier

- [ ] Every dispatched Notion task has "Autonomy Tier" property set (check 3 tasks in Notion after dispatch)
- [ ] UI-only low-complexity bug → 🟢 Green (test: submit a bug about a label, dispatch it, check tier)
- [ ] API bug → 🟡 Yellow (test: submit a bug about a server error, dispatch it, check tier)
- [ ] "isolation" or "rls" in layer/technical_constraints → 🔴 Red
- [ ] `feedback_status.autonomy_tier` matches the Notion task tier for all 3 test cases
- [ ] Tier badge is visible in spec preview before admin confirms

### 9.5 GitHub Actions webhook

- [ ] Opening a PR with branch `fix/BUG-260617-A1B2` → `feedback_status` for that report_id updates to `in_progress` within 30 seconds
- [ ] PR URL and number are stored in `feedback_status.pr_url` and `feedback_status.pr_number`
- [ ] PR link appears in the expanded feedback row in the admin UI
- [ ] Sending a webhook with an incorrect signature → 403, no state change
- [ ] Merging a PR → `dispatch_status` updates to `deployed`

### 9.6 PostHog verification

- [ ] 30 minutes after `deployed_at` is set, a verification attempt is logged
- [ ] If error rate drops ≥ 90%: `dispatch_status` = `done`, `posthog_verified` = true, `done_at` set
- [ ] If error rate does not drop: `dispatch_status` = `verify_failed`; item reappears in admin inbox with a ⚠️ indicator
- [ ] Admin can click "Verify Fix" manually at any time when status is `deployed` or `verify_failed`
- [ ] If PostHog has zero baseline events for that page, item auto-marks `done` (no baseline = can't disprove fix)

---

## 10. Implementation Order

Work in this sequence. Each phase is independently deployable.

**Phase 1 — Foundation (no UI changes)**
1. DB migration: new columns on `feedback_status`
2. `compute_autonomy_tier()` in `feedback_task_engineer.py`
3. Write tier to Notion task and `feedback_status` in `dispatch/create`
4. Run the audit: open 5 test items, dispatch them, confirm Notion tasks have tier set

**Phase 2 — PostHog enrichment**
5. `posthog_context.py` service module
6. `collectDiagnostics()` in `diagnostics.ts` — add `posthog_id`
7. Wire `fetch_session_context()` into `dispatch/preview`
8. Verify: draft a spec for a test submission, confirm event timeline in preview

**Phase 3 — Progressive button strip**
9. `ProgressStrip.tsx` component
10. Replace Dispatch column in `FeedbackTab.tsx`
11. Add Triage inline picker
12. Add spec preview panel (previously only shown in a modal — move inline)
13. Wire `verifyFeedback()` API call
14. Visual QA: walk through all 11 states manually

**Phase 4 — GitHub webhooks**
15. `github_webhook.py` router (both registrations per CLAUDE.md)
16. `.github/workflows/feedback-status-sync.yml`
17. Add secrets to GitHub repo settings
18. Test: open a PR with a `fix/` branch, confirm state advances

**Phase 5 — PostHog verification**
19. `posthog_context.verify_fix()` function
20. Scheduling mechanism (check if scheduler exists; use background task as fallback)
21. Manual verify endpoint
22. Test: deploy a fix for a tracked page, confirm verify runs 30 min later

---

## 11. Open Questions for Claude Code

Before implementing, Claude Code should check the following in the repo:

1. **What is the current `dispatch_status` constraint?** Run: `grep -r "dispatch_status" supabase/migrations/ | grep -i "check\|enum"`. The new values must be added to (not replace) the existing constraint.

2. **Does a scheduling mechanism exist?** Check `backend/app/` for any `scheduler`, `background_tasks`, `cron`, or `apscheduler` references. If yes, use it. If no, use FastAPI `BackgroundTasks` for Phase 5 with a note that it doesn't survive restarts.

3. **What is the exact Autonomy Tier property name in Notion?** Check `notion_work_queue.py` → `build_properties()` for existing property names. The tier write must use the exact same property key string.

4. **Is PostHog installed in the frontend?** Check `frontend/src/` for any `posthog` import. If not installed, `npm install posthog-js` and initialise in `main.tsx` or `App.tsx` with `VITE_POSTHOG_KEY` env var. The `collectDiagnostics()` change in Step 6 depends on PostHog being initialised before the widget loads.

5. **How does `dispatch_status` currently differ from `feedback_status.status`?** Check if these are the same column or two separate columns. The state machine in this spec assumes `dispatch_status` is the pipeline state column (distinct from the triage `status` field new/reviewed/acted_on).
