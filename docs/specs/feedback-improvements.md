> **SUPERSEDED (2026-09-04).** Do not implement this document. The live ingest path is
> `POST /api/feedback` (`FeedbackWidget` → `submitProductFeedback`), not a direct
> Supabase insert. AI title/sentiment/layer columns on `public.feedback` were never
> the ticket model; use `feedback_status` + `engineer_task`. Canonical design:
> `docs/specs/feedback-closed-loop.md`. Canonical plan:
> `docs/superpowers/plans/2026-09-04-feedback-closed-loop.md`.

# Feedback widget — improvement spec
> Hand this document to Claude Code in a session with the repo mounted.
> Implement the three features in order. Each is independent — no cross-feature dependencies.

---

## Context: what already exists

The feedback system lives across these files. Read them before touching anything:

| File | Role |
|------|------|
| `frontend/src/components/FeedbackWidget.tsx` | Floating widget; does a direct Supabase insert on submit |
| `frontend/src/components/admin/FeedbackTab.tsx` | Admin triage table; reads from Supabase, updates status and admin_notes inline |
| `supabase/migrations/20260502110000_feedback.sql` | Base schema (id, user_id, page_url, category, message, status, created_at) |
| `supabase/migrations/20260617120000_feedback_screenshot_reportid.sql` | Added screenshot_data, report_id |
| `supabase/migrations/20260726000000_feedback_admin_notes_browser.sql` | Added admin_notes, browser — **apply this first if not yet applied** |

Current `public.feedback` columns after all migrations:
```
id              UUID PK
user_id         UUID → auth.users
page_url        TEXT
category        TEXT  CHECK IN ('bug','idea','other')
message         TEXT  1–2000 chars
status          TEXT  CHECK IN ('new','reviewed','acted_on')  DEFAULT 'new'
screenshot_data TEXT  (JPEG base64 data URL, nullable)
report_id       TEXT  (e.g. BUG-260617-A1B2, nullable)
admin_notes     TEXT  (nullable)
browser         TEXT  (navigator.userAgent slice, nullable)
created_at      TIMESTAMPTZ
```

RLS: authenticated users INSERT own rows; ADMIN role SELECT + UPDATE.
The admin UPDATE policy is a blanket update — new columns are automatically covered.

---

## Feature 1 — AI auto-classification

### What it does
After a user submits feedback, the backend classifies it automatically and writes three fields back to the row:
- `ai_title` — a one-sentence summary replacing the raw message in the admin table
- `ai_sentiment` — `positive | neutral | negative`
- `ai_layer` — `ui | api | flow | copy | other` (what part of the product this touches)

### Why
"does not work" and "hr regression probe" give the admin nothing. A 10-word AI title like "Employee roadmap page fails to load on /employee/journey" makes triage instant.

### Step 1 — DB migration

Create `supabase/migrations/20260727000000_feedback_ai_fields.sql`:

```sql
-- AI classification fields written by the auto-classify backend endpoint.
ALTER TABLE public.feedback
  ADD COLUMN IF NOT EXISTS ai_title     TEXT,
  ADD COLUMN IF NOT EXISTS ai_sentiment TEXT CHECK (ai_sentiment IN ('positive', 'neutral', 'negative')),
  ADD COLUMN IF NOT EXISTS ai_layer     TEXT CHECK (ai_layer IN ('ui', 'api', 'flow', 'copy', 'other'));

-- No new RLS policies needed — blanket admin UPDATE covers these.
-- INSERT policy covers them too (widget doesn't write them; backend does via service role).
```

### Step 2 — Backend endpoint

Create `backend/app/routers/feedback_classify.py`. Follow the exact dual-layer registration pattern from CLAUDE.md §"Routers must be registered in BOTH".

```python
"""
feedback_classify.py — POST /api/feedback/classify
Classifies a single feedback submission with a lightweight LLM call.
Called fire-and-forget from FeedbackWidget after a successful Supabase insert.
"""
```

