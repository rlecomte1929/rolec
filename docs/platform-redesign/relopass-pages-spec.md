# ReloPass Pages Specification
**Version:** 1.0 — May 2026  
**Status:** Foundation spec — feeds T01–T24 redesign tasks  
**Scope:** App shell + all 24 screens (S0–S10 and supporting views)

---

## Design intent

Every relocation case is **visible, compliant, and on-time**.

The employee should feel **zero friction** — the system answers before they ask, pre-fills what it already knows, and surfaces the single next action they need to take.

HR is the **support function and facilitator**, not the bottleneck. HR gets the operational clarity to act, not the administrative burden of chasing.

The platform is **infrastructure**, not a collaboration tool. Every screen reinforces structure, status, and confidence — never busyness or noise.

---

## Conventions used in this spec

| Symbol | Meaning |
|--------|---------|
| `[token]` | CSS custom property from `relopass-design-tokens.json` |
| `[icon: X]` | Lucide-react icon named X |
| `→` | Navigates to |
| `≥ hr` | Visible to plan_tier hr or admin only |
| `≥ admin` | Visible to plan_tier admin only |
| `employee only` | Visible to role: employee only |
| `real-time` | Updates via Supabase Realtime channel |

All spacing uses the 8px grid (`[spacing-2]` = 8px, `[spacing-4]` = 16px etc.).  
All colours reference tokens, never raw hex.

---

## App Shell

The shell is always present. It renders behind every authenticated screen.

### Sidebar

**Layout**  
- Fixed left edge, full viewport height  
- Expanded width: `[layout-sidebar_w_expanded]` (232px)  
- Collapsed width: `[layout-sidebar_w_collapsed]` (58px)  
- Collapse toggle: icon-only button at bottom of sidebar, persists state in `localStorage["rp-sidebar"]`
- Background: `[color-surface-sidebar]`  
- Right border: `[color-border-subtle]` 1px solid

**Sections (top to bottom)**

1. **Logo lockup** — ReloPass wordmark (expanded) or "R" glyph (collapsed). Links → `/dashboard` or `/my-move` depending on role.

2. **Primary nav** — vertical list of `NavItem` entries. Rendered from `nav_items` in design tokens. Items hidden when `plan_tier` doesn't match `visible_to`.

3. **Section dividers** — 1px `[color-border-subtle]` line + optional section label (hidden when collapsed).

4. **AI Panel toggle** — icon button `[icon: Sparkles]`, colour `[color-accent-teal]`. Expands/collapses AIPanel. Has a pulsing dot indicator when AI has a suggestion for the current view.

5. **User row** (bottom) — avatar + name + role pill (expanded) or avatar only (collapsed). Clicking → `/profile`.

**Nav item anatomy (expanded)**  
`[icon]` · `[label]` · `[badge]` (right-aligned)

**Nav item anatomy (collapsed)**  
`[icon]` only — tooltip on hover shows label.

**Active state**  
Background `[color-surface-sidebar-active]`, left accent bar `[color-accent-teal]` 3px.

**Badge types**  
- `count`: number pill, background `[pill-danger-bg]` when > 0  
- `dot`: solid circle `[color-accent-amber]`  
- `status`: `[color-accent-teal]` dot (new activity)

**Nav structure by role**

*HR / Admin:*
- Overview section: Dashboard, Cases
- Operations section: Vendors, Analytics (≥ admin)
- Settings section: Policy, Team, Organisation (≥ admin)

*Employee:*
- My Move (landing)
- My Journey (roadmap)
- My Documents
- My Forms
- My Messages

---

### TopBar

**Layout**  
- Fixed top, `z-index: [z-topbar]`  
- Height: `[layout-topbar_h]` (56px)  
- Left edge: matches sidebar width (animates with collapse)  
- Background: `[color-surface-topbar]`  
- Bottom border: `[color-border-subtle]` 1px

**Left region**  
Breadcrumb trail. Max 3 levels. Separator: `[icon: ChevronRight]` `[color-text-tertiary]`.  
Last item: current page name, `[color-text-primary]` semibold.

**Right region (left to right)**  
1. Search trigger — `[icon: Search]` — opens command palette (`⌘K`)  
2. Notifications bell `[icon: Bell]` — badge with unread count → opens slide-over  
3. Theme toggle `[icon: Sun]` / `[icon: Moon]`  
4. Avatar + name (desktop only)

---

### AI Panel

**Layout**  
- Fixed right drawer, full viewport height  
- Width: `[layout-ai_panel_w]` (360px)  
- Background: `[color-surface-ai-panel]`  
- Slides in from right; main content area shrinks to accommodate  
- Left border: `[color-border-subtle]`

**Header**  
- `[icon: Sparkles]` + "AI Assistant" label  
- Close button `[icon: X]`  
- Model label: "claude-haiku-4-5-20251001" or "claude-sonnet-4-6" — small tag, muted

