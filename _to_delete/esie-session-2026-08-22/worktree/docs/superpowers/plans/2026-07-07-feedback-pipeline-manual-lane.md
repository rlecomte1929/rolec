# Feedback Pipeline Manual-Lane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the manual admin feedback triage→dispatch→track gaps: feed captured reproduction diagnostics into the task engineer, compute and persist an Autonomy Tier on dispatch, add a shared pipeline-state model on `feedback_status` (written by both the human lane and the autopilot), and surface it as a Progressive Button Strip.

**Architecture:** Backend FastAPI (`backend/app/`), Supabase/Postgres via additive migration, React/TS admin UI (`frontend/src/components/admin/`). The manual lane (`admin_feedback.py` + `FeedbackTab.tsx`) and the autonomous Feedback Autopilot (`autopilot_ingest.py` + `autofix-validate.yml` → `POST /api/crons/autopilot-event`) share one `feedback_status` pipeline-state column. No PostHog API calls, no GitHub webhook this round.

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy Core (`text()`), Anthropic sync LLM path, TypeScript / React / Vite, Vitest, pytest.

## Global Constraints

- **Run backend tests on the root `.venv311`** (local Python is 3.9; repo needs 3.11). `RELOPASS_DISABLE_RATE_LIMITS=1` for rate-limited paths.
- **Migration timestamp:** true dir max on `origin/main` is `20260907000000`; this plan uses **`20260908000000`**. Confirm still-max before creating: `git ls-tree -r origin/main --name-only supabase/migrations | grep -oE '[0-9]{14}' | sort | tail -1`. If a higher one exists, use max+1 day.
- **Migration discipline:** commit the migration file; apply to prod out-of-band (operator). Do NOT insert into `schema_migrations` from code. Validate DDL via a rollback-tx (inline DDL + seed + asserts ending `RAISE EXCEPTION 'ALL_TESTS_PASSED'`).
- **No new router registration needed:** `PATCH /state` lives on the already-dual-registered `admin_feedback` router; the event bridge extends the already-allowlisted `/api/crons/autopilot-event`.
- **PII:** any user free-text placed in an LLM prompt passes `_scrub()` (mask_pii + residue guard) — never trust upstream scrubbing.
- **Frontend jsdom trap:** in Vitest tests, never import `api/supabase` (breaks jsdom). Use `vi.mock` for API wrappers.
- **DESIGN.md:** navy/accent Tailwind, antigravity components, no purple. Tier chips: green `#1f8e8b`-family accent / yellow amber / red danger — use existing Badge variants.
- **`notion_task_id` canonical format (this plan's contract):** dashless, lowercase, 32 hex. The autopilot-event bridge join key is its first 16 chars, matching the workflow's `autofix/bug-<16hex>` branch id.

---

### Task 1: Diagnostics enrichment into `engineer_task` (both lanes) + `posthog_id` capture

**Files:**
- Modify: `backend/app/services/feedback_task_engineer.py` (add `format_diagnostics()`, add `diagnostics` param to `engineer_task`)
- Modify: `backend/app/routers/admin_feedback.py` (`_load_product_fields` selects `client_context`; `dispatch_preview` builds + passes the block)
- Modify: `backend/app/services/autopilot_ingest.py:152` (`_dispatch_one` passes `diagnostics`)
- Modify: `frontend/src/lib/diagnostics.ts` (`collectDiagnostics()` returns `posthog_id`)
- Test: `backend/tests/test_feedback_diagnostics_enrichment.py` (new)

**Interfaces:**
- Produces: `format_diagnostics(client_context: Any) -> str` (empty-safe); `engineer_task(..., diagnostics: Optional[str] = None)`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_feedback_diagnostics_enrichment.py
from backend.app.services.feedback_task_engineer import format_diagnostics


def test_format_diagnostics_extracts_error_and_requests():
    ctx = {
        "recentErrors": [{"message": "TypeError: x is undefined", "fingerprint": "abc123"}],
        "recentFailedRequests": [
            {"status": 500, "path": "/api/cases/42", "requestId": "req-1"},
            {"status": 404, "path": "/api/policy/9", "requestId": "req-2"},
        ],
    }
    out = format_diagnostics(ctx)
    assert "abc123" in out and "/api/cases/42" in out and "500" in out


def test_format_diagnostics_empty_safe():
    assert format_diagnostics(None) == ""
    assert format_diagnostics({}) == ""
    assert format_diagnostics("not json") == ""


def test_format_diagnostics_parses_json_string():
    out = format_diagnostics('{"recentErrors":[{"message":"boom","fingerprint":"f1"}]}')
    assert "boom" in out and "f1" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/romainlecomte/Documents/GitHub/rolec && .venv311/bin/pytest backend/tests/test_feedback_diagnostics_enrichment.py -v`
Expected: FAIL with `ImportError: cannot import name 'format_diagnostics'`

- [ ] **Step 3: Add `format_diagnostics` + wire `engineer_task`**

In `backend/app/services/feedback_task_engineer.py`, add after `_scrub`:

```python
def format_diagnostics(client_context: Any) -> str:
    """Compact reproduction signal from a feedback item's client_context.
    Empty-safe: returns '' for None / {} / unparseable input. Not yet PII-masked —
    engineer_task re-scrubs it before the prompt."""
    ctx = client_context
    if isinstance(ctx, str):
        try:
            ctx = json.loads(ctx)
        except Exception:  # noqa: BLE001
            return ""
    if not isinstance(ctx, dict) or not ctx:
        return ""
    lines = []
    errs = ctx.get("recentErrors") or []
    if errs:
        e0 = errs[0] or {}
        lines.append(f"Top error: {e0.get('message', '?')} (fingerprint {e0.get('fingerprint', '?')})")
    for r in (ctx.get("recentFailedRequests") or [])[:3]:
        lines.append(f"Failed request: {r.get('status', '?')} {r.get('path', '?')}")
    fn = ctx.get("failingFunction") or ctx.get("failing_function")
    if fn:
        lines.append(f"Failing function: {fn}")
    return "\n".join(lines)
```

Change the `engineer_task` signature to add `diagnostics: Optional[str] = None` (keyword-only, after `admin_context`), and inside, after `masked_reporter = ...`:

```python
    masked_diag = _scrub(diagnostics) if diagnostics else ""
```

and append to the `user` string (before the closing `)`), after the ADMIN CONTEXT line:

```python
        f"\nREPRODUCTION SIGNAL (auto-captured diagnostics):\n{masked_diag or '(none)'}\n"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv311/bin/pytest backend/tests/test_feedback_diagnostics_enrichment.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Wire the manual lane (`admin_feedback.py`)**

