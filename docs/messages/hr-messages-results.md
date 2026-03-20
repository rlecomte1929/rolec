# HR Messages — implementation results

## Old vs new behavior

| Area | Before | After |
|------|--------|--------|
| HR list data | `GET /api/hr/messages` (all rows where `hr_user_id` = user) | `GET /api/hr/messages/conversations` (one summary row per `assignment_id`, company-safe) |
| Initial payload | Full message bodies for all threads | **Summaries only** (preview, counts, metadata) |
| Open thread | First thread auto-selected on desktop | **No auto-select**; open via row (still supports `?assignmentId=` deep link) |
| Thread body | Already in memory | **Lazy** `GET /api/hr/messages/threads/{assignment_id}` |
| Archive | N/A | **Per-user soft archive** via `message_conversation_prefs` + filter |

## Grouping key

- **Folded list**: **one row per `assignment_id`** (case assignment thread).
- **Participant label**: employee display name from profile / assignment name fields; **case id** shown as a small tag when present.

## Edit mode actions

- **Edit** toggles selection checkboxes on each row.
- **Archive selected**: `POST /api/hr/messages/conversations/archive` with `{ assignment_ids, archived: true }` — sets `archived_at` (hidden from **Active** filter).
- **Restore selected**: same endpoint with `archived: false` — **deletes** the preference row (conversation returns to active list). **No hard delete** of `messages`.
- **“Remove from view”**: not implemented as a separate destructive action; **archive** is the supported non-destructive hide.

## Archive semantics

- **Active** filter: `archived_at IS NULL` (including rows with **no** preference row).
- **Archived** filter: `archived_at IS NOT NULL`.
- **All**: no archive predicate.
- Data in `messages` is **unchanged**.

## Filters

- **Search** (debounced ~320ms): name, email, employee identifier, `case_id` / `canonical_case_id` — applied **server-side** on the **grouped** list.
- **Archive**: Active / Archived / All.
- **Unread only**: threads where **unread for current user** &gt; 0 (`recipient_user_id` = viewer, `read_at` and `dismissed_at` null).
- **Sort**: latest message first (server).

## Loading model

- **On page entry (HR)**: conversation **summaries** only.
- **On thread open**: **full** message list for that `assignment_id` (until loaded, UI shows “Loading conversation…”).
- **Employee** path: unchanged (`employeeAPI.listMessages()` + existing grouping).

## Backend / schema changes

- **SQLite** (local): `message_conversation_prefs` created in `database.py` init.
- **Supabase**: `supabase/migrations/20260320000000_message_conversation_prefs.sql` + RLS (own rows only for `authenticated`).
- **New routes** in `backend/main.py**: see audit doc.
- **`POST /api/messages/mark-conversation-read`**: now resolves the assignment and enforces **employee = assignment.employee_user_id** or **HR/admin via `_hr_can_access_assignment`** before updating read state (no cross-assignment read marking).

## Manual verification checklist

- [ ] HR **Messages** shows **one row per case thread** (not one per message).
- [ ] **Clicking** a row opens the thread; **message bodies** appear after load, not all at once on first paint.
- [ ] **Edit** shows checkboxes; **Archive selected** hides threads from **Active**; they appear under **Archived**.
- [ ] **Restore selected** brings threads back to **Active**.
- [ ] **Search** narrows the list; **Unread only** filters correctly.
- [ ] **Company scoping**: HR user does not see threads for other companies’ assignments (spot-check with two companies).
- [ ] **Deep link** `?assignmentId=` selects that thread when present in the list.
- [ ] **Impersonation**: archive returns **403** (read-only), consistent with other HR mutations.
