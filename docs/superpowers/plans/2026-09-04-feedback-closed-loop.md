# Feedback closed loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Feedback → documented spec → admin approval → Cursor/dev-queue brief a single operator path, and put PostHog replay/person/events on the ticket so they are used, not optional archaeology.

**Architecture:** Keep `public.feedback` + `public.feedback_status` + Notion AI Work Queue. Do not add a second ticket store. Phase A is in-product (ingest, `format_diagnostics`, inbox UI, copyable brief). Later phases add GitHub draft-PR status and PostHog verify; none auto-merge to `main`.

**Tech Stack:** FastAPI (`backend/app/routers/feedback.py`, `admin_feedback.py`), `feedback_task_engineer.py`, React `FeedbackTab.tsx` / `FeedbackWidget.tsx` / `analytics.ts`, PostHog JS + optional PostHog Query API, Vitest, pytest.

**Spec:** `docs/specs/feedback-closed-loop.md`

## Global Constraints

- Dual-router registration if a **new** router is added; Phase A extends existing `feedback` and `admin_feedback` routers (already dual-registered).
- PII: any free text in an LLM prompt goes through `mask_pii` / `_scrub` in `feedback_task_engineer.py`. Do not put raw emails from diagnostics into PostHog event properties.
- Consent: never call `startSessionRecording` unless `getAnalyticsConsent() === 'granted'`.
- Serving/LLM isolation: this pipeline is authoring/admin, not the requirement serving path. Do not import `llm_client` from serving engines.
- DESIGN.md: muted text on light surfaces is `text-slate-500`, not `text-slate-400` / `text-gray-400`, on any **new** markup.
- `docs/specs/feedback-improvements.md` describes a dead Supabase insert path — do not implement it. Task 1 banners it superseded.
- No `supabase db push`. New migrations: timestamp above **both** repo max and prod ledger max (CLAUDE.md).
- Backend tests: `DATABASE_URL=sqlite:///./ci_test.db` (or CI sqlite) and `RELOPASS_DISABLE_RATE_LIMITS=1`.
- Frontend tests: mock API modules; never import `api/supabase` in jsdom.
- Cursor/cloud agents: Phase A copies a brief. Phase C may open a **draft** PR. Never merge to `main` from this programme.

## File map (Phase A)

| File | Responsibility |
|------|----------------|
| `docs/specs/feedback-improvements.md` | Banner: superseded |
| `backend/app/services/feedback_task_engineer.py` | Include PostHog ids/URLs in `format_diagnostics` |
| `backend/app/routers/feedback.py` | Fail loud (log + metric) on status seed; capture `feedback_submitted` |
| `backend/app/posthog_client.py` | Reuse `get_posthog_client()` for server event |
| `frontend/src/analytics.ts` | `feedback_widget_opened` / `feedback_submitted` properties |
| `frontend/src/components/FeedbackWidget.tsx` | Capture submit event with `report_id` |
| `frontend/src/components/admin/FeedbackTab.tsx` | Stream filter Product vs AI vs other; copy agent brief; PostHog links always |
| `frontend/src/api/adminFeedback.ts` | Types for `/fix` already exist; add copy-brief helper if needed |
| `backend/tests/test_feedback_diagnostics_enrichment.py` | Extend for PostHog lines |
| `frontend/src/components/admin/FeedbackTab.test.tsx` | Stream split + copy brief |

---

### Task 1: Retire the stale feedback-improvements spec

**Files:**
- Modify: `docs/specs/feedback-improvements.md` (top of file)

**Interfaces:** none.

- [ ] **Step 1: Prepend a superseded banner**

Insert at the very top of `docs/specs/feedback-improvements.md`:

```markdown
> **SUPERSEDED (2026-09-04).** Do not implement this document. The live ingest path is
> `POST /api/feedback` (`FeedbackWidget` → `submitProductFeedback`), not a direct
> Supabase insert. AI title/sentiment/layer columns on `public.feedback` were never
> the ticket model; use `feedback_status` + `engineer_task`. Canonical design:
> `docs/specs/feedback-closed-loop.md`. Canonical plan:
> `docs/superpowers/plans/2026-09-04-feedback-closed-loop.md`.
```

- [ ] **Step 2: Commit**

```bash
git add docs/specs/feedback-improvements.md docs/specs/feedback-closed-loop.md docs/superpowers/plans/2026-09-04-feedback-closed-loop.md
git commit -m "$(cat <<'EOF'
docs(feedback): point closed-loop work at the live ingest path

EOF
)"
```

---

### Task 2: Put PostHog onto the engineered spec (the unused capacity)

**Why:** `client_context` already has `posthog_id`, `posthog_session_id`, `posthog_replay_url`. `format_diagnostics()` never prints them, so Notion tasks and agents cannot open the replay.