In `_load_product_fields`, add `client_context` to the SELECT and the returned dict:

```python
        "SELECT message, category, page_url, "
        "(CASE WHEN screenshot_data IS NOT NULL THEN 1 ELSE 0 END), reporter_name, report_id, "
        "client_context "
        "FROM feedback WHERE CAST(id AS TEXT) = :id"
```
```python
        "report_id": row[5],
        "client_context": row[6],
```

In `dispatch_preview`, after `reporter_name = pf["reporter_name"]`, add:

```python
    from ..services.feedback_task_engineer import format_diagnostics
    diagnostics = format_diagnostics(pf["client_context"]) if pf else ""
```

and pass `diagnostics=diagnostics` to the `engineer_task(...)` call.

- [ ] **Step 6: Wire the autopilot lane (`autopilot_ingest.py`)**

In `_dispatch_one`, in the `engineer_task(...)` call (~line 152), add:

```python
            diagnostics=engineer.format_diagnostics(rep.get("client_context")),
```
Ensure `format_diagnostics` is importable — change the top import to:
```python
from .feedback_task_engineer import engineer_task, status_from_complexity, format_diagnostics
```
and use `format_diagnostics(...)` directly (drop the `engineer.` prefix above).

- [ ] **Step 7: Add `posthog_id` to `collectDiagnostics()`**

In `frontend/src/lib/diagnostics.ts`, add to the `ClientContext` interface:
```typescript
  posthog_id: string | null;
```
and to the object returned by `collectDiagnostics()`:
```typescript
    posthog_id: safe(() => (window as any).posthog?.get_distinct_id?.() ?? null, null),
```
(No PostHog API call, no env var — captured into `client_context` at submit for the deferred verify layer.)

- [ ] **Step 8: Typecheck + commit**

Run: `cd frontend && npx tsc --noEmit` → Expected: clean
```bash
git add backend/app/services/feedback_task_engineer.py backend/app/routers/admin_feedback.py backend/app/services/autopilot_ingest.py frontend/src/lib/diagnostics.ts backend/tests/test_feedback_diagnostics_enrichment.py
git commit -m "feat(feedback): feed captured diagnostics into engineer_task + posthog_id capture"
```

---

### Task 2: Compute + write Autonomy Tier on dispatch

**Files:**
- Modify: `backend/app/services/feedback_task_engineer.py` (`compute_autonomy_tier`, set on task in `engineer_task`)
- Modify: `backend/app/services/notion_work_queue.py` (`build_properties` writes `Autonomy Tier`)
- Test: `backend/tests/test_autonomy_tier.py` (new)

**Interfaces:**
- Produces: `compute_autonomy_tier(*, task_type, complexity, layer, product_area, area=None, files_to_touch=None) -> str` ∈ `{'green','yellow','red'}`; `engineer_task` return dict gains `task["autonomy_tier"]`.
- Consumes (Notion): the real select option labels `🟢 Green — auto` / `🟡 Yellow — self-validate + sample` / `🔴 Red — full human gate`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_autonomy_tier.py
from backend.app.services.feedback_task_engineer import compute_autonomy_tier


def test_red_for_isolation_layer():
    assert compute_autonomy_tier(task_type="Backend Implementation", complexity="Low",
                                 layer="Isolation", product_area="Core Product") == "red"


def test_red_for_auth_area():
    assert compute_autonomy_tier(task_type="Frontend Implementation", complexity="Trivial",
                                 layer="UI", product_area="Core Product", area="auth") == "red"


def test_red_for_database_migration():
    assert compute_autonomy_tier(task_type="Database Migration", complexity="Low",
                                 layer="Infrastructure", product_area="Infrastructure") == "red"


def test_green_for_trivial_ui_copy():
    assert compute_autonomy_tier(task_type="UX Redesign", complexity="Trivial",
                                 layer="UI", product_area="UX") == "green"