**Endpoint signature:**
```
POST /api/feedback/classify
Authorization: Bearer <user token>   (any authenticated user)
Body: { "report_id": "BUG-260617-A1B2" }
Response 200: { "ok": true }
Response 404: { "detail": "Not found" }
```

**Implementation rules:**
1. Use `get_supabase_admin_client()` (from `backend/app/services/supabase_client.py`) to fetch and write the row — the user's anon key can only select their own rows, but the service role key bypasses RLS.
2. Fetch `message` and `page_url` from `public.feedback` WHERE `report_id = ?` AND `user_id = auth.uid()` (validate ownership by also checking the user's JWT uid matches `user_id` — don't let a user classify someone else's feedback).
3. **Mask PII before the LLM call** — import `mask_pii` from `backend.app.services.pii_masker` and call it on `message`. This is mandatory per CLAUDE.md §"Data minimisation".
4. Use `AnthropicClient` from `backend.app.services.policy_assistant_llm_client` (same client the policy assistant uses). Use `claude-haiku-4-5-20251001` for cost — this is a tiny classification task.
5. System prompt (exact):

```
You are a triage assistant for a corporate relocation SaaS product called ReloPass.
Classify the user-submitted feedback below. Reply with valid JSON only — no markdown, no explanation.

{
  "title": "<one sentence, max 12 words, describing the specific issue or idea>",
  "sentiment": "<positive|neutral|negative>",
  "layer": "<ui|api|flow|copy|other>"
}

Layer definitions:
- ui: visual/layout/component problem or idea
- api: data not loading, wrong values, server error
- flow: the sequence of steps is broken or confusing
- copy: text, label, or wording issue
- other: anything that doesn't fit above

Be specific in the title. Never use "does not work" or "issue" alone.
Page context: {page_url}
```

User message: `mask_pii(message)`

6. Parse the JSON response. If parsing fails or a field is missing, write `null` for that field (don't crash).
7. Write back with `supabase_admin.table('feedback').update({ai_title, ai_sentiment, ai_layer}).eq('report_id', report_id).execute()`.
8. Return `{"ok": True}`. Errors are logged but never bubble to the user (this is background enrichment).

**Register in both entry points** (CLAUDE.md §"Routers must be registered in BOTH"):

In `backend/app/main.py`:
```python
from .routers import feedback_classify as feedback_classify_router
app.include_router(feedback_classify_router.router)
```

In `backend/main.py` (around line 580 with the other include_router blocks):
```python
from .app.routers import feedback_classify as feedback_classify_router
app.include_router(feedback_classify_router.router)
```

### Step 3 — Frontend: fire-and-forget after submit

In `FeedbackWidget.tsx`, after the successful Supabase insert (inside the `else` branch of `if (error)`), add a fire-and-forget call:

```typescript
// fire-and-forget — don't await, don't block the success UX
void fetch('/api/feedback/classify', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ report_id: rid }),
}).catch(() => { /* silent — classification is best-effort */ });
```

The `fetch` must use a relative URL so the Vite dev proxy (`/api → localhost:8000`) handles it in dev. Do not use `VITE_API_URL` here — the widget is already using the Supabase client directly and this piggybacks the same session cookies/headers.

Wait — there's no auth header in a raw `fetch`. The endpoint needs to be callable without auth OR we need to pass the Supabase JWT. Get the session token:

```typescript
const { data: { session } } = await supabase.auth.getSession();
void fetch('/api/feedback/classify', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    ...(session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {}),
  },
  body: JSON.stringify({ report_id: rid }),
}).catch(() => {});
```

On the backend, use the standard `get_current_user` dependency from `backend.app.auth_deps` to validate the JWT.

### Step 4 — Admin UI: show AI fields

In `FeedbackTab.tsx`:

1. Add to `FeedbackRow` interface:
```typescript
ai_title:     string | null;
ai_sentiment: 'positive' | 'neutral' | 'negative' | null;
ai_layer:     'ui' | 'api' | 'flow' | 'copy' | 'other' | null;
```

2. Add `ai_title, ai_sentiment, ai_layer` to the Supabase `.select()` string.

3. In the **message preview column** (compact row), show `ai_title` if present, falling back to `row.message`:
```tsx
<p className="text-[12px] text-gray-700 truncate">
  {row.ai_title ?? row.message}
</p>
```

4. In the **expanded row**, after the category badge line, add:
```tsx
{row.ai_layer && (
  <span className="text-[10.5px] px-1.5 py-0.5 rounded bg-purple-50 text-purple-600 border border-purple-200 font-medium">
    {row.ai_layer}
  </span>
)}
{row.ai_sentiment && (
  <span className={`text-[10.5px] px-1.5 py-0.5 rounded border font-medium ${
    row.ai_sentiment === 'negative' ? 'bg-red-50 text-red-600 border-red-200' :
    row.ai_sentiment === 'positive' ? 'bg-green-50 text-green-600 border-green-200' :
    'bg-gray-100 text-gray-500 border-gray-200'
  }`}>
    {row.ai_sentiment}
  </span>
)}
```

5. Add `ai_layer` as a filter option alongside the existing category filter. New state: `const [filterLayer, setFilterLayer] = useState<string>('all')`. Add filter to `displayed`. Add a third filter pill row for layer.

---

## Feature 2 — Priority field

### What it does
Adds a `priority` column (critical / high / normal / low) that the admin can set per submission. Critical items float visually.

### Step 1 — DB migration

Create `supabase/migrations/20260728000000_feedback_priority.sql`:

```sql
ALTER TABLE public.feedback
  ADD COLUMN IF NOT EXISTS priority TEXT NOT NULL DEFAULT 'normal'
    CHECK (priority IN ('critical', 'high', 'normal', 'low'));

CREATE INDEX IF NOT EXISTS feedback_priority_idx ON public.feedback(priority);
```

### Step 2 — Admin UI only (no backend change needed)

In `FeedbackTab.tsx`:

1. Add `priority: 'critical' | 'high' | 'normal' | 'low'` to `FeedbackRow`.

2. Add to the `.select()` string.

3. Style map:
```typescript
const PRIORITY_CHIP: Record<string, string> = {
  critical: 'bg-red-100 text-red-700 border-red-300',
  high:     'bg-orange-100 text-orange-700 border-orange-200',
  normal:   'bg-gray-100 text-gray-500 border-gray-200',
  low:      'bg-gray-50 text-gray-400 border-gray-100',
};
```

4. In the **compact row**, add a priority `<select>` next to the status select (new column in the grid, or tucked into the status column). Follow the exact same `updateStatus` pattern:

```typescript
const updatePriority = async (row: FeedbackRow, newPriority: string) => {
  setSavingId(row.id);
  const { error: err } = await supabase
    .from('feedback')
    .update({ priority: newPriority })
    .eq('id', row.id);
  if (!err) setRows((prev) => prev.map((r) => r.id === row.id ? { ...r, priority: newPriority as FeedbackRow['priority'] } : r));
  setSavingId(null);
};
```

5. Add a **priority filter** alongside the existing status/category filters. Critical items should sort to top — when `filterStatus === 'all'` and no sort is active, render `critical` rows first (sort `displayed` by priority: critical → high → normal → low before rendering).

6. Add a priority summary stat card: replace the otherwise redundant 4th stat card (or add a 5th) with `Critical: {counts.critical}` in red.

---

## Feature 3 — Sortable columns

### What it does
Clicking any column header in the FeedbackTab table sorts by that column. Default is `created_at DESC` (unchanged). This is a pure frontend change — no DB or backend work.

### Implementation

In `FeedbackTab.tsx`:

1. Add state:
```typescript
type SortField = 'created_at' | 'category' | 'status' | 'priority' | 'page_url';
type SortDir   = 'asc' | 'desc';
const [sortField, setSortField] = useState<SortField>('created_at');
const [sortDir,   setSortDir]   = useState<SortDir>('desc');
```

2. Add a sort helper:
```typescript
function toggleSort(field: SortField) {
  if (sortField === field) setSortDir((d) => d === 'asc' ? 'desc' : 'asc');
  else { setSortField(field); setSortDir('asc'); }
}
```

3. Sort `displayed` after filtering:
```typescript
const sorted = [...displayed].sort((a, b) => {
  let av: string | number = a[sortField] ?? '';
  let bv: string | number = b[sortField] ?? '';
  if (sortField === 'created_at') { av = new Date(av as string).getTime(); bv = new Date(bv as string).getTime(); }
  if (sortField === 'priority') {
    const rank: Record<string, number> = { critical: 0, high: 1, normal: 2, low: 3 };
    av = rank[av as string] ?? 99; bv = rank[bv as string] ?? 99;
  }
  if (av < bv) return sortDir === 'asc' ? -1 : 1;
  if (av > bv) return sortDir === 'asc' ? 1 : -1;
  return 0;
});
```

Render `sorted` instead of `displayed`.

4. In each sortable column header, replace the plain `<div>` with a clickable button that shows a sort indicator (↑ / ↓ / ↕):

```tsx
function SortHeader({ field, label, currentField, currentDir, onSort }: {
  field: SortField; label: string;
  currentField: SortField; currentDir: SortDir;
  onSort: (f: SortField) => void;
}) {
  const active = field === currentField;
  return (
    <button
      onClick={() => onSort(field)}
      className="flex items-center gap-1 text-[11px] font-semibold text-gray-400 uppercase tracking-wide hover:text-gray-600 transition-colors"
    >
      {label}
      <span className="opacity-50">{active ? (currentDir === 'asc' ? '↑' : '↓') : '↕'}</span>
    </button>
  );
}
```

Wrap each sortable column header cell with `<SortHeader>`. Non-sortable columns (Shot, Message) keep plain text.

---

## Implementation checklist

Work through these in order. Run `cd frontend && npx tsc --noEmit` after each feature before moving to the next. For backend changes, also verify the route appears in:

```bash
python3 -c "from backend.main import app; print([r.path for r in app.routes if 'feedback' in r.path])"
```

- [ ] Apply migration `20260726000000_feedback_admin_notes_browser.sql` if not yet applied (`supabase db push`)
- [ ] Feature 1: DB migration `20260727000000_feedback_ai_fields.sql`
- [ ] Feature 1: `backend/app/routers/feedback_classify.py`
- [ ] Feature 1: Register in `backend/app/main.py` AND `backend/main.py`
- [ ] Feature 1: `FeedbackWidget.tsx` — fire-and-forget classify call
- [ ] Feature 1: `FeedbackTab.tsx` — ai_title in message column, badges + layer filter in expanded row
- [ ] `tsc --noEmit` — clean
- [ ] Feature 2: DB migration `20260728000000_feedback_priority.sql`
- [ ] Feature 2: `FeedbackTab.tsx` — priority select, filter, sort-by-critical default, stat card
- [ ] `tsc --noEmit` — clean
- [ ] Feature 3: `FeedbackTab.tsx` — sort state, `toggleSort`, `SortHeader`, render `sorted`
- [ ] `tsc --noEmit` — clean

## Do NOT

- Do not change the Supabase RLS policies — existing blanket admin UPDATE covers all new columns.
- Do not touch `FeedbackWidget.tsx` for Features 2 or 3 — priority and sort are admin-only.
- Do not use `backend/database.py` (legacy psycopg2 layer) for the new endpoint — use `get_supabase_admin_client()` from `backend/app/services/supabase_client.py`.
- Do not send raw `message` text to the LLM — always call `mask_pii(message)` first (CLAUDE.md §"Data minimisation — PII in AI prompts").
- Do not rebuild or restructure `FeedbackTab.tsx` — add to what's there.