**Context strip**  
- 1-line contextual hint tied to current route (from `route_ai_context` token)  
- Example on `/cases/[id]/roadmap`: *"I can explain any step, suggest what to tackle next, or draft a message to a vendor."*  
- Background: `[color-surface-ai-context-strip]`

**Suggested prompts**  
- 2–3 chips with pre-seeded questions for the current view  
- Clicking a chip inserts it into the input  
- Chips disappear after the first user message

**Message list**  
- Scrollable, newest at bottom  
- User messages: right-aligned, background `[color-surface-ai-user-bubble]`  
- AI messages: left-aligned, background `[color-surface-ai-assistant-bubble]`  
- Streaming: animated typing indicator, text streams in character by character  
- AI messages can contain suggested action chips (e.g. "Update step status", "Open thread")

**Input area**  
- Textarea, auto-grows to max 4 lines  
- Send button `[icon: ArrowUp]`, disabled when empty  
- Pressing `Enter` sends; `Shift+Enter` inserts newline  
- "Clear conversation" link, muted, at bottom of panel

---

### Command Palette (`⌘K`)

Full-screen overlay with search input. Sections:

1. **Recent** — last 5 navigated pages  
2. **Cases** — live search over case employee names and IDs  
3. **Actions** — contextual quick actions for current view  
4. **Navigation** — all nav items

`Esc` closes. `↑↓` navigate. `Enter` activates.

---

## Screens

---

### S0 — Sign In / Sign Up / Reset Password

**Route:** `/sign-in`, `/sign-up`, `/reset-password`

**Layout**  
Two-column. Left: full-height brand panel. Right: form.  

**Left panel (brand)**  
- Background: `[color-surface-brand-panel]` (deep navy, matches globe canvas background `#0A0E1A`)  
- GlobeCanvas component centred, 60fps animation, 7 corridor arcs  
- Overlay: ReloPass wordmark (white) + tagline "Every relocation case. Visible, compliant, on-time."  
- Arc colours: teal `#1DBFA2`, blue `#4A9AE8`, amber `#EFA827`  
- Canvas is decorative, `aria-hidden="true"`

**Right panel (form)**  
- Background: `[color-surface-base]`  
- Max width 400px, vertically centred  
- Top: "ReloPass" text link back to marketing site

*Sign In form fields:*  
- Email — `type="email"` `autocomplete="email"`  
- Password — `type="password"` `autocomplete="current-password"`  
- "Forgot password?" link → `/reset-password`  
- CTA: "Sign in" (primary button, full width)  
- Divider: "or"  
- "Create an account" link → `/sign-up`

*Sign Up form fields:*  
- Full name  
- Work email  
- Password (min 8 chars, 1 number, 1 special)  
- Password strength indicator (3 segments: weak / ok / strong)  
- Company slug (optional — for joining existing org) or "Create new organisation" flow  
- Invite token auto-fills if present in URL `?invite=…`  
- CTA: "Create account" (primary, full width)  
- By signing up: link to Privacy Policy and Terms

*Reset Password form:*  
- Email field  
- CTA: "Send reset link"  
- Confirmation state: green success banner, "Check your email"

**Validation**  
- Inline, on blur  
- Error state: field border `[color-status-error]`, error text below field `[color-text-danger]`

**Loading state**  
CTA button shows spinner, fields disabled.

---

### S1 — HR Dashboard

**Route:** `/dashboard`  
**Visible to:** `≥ hr`

**Intent**  
The single operational view where HR sees everything that needs attention right now. Not a metrics page — an action trigger. HR should be able to scan this in 30 seconds and know exactly where to focus.

**Layout**  
Single column. Topbar breadcrumb: "Dashboard".

**Section 1 — Attention queue (above the fold)**  
Header: "Needs your attention" + count badge.  
Horizontally scrollable card row. Each card:

```
[CaseAttentionCard]
─────────────────────────────
Employee name + avatar
Corridor: 🇫🇷 FR → 🇩🇪 DE
Stage pill
Issue type: "Blocked step" / "Overdue document" / "Exception pending"
Issue description (1 line)
[View case →] button
─────────────────────────────
```

Empty state: `[icon: CheckCircle]` + "Nothing needs your attention right now."

**Section 2 — Active cases snapshot**  
Mini table. Columns: Employee, Corridor, Stage, Progress, Last updated.  
Row click → `S3 Case Detail`.  
"View all cases →" link → `S2`.

**Section 3 — GlobeCanvas** (if `globe_canvas_enabled`)  
Full-width canvas, height 320px. Animated corridor arcs for all active cases of this company.  
`real-time`: arc count updates as cases change status.  
Below canvas: row of corridor count chips (e.g. "FR→DE · 4 cases").

**Section 4 — Recent activity feed**  
Up to 10 most recent events across all cases (status changes, documents approved, messages, exceptions decided).  
Each item: avatar + action description + case link + relative timestamp.  
`real-time`: new items prepend with slide-in animation.