def test_yellow_default():
    assert compute_autonomy_tier(task_type="Backend Implementation", complexity="Medium",
                                 layer="API", product_area="Core Product") == "yellow"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv311/bin/pytest backend/tests/test_autonomy_tier.py -v`
Expected: FAIL (`cannot import name 'compute_autonomy_tier'`)

- [ ] **Step 3: Implement `compute_autonomy_tier` + set it in `engineer_task`**

In `feedback_task_engineer.py`, add:

```python
_TIER_LABELS = {
    "green": "🟢 Green — auto",
    "yellow": "🟡 Yellow — self-validate + sample",
    "red": "🔴 Red — full human gate",
}
_RED_KEYWORDS = ("auth", "login", "password", "billing", "payment", "invoic",
                 "security", "rls", "permission", "migration", "isolation", "secret", "token")


def compute_autonomy_tier(*, task_type: Optional[str], complexity: Optional[str],
                          layer: Optional[str], product_area: Optional[str],
                          area: Optional[str] = None, files_to_touch: Optional[str] = None) -> str:
    """Deterministic risk tier. Red on any sensitive signal; green only for low-risk
    UI copy; yellow otherwise (default-safe)."""
    blob = " ".join(str(x or "").lower() for x in (area, product_area, files_to_touch, task_type))
    if layer == "Isolation" or task_type == "Database Migration" or any(k in blob for k in _RED_KEYWORDS):
        return "red"
    if (complexity in ("Trivial", "Low") and layer == "UI"
            and task_type in ("Frontend Implementation", "UX Redesign")
            and product_area in ("UX", "Core Product", "GTM")):
        return "green"
    return "yellow"