**Files:**
- Modify: `backend/app/services/feedback_task_engineer.py` (`format_diagnostics`)
- Test: `backend/tests/test_feedback_diagnostics_enrichment.py`

**Interfaces:**
- Consumes: `client_context` dict as stored on `public.feedback`
- Produces: extra lines in `format_diagnostics` return string; still empty-safe

- [ ] **Step 1: Write the failing tests** (append to `backend/tests/test_feedback_diagnostics_enrichment.py`)

```python
def test_format_diagnostics_includes_posthog_replay_and_person():
    from backend.app.services.feedback_task_engineer import format_diagnostics

    out = format_diagnostics(
        {
            "posthog_id": "user-abc",
            "posthog_session_id": "sess-xyz",
            "posthog_replay_url": "https://eu.posthog.com/replay/sess-xyz",
            "route": "/admin/countries",
        }
    )
    assert "https://eu.posthog.com/replay/sess-xyz" in out
    assert "user-abc" in out
    assert "sess-xyz" in out
    assert "LEAD" in out or "lead" in out.lower()


def test_format_diagnostics_posthog_absent_is_still_empty_safe():
    from backend.app.services.feedback_task_engineer import format_diagnostics

    assert "posthog" not in format_diagnostics({"route": "/x"}).lower()
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd /Users/romainlecomte/Documents/GitHub/rolec && DATABASE_URL=sqlite:///./ci_test.db .venv/bin/pytest backend/tests/test_feedback_diagnostics_enrichment.py -q --tb=short
```

Expected: assertion fail (no replay URL in output).

- [ ] **Step 3: Implement**

At the end of `format_diagnostics`, before `return "\n".join(lines)`, append:

```python
    ph_id = str(ctx.get("posthog_id") or "").strip()
    ph_sess = str(ctx.get("posthog_session_id") or "").strip()
    ph_replay = str(ctx.get("posthog_replay_url") or "").strip()
    if ph_replay or ph_id or ph_sess:
        lines.append(
            "PostHog (LEAD, not proof of root cause): "
            f"replay={ph_replay or 'none'} person_id={ph_id or 'none'} "
            f"session_id={ph_sess or 'none'}. "
            "Replay may start when the widget opened, after the failure."
        )
```

Do not fetch PostHog APIs here. URLs already on the row are enough for Phase A.

- [ ] **Step 4: Re-run tests — expect PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
fix(feedback): include PostHog replay in engineered task diagnostics

EOF
)"
```

---

### Task 3: Product analytics events that join to a ticket

**Why:** Metrics tab and PostHog UI cannot answer “what happened around BUG-…” unless submit is an event with `report_id`.

**Files:**
- Modify: `frontend/src/analytics.ts` (typed helper or document property names next to existing `capture`)
- Modify: `frontend/src/components/FeedbackWidget.tsx` (open + successful submit)
- Modify: `backend/app/routers/feedback.py` (server-side capture after insert; same names)
- Test: `frontend/src/components/FeedbackWidget.test.tsx` (mock analytics)

**Interfaces:**
- Produces events (client and server, both consent/token gated):
  - `feedback_widget_opened` — properties: `{ route: string }`
  - `feedback_submitted` — properties: `{ report_id: string, category: string, route: string }`
- Never put `message` body or screenshot into PostHog properties.

- [ ] **Step 1: Add a focused test** that submit calls analytics with `report_id` (mock `capture` / module `track`).

If `FeedbackWidget.test.tsx` already stubs analytics, extend it rather than duplicating.

- [ ] **Step 2: Client capture**

In `FeedbackWidget.tsx`, after a **successful** `submitProductFeedback` (response has `report_id`):

```typescript
import { track } from '../analytics'; // use the existing capture wrapper name in analytics.ts

track('feedback_submitted', {
  report_id: result.report_id,
  category,
  route: window.location.pathname,
});
```

On popover open (alongside `startBugReportRecording`):

```typescript
track('feedback_widget_opened', { route: window.location.pathname });
```

`track` must no-op when PostHog is disabled or consent is not granted (same as today’s `capture`).

- [ ] **Step 3: Server capture**

In `submit_feedback` after the `feedback` INSERT succeeds:

```python
try:
    ph = get_posthog_client()
    if ph is not None:
        ph.capture(
            distinct_id=str(reporter_id or report_id),
            event="feedback_submitted",
            properties={
                "report_id": report_id,
                "category": category,
                "route": (page_url or "")[:200],
                "source": "api",
            },
        )
except Exception:
    log.warning("posthog feedback_submitted failed report_id=%s", report_id)