**Section 5 — Open exceptions** (`≥ admin`)  
List of pending policy exceptions. Each row: employee name, benefit requested, amount, justification excerpt, "Review" button → `S3 Policy tab`.  
Empty state: "No pending exceptions."

---

### S2 — Case Management (HR List)

**Route:** `/cases`  
**Visible to:** `≥ hr`

**Intent**  
The full operational case table. Every open relocation managed by this HR team. Designed for efficient triage across many cases simultaneously.

**Layout**  
Full-width table with fixed header. TopBar breadcrumb: "Cases".

**Toolbar (above table)**  
- Left: "Cases" heading + total count badge  
- Right: Search input `[icon: Search]`, Filter button `[icon: SlidersHorizontal]`, Column picker `[icon: Columns]`, "New case" button `[icon: Plus]`

**Filter panel** (slides in from right when Filter clicked)  
Filters:
- Status (multi-select chips): Draft / Active / On Hold / Completed / Cancelled  
- Stage (multi-select chips)  
- Corridor (searchable multi-select)  
- HR Owner (searchable select, self-assignee shortcut)  
- Policy Tier (multi-select)  
- Has blocked items (toggle)  
- Date range (target start date)

Active filter count shown on Filter button badge.  
"Clear all" link.

**Table columns (default visible)**  
Employee | Corridor | Stage | Progress | Status | HR Owner | Target Start | Blocked | Updated

**Table columns (optional, shown via column picker)**  
Policy Tier | Days Until Move | Unread Messages | Open Exceptions

**Table behaviour**  
- `MovableColumns` — drag handle `[icon: GripVertical]` on column header  
- Column order and visibility persisted in `localStorage["rp-columns-cases"]`  
- Column header click → sort (asc/desc toggle, indicator arrow)  
- Row click → `S3 Case Detail`  
- Row hover → subtle background `[color-surface-row-hover]`

**Progress column**  
Mini progress bar (80px wide). Background `[color-bg-progress-track]`, fill `[color-accent-teal]`.  
Percentage label right of bar.

**Blocked column**  
Count badge. `[pill-danger-bg]` when > 0.

**Empty state**  
`[icon: Inbox]` + "No cases match your filters." + "Clear filters" link.

**Pagination**  
Per-page: 25 / 50 / 100. Next/Prev buttons. "Showing X–Y of Z cases."

**"New case" flow**  
Modal slide-over:
```
Create new case
───────────────
Employee (searchable select from profiles)
Origin country (searchable select, flag emoji prefix)
Destination country (searchable select, flag emoji prefix)
Target start date (date picker)
Policy tier (select, optional)
HR Owner (select, defaults to self)
[Cancel] [Create case →]
```
On submit: creates case with status `draft`, navigates to `S3 → Intake tab`.

---

### S3 — Case Detail

**Route:** `/cases/:id`  
**Visible to:** `≥ hr`

**Intent**  
The full operational record for one relocation case. HR has everything in one place — roadmap, documents, forms, policy, messages. Tab navigation between domains; all tabs share the same case context header.

**Case Header** (sticky below TopBar)  
```
[Employee avatar (48px)]  [Full name]  [Role / Title]
[Corridor flag + text: 🇫🇷 Paris, France  →  🇩🇪 Berlin, Germany]
[Stage pill]  [Status pill]  [Progress bar 200px]  [x% complete]
[HR Owner: avatar + name]  [Policy Tier: name]  [Target date: DD MMM YYYY]
[Action buttons: Edit  ·  Hold  ·  Close case  ·  ...]
```

Progress bar: `[color-accent-teal]` fill, background `[color-bg-progress-track]`.  
"Edit" → opens case edit slide-over.  
"Hold" → confirms then sets status `on_hold`.  
"Close case" → confirmation modal, records `actual_close_date`.

**Tab navigation**  
Tabs: Overview · Roadmap · Documents · Forms · Policy · Messages  
Active tab: bottom border `[color-accent-teal]` 2px, label `[color-text-primary]`.

---

#### S3-A — Overview tab

**Left column (2/3 width)**

*Next actions panel*  
Header: "Next actions" + count.  
Cards stacked vertically. Each card:
```
[icon] [type pill: Step / Document / Form]
[Title]
[Description, 2 lines max]
Owner: [avatar + name]  Due: [relative date]  [urgency dot]
[Mark complete / Upload / Fill form] button
```
Empty state: `[icon: PartyPopper]` "All caught up."

*Recent activity*  
Last 10 events on this case. Timestamp relative (e.g. "2 hours ago"). Full timestamp on hover.  
`real-time`: new events prepend.

**Right column (1/3 width)**

*Case summary card*  
- Case ID (monospace, copyable)  
- Created date  
- Employee name + email + phone  
- Origin address (from intake)  
- Destination address (if confirmed)

*Dependents*  
List: name, relationship, age. "Add dependent" link.

*Vendor panel*  
Active vendors on this case, each with service type and contact. "Add vendor" button → `S8 Vendor Directory`.

