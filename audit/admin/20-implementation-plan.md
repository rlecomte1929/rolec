# Admin Hardening — Build-First Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:subagent-driven-development or superpowers:executing-plans to implement task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Implement the 6 build-first items from the Admin audit (`audit/admin/00-admin-audit.md`) — turning the admin from a CMS into a governable operations console (close the top security, feedback-loop, AI-control, and access/audit gaps).

**Architecture:** Each task is one PR-sized, independently shippable deliverable. Backend = FastAPI (`backend/main.py` monolith + `backend/app/routers/*`), new tables via Supabase migrations (committed; applied out-of-band). Frontend = React/TS SPA (`frontend/src`), admin under `/admin/*`. AI-governance is built on a new `platform_settings` store read with **env → DB → default** precedence so default behavior never changes until an admin acts.

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy + raw SQL, React + TypeScript + Vite + react-query, Supabase/Postgres (RLS), pytest, vitest.

## Global Constraints

- **Run tests with** `/Users/romainlecomte/Documents/GitHub/rolec/.venv311/bin/python -m pytest -c backend/pytest.ini --rootdir . <paths> -p no:cacheprovider` (Py3.9 system pytest can't collect; the repo venv is 3.11). Frontend: `cd frontend && npx tsc --noEmit` and `npx vitest`.
- **Budgets out until July 1:** GitHub Actions CI and Render both fail on billing. Validate **locally**; open PRs but **hold them open** (do not merge — merging triggers an instant-fail Render deploy). One PR per task.
- **Dual-router rule:** any NEW router must be registered in BOTH `backend/main.py` AND `backend/app/main.py`; import auth deps from `backend.app.auth_deps` (NOT `backend.main`). Verify with `python scripts/check_router_registrations.py`.
- **New `public` tables (HARD GATE):** every migration must `ENABLE ROW LEVEL SECURITY` + ≥1 policy + `REVOKE ALL ... FROM anon`; idempotent DDL; timestamp greater than the current max under `supabase/migrations/` (currently `20260816000000`). **Commit the file only — do NOT apply to prod** unless Romain authorizes; flag it in the PR.
- **Route auth:** every new endpoint uses an auth `Depends` (`require_admin`) or is allowlisted in `scripts/route_auth_allowlist.txt` with a comment. Verify with `python scripts/check_route_auth.py`.
- **Audit pattern:** id-less / semantic events go into `audit_logs` via an app-level writer with the event in `new_value.event` (the trigger only covers `mobility_cases`/`case_people`/`case_documents` and needs an `id` column).
- **No behavior flips:** new flags/controls default to current behavior; flipping is a gated admin action.
- Commit messages end with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

## File structure (created/modified across the plan)

- `backend/app/routers/admin_admins.py` (new) — admin lifecycle endpoints (Task 7).
- `backend/app/routers/admin_settings.py` (new) — AI-governance settings + kill-switch (Task 4).
- `backend/app/routers/admin_feedback.py` (new) — unified feedback read + triage (Task 6).
- `backend/app/services/platform_settings.py` (new) — settings store + `get_setting` resolver (Task 3).
- `backend/app/services/admin_audit.py` (new) — `record_admin_event()` app-level audit writer (Task 1, reused after).
- `supabase/migrations/2026081700_*.sql … 2026082100_*.sql` (new) — `platform_settings`, `feedback_status`, admin-audit coverage (per task).
- Frontend: `frontend/src/features/policy-assistant/AnswerFeedback.tsx` (new, Task 2); `pages/admin/AdminAiControlsPage.tsx`, `AdminAuditLogPage.tsx`, `AdminAdminsPage.tsx` (new); edits to `App.tsx`, `routes.ts`, `navigation/routes.ts`, `PlatformShellSidebar.tsx`.

---

### Task 1: Guard `/admin/countries` + consolidate admin checks + audit-writer helper

**Closes:** A-01 (P1), A-07 (P2). Foundation: ships the shared `record_admin_event()` used by later tasks.

**Files:**
- Modify: `frontend/src/App.tsx` (wrap the two `/admin/countries` routes), `frontend/src/routes.ts` (note the route defs)
- Modify: `backend/app/routers/admin_workflow_analytics.py` (replace local `_require_admin` with `auth_deps.require_admin`)
- Create: `backend/app/services/admin_audit.py`
- Test: `frontend/src/features/admin/__tests__/RequireAdminRoute.countries.test.tsx`, `backend/tests/test_admin_audit_writer.py`

**Interfaces:**
- Produces: `admin_audit.record_admin_event(db, *, actor_id: str, event: str, entity: str|None=None, entity_id: str|None=None, detail: dict|None=None) -> None` — writes one `audit_logs` row with `actor_type='human'`, `action_type='update'`, `new_value={'event': event, **(detail or {})}`. Never raises (best-effort, logs on failure).

- [ ] **Step 1: Failing FE test — `/admin/countries` requires admin**

```tsx
// renders the route tree as a non-admin; expects redirect away from /admin/countries
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
// seed a non-admin auth context (mirror existing RequireAdminRoute tests)
test('non-admin cannot reach /admin/countries', () => {
  renderAppAt('/admin/countries', { role: 'EMPLOYEE' })
  expect(screen.queryByTestId('countries-page')).toBeNull()
})
```

- [ ] **Step 2: Run it — Expected FAIL** (currently renders the page): `cd frontend && npx vitest run src/features/admin/__tests__/RequireAdminRoute.countries.test.tsx`
- [ ] **Step 3: Wrap the routes** in `App.tsx`: change the two country routes to `<RequireAdminRoute><CountriesPage/></RequireAdminRoute>` and `…<CountryDetailPage/>…` (mirror the other `/admin/*` entries). Add `data-testid="countries-page"` to `CountriesPage` root if absent.
- [ ] **Step 4: Run it — Expected PASS.**
- [ ] **Step 5: Backend — failing test for the audit writer**

```python
def test_record_admin_event_writes_row(db_session):
    from backend.app.services.admin_audit import record_admin_event
    record_admin_event(db_session, actor_id="u1", event="test_event", detail={"k": 1})
    rows = db_session.execute(text("select new_value from audit_logs where actor_id='u1'")).all()
    assert rows and rows[0][0]["event"] == "test_event"
```

- [ ] **Step 6: Run — Expected FAIL** (module missing).
- [ ] **Step 7: Implement `admin_audit.record_admin_event`** (insert into `audit_logs`; `new_value=json(...)`; wrap in try/except logging). Replace `admin_workflow_analytics._require_admin` with `from ..auth_deps import require_admin` and use it in the route deps.
- [ ] **Step 8: Run backend test + guards — Expected PASS:** `… pytest backend/tests/test_admin_audit_writer.py -q`; `python scripts/check_route_auth.py`; `cd frontend && npx tsc --noEmit`.
- [ ] **Step 9: Commit** (`fix(admin): guard /admin/countries, unify admin check, add audit writer`), push branch `feat/admin-01-guard-audit`, open held PR.

---

### Task 2: Wire the policy-answer thumbs UI (activate `policy_answer_helpfulness`)

**Closes:** F-01 (P1). The endpoint exists; no UI submits it.

**Files:**
- Create: `frontend/src/features/policy-assistant/AnswerFeedback.tsx`
- Modify: the policy-assistant answer component that renders an answer (locate via `grep -rl "rag-query\|policy-assistant/query\|grounding" frontend/src` — likely under `features/policy-builder` or `features/policy-assistant`); add `<AnswerFeedback traceSessionId={...} />` beneath the answer.
- Create: `frontend/src/api/policyHelpfulness.ts` (POST wrapper)
- Test: `frontend/src/features/policy-assistant/__tests__/AnswerFeedback.test.tsx`

**Interfaces:**
- Consumes: `POST /api/policy-assistant/helpfulness` body `{trace_session_id: string, helpful: boolean, comment?: string}` (from `routers/policy_helpfulness.py`).
- Produces: `submitHelpfulness(traceSessionId, helpful, comment?)` in `api/policyHelpfulness.ts`.

- [ ] **Step 1: Failing test** — clicking 👍 calls the API with `helpful:true` and shows a thank-you; mirror the immigration thumbs test (`features/immigration/__tests__`). Mock the axios client.
- [ ] **Step 2: Run — Expected FAIL.**
- [ ] **Step 3: Implement `api/policyHelpfulness.ts`**

```ts
import { api } from '../api/client'
export async function submitHelpfulness(traceSessionId: string, helpful: boolean, comment?: string) {
  await api.post('/api/policy-assistant/helpfulness', { trace_session_id: traceSessionId, helpful, comment })
}
```

- [ ] **Step 4: Implement `AnswerFeedback.tsx`** — two antigravity `Button`s (👍/👎), optional comment box on 👎, calls `submitHelpfulness`, disables after submit, shows "Thanks". Needs the answer's `trace_session_id` — confirm the rag-query response exposes it; if not, thread it through (the engine already creates the trace; surface its id in the response payload).
- [ ] **Step 5: Wire it** into the answer component; pass the trace id.
- [ ] **Step 6: Run test + `npx tsc --noEmit` — Expected PASS.**
- [ ] **Step 7: Commit** (`feat(policy-assistant): end-user answer helpfulness thumbs`), branch `feat/admin-02-helpfulness-ui`, held PR.

> If the rag-query response does not already include `trace_session_id`, add it to the response model in `policy_assistant_rag_engine`/its router (small backend change) as Step 4a, with a test asserting the field is present.

---

### Task 3: `platform_settings` store + env→DB→default resolver

**Foundation for Tasks 4 & 5.** No behavior change on its own.

**Files:**
- Create: `supabase/migrations/20260817000000_platform_settings.sql`
- Create: `backend/app/services/platform_settings.py`
- Test: `backend/tests/test_platform_settings.py`

**Interfaces:**
- Produces: `platform_settings.get_setting(key: str, *, env_var: str|None=None, default: str|None=None, db=None) -> str|None` with precedence **env_var (if set) → DB value → default**; `set_setting(db, key, value, *, actor_id) -> None` (writes row + `record_admin_event`); `list_settings(db) -> list[dict]`.

- [ ] **Step 1: Migration** — `platform_settings(key text primary key, value_json jsonb not null, updated_by text, updated_at timestamptz default now())` + `ENABLE RLS` + admin-read/service-write policies + `REVOKE ALL FROM anon`. Timestamp `20260817000000`.
- [ ] **Step 2: Failing test**

```python
def test_get_setting_precedence(db_session, monkeypatch):
    from backend.app.services import platform_settings as ps
    # default when nothing set
    assert ps.get_setting("x", default="d", db=db_session) == "d"
    # DB overrides default
    ps.set_setting(db_session, "x", "dbval", actor_id="a")
    assert ps.get_setting("x", default="d", db=db_session) == "dbval"
    # env overrides DB
    monkeypatch.setenv("X_ENV", "envval")
    assert ps.get_setting("x", env_var="X_ENV", default="d", db=db_session) == "envval"
```

- [ ] **Step 3: Run — Expected FAIL.**
- [ ] **Step 4: Implement `platform_settings.py`** (resolver with the 3-level precedence; `set_setting` writes jsonb + calls `record_admin_event`; best-effort DB read that returns `default` if the table is absent, so pre-migration behavior is safe).
- [ ] **Step 5: Run — Expected PASS.**
- [ ] **Step 6: Commit** (`feat(admin): platform_settings store + env->DB->default resolver`), branch `feat/admin-03-settings-store`, held PR. Note in PR: migration committed-not-applied.

---

### Task 4: Admin AI-governance panel (surface + gate the 3 flags, with kill-switch)

**Closes:** C-01 (P1), H-02 (P1), H-03 (P2). Depends on Task 3.

**Files:**
- Modify: `backend/app/services/policy_assistant_rag_engine.py` (gate reads), `policy_chunk_retriever.py` (rerank read), `recommendations/weights.py` (`SUPPLIER_LEARNED_WEIGHTS` read) — replace each `os.environ.get(FLAG)` with `platform_settings.get_setting(<key>, env_var=<FLAG>, default="0")` so **env still wins** (no behavior change) but an admin DB value applies when env is unset.
- Create: `backend/app/routers/admin_settings.py` — `GET /api/admin/ai-controls` (current resolved values + source env/db/default), `POST /api/admin/ai-controls` (set a flag/threshold; gated `require_admin`; audited), `POST /api/admin/ai-controls/kill/{feature}` (force safe default).
- Register router in BOTH `backend/main.py` and `backend/app/main.py`.
- Create: `frontend/src/pages/admin/AdminAiControlsPage.tsx` + route + sidebar entry.
- Test: `backend/tests/test_admin_ai_controls.py`, FE `AdminAiControlsPage.test.tsx`.

**Interfaces:**
- Consumes: `platform_settings.get_setting/set_setting`, `record_admin_event`.
- Produces: settings keys `policy_rag_groundedness_gate`, `policy_rag_groundedness_min_score`, `policy_rag_rerank`, `supplier_learned_weights`.

- [ ] **Step 1: Failing test** — `GET /api/admin/ai-controls` returns the 4 keys with `{value, source}`; `POST` requires admin (401 without), sets the DB value, and writes an audit row; resolver then returns the new value when env is unset.

```python
def test_set_ai_control_audited(admin_client, db_session, monkeypatch):
    monkeypatch.delenv("POLICY_RAG_RERANK", raising=False)
    r = admin_client.post("/api/admin/ai-controls", json={"key": "policy_rag_rerank", "value": "1", "reason": "enable"})
    assert r.status_code == 200
    from backend.app.services.platform_settings import get_setting
    assert get_setting("policy_rag_rerank", env_var="POLICY_RAG_RERANK", default="0", db=db_session) == "1"
    assert db_session.execute(text("select 1 from audit_logs where new_value->>'event'='ai_setting_changed'")).first()
```

- [ ] **Step 2: Run — Expected FAIL.**
- [ ] **Step 3: Implement the router** (`require_admin`; validate key in an allowlist of known settings; `set_setting` + `record_admin_event(event='ai_setting_changed', detail={key,value,reason})`; kill endpoint sets the safe default `"0"`). Register in both apps.
- [ ] **Step 4: Swap the 3 reads** to `get_setting(..., env_var=...)` (env precedence preserves current prod behavior). Keep existing `_*_enabled()` helper signatures; only change their body to consult the resolver.
- [ ] **Step 5: Run backend tests + `check_router_registrations.py` + `check_route_auth.py` — Expected PASS.**
- [ ] **Step 6: FE panel** — `AdminAiControlsPage` lists the controls with current value + source, a gated toggle (confirm + reason), and a red "kill (force off)" per feature; add route `/admin/ai-controls` (guarded) + sidebar item. Show the gate-impact number inline if `GET /answer-provenance` exposes it.
- [ ] **Step 7: FE test + tsc — Expected PASS.**
- [ ] **Step 8: Commit** (`feat(admin): AI-governance controls panel (gated flags + kill-switch)`), branch `feat/admin-04-ai-controls`, held PR.

---

### Task 5: Gate the daily source-reliability recompute

**Closes:** H-01 (P1). Depends on Task 3.

**Files:**
- Modify: `backend/app/services/source_reliability_service.py` (add a kill-switch + propose-mode), `.github/workflows/reliability-recompute-daily.yml` (respect a "propose only" setting)
- Create (optional): `source_reliability_proposals` table migration if storing proposed deltas for admin approval
- Test: `backend/tests/test_source_reliability_gate.py`

**Interfaces:**
- Consumes: `platform_settings.get_setting('source_reliability_autoapply', default='1')`.

- [ ] **Step 1: Failing test** — when `source_reliability_autoapply` is `"0"`, the recompute computes deltas but does NOT mutate source trust (writes proposals / logs instead); when `"1"` (default), behavior is unchanged.
- [ ] **Step 2: Run — Expected FAIL.**
- [ ] **Step 3: Implement** — wrap the apply step in `if get_setting('source_reliability_autoapply', default='1') == '1': apply else: record proposal + audit`. Default `'1'` preserves today's behavior. Add a kill via the Task-4 panel (key reuse).
- [ ] **Step 4: Run — Expected PASS.** Validate workflow YAML with `actionlint` (note: gh token has workflow scope).
- [ ] **Step 5: Commit** (`feat(admin): gate daily source-reliability recompute behind a setting`), branch `feat/admin-05-reliability-gate`, held PR.

> If proposals storage is added, the migration follows the new-table HARD GATE and is committed-not-applied. If kept log-only for v1, no migration is needed.

---

### Task 6: Admin Feedback console (read API + view + promote)

**Closes:** F-02 (P1), F-04 (P2). (F-03 beacons surfacing is a follow-on.)

**Files:**
- Create: `backend/app/routers/admin_feedback.py` — `GET /api/admin/feedback?stream=&status=&since=` (normalized rows across `feedback`, `ai_human_feedback`, `policy_answer_helpfulness`); `PATCH /api/admin/feedback/{stream}/{id}` (status/owner/resolution).
- Create: `supabase/migrations/20260818000000_feedback_status.sql` — a `feedback_status(stream text, source_id text, status text, owner text, resolution text, updated_at, primary key(stream, source_id))` table so AI/ML tables are never mutated.
- Register router in both apps.
- Modify: `frontend/src/pages/admin/AdminFeedback.tsx` to use the new API; add to `PlatformShellSidebar.tsx`.
- Test: `backend/tests/test_admin_feedback_api.py`, FE test.

**Interfaces:**
- Consumes: `feedback`, `ai_human_feedback`, `policy_answer_helpfulness`, `feedback_status`, `record_admin_event`.
- Produces: normalized item `{id, stream, source_ref, text, verdict, user_id, company_id, created_at, status, owner, resolution}`.

- [ ] **Step 1: Migration** (`feedback_status` + RLS hard-gates + timestamp `20260818000000`).
- [ ] **Step 2: Failing test** — `GET /api/admin/feedback?stream=helpfulness` returns rows joined to status; `PATCH` sets status + writes an audit row; non-admin → 401.
- [ ] **Step 3: Run — Expected FAIL.**
- [ ] **Step 4: Implement** the read (UNION-normalize the three streams, left join `feedback_status`) + the PATCH (upsert `feedback_status` + `record_admin_event(event='feedback_triaged')`). Register in both apps. (ML consumers untouched.)
- [ ] **Step 5: Run backend tests + guards — Expected PASS.**
- [ ] **Step 6: FE** — point `AdminFeedback`/`FeedbackTab` at the API; add stream tabs + triage actions; add the sidebar item.
- [ ] **Step 7: FE test + tsc — Expected PASS.**
- [ ] **Step 8: Commit** (`feat(admin): unified feedback console (read+triage all streams)`), branch `feat/admin-06-feedback-console`, held PR.

---

### Task 7: Admin lifecycle (add/remove/disable) + audit-log viewer

**Closes:** A-03 (P1), A-05 (P1).

**Files:**
- Create: `backend/app/routers/admin_admins.py` — `GET /api/admin/admins`, `POST /api/admin/admins` (add by email), `PATCH /api/admin/admins/{id}` (enable/disable). All `require_admin`, audited.
- Modify: `backend/db/users.py` — add `remove_admin_allowlist(email)` / `set_admin_enabled(email, enabled)` (the remove/disable functions that don't exist today).
- Create: `backend/app/routers/admin_audit_log.py` — `GET /api/admin/audit-log?since=&actor=&event=` over `audit_logs` (paginated, admin-only).
- Register both routers in both apps.
- Create: `frontend/src/pages/admin/AdminAdminsPage.tsx`, `AdminAuditLogPage.tsx` + routes + sidebar entries.
- Test: `backend/tests/test_admin_lifecycle.py`, `test_admin_audit_log_api.py`, FE tests.

**Interfaces:**
- Consumes: `db.add_admin_allowlist`, new `set_admin_enabled`/`remove_admin_allowlist`, `is_admin_allowlisted`, `record_admin_event`, `audit_logs`.

- [ ] **Step 1: Failing test (lifecycle)** — `POST /admins {email}` adds an allowlist row (enabled) + audit; `PATCH .../{id} {enabled:false}` disables it so `is_admin_allowlisted` returns false; non-admin → 401.
- [ ] **Step 2: Run — Expected FAIL.**
- [ ] **Step 3: Implement** `set_admin_enabled`/`remove_admin_allowlist` in `db/users.py` + the router (audited via `record_admin_event(event='admin_added'|'admin_disabled')`). Register in both apps. Guard: an admin cannot disable themselves (return 400).
- [ ] **Step 4: Failing test (audit viewer)** — `GET /api/admin/audit-log` returns recent rows with filters; admin-only.
- [ ] **Step 5: Implement** the audit-log read (select from `audit_logs` ordered desc, filter by actor/event/since, limit/offset).
- [ ] **Step 6: Run backend tests + guards — Expected PASS.**
- [ ] **Step 7: FE** — `AdminAdminsPage` (list + add + enable/disable) and `AdminAuditLogPage` (table + filters); routes guarded; sidebar entries.
- [ ] **Step 8: FE tests + tsc — Expected PASS.**
- [ ] **Step 9: Commit** (`feat(admin): admin lifecycle management + platform audit-log viewer`), branch `feat/admin-07-lifecycle-audit`, held PR.

---

## Sequencing & dependencies

`T1` (security + audit helper) → `T2` (independent) → `T3` (settings store) → `T4` (needs T3) → `T5` (needs T3) → `T6` (uses T1 audit helper) → `T7` (uses T1 audit helper). T2/T6/T7 are independent of T3–T5 and can run in parallel agents; T4 and T5 must follow T3. Recommended order matches the audit shortlist: **T1, T2, T4(+T3), T6, T7, T5**.

## Verification (whole plan)

1. Per task: `… pytest <task tests>` green locally; `cd frontend && npx tsc --noEmit` clean; `python scripts/check_router_registrations.py` + `python scripts/check_route_auth.py` exit 0 for tasks adding routers/routes.
2. Behavior-preservation: with no DB settings and unchanged env, `get_setting` returns the same values as before (T3 test) → gate/rerank/weights behavior unchanged until an admin acts.
3. Each new table migration carries the 3 RLS hard-gates and is committed-not-applied (listed in its PR).
4. All PRs **held open** until July 1 (CI + Render budgets); merge after budgets return and each PR's CI is green.
5. Defer to the live admin walkthrough (post-July-1) to confirm the new pages render and are reachable from the sidebar ≤2 clicks.

## Out of scope (follow-on plans)

D-BugRoutine (B-01, the in-app report→agent dispatch bridge) is the larger build and depends on T6's ticket model — its own plan. Full weights/threshold editing (C-02/C-03), beacons surfacing (F-03), IA cleanup of dead/duplicate surfaces (I-01/I-02), and blast-radius labeling (BR-01/03) are separate, lower-priority plans.