```

Do not fail the HTTP handler if PostHog is down.

- [ ] **Step 4: Run frontend + a thin backend test** if one already mocks `get_posthog_client`; otherwise a unit test that `submit_feedback` still returns `ok` when `get_posthog_client` raises.

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(feedback): emit PostHog events keyed by report_id

EOF
)"
```

---

### Task 4: Seed `feedback_status` must not disappear

**Files:**
- Modify: `backend/app/routers/feedback.py` (the `except` around INSERT into `feedback_status`)
- Test: `backend/tests/test_feedback_ticket.py` (or the existing submit tests)

**Interfaces:**
- HTTP submit still returns 200 with `report_id` if the **product row** landed (reporter must not see a hard fail for a secondary table).
- Response gains `ticket_seeded: bool`.
- Log at **error** (not warning) on seed failure; include `report_id` and exception type.

- [ ] **Step 1: Test** that a mocked failing `feedback_status` insert still returns `ok: True` and `ticket_seeded: False`.

- [ ] **Step 2: Implement** `ticket_seeded` on the JSON body; keep swallow (reporter UX) but stop calling it “best-effort suppressed” as if it were fine.

- [ ] **Step 3: Admin list** — if `FeedbackTab` already left-joins status, show a Badge `Ticket incomplete` when product stream has no `feedback_status` row (`severity`/`dispatch_status` null). Test: render fixture row without status.

- [ ] **Step 4: Commit**

```bash
git commit -m "$(cat <<'EOF'
fix(feedback): surface failed ticket seed instead of swallowing it

EOF
)"
```

---

### Task 5: Inbox split — Product vs AI eval vs other

**Why:** Dispatching a thumbs-down policy answer as a frontend bug is the classic ticket mistake.

**Files:**
- Modify: `frontend/src/components/admin/FeedbackTab.tsx`
- Test: `frontend/src/components/admin/FeedbackTab.test.tsx`

**Interfaces:**
- Filter chips become: `Product` (`stream === 'product'`), `AI answers` (`ai_answers` + `helpfulness`), `HR` (`hr_assignment` + `hr_case`), plus existing All / Dispatched.
- Default chip: `Product` (not All), so the founder loop starts on widget bugs.
- Copy under AI answers: “This stream feeds eval gold, not a code dispatch by default.” One sentence, no EU AI Act claims.

- [ ] **Step 1: Failing test** — render with mixed streams; default view does not show an `ai_answers` row title.

- [ ] **Step 2: Implement filter** using existing `STREAMS` / `activeStream` state. Rename labels only; do not change API.

- [ ] **Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(feedback): default inbox to product tickets, not AI thumbs

EOF
)"
```

---

### Task 6: One-click agent brief (Cursor / Claude Code) after spec exists

**Why:** `/fix` requires dispatch + Notion Ready for AI and is flag-gated. Operators need a **copyable brief** as soon as preview exists, without auto-running agents.

**Files:**
- Modify: `backend/app/routers/admin_feedback.py` — new `POST /feedback/{stream}/{item_id}/agent-brief`
- Modify: `frontend/src/api/adminFeedback.ts`
- Modify: `frontend/src/components/admin/FeedbackTab.tsx` (button “Copy Cursor brief” on previewed/dispatched rows)
- Test: `backend/tests/test_feedback_ticket.py` or a new `test_admin_feedback_agent_brief.py`
- Test: `FeedbackTab.test.tsx` (button present; click calls clipboard mock)

**Interfaces:**

```python
# Response JSON
{
  "report_id": str | None,
  "stream": str,
  "item_id": str,
  "notion_url": str | None,
  "command": str,          # e.g. "/relopass-dev-queue AIQ-1234" or "Work this ticket in Cursor"
  "brief": str,            # markdown: reporter quote, admin context, diagnostics, PostHog URLs, constraints
}
```

`brief` must include:

1. Verbatim reporter `text` (already stored; pass through `_scrub` only if this brief is ever sent to an LLM — for clipboard to the admin, keep verbatim in the admin UI, scrub if the endpoint is logged).
2. Admin `dispatch_context`.
3. `format_diagnostics(client_context)` (now with PostHog).
4. Hard fence: “Do not merge to main. Open a feature branch and a PR. Do not touch serving LLM isolation. Mask PII.”
5. Notion URL if dispatched.

Do **not** set Notion to Ready for AI in this endpoint (that remains `/fix`).

- [ ] **Step 1: Backend test** — call `agent_brief` with a stubbed DB row; assert `brief` contains the replay URL fixture and the fence sentence `Do not merge to main`.

- [ ] **Step 2: Implement the route** next to `trigger_fix`. Reuse `_load_product_fields` / unified item loader. Register is already on `admin_feedback.router`.

- [ ] **Step 3: Frontend** — `navigator.clipboard.writeText(brief + "\n\n" + command)`. On failure, show the text in a `<pre>` (no silent fail).

- [ ] **Step 4: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(feedback): copy an agent brief without flipping Ready for AI

EOF
)"
```