*Blockers*  
Count of blocked steps and overdue items, highlighted. Link to Roadmap tab filtered to blocked.

---

#### S3-B — Roadmap tab

**Intent**  
The full step-by-step plan for this relocation. HR can update step status, assign vendors, set due dates. Status reflects the employee's journey.

**Layout**  
Left: track list (1/4 width, sticky). Right: step detail (3/4 width).

**Track list**  
One row per track: `[icon]` + Track name + progress mini-bar + completed/total count.  
Active track: background `[color-surface-sidebar-active]`.

**Step list** (for selected track)  
Vertical timeline. Each step:

```
[status icon (colour-coded)]
[Step number]  [Title]  [Owner pill]  [Due date]
[Description, expandable]
[Vendor: name if assigned]
[Dependency note: "Waiting on: [step name]"]
[action row: Update status ▼  ·  Assign vendor  ·  Set due date  ·  Add note]
```

Status icon colours:
- `pending`: `[color-text-tertiary]`
- `in_progress`: `[color-accent-teal]`
- `awaiting_*`: `[color-accent-amber]`
- `blocked`: `[color-status-error]`
- `completed`: `[color-status-success]`
- `skipped`: `[color-text-muted]`

Blocked steps: left border `[color-status-error]` 3px, subtle error background.

**Update status dropdown**  
All StepStatus values. Selecting "completed" shows confirmation + optional completion note.

**Add note flow**  
Inline textarea, saves as step note + triggers activity event.

**AI step guidance** (when AIPanel is open)  
Clicking any step title sends the step context to AIPanelContext, pre-seeding "What does this step require?" prompt.

---

#### S3-C — Documents tab

**Intent**  
All document requirements for this case, their submission status, and uploaded files. Designed to eliminate email back-and-forth on document collection.

**Layout**  
Left: requirement list (grouped by category). Right: document detail / upload.

**Requirement list**  
Grouped by `RequirementCategory`. Group header: category label + count progress (e.g. "3/5 complete").

Each requirement row:
```
[DocStatus colour dot]  [Requirement name]
[category pill]  [mandatory badge if is_mandatory]  [due date]
```

Row click → selects requirement, loads document panel on right.

**Document panel (right)**  
When requirement selected:

```
[Requirement name] — [status pill]
[Instructions (expandable)]
[Template download link (if available)]

Uploaded documents:
[file icon]  [filename]  [upload date]  [status pill]  [actions: Preview · Download · Delete]

[Upload zone: drag-drop or click]
"Drag a file here or click to upload"
Accepts: PDF, JPEG, PNG, DOCX (max 25MB)
[OCR indicator: "This document will be scanned to pre-fill your forms"]
```

On upload: progress bar, then OCR runs in background. Toast on completion: "1 form auto-filled from this document."

**Rejection banner**  
When status = `rejected`: red banner with `rejection_reason`, "Re-upload" button.

**Expiry warning**  
When `expires_at` within 90 days: amber banner "This document expires in X days."

**Overall completion**  
Top of tab: `[X/Y required documents uploaded]` progress bar.  
Filter: All / Pending / Submitted / Approved / Rejected.

---

#### S3-D — Forms tab

**Intent**  
Smart forms that pre-fill from OCR and intake data. Employee fills forms once; the system re-uses what it already knows.

**Form list**  
Card grid. Each card:
```
[FormType icon]
[Form name]
[Status pill]
[Last updated: relative time]
[Auto-filled badge: "X fields pre-filled" (teal)]
[Open form →]
```

**Form editor** (full-page or slide-over)  
- Two-column layout for long forms: field groups on left, contextual help on right  
- Pre-filled fields: subtle teal left border + `[icon: Zap]` "Pre-filled from your passport" tooltip  
- Required fields: asterisk, validated on blur  
- Save draft: auto-saves every 30s, manual "Save draft" button  
- Submit: confirmation step showing summary of all values  
- Post-submit: status → `submitted`, form becomes read-only, timestamp shown

**Empty state**  
"No forms yet. Forms are generated automatically once the intake wizard is complete."

---

#### S3-E — Policy tab

**Intent**  
What this employee's policy tier entitles them to, and any exception requests. HR can approve/deny exceptions directly here.

**Layout**  
Left: policy summary. Right: exceptions.

**Policy summary**  
```
[Policy tier name] — [rank label]
[Description]

Benefits:
[benefit icon]  [benefit name]        [value]
[benefit icon]  [benefit name]        [value]
...
```

Each benefit rendered as a table row: icon, name, value formatted by `value_type` (€ amount / days / Yes-No / text).

**Exception requests**  
List of pending and decided exceptions for this case.  
Each exception:
```
[Benefit name]
Requested: [requested_value]  ·  Policy allows: [benefit_value]
Justification: [text, expandable]
[Approve] [Deny] buttons (≥ hr, when status = pending)
[Status pill when decided]  [Decision notes]
```

