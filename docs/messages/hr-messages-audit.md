# HR Messages — data model & audit

## Current entity model (messages)

- **Primary store**: `messages` table (`id`, `assignment_id`, `hr_user_id`, `employee_identifier`, `subject`, `body`, `status`, `created_at`, plus delivery fields `delivered_at`, `read_at`, `dismissed_at`, `recipient_user_id`, `sender_user_id`).
- **Each row** is a **single message** (not a thread). There is **no separate `thread_id`**: the **canonical thread key is `assignment_id`** (one case assignment / employee case thread).
- **Links**:
  - **Case / thread**: `assignment_id` → `case_assignments.id`.
  - **Employee**: via assignment `employee_user_id` and/or `employee_identifier` on the message row; profile data from `profiles` joined on `employee_user_id`.
  - **HR**: `hr_user_id` on the message (historical sender for HR-originated rows); assignment `hr_user_id` for case ownership.
  - **Company**: `relocation_cases.company_id` and/or `hr_users.company_id` through `case_assignments` (same pattern as `assignment_belongs_to_company`).

## Previous rendering model (pain points)

- **API**: `GET /api/hr/messages` returned **every message row** where `messages.hr_user_id = :hr` — **not** company-scoped and **not** aligned with “all threads I can see as HR”.
- **Frontend**: `buildConversationsFromMessages` **already grouped by `assignment_id`**, so the **UI list was one row per conversation** in `ConversationList`, but:
  - The **payload was still all messages**, so the client did redundant work and held full bodies for every thread.
  - **First conversation auto-opened** on desktop, which fought the desired “summary first, open on click” pattern.
  - **Unread** in the client builder was effectively **not wired** (placeholder `0` in grouped view).
- **Clutter perception**: repeated content often came from **many messages in one mental “thread”** if users mentally compared to email; structurally the list was per-assignment, but **loading all messages at once** made the page feel heavy and noisy.

## Recommended folded conversation grouping key

- **Canonical key**: **`assignment_id`** (one folded row per assignment / case thread).
- **Do not merge** across assignments by email alone — the same person could appear on **different cases**; keeping **`assignment_id`** prevents cross-case merging.

## Schema / backend adjustments (for proper grouping & archive)

Implemented (minimal):

1. **`message_conversation_prefs`** (`user_id`, `assignment_id`, `archived_at`) — **per HR user**, soft archive for the **list** (non-destructive to `messages`).
2. **`GET /api/hr/messages/conversations`** — **company-scoped** summaries (mirrors `_hr_can_access_assignment` / assignment–company join logic in SQL).
3. **`GET /api/hr/messages/threads/{assignment_id}`** — full thread for one assignment after authorization.
4. **`POST /api/hr/messages/conversations/archive`** — set/clear archive preference; **blocked under impersonation** (`_deny_if_impersonating`), same as other mutating HR actions.

Legacy **`GET /api/hr/messages`** remains for compatibility but should be considered **deprecated** for the HR UI.

## Security notes

- **Thread detail** and **archive** must use **`_hr_can_access_assignment`** (or equivalent SQL visibility) so **HR only sees assignments for their company / ownership**, not merely `messages.hr_user_id` matching.
- **Grouping query** applies the same visibility rules so **no cross-company rows** appear in the summary list.
