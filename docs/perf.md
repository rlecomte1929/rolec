# Performance instrumentation (frontend & backend)

This document describes the lightweight performance instrumentation added to ReloPass.

It is designed for **local / Render debugging** and avoids:

- DB schema changes
- External telemetry vendors
- Logging of PII (no tokens, emails, or payload bodies)

---

## Enabling the frontend perf panel

Set the following env var for the frontend build:

- `VITE_PERF_DEBUG=1`

In development you can add it to `frontend/.env.development`. In production, use the Render dashboard env var configuration for the static site.

When enabled, a small **Perf Interactions** panel appears in the bottom-right corner of the app. It shows:

- The last 10 interactions (e.g. `HR_ASSIGN_CLICK`)
- `click_to_render_ms` for each interaction
- Number of associated requests (based on `X-Request-ID`)

---

## Frontend instrumentation

### Request wrapper

All HTTP calls made through:

- `axios` instance in `frontend/src/api/client.ts`
- `apiGet/apiPost/apiPatch` helpers in `frontend/src/api/client.ts`

now:

- Attach a **`X-Request-ID`** header to every call
  - If the call happens during an active interaction, it reuses the interaction id
  - Otherwise a new UUID is generated
- Measure timings based on `performance.now()`:
  - `durationHeadersMs` – time until the response is available
  - `durationBodyMs` – time until the body is parsed (for `fetch`-based helpers)
- Log a structured console line:

  ```text
  [perf] req <request_id> <METHOD> <PATH> status=<status> ok=<bool> headers_ms=<...> body_ms=<...>
  ```

- Store the last 200 request entries in an in-memory ring buffer (for the debug panel)

### Interaction timing (click → UI render)

The module `frontend/src/perf/perf.ts` provides:

- `startInteraction(name: string)` → `{ id, name, t0 }`
- `endInteraction(handle)` → measures `click_to_render_ms` using `requestAnimationFrame`
- `recordRequestPerf(...)` → associates request logs by `requestId`

Example usage (HR assign button in `HrDashboard`):

```ts
const interaction = startInteraction('HR_ASSIGN_CLICK');
try {
  const response = await hrAPI.assignCase(caseId, employeeIdentifier.trim());
  // ... update state ...
} finally {
  void endInteraction(interaction);
}
```

`endInteraction`:

- Awaits the next paint via `requestAnimationFrame`
- Computes `click_to_render_ms`
- Counts the number of requests with `requestId === interaction.id`
- Logs:

```text
[perf] interaction HR_ASSIGN_CLICK id=<id> click_to_render_ms=<...> requests=<count>
```

These interactions are shown in the Perf panel when `VITE_PERF_DEBUG=1`.

---

## Backend instrumentation (FastAPI)

### Request middleware

A global `@app.middleware("http")`:

- Extracts `X-Request-ID` from incoming headers, or generates a UUID if missing
- Stores it on `request.state.request_id`
- Mirrors it back to the client via the **`X-Request-ID` response header**
- Measures total handler duration using `time.perf_counter()`
- Logs a structured line:

```text
request_id=<id> method=<method> path=<path> status=<status> dur_ms=<...> user_id=<user_id_or_None>
```

`user_id` is populated by `get_current_user` via `request.state.user_id` (no emails, no tokens).

### Per-endpoint spans

The helper `timed(span: str, request_id: Optional[str])` in `backend/main.py` is a context manager:

```python
with timed("db.list_assignments_for_hr", request.state.request_id):
    assignments = db.list_assignments_for_hr(effective["id"], request_id=request.state.request_id)
```

It logs:

```text
request_id=<id> span=<span> dur_ms=<...>
```

This is applied to a few critical paths:

- HR assignments list (`/api/hr/assignments`)
- HR assign case (`/api/hr/cases/{case_id}/assign`)

---

## DB query timing (database.py)

`backend/database.py` now includes an internal helper:

```python
def _exec(self, conn, sql: str, params: Dict[str, Any], op_name: str, request_id: Optional[str] = None):
    start = time.perf_counter()
    result = conn.execute(text(sql), params)
    dur_ms = (time.perf_counter() - start) * 1000
    if request_id:
        log.info("request_id=%s db_op=%s dur_ms=%.2f", request_id, op_name, dur_ms)
    else:
        log.info("db_op=%s dur_ms=%.2f", op_name, dur_ms)
    return result
```

Selected high-traffic methods now route through `_exec` and accept an optional `request_id`:

- `create_assignment(...)`
- `update_assignment_status(...)`
- `attach_employee_to_assignment(...)`
- `set_assignment_submitted(...)`
- `set_assignment_decision(...)`
- `get_assignment_by_id(...)`
- `get_assignment_by_case_id(...)`
- `get_assignment_for_employee(...)`
- `get_unassigned_assignment_by_identifier(...)`
- `list_assignments_for_hr(...)`
- `list_notifications(...)`
- `count_unread_notifications(...)`

API endpoints pass `request.state.request_id` where available, so DB logs are correlated with the same request id used by:

- Frontend `X-Request-ID` header
- Middleware request logs
- Span logs from `timed(...)`

No query parameters or payloads are logged.

---

## How to test end-to-end

1. **Enable frontend perf debug**

   - Set `VITE_PERF_DEBUG=1` in the frontend env.
   - Run the frontend (or deploy) so the Perf panel appears.

2. **Trigger an HR assign interaction**

   - Navigate to the HR dashboard.
   - Fill in the assign case form.
   - Click the **Assign** button.

3. **Observe frontend logs and panel**

   - Open the browser console:
     - You should see lines like:

       ```text
       [perf] interaction HR_ASSIGN_CLICK id=<id> click_to_render_ms=123.4 requests=1
       [perf] req <id> POST /api/hr/cases/<case_id>/assign status=200 ok=true headers_ms=45.6 body_ms=52.3
       ```

   - In the Perf panel (bottom-right), the latest interaction entry should match:
     - `name = HR_ASSIGN_CLICK`
     - `click_to_render_ms` shown
     - `requests = 1` (or more, depending on the flow)

4. **Check backend logs on Render**

   - In the Render dashboard logs for the backend service:
     - Search for `request_id=<id>` (using the same id from the frontend logs).
     - You should see:

       ```text
       request_id=<id> method=POST path=/api/hr/cases/<case_id>/assign status=200 dur_ms=...
       request_id=<id> db_op=create_assignment dur_ms=...
       request_id=<id> span=db.create_assignment dur_ms=...
       ```

   - For HR dashboard loads (`/api/hr/assignments`) you should see:

       ```text
       request_id=<id> method=GET path=/api/hr/assignments status=200 dur_ms=...
       request_id=<id> db_op=list_assignments_for_hr dur_ms=...
       request_id=<id> span=db.list_assignments_for_hr dur_ms=...
       ```

This gives you an end-to-end view of:

- **Click → UI update** latency (frontend)
- **Per-request network timings** (frontend, `headers_ms` / `body_ms`)
- **Backend handler duration** (FastAPI middleware)
- **Per-DB query durations** tagged by `db_op` and correlated via `request_id`.