"Request exception" button (≥ hr) → opens slide-over form:
```
Benefit name (text or select from policy benefits)
Requested value
Justification (textarea, required)
[Submit request]
```

---

#### S3-F — Messages tab

**Intent**  
All threads related to this case. Replaces email chains with structured, case-contextualised communication. Every message is permanently linked to the case record.

**Left: thread list**  
One row per thread:
```
[context icon]  [subject or auto-generated summary]
[last message preview, 1 line]  [unread count badge]  [relative timestamp]
[participants: avatar stack]
```

Active thread: highlighted background.  
"New thread" button → opens create thread slide-over.

**Right: message view**  
```
[Thread subject]  [context pill: Step / Requirement / Vendor]  [Resolve thread button]

[message stream — chronological]
[Avatar] [Name] · [timestamp]
[message body]
[attachments if any: file card with name + size + download]

─────────────────
[Textarea: Reply...]
[Attach document icon]  [Send button]
```

System messages: centre-aligned, italic, `[color-text-tertiary]`.  
`real-time`: new messages append without page reload.  
Resolved threads: read-only, "Resolved" banner.

---

### S4 — Intake Wizard (Employee-facing, HR can view)

**Route:** `/cases/:id/intake`  
**Visible to:** employee (their own case), `≥ hr` (read-only view)

**Intent**  
The employee completes this once. The answers seed every requirement, roadmap step, form, and AI suggestion downstream. It must feel like a guided conversation, not a bureaucratic form — zero friction, maximum helpfulness.

**Design principles for this screen**  
- One step at a time — never show the whole form at once  
- Progress is always visible but never oppressive  
- Pre-fill everything possible from profile data  
- Save progress on every field change (auto-save, no "save draft" button needed)  
- Plain language — no legal or technical jargon  
- Estimated time shown upfront: "About 8 minutes"

**Layout**  
Centred, max-width 640px. No sidebar during wizard (full focus). Minimal topbar (logo + progress only).

**Progress header**  
Step X of 8 · `[step name]`  
Segmented progress bar: 8 segments, completed = `[color-accent-teal]`, current = active animation, future = `[color-bg-progress-track]`.

**Step structure**  
Each step:
```
[Step illustration or icon — context-appropriate]

[Question heading, large]
[Optional sub-text — plain language explanation of why we're asking]

[Field or multi-select or card choice group]

[Back]  [Continue →]
```

No "skip" option for mandatory steps. Optional steps show "(Optional)" in heading.

**Step 1 — Your family**  
Heading: "Who's moving with you?"  
Options (card grid, multi-select):  
- Just me  
- With my partner  
- With children  
- With my partner and children  
- Other family members

If partner selected: "Is your partner planning to work in [destination country]?" → yes/no  
If children: add children flow (number, ages — inline row adder, up to 6 children)

**Step 2 — Where you'll live**  
Heading: "What kind of home are you looking for?"  
- Apartment / House / Flexible  
- Minimum bedrooms: stepper (1–5+)  
- Monthly budget (optional): currency input, `[origin country currency]` default  
- Neighbourhood preferences: free text tag input  
- Do you have pets? yes/no  
- Any accessibility requirements? yes/no → text field if yes

**Step 3 — Short-term housing**  
Heading: "Do you need somewhere to stay when you first arrive?"  
- Yes, I'll need temporary housing / No, I have arrangements  
If yes:
- How long? stepper in weeks (1–12)  
- Preference: "Near work" / "Near chosen neighbourhood" / "No preference"  
- Serviced apartment OK? yes/no

**Step 4 — Your documents**  
Heading: "Tell us about your travel documents"  
- Passport nationalities (multi-select with search, flag emoji prefix)  
- Do you already have a work permit for [dest country]? yes/no  
- Current visa type (optional, text)  
- Visa expiry (optional, date picker)  
- Dual citizenship? yes/no

Info banner: "We'll use this to recommend the right visa pathway for your move."

**Step 5 — Moving your things**  
Heading: "What are you bringing?"  
- Estimated volume: "Minimal (1–5 m³)" / "Moderate (5–15 m³)" / "Full household (15 m³+)"  
- Do you have a vehicle? yes/no → how many to ship?  
- Any special items? (chips: Piano / Art / Wine / Pets / Fragile items)  
- Preferred move window: earliest / latest date pickers (optional)

**Step 6 — Finances & tax**  
Heading: "A few questions about your finances"  
- Will you need help setting up a bank account? yes/no  
- Do you need tax advice for this move? yes/no  
- Do you have a property to sell? yes/no  
- Do you have rental income in either country? yes/no  
- Do you need help with a home sale? yes/no

Info banner: "We'll connect you with a tax advisor if needed — at no extra cost."

**Step 7 — School search**  
*Conditionally shown if children_school_age = true*  
Heading: "Finding the right school for your children"  
- School type preference: chips (Public / Private / International / No preference)  
- Language of instruction preference: multi-select (searchable)  
- Any special educational needs? yes/no → text field if yes