```

In `engineer_task`, after `task["status"] = status_from_complexity(...)`:

```python
    task["autonomy_tier"] = compute_autonomy_tier(
        task_type=task.get("task_type"), complexity=task.get("complexity"),
        layer=task.get("layer"), product_area=task.get("product_area"),
        area=area, files_to_touch=task.get("files_to_touch"),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv311/bin/pytest backend/tests/test_autonomy_tier.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Write the Notion property (test first)**

Add to a new/existing notion test `backend/tests/test_notion_work_queue_properties.py`:

```python
from backend.app.services.notion_work_queue import build_properties


def test_build_properties_writes_autonomy_tier():
    props = build_properties({"title": "t", "strategic_objective": "s", "execution_prompt": "e",
                              "expected_output": "o", "validation_criteria": "v",
                              "priority": "P2", "complexity": "Low", "task_type": "UX Redesign",
                              "layer": "UI", "product_area": "UX", "status": "Ready for AI",
                              "autonomy_tier": "green"},
                             failure_evidence="fe", context_links="cl")
    assert props["Autonomy Tier"]["select"]["name"] == "🟢 Green — auto"


def test_build_properties_omits_tier_when_absent():
    props = build_properties({"title": "t", "strategic_objective": "s", "execution_prompt": "e",
                              "expected_output": "o", "validation_criteria": "v", "priority": "P2",
                              "complexity": "Low", "task_type": "UX Redesign", "layer": "UI",
                              "product_area": "UX", "status": "Ready for AI"},
                             failure_evidence="fe", context_links="cl")
    assert props["Autonomy Tier"]["select"] is None
```

Run: `.venv311/bin/pytest backend/tests/test_notion_work_queue_properties.py -v` → Expected: FAIL (KeyError `Autonomy Tier`)

- [ ] **Step 6: Add the property to `build_properties`**

In `notion_work_queue.py`, import the labels at top: `from .feedback_task_engineer import _TIER_LABELS` (or duplicate the dict locally to avoid a cross-import cycle — prefer a local `_TIER_LABELS` copy in `notion_work_queue.py`). Then in the returned dict, add:

```python
        "Autonomy Tier": _select(_TIER_LABELS.get(task.get("autonomy_tier"))),
```
Confirm `_select(None)` returns `{"select": None}` (it does — Notion ignores a null select). If not, guard: `_select(_TIER_LABELS.get(task.get("autonomy_tier"))) if task.get("autonomy_tier") else {"select": None}`.

- [ ] **Step 7: Run tests + commit**

Run: `.venv311/bin/pytest backend/tests/test_autonomy_tier.py backend/tests/test_notion_work_queue_properties.py -v` → Expected: PASS
```bash
git add backend/app/services/feedback_task_engineer.py backend/app/services/notion_work_queue.py backend/tests/test_autonomy_tier.py backend/tests/test_notion_work_queue_properties.py
git commit -m "feat(feedback): compute + write Autonomy Tier on dispatch"
```

---

### Task 3: Additive `feedback_status` pipeline-state migration

**Files:**
- Create: `supabase/migrations/20260908000000_feedback_status_pipeline.sql`
- Test: validate via rollback-tx (Supabase MCP `execute_sql`, prod-safe)

**Interfaces:**
- Produces columns consumed by Tasks 4–7: `autonomy_tier, pr_url, pr_number, branch_name, triaged_at, spec_drafted_at, dispatched_at, in_progress_at, deployed_at, done_at`; widened `dispatch_status` lifecycle with a permissive CHECK.

- [ ] **Step 1: Write the migration**

```sql
-- 20260908000000_feedback_status_pipeline.sql
-- Shared pipeline-state model on feedback_status (manual lane + autopilot).
-- Additive + idempotent. dispatch_status had no CHECK; adds one after normalizing legacy values.
alter table public.feedback_status
  add column if not exists autonomy_tier   text,
  add column if not exists pr_url          text,
  add column if not exists pr_number       bigint,
  add column if not exists branch_name     text,
  add column if not exists triaged_at      timestamptz,
  add column if not exists spec_drafted_at timestamptz,
  add column if not exists dispatched_at   timestamptz,
  add column if not exists in_progress_at  timestamptz,
  add column if not exists deployed_at     timestamptz,
  add column if not exists done_at         timestamptz;

-- Normalize any legacy dispatch_status values into the canonical lifecycle.
update public.feedback_status set dispatch_status = 'new'           where dispatch_status = 'pending';
update public.feedback_status set dispatch_status = 'verify_failed' where dispatch_status = 'failed';

alter table public.feedback_status drop constraint if exists feedback_status_dispatch_status_ck;
alter table public.feedback_status add constraint feedback_status_dispatch_status_ck
  check (dispatch_status is null or dispatch_status in (
    'new','triaged','spec_drafted','dispatched','in_progress','in_review',
    'deployed','done','verify_failed','dismissed','wont_fix'));

alter table public.feedback_status drop constraint if exists feedback_status_autonomy_tier_ck;
alter table public.feedback_status add constraint feedback_status_autonomy_tier_ck
  check (autonomy_tier is null or autonomy_tier in ('green','yellow','red'));

-- feedback_status already has RLS enabled + admin_read/service_all policies + REVOKE anon
-- (20260818000000). Altering columns inherits that posture — no new table, no new gate.
```

- [ ] **Step 2: Validate via rollback-tx (prod-safe)**

Use Supabase MCP `execute_sql` on project `nsvefcvpvwwwhuqyuqmp` with a single statement wrapping the DDL above + this assert, then `RAISE EXCEPTION 'ALL_TESTS_PASSED'` to roll back:

```sql
DO $$ BEGIN
  -- (paste the ALTERs above here)
  INSERT INTO public.feedback_status (stream, source_id, dispatch_status)
    VALUES ('product', 'rolltest-1', 'spec_drafted') ON CONFLICT DO NOTHING;
  PERFORM 1 FROM public.feedback_status WHERE source_id='rolltest-1' AND dispatch_status='spec_drafted';
  IF NOT FOUND THEN RAISE EXCEPTION 'canonical value rejected'; END IF;
  RAISE EXCEPTION 'ALL_TESTS_PASSED';
END $$;
```
Expected: the call errors with `ALL_TESTS_PASSED` (everything rolled back). Any *other* error (e.g. a CHECK violation on existing rows) means legacy data has an unexpected `dispatch_status` — inspect with `SELECT DISTINCT dispatch_status FROM feedback_status;` and extend the normalization before committing.

- [ ] **Step 3: Commit (do NOT apply from code; operator applies out-of-band)**

```bash
git add supabase/migrations/20260908000000_feedback_status_pipeline.sql
git commit -m "feat(feedback): additive feedback_status pipeline-state columns + CHECK"
```

---

### Task 4: State writers — dispatch/preview stamps `spec_drafted`, dispatch/create stamps `dispatched` + join key + tier

**Files:**
- Modify: `backend/app/routers/admin_feedback.py` (`dispatch_preview`, `dispatch_create`)
- Modify: `backend/app/services/autopilot_ingest.py` (`_dispatch_one` writes `notion_task_id` + `dispatched_at` + `autonomy_tier`)
- Test: `backend/tests/test_feedback_state_writers.py` (new; app-mounted harness)

**Interfaces:**
- Produces: on `dispatch/preview` → `dispatch_status='spec_drafted'`, `spec_drafted_at=now`. On `dispatch/create` → `dispatch_status='dispatched'`, `dispatched_at=now`, `dispatch_ref=url`, `notion_task_id=<dashless-lower 32hex>`, `autonomy_tier=<green|yellow|red>`.
- **Clarification (explicit):** `spec_drafted` is stamped in **`dispatch/preview`** (when the AI drafts the task), NOT in `dispatch/create`. `dispatched` is stamped in `dispatch/create`.

- [ ] **Step 1: Write the failing test** (app-mounted harness; override `backend.app.auth_deps.require_admin`)

```python
# backend/tests/test_feedback_state_writers.py — requires RELOPASS_QUERY_COUNTER_OFF=1
import os; os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
# ... (mirror an existing app-mounted admin_feedback test: seed a feedback + feedback_status row,
#      monkeypatch engineer_task to return a fixed task incl. autonomy_tier, monkeypatch
#      notion_work_queue.create_work_queue_task -> "https://www.notion.so/Task-0123456789abcdef0123456789abcdef")

def test_preview_stamps_spec_drafted(client, seed_item):
    client.post(f"/api/admin/feedback/product/{seed_item}/dispatch/preview", json={"text": "x", "category": "bug"})
    row = fetch_feedback_status(seed_item)
    assert row["dispatch_status"] == "spec_drafted" and row["spec_drafted_at"] is not None


def test_create_stamps_dispatched_and_join_key(client, seed_item):
    task = {"title": "t", "autonomy_tier": "yellow", ...}
    client.post(f"/api/admin/feedback/product/{seed_item}/dispatch/create", json={"task": task})
    row = fetch_feedback_status(seed_item)
    assert row["dispatch_status"] == "dispatched" and row["dispatched_at"] is not None
    assert row["autonomy_tier"] == "yellow"
    assert row["notion_task_id"] == "0123456789abcdef0123456789abcdef"  # dashless lower
```

- [ ] **Step 2: Run test to verify it fails**

Run: `RELOPASS_DISABLE_RATE_LIMITS=1 .venv311/bin/pytest backend/tests/test_feedback_state_writers.py -v`
Expected: FAIL (columns not written)

- [ ] **Step 3: Stamp `spec_drafted` in `dispatch_preview`**

`dispatch_preview` currently opens a short-lived `_db = SessionLocal()` and closes it before the LLM call. After the `engineer_task(...)` succeeds (just before `return {"task": task}`), open a fresh short session and write:

```python
    _db2 = SessionLocal()
    try:
        _db2.execute(text(
            "INSERT INTO feedback_status (stream, source_id, status, dispatch_status, spec_drafted_at, updated_at) "
            "VALUES (:s, :id, 'new', 'spec_drafted', :now, :now) "
            "ON CONFLICT (stream, source_id) DO UPDATE SET "
            "  dispatch_status = 'spec_drafted', spec_drafted_at = COALESCE(feedback_status.spec_drafted_at, :now), "
            "  updated_at = :now"), {"s": stream, "id": item_id, "now": datetime.utcnow().isoformat()})
        _db2.commit()
    finally:
        _db2.close()
```
(Keep it out of the LLM-holding session — same pooler-drop reason documented in the handler.)

- [ ] **Step 4: Stamp `dispatched` + join key + tier in `dispatch_create`**

Replace the existing `INSERT ... feedback_status ... 'dispatched'` block with one that also writes `dispatched_at`, `notion_task_id`, `autonomy_tier`:

```python
    now = datetime.utcnow().isoformat()
    page_id = notion_work_queue.page_id_from_ref(url) or ""
    notion_task_id = re.sub(r"[^0-9a-f]", "", page_id.lower())  # dashless-lower 32hex join key
    tier = (task.get("autonomy_tier") or None)
    db.execute(text(
        "INSERT INTO feedback_status "
        "(stream, source_id, status, dispatch_ref, dispatch_status, dispatched_at, notion_task_id, autonomy_tier, updated_at) "
        "VALUES (:s, :id, 'new', :ref, 'dispatched', :now, :ntid, :tier, :now) "
        "ON CONFLICT (stream, source_id) DO UPDATE SET "
        "  dispatch_ref = excluded.dispatch_ref, dispatch_status = 'dispatched', "
        "  dispatched_at = :now, notion_task_id = excluded.notion_task_id, "
        "  autonomy_tier = excluded.autonomy_tier, updated_at = :now"),
        {"s": stream, "id": item_id, "ref": url, "now": now, "ntid": notion_task_id, "tier": tier})
```
Add `import re` at top if not present.

- [ ] **Step 5: Mirror the join key + tier in the autopilot lane**

In `autopilot_ingest._dispatch_one`, replace its `INSERT ... feedback_status` with the same extra columns (`dispatched_at`, `notion_task_id` from `nwq.page_id_from_ref(url)` dashless-lower, `autonomy_tier` from `task.get("autonomy_tier")`). This makes autopilot-dispatched items advanceable by the bridge (Task 5).

- [ ] **Step 6: Run tests + commit**

Run: `RELOPASS_DISABLE_RATE_LIMITS=1 .venv311/bin/pytest backend/tests/test_feedback_state_writers.py -v` → Expected: PASS
```bash
git add backend/app/routers/admin_feedback.py backend/app/services/autopilot_ingest.py backend/tests/test_feedback_state_writers.py
git commit -m "feat(feedback): stamp spec_drafted on preview, dispatched+join-key+tier on create"
```

---

### Task 5: Autopilot-event → `feedback_status` bridge

**Files:**
- Create: `backend/app/services/feedback_status_bridge.py` (`advance_status_for_event`)
- Modify: `backend/app/routers/crons.py` (`autopilot_event` calls the bridge)
- Test: `backend/tests/test_feedback_status_bridge.py` (new)

**Interfaces:**
- Consumes: `feedback_status.notion_task_id` (dashless-lower 32hex, written in Task 4); `event.entity_id` = the workflow's `$NOTION_ID` (dashless 16-hex branch prefix).
- Produces: `advance_status_for_event(session, event_type: str, entity_id: Optional[str]) -> bool` (True if a row advanced). Best-effort, never raises.
- **Join key (explicit):** `substr(feedback_status.notion_task_id, 1, 16) == lower(entity_id)`. This is portable (no PG-only regex): both sides are already dashless-lower, so a plain `substr`/`LEFT` prefix compare works on SQLite and Postgres. Event→state map: `fix_attempted→in_progress(+in_progress_at)`, `merged→in_review`, `canary_passed→deployed(+deployed_at)`, `task_done→done(+done_at)`, `canary_failed|reverted→verify_failed`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_feedback_status_bridge.py
from backend.app.services.feedback_status_bridge import advance_status_for_event


def test_bridge_advances_on_task_done(session_with_dispatched_row):
    s = session_with_dispatched_row  # feedback_status row with notion_task_id='0123456789abcdef0123456789abcdef'
    ok = advance_status_for_event(s, "autopilot.task_done", "0123456789abcdef")  # 16-hex prefix
    assert ok is True
    row = s.execute(text("SELECT dispatch_status, done_at FROM feedback_status WHERE source_id=:i"),
                    {"i": "seed"}).fetchone()
    assert row[0] == "done" and row[1] is not None


def test_bridge_noop_on_unknown_entity(session_with_dispatched_row):
    assert advance_status_for_event(session_with_dispatched_row, "autopilot.merged", "ffffffffffffffff") is False


def test_bridge_ignores_non_lifecycle_events(session_with_dispatched_row):
    assert advance_status_for_event(session_with_dispatched_row, "autopilot.run_started", "0123456789abcdef") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv311/bin/pytest backend/tests/test_feedback_status_bridge.py -v` → Expected: FAIL (module missing)

- [ ] **Step 3: Implement the bridge**

```python
# backend/app/services/feedback_status_bridge.py
"""Advance feedback_status when the autopilot's CI funnel events arrive.
Join: feedback_status.notion_task_id (dashless-lower 32hex) prefix == event entity_id (16hex)."""
from __future__ import annotations
import logging, re
from datetime import datetime
from typing import Optional
from sqlalchemy import text

log = logging.getLogger(__name__)

# event_type -> (target dispatch_status, optional timestamp column)
_STATE_FOR_EVENT = {
    "autopilot.fix_attempted": ("in_progress", "in_progress_at"),
    "autopilot.merged":        ("in_review", None),
    "autopilot.canary_passed": ("deployed", "deployed_at"),
    "autopilot.task_done":     ("done", "done_at"),
    "autopilot.canary_failed": ("verify_failed", None),
    "autopilot.reverted":      ("verify_failed", None),
}


def advance_status_for_event(session, event_type: str, entity_id: Optional[str]) -> bool:
    m = _STATE_FOR_EVENT.get(event_type)
    if not m or not entity_id:
        return False
    state, ts_col = m
    eid = re.sub(r"[^0-9a-f]", "", entity_id.lower())[:16]
    if len(eid) < 16:
        return False
    now = datetime.utcnow().isoformat()
    set_ts = f", {ts_col} = :now" if ts_col else ""
    try:
        res = session.execute(text(
            f"UPDATE feedback_status SET dispatch_status = :st{set_ts}, updated_at = :now "
            "WHERE substr(notion_task_id, 1, 16) = :eid"),
            {"st": state, "now": now, "eid": eid})
        session.commit()
        return (res.rowcount or 0) > 0
    except Exception as exc:  # noqa: BLE001 — best-effort, funnel event already emitted
        log.warning("feedback_status bridge failed for %s/%s: %s", event_type, eid, exc)
        return False
```

- [ ] **Step 4: Call it from `autopilot_event`**

In `crons.py`, after `ev.emit(...)` in `autopilot_event`, add (best-effort, own session):

```python
    from ..services.feedback_status_bridge import advance_status_for_event
    from ..db import SessionLocal
    _s = SessionLocal()
    try:
        advance_status_for_event(_s, body.event_type, body.entity_id)
    finally:
        _s.close()
```

- [ ] **Step 5: Run tests + commit**

Run: `.venv311/bin/pytest backend/tests/test_feedback_status_bridge.py -v` → Expected: PASS
```bash
git add backend/app/services/feedback_status_bridge.py backend/app/routers/crons.py backend/tests/test_feedback_status_bridge.py
git commit -m "feat(feedback): bridge autopilot CI events into feedback_status pipeline state"
```

---

### Task 6: `PATCH /state` transition endpoint + validator

**Files:**
- Create: `backend/app/services/feedback_state_machine.py` (`ALLOWED_TRANSITIONS`, `validate_transition`)
- Modify: `backend/app/routers/admin_feedback.py` (new `PATCH /feedback/{stream}/{item_id}/state`)
- Test: `backend/tests/test_feedback_state_machine.py` (new)

**Interfaces:**
- Produces: `validate_transition(current: Optional[str], target: str) -> bool`; endpoint `PATCH /api/admin/feedback/{stream}/{item_id}/state` body `{"target": str}` → 200 `{ok, dispatch_status}` or 409.
- `ALLOWED_TRANSITIONS`: `new→{triaged,dismissed,wont_fix}`, `triaged→{spec_drafted,dismissed,wont_fix}`, `spec_drafted→{dispatched,dismissed,wont_fix}`, `dispatched→{in_progress,verify_failed,dismissed}`, `in_progress→{in_review,verify_failed}`, `in_review→{deployed,verify_failed}`, `deployed→{done,verify_failed}`, `verify_failed→{in_progress,dismissed,wont_fix}`, terminal `{done,dismissed,wont_fix}→{}`. `None`/absent current treated as `new`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_feedback_state_machine.py
from backend.app.services.feedback_state_machine import validate_transition


def test_legal_transition():
    assert validate_transition("dispatched", "in_progress") is True


def test_illegal_jump():
    assert validate_transition("new", "deployed") is False


def test_terminal_is_dead_end():
    assert validate_transition("done", "in_progress") is False


def test_none_treated_as_new():
    assert validate_transition(None, "triaged") is True
```

- [ ] **Step 2: Run test to verify it fails** → `.venv311/bin/pytest backend/tests/test_feedback_state_machine.py -v` → FAIL

- [ ] **Step 3: Implement the state machine**

```python
# backend/app/services/feedback_state_machine.py
from typing import Dict, Optional, Set

ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
    "new": {"triaged", "dismissed", "wont_fix"},
    "triaged": {"spec_drafted", "dismissed", "wont_fix"},
    "spec_drafted": {"dispatched", "dismissed", "wont_fix"},
    "dispatched": {"in_progress", "verify_failed", "dismissed"},
    "in_progress": {"in_review", "verify_failed"},
    "in_review": {"deployed", "verify_failed"},
    "deployed": {"done", "verify_failed"},
    "verify_failed": {"in_progress", "dismissed", "wont_fix"},
    "done": set(), "dismissed": set(), "wont_fix": set(),
}
_TS_COL = {"triaged": "triaged_at", "spec_drafted": "spec_drafted_at", "dispatched": "dispatched_at",
           "in_progress": "in_progress_at", "deployed": "deployed_at", "done": "done_at"}


def validate_transition(current: Optional[str], target: str) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current or "new", set())


def timestamp_column(target: str) -> Optional[str]:
    return _TS_COL.get(target)
```

- [ ] **Step 4: Run test to verify it passes** → PASS

- [ ] **Step 5: Add the `PATCH /state` endpoint** (test with the app-mounted harness)

In `admin_feedback.py`:

```python
class StateBody(BaseModel):
    target: str


@router.patch("/feedback/{stream}/{item_id}/state")
def set_state(stream: str, item_id: str, body: StateBody,
              db: Session = Depends(_get_db), user: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    from ..services.feedback_state_machine import validate_transition, timestamp_column, ALLOWED_TRANSITIONS
    if body.target not in ALLOWED_TRANSITIONS:
        raise HTTPException(status_code=422, detail=f"unknown state {body.target!r}")
    row = db.execute(text("SELECT dispatch_status FROM feedback_status WHERE stream=:s AND source_id=:id"),
                     {"s": stream, "id": item_id}).fetchone()
    current = (row[0] if row else None)
    if not validate_transition(current, body.target):
        raise HTTPException(status_code=409, detail=f"illegal transition {current} → {body.target}")
    now = datetime.utcnow().isoformat()
    ts_col = timestamp_column(body.target)
    set_ts = f", {ts_col} = :now" if ts_col else ""
    db.execute(text(
        f"INSERT INTO feedback_status (stream, source_id, status, dispatch_status, updated_at{(', ' + ts_col) if ts_col else ''}) "
        f"VALUES (:s, :id, 'new', :t, :now{', :now' if ts_col else ''}) "
        f"ON CONFLICT (stream, source_id) DO UPDATE SET dispatch_status = :t, updated_at = :now{set_ts}"),
        {"s": stream, "id": item_id, "t": body.target, "now": now})
    return {"ok": True, "dispatch_status": body.target}
```

- [ ] **Step 6: Run backend suite for the router + commit**

Run: `RELOPASS_DISABLE_RATE_LIMITS=1 .venv311/bin/pytest backend/tests/test_feedback_state_machine.py -v`
```bash
git add backend/app/services/feedback_state_machine.py backend/app/routers/admin_feedback.py backend/tests/test_feedback_state_machine.py
git commit -m "feat(feedback): PATCH /state transition endpoint + validated state machine"
```

---

### Task 7: Progressive Button Strip in `FeedbackTab`

**Files:**
- Create: `frontend/src/components/admin/ProgressStrip.tsx`
- Modify: `frontend/src/api/adminFeedback.ts` (widen `DispatchStatus`, add `advanceState`, add `autonomy_tier` to `UnifiedFeedbackItem`)
- Modify: `frontend/src/components/admin/FeedbackTab.tsx` (render `<ProgressStrip>` per row)
- Test: `frontend/src/components/admin/ProgressStrip.test.tsx` (new)

**Interfaces:**
- Consumes: `advanceState(stream, id, target): Promise<{dispatch_status: string}>` → `PATCH /api/admin/feedback/{stream}/{id}/state`.
- Produces: `<ProgressStrip status={...} tier={...} onAdvance={(target) => ...} busy={bool} />`.

- [ ] **Step 1: Widen types + add the wrapper (`adminFeedback.ts`)**

```typescript
export type DispatchStatus =
  | 'new' | 'triaged' | 'spec_drafted' | 'dispatched' | 'in_progress'
  | 'in_review' | 'deployed' | 'done' | 'verify_failed' | 'dismissed' | 'wont_fix'
  | 'pending' | 'failed';  // legacy, tolerated on read
export type AutonomyTier = 'green' | 'yellow' | 'red';
```
Add `autonomy_tier?: AutonomyTier | null;` to `UnifiedFeedbackItem`, and:
```typescript
export async function advanceState(stream: FeedbackStream, id: string, target: DispatchStatus) {
  return apiPatch<{ ok: boolean; dispatch_status: DispatchStatus }>(
    `/api/admin/feedback/${stream}/${id}/state`, { target });
}
```

- [ ] **Step 2: Write the failing test**

```typescript
// frontend/src/components/admin/ProgressStrip.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ProgressStrip } from './ProgressStrip';

describe('ProgressStrip', () => {
  it('shows the valid next action for the current state', () => {
    render(<ProgressStrip status="dispatched" tier="yellow" busy={false} onAdvance={() => {}} />);
    expect(screen.getByRole('button', { name: /in progress/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^done$/i })).toBeNull();
  });
  it('fires onAdvance with the target state', () => {
    const spy = vi.fn();
    render(<ProgressStrip status="deployed" tier="green" busy={false} onAdvance={spy} />);
    fireEvent.click(screen.getByRole('button', { name: /^done$/i }));
    expect(spy).toHaveBeenCalledWith('done');
  });
});
```

- [ ] **Step 3: Run test to verify it fails** → `cd frontend && npx vitest run src/components/admin/ProgressStrip.test.tsx` → FAIL (no module)

- [ ] **Step 4: Implement `ProgressStrip.tsx`**

Mirror the `ALLOWED_TRANSITIONS` map (subset shown to the admin — the primary forward action + escapes). Use antigravity `Button` + `Badge`. Do NOT import `api/supabase`.

```tsx
import { Button } from '../antigravity/Button';
import { Badge } from '../antigravity/Badge';

const NEXT: Record<string, { target: string; label: string }[]> = {
  new: [{ target: 'triaged', label: 'Triage' }],
  triaged: [{ target: 'spec_drafted', label: 'Draft spec' }],
  spec_drafted: [{ target: 'dispatched', label: 'Create task' }],
  dispatched: [{ target: 'in_progress', label: 'Mark in progress' }],
  in_progress: [{ target: 'in_review', label: 'Mark in review' }],
  in_review: [{ target: 'deployed', label: 'Mark deployed' }],
  deployed: [{ target: 'done', label: 'Done' }, { target: 'verify_failed', label: 'Verify failed' }],
  verify_failed: [{ target: 'in_progress', label: 'Retry' }],
};
const TIER_VARIANT: Record<string, 'success' | 'warning' | 'danger'> = {
  green: 'success', yellow: 'warning', red: 'danger',
};
const ORDER = ['new','triaged','spec_drafted','dispatched','in_progress','in_review','deployed','done'];

export function ProgressStrip({ status, tier, busy, onAdvance }: {
  status: string; tier?: string | null; busy: boolean; onAdvance: (target: string) => void;
}) {
  const idx = ORDER.indexOf(status);
  return (
    <div className="flex items-center gap-2 flex-wrap">
      {tier && <Badge variant={TIER_VARIANT[tier] ?? 'default'}>{tier}</Badge>}
      <span className="text-xs text-navy-500">
        {ORDER.map((s, i) => <span key={s} className={i <= idx ? 'font-semibold' : 'opacity-40'}>{s}{i < ORDER.length - 1 ? ' › ' : ''}</span>)}
      </span>
      {(NEXT[status] ?? []).map((a) => (
        <Button key={a.target} size="sm" disabled={busy} onClick={() => onAdvance(a.target)}>{a.label}</Button>
      ))}
    </div>
  );
}
```

- [ ] **Step 5: Run test to verify it passes** → `npx vitest run src/components/admin/ProgressStrip.test.tsx` → PASS

- [ ] **Step 6: Render it in `FeedbackTab`**

In the row render, add `<ProgressStrip status={row.dispatch_status ?? 'new'} tier={row.autonomy_tier} busy={savingId === row.id} onAdvance={(t) => handleAdvance(row, t)} />` and a `handleAdvance` callback that calls `advanceState(row.stream, row.id, t)`, updates local `rows` state on success, and surfaces a 409 into `dispatchErrors[row.id]`. Import `ProgressStrip` and `advanceState`.

- [ ] **Step 7: Typecheck, build, commit**

Run: `cd frontend && npx tsc --noEmit && npx vitest run src/components/admin/ProgressStrip.test.tsx && npm run build`
Expected: all green
```bash
git add frontend/src/components/admin/ProgressStrip.tsx frontend/src/components/admin/ProgressStrip.test.tsx frontend/src/api/adminFeedback.ts frontend/src/components/admin/FeedbackTab.tsx
git commit -m "feat(feedback): Progressive Button Strip + advanceState wiring in FeedbackTab"
```

---

## Self-Review

**Spec coverage:** P1 diagnostics enrichment → Task 1 (+ posthog_id). P2 Autonomy Tier → Task 2. P3 shared state model → Tasks 3 (schema), 4 (writers), 5 (autopilot bridge). P4 Progressive Button Strip + `PATCH /state` → Tasks 6–7. User additions: (1) explicit bridge join key → Task 5 interface block + Task 4 writes `notion_task_id`; (2) `posthog_id` → Task 1 Step 7; (3) `spec_drafted` stamped on `dispatch/preview` not `create` → Task 4 interface "Clarification". Deferred (webhook, PostHog-verify) correctly absent.

**Placeholder scan:** The app-mounted harness fixtures in Tasks 4–6 use `...` for boilerplate seed/mock setup that mirrors an existing `admin_feedback` test — the engineer copies the nearest existing app-mounted test's fixtures (`RELOPASS_QUERY_COUNTER_OFF=1`, override `backend.app.auth_deps.require_admin`). All production code is complete.

**Type consistency:** `format_diagnostics`, `compute_autonomy_tier`, `_TIER_LABELS`, `notion_task_id` (dashless-lower), `advance_status_for_event`, `validate_transition`/`timestamp_column`, `advanceState`, `ProgressStrip` props — names match across tasks. `dispatch_status` lifecycle values identical in migration CHECK, state machine, and TS type.