---

### Task 7: Force-dispatch requires a reason

**Files:**
- Modify: `backend/app/routers/admin_feedback.py` (`dispatch/create` when `force=true`)
- Modify: `frontend/src/components/admin/FeedbackTab.tsx` (`EvalGatePanel`)
- Test: existing dispatch/eval tests

**Interfaces:**
- Body: `force_dispatch: bool`, `force_reason: str` (min 12 chars when force is true).
- 422 if force without reason.
- Persist reason into `dispatch_context` suffix or `record_admin_event` detail (do not invent a migration unless the event table cannot hold it).

- [ ] **Step 1: Test 422** when `force_dispatch` is true and `force_reason` is `""`.

- [ ] **Step 2: UI** — textarea “Why override the quality gate?” enabled only when forcing.

- [ ] **Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
fix(feedback): require a written reason to force-dispatch a blocked spec

EOF
)"
```

---

## Phase B (after A is on `main` and you have used it for a week)

### Task 8: Research vs Implementation as an explicit admin choice

**Files:** `FeedbackTab.tsx` dispatch form; `engineer_task` already prefers Research for questions — surface `task_type` as a required radio **before** preview: `Research` | `Implementation`. Default `Research` if message contains `?`.

**Done when:** preview cannot fire without a choice; Implementation without failed-request or screenshot or replay shows a confirm modal (“weak evidence”).

### Task 9: `identify` ReloPass user on PostHog

**Files:** `frontend/src/analytics.ts` + login success path (`auth` client).

Call `posthog.identify(relopassUserId, { email_hash or role })` only after consent. Do not send raw email if avoidable; role + user uuid is enough to join `feedback_submitted`.

---

## Phase C (draft PR, not merge)

### Task 10: Store PR URL on the ticket when an agent opens a PR

**Files:** `feedback_status.pr_url` (column may already exist from 2026-07 pipeline migration — **verify live schema first**). GitHub webhook **or** manual paste field in FeedbackTab.

**Done when:** dispatched row shows a link to a **draft** PR. Still no auto-merge.

Do not implement GitHub webhook and Notion sync changes in the same PR as Phase A.

---

## Phase D (verify)

### Task 11: “Verified on this URL” admin action

**Files:** `PATCH .../state` already exists — add UI button that moves `deployed`/`in_review` → `done` with `detail.verified_by` and `verified_url`.

This is the honest close. PostHog is supporting evidence.

### Task 12: Optional PostHog verify query

**Files:** new `backend/app/services/feedback_posthog_verify.py` using PostHog Query API / HogQL: count `exception` or failed `$exception` **or** reuse mirrored `analytics_events` for the same `distinct_id` + route **after** `deployed_at`.

**Pass:** no new exceptions on that route for that person in 24h **or** admin override (Task 11).

**Fail:** `verify_failed`. Never auto-`done` on “LLM said fixed.”

Requires `POSTHOG_PERSONAL_API_KEY` or project query key in server env — add only if not already present. Document in `.env.example`, not in git secrets.

---

## PostHog operator playbook (no code)

Use this **now**, while Phase A ships:

1. Open a feedback row → Diagnostics → **Watch session replay** if the link exists. If it is missing, consent was denied or replay never started — believe the screenshot and failed requests instead.
2. Product metrics tab = warehouse counts. For funnels and recordings, use the linked EU PostHog project (`posthogEventsUrl()`).
3. After Phase A, in PostHog: save an insight **filter event `feedback_submitted`**, breakdown `category`, property `report_id`. That is the join key to the inbox.
4. Cursor PostHog MCP (if connected in the IDE): ad-hoc HogQL is for investigation, not the system of record. Persist conclusions in `dispatch_context`.

---

## Out of order / do not do

- Implement `docs/specs/feedback-improvements.md` AI columns on `public.feedback`.
- Start session replay for all authenticated users without a privacy review.
- Auto Ready-for-AI on every dispatch.
- Auto-merge Cursor cloud agent PRs.
- Put the reporter’s raw message into PostHog event properties.

---

## Self-review

| Spec requirement | Task |
|------------------|------|
| PostHog on the spec | Task 2 |
| Events joinable by `report_id` | Task 3 |
| Seed failure visible | Task 4 |
| Inbox honesty | Task 5 |
| Cursor brief without auto-run | Task 6 |
| Force-dispatch discipline | Task 7 |
| Research default | Task 8 |
| identify() | Task 9 |
| Draft PR on ticket | Task 10 |
| Human verify | Task 11 |
| PostHog verify query | Task 12 |
| Stale spec retired | Task 1 |