**Step 8 — Language & settling in**  
Heading: "How are you feeling about the language?"  
- Destination language level: "None" / "Basic" / "Intermediate" / "Fluent"  
If not fluent: "Would you like language lessons arranged?" yes/no  
- Would you find a cultural orientation session useful? yes/no

**Completion screen**  
Heading: "You're all set."  
Sub-text: "We've set up your relocation plan. Your HR team has been notified and will be in touch shortly."

Summary panel:
- Corridor confirmed  
- X requirements generated  
- X steps in your roadmap  
- Target start date  

CTA: "Go to My Move →" → S5

---

### S5 — Employee: My Move (Dashboard)

**Route:** `/my-move`  
**Visible to:** `employee only`

**Intent**  
The employee's home base for their relocation. They should land here and immediately know: where am I in the process, what do I need to do next, and who is supporting me. One clear next action, always.

**Layout**  
Single column, max-width 800px, centred. Topbar breadcrumb: "My Move".

**Hero panel**  
```
👋 Welcome, [First name].
Your move to [Destination city, Country flag] is [X days away / underway / completed].

[Overall progress bar — full width, labelled]
[X% complete · Stage: [stage label]]
```

Background: subtle gradient, `[color-surface-hero]`.

**Next action card** (most prominent element on page)  
```
───────────────────────────────────────────────
YOUR NEXT STEP
[urgency indicator — colour dot]
[icon]  [Action title]
[Action description — 2 lines, plain language]
[Due: [relative date] if applicable]
[Primary action button: "Do this now →"]
───────────────────────────────────────────────
```

If no next action: success state — "Nothing to do right now. Your HR team is taking care of the next steps."

**Track progress section**  
Heading: "Your relocation at a glance"  
Card row (horizontal scroll on mobile):  
Each track card:
```
[icon]  [Track name]
[Mini progress bar]
[X/Y steps complete]
[Next step: "..." (1 line)]
[View →]
```

**Overdue items** (if any)  
Warning banner: `[color-status-warning]` background, `[icon: AlertTriangle]`  
"You have [X] overdue items."  
List of overdue item titles with "Fix it" links.

**HR contact card**  
```
Your relocation is managed by:
[HR avatar]  [HR full name]
[HR email]  [HR phone if available]
[Send message →] button → opens thread
```

**Support resources**  
Links: "FAQ · Vendor contacts · Policy benefits"

---

### S6 — Employee: My Journey (Roadmap)

**Route:** `/my-move/journey`  
**Visible to:** `employee only`

**Intent**  
The employee sees their full roadmap as a journey — not a task list. Progress is celebrated. Upcoming steps are clearly explained in plain language. No jargon.

**Layout**  
Track tabs across top (horizontal tabs, scrollable). Step list below.

**Track tabs**  
Each tab: `[icon]` + `[Track name]` + mini progress ring (SVG).  
Active tab: `[color-accent-teal]` bottom border.

**Step list**  
Vertical timeline design. Steps connected by a vertical line, coloured by completion state.

Each step card:
```
[status icon]
[Step number]  [Title]
[Plain-language description]
[Owner: "Managed by your HR team" OR "You need to do this" — clear distinction]
[Due date if set]
[Required documents for this step (if any)]
[Open task button / View document button (if employee action required)]
```

Completed steps: collapsed by default with "Show completed" toggle.

**AI suggestion** (in context strip at top of page)  
"Based on your timeline, we suggest starting your visa application no later than [date]."  
Dismissible. Refreshes on next visit.

**Progress celebration**  
When a track reaches 100%: confetti animation + inline toast "🎉 Immigration track complete!"

---

### S7 — Employee: My Documents

**Route:** `/my-move/documents`  
**Visible to:** `employee only`

**Intent**  
The employee's document portal. One place to see everything they need to submit, upload it, and know its status. No email hunting for what's needed.

**Layout**  
List-detail split (same as S3-C but employee-perspective copy).

**Left: requirement list**  
Grouped by category. Same visual structure as HR view.  
Employee copy: plain-language descriptions. "What is this?" expandable info.

**Right: upload panel**  
Employee copy:
- "Here's what [requirement name] is for: [plain language]"
- "Instructions: [step-by-step instructions from requirement.instructions]"
- Upload zone: drag-drop or tap  
- Status of uploaded file: "Submitted — waiting for review" / "Approved ✓" / "Rejected — see reason below"

If rejected: amber banner "Needs re-upload: [reason]" + "Upload again" button.

**OCR notice** (when uploading passport/ID)  
"We'll scan this document to pre-fill your forms. You won't need to re-type your details."

**Overall progress**  
"X of Y documents submitted" progress bar at top.

---

### S8 — Vendor Directory

**Route:** `/vendors`  
**Visible to:** `≥ hr`

**Intent**  
The curated list of vendor partners for this company. HR can browse, assess, and assign vendors to cases from here.

**Layout**  
Filter sidebar (fixed left, 220px) + card grid (remaining width).

