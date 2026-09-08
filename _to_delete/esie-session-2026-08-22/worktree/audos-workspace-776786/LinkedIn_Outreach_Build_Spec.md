# ReloPass — LinkedIn Outreach Management System (Build Spec, codebase-aware)

**Status: BUILT.** Everything below is implemented in this workspace as of 2026-07-14. This document is the system of record for the feature — use it as the reference (or as a Claude Code prompt) for any future extension. Every proposed table/file maps to what actually exists; do not rebuild or duplicate.

**What it is:** an admin-only CRM-lite for founder-managed LinkedIn prospect outreach. Drafting + tracking ONLY — there is **no LinkedIn API integration and no automated sending** (not permitted by LinkedIn). The founder drafts in-app, copies, and pastes into LinkedIn manually.

---

## 1. Contacts database — WorkspaceDB table `outreach_contacts` (EXISTS)

Created via the platform's `workspace_db_create_table` (the only supported DDL path — never CREATE TABLE via raw SQL). Standard columns `id`, `session_id`, `created_at`, `updated_at` are auto-added by the platform.

| Column | Type | Notes |
|---|---|---|
| `full_name` | text NOT NULL | Prospect's full name |
| `company` | text | Company name |
| `job_title` | text | e.g. HR Generalist, People Ops Manager |
| `linkedin_url` | text | Profile URL (rendered as an outbound link) |
| `status` | text NOT NULL, default `'prospected'` | Enum: `prospected` \| `messaged` \| `awaiting_reply` \| `replied` \| `converted` \| `no_response` |
| `first_message_sent_at` | date | Set by "Mark as messaged" (first time only) |
| `last_activity_at` | timestamp | Touched on every action/status change |
| `notes` | text | Free text; logged replies are appended with a `[Reply logged YYYY-MM-DD]` stamp |
| `follow_up_reminder_sent` | boolean, default false | Set by "Mark follow-up sent" |
| `reply_summary` | text | AI one-line summary from "Summarise & next step" |
| `next_action` | text | AI-suggested next action |

**Data access:** exclusively via the auto-injected WorkspaceDB SDK — `useWorkspaceDB('outreach_contacts', { shared: true, … })` for reads and `window.__workspaceDb.from('outreach_contacts', { shared: true })` for writes. `shared: true` is required so founder-entered and MCP-seeded rows (session_id = NULL) are all visible.

---

## 2. Admin "Outreach" app (EXISTS)

### Files

| File | Role |
|---|---|
| `apps/Outreach/App.tsx` | The full admin app (list + detail + actions). Default export `Outreach`. |
| `apps/Outreach/templates.ts` | Hardcoded message templates, status enum/labels, `draftFirstOutreach()`, `draftFollowUp()`, `daysSince()`, `isFollowUpDue()` helpers. |
| `config.json` | App registered as `{ id: "outreach", icon: "Send", component: "apps/Outreach/App.tsx", allowedRoles: ["admin", "owner", "founder"] }`. |
| `Desktop.tsx` | Additive changes only: `Send` icon imported + added to `baseIconMap`; dock/launcher/mobile app lists now render `visibleApps = config.apps.filter(app => checkRoleAccess(app.allowedRoles))`. |
| `agent/customer-prompt.md` | Section "6. Outreach — INTERNAL, founder-facing" so the in-space agent never pitches it to HR customers. |

### Admin gating (two layers)
1. **Shell:** `Desktop.tsx` hides any app with `allowedRoles` from sessions lacking those roles, using the existing `checkRoleAccess` from `SpaceRuntimeContext` (entrepreneur mode always passes).
2. **In-app:** `Outreach()` renders an "Admin only" lock screen unless `mode === 'entrepreneur' || checkRoleAccess(['admin','owner','founder'])` — covers deep links (`#outreach`).

### Contacts list view
- Table: name, company, title, status pill, last activity date; search across name/company/title.
- Filter chips: All, **Follow up due (n)**, and each of the six statuses.
- Metrics strip: Prospects / Messaged / Awaiting reply / Replied / Converted / Follow-ups due.
- "Add contact" form with all fields (name required; optional company, title, LinkedIn URL, status, first-message date, notes).
- Follow-up-due rows get an **amber highlight + "Follow up due" badge** and sort to the top.

### Contact detail / action panel
- Full profile info incl. LinkedIn link, first-message date (with days-ago), last activity.
- **Draft outreach message** — fills the editable textarea from the first-outreach template, personalised with first name + company. **Copy message** button copies to clipboard.
- **Draft follow-up** — fills the textarea from the follow-up template, with the real day count substituted for "[X days ago]".
- **Mark as messaged** — status → `messaged`, sets `first_message_sent_at` (today, first time only).
- **Log reply received** — opens a paste box; saving sets status → `replied` and appends the reply to `notes`.
- **Summarise & next step** — sends the pasted reply to the platform OpenAI proxy (`POST /proxy/openai/v1/chat/completions`, `gpt-4o-mini`, JSON-only response) and stores `{reply_summary, next_action}` (e.g. "Schedule a 20-min call", "Send product link", "Not interested — archive"). Rendered as a "Reply digest" card.
- **Mark as converted** — status → `converted`.
- **Mark follow-up sent** — sets `follow_up_reminder_sent = true`, status → `awaiting_reply`.
- Manual status override select + editable notes with explicit save.
- Every action touches `last_activity_at`.

### Follow-up logic (deterministic, in `templates.ts`)
```
isFollowUpDue(c) =
  (c.status === 'messaged' || c.status === 'awaiting_reply')
  && !c.follow_up_reminder_sent
  && daysSince(c.first_message_sent_at) >= 10
```
Due contacts are flagged in the table (amber row + badge), counted in the metrics strip, filterable, and get an explanatory banner in the detail panel.

---

## 3. Message templates (hardcoded defaults in `apps/Outreach/templates.ts`; founder edits per-draft in the textarea)

**First outreach** (`draftFirstOutreach(fullName, company)` — `[Name]` → first name, `[Company]` → company or "your company"):

> Hi [Name], I'm building ReloPass — a relocation operating layer specifically for HR generalists at companies like [Company] who are managing international employee moves without a specialist team. We've started with the 5 corridors, and the core product flags the non-obvious requirements before they become missed deadlines. Would love to get 15 minutes with you to understand whether this is something you've run into.
> Happy to work around your schedule.

**10-day follow-up** (`draftFollowUp(fullName, daysAgo)` — `[X days ago]` → computed from `first_message_sent_at`):

> Hi [Name], just circling back on my note from [X days ago]. No pressure at all — I know timing matters. If international relocation compliance isn't a current pain point, completely understood. If it is, I'd still love a quick chat.
> Either way, thanks for your time.

---

## Technical notes / constraints honoured
- Internal admin tool only — hidden from customers at both the shell and app layer; no public-facing UI.
- Uses the existing design system: `lib/colors.ts` `tw.*` helpers and `--space-*` CSS variables throughout (same patterns as `apps/case-command/App.tsx` and `apps/TasksDB/App.tsx`).
- All data in WorkspaceDB (`outreach_contacts`); no external SDKs; AI summarisation via the platform OpenAI proxy only.
- No LinkedIn API, no automation — copy-to-clipboard + manual paste, stated explicitly in the UI.