**Filter sidebar**  
- Service type (multi-select: Immigration, Moving, Housing, Tax, Schooling, Banking, Language, Cultural)  
- Coverage (corridor or country select)  
- Preferred only (toggle)  
- Active only (toggle, default on)

**Vendor card**  
```
[Logo (60×60, rounded square)]  [Name]
[Service type pill]  [Coverage: "Global" or country flags]
[Rating: star row, e.g. ★★★★☆ 4.2]  [is_preferred: ★ "Preferred"]
[Description, 2 lines]
[Active cases: X currently assigned]
[Contact: email / website links]
[Assign to case ▼]  [View detail →]
```

**Vendor detail slide-over**  
Full Vendor entity + CompanyVendor notes + all cases currently assigned + contact details + contract link.

**Global vendors section**  
Top of grid: "Your global partners" header, preferred/global vendors first.

**"Assign to case" flow**  
Dropdown: search and select case → then select step → "Assign" button.

---

### S9 — Analytics

**Route:** `/analytics`  
**Visible to:** `≥ admin`

**Intent**  
Operational intelligence for mobility leaders. Not vanity metrics — data that supports HR's case for the operating budget and helps them catch problems before they become delays.

**Layout**  
Topbar: period picker (Last 30 days / Last quarter / Last 12 months / Custom range). Breadcrumb: Analytics.

**KPI row (4 cards)**  
- Active cases (with trend arrow vs. prev period)  
- Average case duration (days)  
- On-time completion rate (%)  
- Compliance completion rate (%)

Each card: large number, trend indicator (`[color-status-success]` up or `[color-status-error]` down), spark line.

**Charts section**  

1. **Cases over time** — area chart. X: months. Y: count. Stacked series: opened / completed / active.

2. **Top corridors** — horizontal bar chart. X: case count. Bars: coloured by service load.

3. **Stage distribution** — donut chart. Segments by `CaseStage`.

4. **Average duration by corridor** — bar chart, sorted descending.

5. **Document completion rate** — horizontal bar chart per policy tier.

**Table: Cases by HR owner** (admin only)  
Columns: HR name, active cases, avg duration, on-time %, exceptions resolved.

**Export**  
"Export as CSV" button for each table/chart. Date-stamped filename.

**Chart design tokens**  
- Chart colours: `[color-chart-teal]`, `[color-chart-blue]`, `[color-chart-amber]`, `[color-chart-purple]`, `[color-chart-gray]`  
- Grid lines: `[color-border-chart]`  
- Axis labels: `[color-text-tertiary]`  
- Tooltip: `[color-surface-tooltip]` background, `[color-text-primary]`  
- All charts use `Chart.js` with the ReloPass custom theme plugin

---

### S10 — Settings

**Routes:** `/settings/policy`, `/settings/team`, `/settings/organisation`  
**Visible to:** `≥ admin` (policy, org); `≥ hr` (team, own profile)

#### S10-A — Policy Settings (`/settings/policy`)

**Layout**  
Left nav (policy tiers list) + right detail panel.

**Policy tier list**  
Each item: tier name + rank + employee count.  
"Add tier" button at bottom.

**Tier detail**  
```
[Tier name] — edit inline
[Description]
[Rank: stepper]
[Max budget: currency input]
[Lump sum: currency input]
[Temp housing days: stepper]

Benefits:
[add/edit/remove benefit rows]
Each row: [Category select] [Name] [Value type select] [Value] [Currency if applicable]

[Save changes]  [Delete tier] (with confirmation)
```

#### S10-B — Team Settings (`/settings/team`, `≥ hr`)

**Layout**  
Team member table + invite flow.

**Team table**  
Columns: Name, Email, Role, Plan Tier, Cases assigned, Last active, Actions (Edit role / Remove).

**Invite flow**  
"Invite HR member" button → slide-over:
- Email input  
- Role select: `hr` / `admin`  
- "Send invite" → email dispatched, pending row added to table

**Pending invites section**  
List of sent invites: email, sent date, "Resend" / "Cancel" actions.

#### S10-C — Organisation Settings (`/settings/organisation`, `≥ admin`)

Fields: Organisation name, logo upload, default currency, fiscal year start, AI enabled toggle, GlobeCanvas enabled toggle, theme override.

---

## Shared components

### StatusPill

Props: `status: CaseStatus | StepStatus | DocStatus | ExceptionStatus`, `size: 'sm' | 'md'`  
Renders coloured pill using `DOC_STATUS_PILL`, `CASE_STATUS_PILL`, `STEP_STATUS_PILL` maps.  
Background / text / border from design token `pill_variants`.

### ProgressBar

Props: `value: number` (0–100), `size: 'sm' | 'md' | 'lg'`, `color?: 'teal' | 'amber' | 'error'`  
Default colour: `[color-accent-teal]`. Track: `[color-bg-progress-track]`.

### Avatar

Props: `url: string | null`, `name: string`, `size: 24 | 32 | 40 | 48 | 64`  
Fallback: initials, background from deterministic hash of name → one of 6 accent colours.

### CountryFlag

Props: `iso2: string`, `size: 'sm' | 'md'`  
Renders flag emoji + country name. Uses `Country.flag_emoji` from tokens.

### CorridorBadge

Props: `corridor: CorridorCode`  
Renders `[origin_flag] [origin_iso2] → [dest_flag] [dest_iso2]`

### DocumentUploadZone

Props: `onUpload: (file: File) => void`, `accept: string[]`, `maxSizeMB: number`, `hint?: string`  
States: idle / dragging-over (teal border, teal background tint) / uploading (progress bar) / success / error.

### ConfirmModal

Props: `title: string`, `body: string`, `confirmLabel: string`, `onConfirm: () => void`, `destructive?: boolean`  
Destructive = red confirm button.

### CommandPalette

Global singleton, triggered by `⌘K`. Managed by `CommandPaletteProvider`.

### GlobeCanvas

Props: `corridors: GlobeCorridorArc[]`, `width: number`, `height: number`, `interactive?: boolean`  
Canvas 2D flat-map projection. 60fps via `requestAnimationFrame`. 7 animated Bezier arcs.  
Arc colours from `globe_canvas_colors` tokens: teal (#1DBFA2), blue (#4A9AE8), amber (#EFA827).  
Background: `#0A0E1A`.  
`aria-hidden="true"` — decorative only.

### DatePicker

Wrapper around a headless date picker. Single date or range mode.  
Uses `[color-accent-teal]` for selected date highlight.

### InlineEdit

Props: `value: string`, `onSave: (v: string) => void`, `type: 'text' | 'number' | 'date'`  
Click-to-edit inline. Save on blur or Enter. Cancel on Escape.

---

## Responsive behaviour

ReloPass is primarily a **desktop web application** (minimum supported: 1280px wide). Mobile is supported at ≥ 375px for the employee-facing screens only (S4, S5, S6, S7).

**Desktop (≥ 1280px):** Full layout as specified above.

**Tablet (768–1279px):** Sidebar auto-collapses. AI panel becomes a full-screen modal overlay.

**Mobile (375–767px, employee screens only):**  
- Sidebar replaced by bottom tab bar: My Move · Journey · Documents · Forms  
- Single-column layouts  
- TopBar: logo only + hamburger  
- S4 intake wizard: full-screen single-step  
- GlobeCanvas: hidden  
- MovableColumns: disabled, fixed column layout

---

## Accessibility

- Minimum contrast ratio: 4.5:1 for body text, 3:1 for large text (WCAG 2.1 AA)  
- All interactive elements keyboard-navigable; focus ring `[color-accent-teal]` 2px, 2px offset  
- All images and icons have `aria-label` or `aria-hidden="true"`  
- Form fields: `<label>` associated via `htmlFor`, error states linked via `aria-describedby`  
- Modal and slide-overs: `role="dialog"`, `aria-modal="true"`, focus trap on open, return focus on close  
- Live regions: toast notifications use `role="alert"`, real-time updates use `aria-live="polite"`  
- Reduced motion: `prefers-reduced-motion: reduce` disables GlobeCanvas animation and progress bar transitions

---

## Loading and error states

**Loading**  
Skeleton screens for all data-dependent sections. Skeleton uses `[color-skeleton-base]` with shimmer animation (`[color-skeleton-highlight]`). Never show a full-page spinner — always skeleton the layout.

**Error**  
- API error: inline error banner with `[color-status-error]` background, `[icon: AlertCircle]`, error message, retry button  
- 404: friendly full-page state — `[icon: SearchX]`, "We couldn't find that page.", Back button  
- 403: "You don't have access to this page." + "Go to Dashboard" button  
- Network error: toast with `[icon: WifiOff]` + "Reconnecting..." that auto-retries

**Empty states**  
Every list/table has an empty state with: contextual icon, explanation (1 line), and an action where relevant (e.g. "Create your first case").

---

## Notification system

**In-app notifications (bell icon)**  
Slide-over panel. Notifications grouped: Today / Earlier.  
Types: case status change, document reviewed, message received, exception decided, step assigned.  
"Mark all read" button. Individual notification links to the relevant entity.

**Toast notifications**  
Bottom-right of screen. Stack up to 3 visible. Auto-dismiss after 4s (success/info) or 8s (error). Manual dismiss `[icon: X]`. Uses `ToastMessage` type.

**Real-time connection indicator**  
Dot in topbar: `[color-status-success]` = connected, `[color-status-warning]` = reconnecting, `[color-status-error]` = offline. Tooltip shows status text.

---

## Theme

Light theme: default. Dark theme: toggled via topbar icon or system preference.  
Theme applied as `data-theme="dark"` on `<html>` element.  
Persisted in `localStorage["rp-theme"]`.  
All colours reference CSS custom properties — no hardcoded hex values in components.

---

*End of ReloPass Pages Specification — v1.0*
