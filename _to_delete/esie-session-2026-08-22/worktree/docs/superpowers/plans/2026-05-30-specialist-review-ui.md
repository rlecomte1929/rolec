# Specialist Review UI (AI Output Diff View) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Crawl-phase specialist review workflow where an immigration specialist sees AI-generated roadmap steps, corrects them with reason codes, and approves/rejects the roadmap — persisting every decision as append-only calibration data.

**Architecture:** Append-only `specialist_review_events` table (admin-scoped RLS) is the ground-truth training set, plus a tiny `roadmap_review_status` table holding the per-case `released_to_user` / `regeneration_requested` flags. A reusable `<RoadmapStepDiff>` React component renders AI-vs-edited side-by-side with a reason-code selector; an admin page at `/admin/specialist-review/:case_id` composes it into a full-roadmap review with an overall approve/reject CTA; a transactional `POST /api/internal/specialist-review/submit` endpoint writes the events batch and flips the status flags.

**Tech Stack:** Supabase/Postgres migrations (native ENUM + RLS via `public.is_admin()`), SQLAlchemy ORM (`backend/app/`), FastAPI modular router, React/TypeScript + Vite + Tailwind + antigravity design system, Vitest (frontend), pytest/unittest (backend).

This plan maps 1:1 to the four Notion subtasks of **AIQ-196 (P1-02)**:

| Task | Notion ID | Title |
|------|-----------|-------|
| Task 1 | AIQ-631 (P1-02a) | Migration: `specialist_review_events` (+ `roadmap_review_status`) |
| Task 2 | AIQ-632 (P1-02b) | `<RoadmapStepDiff>` component |
| Task 3 | AIQ-633 (P1-02c) | `/admin/specialist-review/:case_id` page |
| Task 4 | AIQ-634 (P1-02d) | `POST /api/internal/specialist-review/submit` endpoint |

**Build order (per decomposition note):** Task 1 + Task 2 in parallel → Task 3 → Task 4. After all four ship + canary clean, **Archive** AIQ-196 (do NOT mark "Done" — its own Execution Notes say "Parent will Archive once children ship") and set the four children to `Done`.

---

## Decisions & assumptions (confirm before executing)

1. **`released_to_user` / regeneration**: No such column or roadmap-release row exists today; roadmaps are derived on the fly by `backend/app/services/roadmap_builder.py::derive_roadmap()`. This plan adds a small `roadmap_review_status(case_id PK, released_to_user, regeneration_requested, …)` table. "Triggers a re-generation request" (AIQ-634 validation) is modeled as `regeneration_requested = true`, which a downstream job/next-access reads. No new background worker is built here.
2. **AI step JSON shape**: AI-generated steps (with `source_url` and `confidence`) are a **P1-01 output (AIQ-196 depends on P1-01)**. This plan reads steps from the existing roadmap derivation and treats `source_url`/`confidence` as **optional** fields rendered when present. If P1-01 persists AI steps elsewhere, swap the GET data source in Task 3/Task 4 — the component contract does not change.
3. **Endpoint path**: Notion specifies `POST /api/internal/specialist-review/submit`. Admin rate-limiting auto-applies only to `/api/admin/*` (see `backend/app/rate_limits.py`). The plan keeps the spec path and enforces admin access in-handler via `require_admin`; the default `STANDARD_LIMIT` middleware still applies. If you want `ADMIN_LIMIT`, move the prefix to `/api/admin/specialist-review`.
4. **Reason codes** (shared enum, used in DB + component + endpoint): `WRONG_PATHWAY`, `OUTDATED_RULE`, `MISSING_DEPENDENCY`, `INCORRECT_FORM`.
5. **Actions**: `approve` / `reject` / `edit` (native PG enum `specialist_review_action`).

---

## File structure

**Create:**
- `supabase/migrations/20260601010000_specialist_review_events.sql` — both tables + RLS
- `frontend/src/features/admin/specialist-review/RoadmapStepDiff.tsx` — diff component
- `frontend/src/features/admin/specialist-review/RoadmapStepDiff.test.tsx`
- `frontend/src/features/admin/specialist-review/reasonCodes.ts` — shared enum + confidence helper
- `frontend/src/pages/admin/AdminSpecialistReviewPage.tsx` — review page
- `frontend/src/pages/__tests__/AdminSpecialistReviewPage.test.tsx`
- `backend/app/routers/specialist_review.py` — submit + read endpoints
- `backend/tests/test_specialist_review_router.py`

**Modify:**
- `backend/app/models.py` — add `SpecialistReviewEvent`, `RoadmapReviewStatus` ORM models + `SpecialistReviewAction` enum
- `backend/app/main.py` — import + `include_router(specialist_review.router)`
- `frontend/src/api/client.ts` — add `specialistReviewAPI` wrapper
- `frontend/src/navigation/routes.ts` — add `adminSpecialistReview` route def
- `frontend/src/App.tsx` — lazy-load + register guarded route

---

## Task 1: Migration — `specialist_review_events` + `roadmap_review_status` (AIQ-631)

**Files:**
- Create: `supabase/migrations/20260601010000_specialist_review_events.sql`
- Modify: `backend/app/models.py`
- Test: `backend/tests/test_specialist_review_router.py` (RLS/round-trip portion; full file completed in Task 4)

- [ ] **Step 1: Write the migration**

Create `supabase/migrations/20260601010000_specialist_review_events.sql`:

```sql
-- P1-02a (AIQ-631): append-only specialist review calibration data + roadmap release flags.
-- Also consumed by P1-04 (calibration). Do not duplicate the events table elsewhere.

-- ── Enums ────────────────────────────────────────────────────────────────────
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'specialist_review_action') THEN
    CREATE TYPE public.specialist_review_action AS ENUM ('approve', 'reject', 'edit');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'specialist_reason_code') THEN
    CREATE TYPE public.specialist_reason_code AS ENUM (
      'WRONG_PATHWAY', 'OUTDATED_RULE', 'MISSING_DEPENDENCY', 'INCORRECT_FORM'
    );
  END IF;
END$$;

-- ── Append-only events table ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.specialist_review_events (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id            TEXT NOT NULL,
  step_id            TEXT NOT NULL,
  reviewer_id        TEXT NOT NULL,
  action             public.specialist_review_action NOT NULL,
  reason_code        public.specialist_reason_code,
  original_step_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  edited_step_json   JSONB,
  reviewed_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sre_case_id ON public.specialist_review_events (case_id);
CREATE INDEX IF NOT EXISTS idx_sre_step_id ON public.specialist_review_events (step_id);

-- ── Per-case release / regeneration status (supports AIQ-634) ─────────────────
CREATE TABLE IF NOT EXISTS public.roadmap_review_status (
  case_id                TEXT PRIMARY KEY,
  released_to_user       BOOLEAN NOT NULL DEFAULT false,
  regeneration_requested BOOLEAN NOT NULL DEFAULT false,
  reviewer_id            TEXT,
  notes                  TEXT,
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── SEC-003 hard gate: RLS + policy + revoke + grant ─────────────────────────
ALTER TABLE public.specialist_review_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.roadmap_review_status    ENABLE ROW LEVEL SECURITY;

-- Append-only: admin SELECT + INSERT only. No UPDATE/DELETE policy => denied by RLS.
CREATE POLICY specialist_review_events_admin_select
  ON public.specialist_review_events FOR SELECT TO authenticated
  USING (public.is_admin());
CREATE POLICY specialist_review_events_admin_insert
  ON public.specialist_review_events FOR INSERT TO authenticated
  WITH CHECK (public.is_admin());

-- Status row is mutable by admin (upserted on each submit).
CREATE POLICY roadmap_review_status_admin_all
  ON public.roadmap_review_status FOR ALL TO authenticated
  USING (public.is_admin()) WITH CHECK (public.is_admin());

REVOKE ALL ON public.specialist_review_events FROM anon;
REVOKE ALL ON public.roadmap_review_status    FROM anon;

-- Append-only at grant level too: no UPDATE/DELETE on events.
GRANT SELECT, INSERT                 ON public.specialist_review_events TO authenticated, service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.roadmap_review_status    TO authenticated, service_role;
```

- [ ] **Step 2: Apply the migration**

Per project memory, `supabase db push` is blocked by remote history drift — use the Supabase MCP `apply_migration` against project `nsvefcvpvwwwhuqyuqmp` instead. Name: `specialist_review_events`. Paste the SQL body above.
Expected: success; `list_tables` then shows `specialist_review_events` and `roadmap_review_status` with `rls_enabled = true`.

- [ ] **Step 3: Verify RLS round-trip + append-only via SQL**

Run via MCP `execute_sql` (service_role bypasses RLS, so assert structure + policy existence):

```sql
SELECT tablename, COUNT(policyname) AS policies
FROM pg_policies
WHERE schemaname = 'public'
  AND tablename IN ('specialist_review_events','roadmap_review_status')
GROUP BY tablename;
```
Expected: `specialist_review_events → 2`, `roadmap_review_status → 1`.
Then confirm anon is revoked:
```sql
SELECT grantee, privilege_type FROM information_schema.role_table_grants
WHERE table_name = 'specialist_review_events' AND grantee = 'anon';
```
Expected: zero rows.

- [ ] **Step 4: Add ORM models**

In `backend/app/models.py`, add near the other enums/models (mirror the `PolicyFactCanonical` enum+JSON style):

```python
import enum
from sqlalchemy import Column, String, DateTime, Boolean, Text
from sqlalchemy.sql import func
# (Base already imported from .db in this module)


class SpecialistReviewAction(str, enum.Enum):
    APPROVE = "approve"
    REJECT = "reject"
    EDIT = "edit"


class SpecialistReviewEvent(Base):
    __tablename__ = "specialist_review_events"

    id = Column(String, primary_key=True, index=True)
    case_id = Column(String, nullable=False, index=True)
    step_id = Column(String, nullable=False, index=True)
    reviewer_id = Column(String, nullable=False, index=True)
    action = Column(String, nullable=False)          # SpecialistReviewAction value
    reason_code = Column(String, nullable=True)
    original_step_json = Column(Text, nullable=False, default="{}")
    edited_step_json = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, server_default=func.now(), nullable=False)


class RoadmapReviewStatus(Base):
    __tablename__ = "roadmap_review_status"

    case_id = Column(String, primary_key=True, index=True)
    released_to_user = Column(Boolean, nullable=False, default=False)
    regeneration_requested = Column(Boolean, nullable=False, default=False)
    reviewer_id = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), nullable=False)
```

- [ ] **Step 5: Add migration to the RLS allowlist check sanity**

Confirm neither new table needs an allowlist entry (they HAVE policies). Run:
```bash
grep -nE 'specialist_review_events|roadmap_review_status' supabase/rls_allowlist.txt || echo "not on allowlist (correct)"
```
Expected: `not on allowlist (correct)`.

- [ ] **Step 6: Commit**

```bash
git add supabase/migrations/20260601010000_specialist_review_events.sql backend/app/models.py
git commit -m "feat(P1-02a): specialist_review_events + roadmap_review_status tables (AIQ-631)"
```

---

## Task 2: `<RoadmapStepDiff>` component (AIQ-632)

**Files:**
- Create: `frontend/src/features/admin/specialist-review/reasonCodes.ts`
- Create: `frontend/src/features/admin/specialist-review/RoadmapStepDiff.tsx`
- Test: `frontend/src/features/admin/specialist-review/RoadmapStepDiff.test.tsx`

- [ ] **Step 1: Create the shared enum + confidence helper**

`frontend/src/features/admin/specialist-review/reasonCodes.ts`:

```typescript
export const REASON_CODES = [
  'WRONG_PATHWAY',
  'OUTDATED_RULE',
  'MISSING_DEPENDENCY',
  'INCORRECT_FORM',
] as const;

export type ReasonCode = (typeof REASON_CODES)[number];

export const REASON_CODE_OPTIONS: { value: ReasonCode; label: string }[] = [
  { value: 'WRONG_PATHWAY', label: 'Wrong pathway' },
  { value: 'OUTDATED_RULE', label: 'Outdated rule' },
  { value: 'MISSING_DEPENDENCY', label: 'Missing dependency' },
  { value: 'INCORRECT_FORM', label: 'Incorrect form' },
];

export type ReviewDecision = 'approve' | 'reject' | 'edit';

// Confidence badge maps to antigravity Badge variants (green/amber/red), matching dev-plan scheme.
export function confidenceVariant(confidence?: number): 'success' | 'warning' | 'error' | 'neutral' {
  if (confidence == null) return 'neutral';
  if (confidence >= 0.8) return 'success';
  if (confidence >= 0.5) return 'warning';
  return 'error';
}

export function confidenceLabel(confidence?: number): string {
  if (confidence == null) return 'No confidence';
  const pct = Math.round(confidence * 100);
  if (confidence >= 0.8) return `HIGH (${pct}%)`;
  if (confidence >= 0.5) return `MED (${pct}%)`;
  return `LOW (${pct}%)`;
}
```

- [ ] **Step 2: Write the failing component test**

`frontend/src/features/admin/specialist-review/RoadmapStepDiff.test.tsx`:

```tsx
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { RoadmapStepDiff } from './RoadmapStepDiff';

const aiStep = {
  step_id: 'step-1',
  title: 'Apply for residence permit',
  description: 'Submit form UDI-123',
  source_url: 'https://udi.no/permit',
  confidence: 0.92,
};

describe('RoadmapStepDiff', () => {
  it('renders the AI step, confidence badge, and source url', () => {
    render(<RoadmapStepDiff step={aiStep} value={{ decision: 'approve' }} onChange={vi.fn()} />);
    expect(screen.getByText('Apply for residence permit')).toBeInTheDocument();
    expect(screen.getByText(/HIGH \(92%\)/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /source/i })).toHaveAttribute('href', 'https://udi.no/permit');
  });

  it('highlights an edited field and surfaces the reason-code selector', () => {
    const onChange = vi.fn();
    render(
      <RoadmapStepDiff
        step={aiStep}
        value={{ decision: 'edit', edited: { ...aiStep, title: 'Apply for work permit' }, reason_code: 'WRONG_PATHWAY' }}
        onChange={onChange}
      />,
    );
    // changed title is marked as changed
    expect(screen.getByTestId('diff-title')).toHaveAttribute('data-changed', 'true');
    // reason-code selector visible in edit/reject mode
    expect(screen.getByLabelText(/reason code/i)).toBeInTheDocument();
  });

  it('fires onChange with reject when Reject is clicked', () => {
    const onChange = vi.fn();
    render(<RoadmapStepDiff step={aiStep} value={{ decision: 'approve' }} onChange={onChange} />);
    fireEvent.click(screen.getByRole('button', { name: /reject/i }));
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ decision: 'reject' }));
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/features/admin/specialist-review/RoadmapStepDiff.test.tsx`
Expected: FAIL — `Cannot find module './RoadmapStepDiff'`.

- [ ] **Step 4: Implement the component**

`frontend/src/features/admin/specialist-review/RoadmapStepDiff.tsx`:

```tsx
import React from 'react';
import { Badge, Button, Select } from '../../../components/antigravity';
import {
  REASON_CODE_OPTIONS,
  ReasonCode,
  ReviewDecision,
  confidenceLabel,
  confidenceVariant,
} from './reasonCodes';

export interface AiStep {
  step_id: string;
  title: string;
  description?: string;
  source_url?: string;
  confidence?: number;
  [k: string]: unknown;
}

export interface StepReviewValue {
  decision: ReviewDecision;
  edited?: AiStep;
  reason_code?: ReasonCode;
}

interface Props {
  step: AiStep;
  value: StepReviewValue;
  onChange: (next: StepReviewValue) => void;
}

function changed(a: unknown, b: unknown): boolean {
  return b !== undefined && a !== b;
}

export function RoadmapStepDiff({ step, value, onChange }: Props) {
  const edited = value.edited ?? step;
  const showReason = value.decision === 'edit' || value.decision === 'reject';

  const set = (patch: Partial<StepReviewValue>) => onChange({ ...value, ...patch });
  const setEdited = (patch: Partial<AiStep>) =>
    set({ decision: 'edit', edited: { ...edited, ...patch } });

  return (
    <div className="rounded-lg border border-white/10 p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <Badge variant={confidenceVariant(step.confidence)}>{confidenceLabel(step.confidence)}</Badge>
        {step.source_url && (
          <a
            className="text-sm underline opacity-80 hover:opacity-100"
            href={step.source_url}
            target="_blank"
            rel="noreferrer"
          >
            Source
          </a>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div>
          <p className="mb-1 text-xs uppercase tracking-wide opacity-60">AI generated</p>
          <h4 className="font-semibold">{step.title}</h4>
          {step.description && <p className="mt-1 text-sm opacity-80">{step.description}</p>}
        </div>
        <div>
          <p className="mb-1 text-xs uppercase tracking-wide opacity-60">Specialist edit</p>
          <h4
            data-testid="diff-title"
            data-changed={changed(step.title, value.edited?.title)}
            className={changed(step.title, value.edited?.title) ? 'rounded bg-amber-500/20 px-1 font-semibold' : 'font-semibold'}
          >
            <input
              aria-label="Edited title"
              className="w-full bg-transparent outline-none"
              value={edited.title}
              onChange={(e) => setEdited({ title: e.target.value })}
            />
          </h4>
          <textarea
            aria-label="Edited description"
            className="mt-1 w-full bg-transparent text-sm opacity-90 outline-none"
            value={edited.description ?? ''}
            onChange={(e) => setEdited({ description: e.target.value })}
          />
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-end gap-2">
        <Button
          variant={value.decision === 'approve' ? 'primary' : 'outline'}
          size="sm"
          onClick={() => set({ decision: 'approve', edited: undefined, reason_code: undefined })}
        >
          Approve
        </Button>
        <Button
          variant={value.decision === 'reject' ? 'primary' : 'outline'}
          size="sm"
          onClick={() => set({ decision: 'reject' })}
        >
          Reject
        </Button>
        {showReason && (
          <Select
            label="Reason code"
            value={value.reason_code ?? ''}
            onChange={(v) => set({ reason_code: v as ReasonCode })}
            options={REASON_CODE_OPTIONS}
            placeholder="Select reason…"
          />
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/features/admin/specialist-review/RoadmapStepDiff.test.tsx`
Expected: PASS (3 tests).
Then type-check: `cd frontend && npx tsc --noEmit` → no errors.

> If `Select`/`Button`/`Badge` prop names differ from what Task 2 assumes, adjust to the real antigravity signatures (see `frontend/src/components/antigravity/{Select,Button,Badge}.tsx`). Do not invent props.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/admin/specialist-review/
git commit -m "feat(P1-02b): RoadmapStepDiff component + reason codes (AIQ-632)"
```

---

## Task 3: `/admin/specialist-review/:case_id` page (AIQ-633)

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/navigation/routes.ts`
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/pages/admin/AdminSpecialistReviewPage.tsx`
- Test: `frontend/src/pages/__tests__/AdminSpecialistReviewPage.test.tsx`

- [ ] **Step 1: Add the API wrapper**

In `frontend/src/api/client.ts`, add a new exported object (mirror the existing `hrAPI`/`adminAPI` style; reuse the shared `api` axios singleton):

```typescript
import type { AiStep } from '../features/admin/specialist-review/RoadmapStepDiff';
import type { ReasonCode, ReviewDecision } from '../features/admin/specialist-review/reasonCodes';

export interface SpecialistReviewStep extends AiStep {}

export interface SpecialistReviewSubmitItem {
  step_id: string;
  decision: ReviewDecision;
  reason_code?: ReasonCode;
  original_step: AiStep;
  edited_step?: AiStep;
}

export const specialistReviewAPI = {
  getRoadmap: async (caseId: string): Promise<{ case_id: string; steps: SpecialistReviewStep[] }> => {
    const res = await api.get(`/api/internal/specialist-review/${caseId}`);
    return res.data;
  },
  submit: async (
    caseId: string,
    body: { decision: 'approved' | 'rejected'; notes?: string; items: SpecialistReviewSubmitItem[] },
  ): Promise<{ released_to_user: boolean; regeneration_requested: boolean }> => {
    const res = await api.post(`/api/internal/specialist-review/submit`, { case_id: caseId, ...body });
    return res.data;
  },
};
```

- [ ] **Step 2: Register the route**

In `frontend/src/navigation/routes.ts`, add to `ROUTE_DEFS` (alongside the other `adminXxx` entries):

```typescript
adminSpecialistReview: { path: '/admin/specialist-review/:case_id', roles: ['ADMIN'] as RouteRole[] },
```

In `frontend/src/App.tsx`, add the lazy import (next to other admin page imports):

```tsx
const AdminSpecialistReviewPage = lazy(() =>
  import('./pages/admin/AdminSpecialistReviewPage').then((m) => ({ default: m.AdminSpecialistReviewPage })),
);
```

And register the guarded route (next to other `RequireAdminRoute` routes):

```tsx
<Route
  path={ROUTE_DEFS.adminSpecialistReview.path}
  element={<RequireAdminRoute><AdminSpecialistReviewPage /></RequireAdminRoute>}
/>
```

- [ ] **Step 3: Write the failing page test**

`frontend/src/pages/__tests__/AdminSpecialistReviewPage.test.tsx`:

```tsx
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AdminSpecialistReviewPage } from '../admin/AdminSpecialistReviewPage';

vi.mock('../../api/client', () => ({
  specialistReviewAPI: {
    getRoadmap: vi.fn().mockResolvedValue({
      case_id: 'case-1',
      steps: [
        { step_id: 's1', title: 'Step one', confidence: 0.9, source_url: 'https://x' },
        { step_id: 's2', title: 'Step two', confidence: 0.4 },
      ],
    }),
    submit: vi.fn().mockResolvedValue({ released_to_user: true, regeneration_requested: false }),
  },
}));

import { specialistReviewAPI } from '../../api/client';

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/admin/specialist-review/case-1']}>
      <Routes>
        <Route path="/admin/specialist-review/:case_id" element={<AdminSpecialistReviewPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('AdminSpecialistReviewPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('loads and lists all roadmap steps', async () => {
    renderPage();
    await waitFor(() => expect(specialistReviewAPI.getRoadmap).toHaveBeenCalledWith('case-1'));
    expect(await screen.findByText('Step one')).toBeInTheDocument();
    expect(screen.getByText('Step two')).toBeInTheDocument();
  });

  it('submits an overall approval with per-step items', async () => {
    renderPage();
    await screen.findByText('Step one');
    fireEvent.click(screen.getByRole('button', { name: /approve roadmap/i }));
    await waitFor(() => expect(specialistReviewAPI.submit).toHaveBeenCalledTimes(1));
    const [caseId, body] = (specialistReviewAPI.submit as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(caseId).toBe('case-1');
    expect(body.decision).toBe('approved');
    expect(body.items).toHaveLength(2);
  });
});
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/__tests__/AdminSpecialistReviewPage.test.tsx`
Expected: FAIL — `Cannot find module '../admin/AdminSpecialistReviewPage'`.

- [ ] **Step 5: Implement the page**

`frontend/src/pages/admin/AdminSpecialistReviewPage.tsx`:

```tsx
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { AdminLayout } from '../../features/admin/AdminLayout';
import { Alert, Button, Card } from '../../components/antigravity';
import { RoadmapStepDiff, AiStep, StepReviewValue } from '../../features/admin/specialist-review/RoadmapStepDiff';
import { specialistReviewAPI } from '../../api/client';

export function AdminSpecialistReviewPage() {
  const { case_id: caseId } = useParams<{ case_id: string }>();
  const [steps, setSteps] = useState<AiStep[]>([]);
  const [decisions, setDecisions] = useState<Record<string, StepReviewValue>>({});
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!caseId) return;
    setLoading(true);
    try {
      const res = await specialistReviewAPI.getRoadmap(caseId);
      setSteps(res.steps);
      setDecisions(Object.fromEntries(res.steps.map((s) => [s.step_id, { decision: 'approve' }])));
    } catch {
      setError('Failed to load roadmap.');
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => { void load(); }, [load]);

  const allApproved = useMemo(
    () => steps.length > 0 && steps.every((s) => decisions[s.step_id]?.decision === 'approve'),
    [steps, decisions],
  );

  const submit = async (decision: 'approved' | 'rejected') => {
    if (!caseId) return;
    setSaving(true);
    setError(null);
    try {
      const items = steps.map((s) => {
        const d = decisions[s.step_id];
        return {
          step_id: s.step_id,
          decision: d.decision,
          reason_code: d.reason_code,
          original_step: s,
          edited_step: d.edited,
        };
      });
      const res = await specialistReviewAPI.submit(caseId, { decision, notes, items });
      setDone(res.released_to_user ? 'Roadmap released to user.' : 'Submitted; re-generation requested.');
    } catch {
      setError('Submit failed.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <AdminLayout title="Specialist review" subtitle={`Case ${caseId ?? ''}`}>
      {error && <Alert variant="error" title="Error">{error}</Alert>}
      {done && <Alert variant="success" title="Done">{done}</Alert>}
      {loading ? (
        <Card padding="lg">Loading roadmap…</Card>
      ) : (
        <div className="space-y-4">
          {steps.map((s) => (
            <RoadmapStepDiff
              key={s.step_id}
              step={s}
              value={decisions[s.step_id] ?? { decision: 'approve' }}
              onChange={(next) => setDecisions((d) => ({ ...d, [s.step_id]: next }))}
            />
          ))}
          <Card padding="lg">
            <label className="mb-2 block text-sm opacity-80" htmlFor="overall-notes">Overall notes</label>
            <textarea
              id="overall-notes"
              className="mb-3 w-full rounded border border-white/10 bg-transparent p-2"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => void submit('approved')} disabled={saving || !allApproved}>
                {saving ? 'Saving…' : 'Approve roadmap'}
              </Button>
              <Button variant="outline" onClick={() => void submit('rejected')} disabled={saving}>
                Reject roadmap
              </Button>
            </div>
          </Card>
        </div>
      )}
    </AdminLayout>
  );
}
```

> Verify the real `AdminLayout` import path/props (`frontend/src/features/admin/...` or `frontend/src/pages/admin/...`) and match the existing usage in `AdminCatalogQueuePage.tsx`. Adjust if different.

- [ ] **Step 6: Run test + type-check**

Run: `cd frontend && npx vitest run src/pages/__tests__/AdminSpecialistReviewPage.test.tsx`
Expected: PASS (2 tests).
Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 7: Build (pre-push hook parity)**

Run: `cd frontend && npm run build`
Expected: build succeeds (Render auto-deploys `main`, so this must be clean).

- [ ] **Step 8: Commit**

```bash
git add frontend/src/pages/admin/AdminSpecialistReviewPage.tsx frontend/src/pages/__tests__/AdminSpecialistReviewPage.test.tsx frontend/src/api/client.ts frontend/src/navigation/routes.ts frontend/src/App.tsx
git commit -m "feat(P1-02c): /admin/specialist-review/:case_id page (AIQ-633)"
```

---

## Task 4: `POST /api/internal/specialist-review/submit` endpoint (AIQ-634)

**Files:**
- Create: `backend/app/routers/specialist_review.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_specialist_review_router.py`

- [ ] **Step 1: Write the failing endpoint test**

`backend/tests/test_specialist_review_router.py` (in-memory SQLite + ORM, mirroring `test_admin_form_templates_router.py`):

```python
import json
import unittest
import uuid
from unittest import mock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import models
from backend.app.routers import specialist_review as sr


SCHEMA_TABLES = [models.SpecialistReviewEvent, models.RoadmapReviewStatus]


class SpecialistReviewRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        models.Base.metadata.create_all(self.engine, tables=[t.__table__ for t in SCHEMA_TABLES])
        self.Session = sessionmaker(bind=self.engine)
        self.sl_patch = mock.patch.object(sr, "SessionLocal", self.Session)
        self.sl_patch.start()
        self.addCleanup(self.sl_patch.stop)
        self.user = {"id": "admin-1", "is_admin": True, "role": "ADMIN"}

    def _body(self, decision, items):
        return sr.SubmitBody(case_id="case-1", decision=decision, notes="n", items=items)

    def test_full_approval_releases_to_user(self):
        items = [sr.ReviewItem(step_id="s1", decision="approve", original_step={"title": "A"})]
        res = sr.submit_review(body=self._body("approved", items), user=self.user)
        self.assertTrue(res["released_to_user"])
        self.assertFalse(res["regeneration_requested"])
        with self.Session() as db:
            self.assertEqual(db.query(models.SpecialistReviewEvent).count(), 1)
            status = db.get(models.RoadmapReviewStatus, "case-1")
            self.assertTrue(status.released_to_user)

    def test_rejection_requests_regeneration(self):
        items = [sr.ReviewItem(step_id="s1", decision="reject", reason_code="WRONG_PATHWAY",
                               original_step={"title": "A"})]
        res = sr.submit_review(body=self._body("rejected", items), user=self.user)
        self.assertFalse(res["released_to_user"])
        self.assertTrue(res["regeneration_requested"])

    def test_bad_reason_code_raises_422(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            sr.ReviewItem(step_id="s1", decision="reject", reason_code="NOPE", original_step={})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && RELOPASS_DISABLE_RATE_LIMITS=1 pytest tests/test_specialist_review_router.py -v`
Expected: FAIL — `ModuleNotFoundError: backend.app.routers.specialist_review`.

- [ ] **Step 3: Implement the router**

`backend/app/routers/specialist_review.py`:

```python
import json
import uuid
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func

from ..auth_deps import require_admin
from ..db import SessionLocal
from ..models import RoadmapReviewStatus, SpecialistReviewEvent

router = APIRouter(prefix="/api/internal/specialist-review", tags=["specialist-review"])

REASON_CODES = {"WRONG_PATHWAY", "OUTDATED_RULE", "MISSING_DEPENDENCY", "INCORRECT_FORM"}


class ReviewItem(BaseModel):
    step_id: str
    decision: Literal["approve", "reject", "edit"]
    reason_code: Optional[Literal["WRONG_PATHWAY", "OUTDATED_RULE", "MISSING_DEPENDENCY", "INCORRECT_FORM"]] = None
    original_step: Dict[str, Any]
    edited_step: Optional[Dict[str, Any]] = None


class SubmitBody(BaseModel):
    case_id: str
    decision: Literal["approved", "rejected"]
    notes: Optional[str] = None
    items: List[ReviewItem]


@router.get("/{case_id}")
def get_roadmap(case_id: str, user: Dict[str, Any] = Depends(require_admin)):
    # P1-01 dependency: AI-generated steps source. Until P1-01 persists them, derive on the fly.
    from ..services.roadmap_builder import derive_roadmap  # local import avoids cycle
    derived = derive_roadmap({"case_id": case_id})
    steps = derived.get("steps", []) if isinstance(derived, dict) else []
    return {"case_id": case_id, "steps": steps}


@router.post("/submit")
def submit_review(body: SubmitBody, user: Dict[str, Any] = Depends(require_admin)):
    reviewer_id = str(user.get("id", ""))
    any_reject = any(it.decision == "reject" for it in body.items)
    all_approve = all(it.decision == "approve" for it in body.items) and len(body.items) > 0
    released = body.decision == "approved" and all_approve and not any_reject
    regen = body.decision == "rejected" or any_reject

    with SessionLocal() as db:
        for it in body.items:
            db.add(
                SpecialistReviewEvent(
                    id=str(uuid.uuid4()),
                    case_id=body.case_id,
                    step_id=it.step_id,
                    reviewer_id=reviewer_id,
                    action=it.decision,
                    reason_code=it.reason_code,
                    original_step_json=json.dumps(it.original_step),
                    edited_step_json=json.dumps(it.edited_step) if it.edited_step else None,
                )
            )
        status = db.get(RoadmapReviewStatus, body.case_id)
        if status is None:
            status = RoadmapReviewStatus(case_id=body.case_id)
            db.add(status)
        status.released_to_user = released
        status.regeneration_requested = regen
        status.reviewer_id = reviewer_id
        status.notes = body.notes
        status.updated_at = func.now()
        db.commit()

    return {"released_to_user": released, "regeneration_requested": regen}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && RELOPASS_DISABLE_RATE_LIMITS=1 pytest tests/test_specialist_review_router.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Register the router**

In `backend/app/main.py`: add `specialist_review` to the `from .routers import (...)` block, and inside `create_app()` add:

```python
app.include_router(specialist_review.router)
```

- [ ] **Step 6: Smoke-test wiring + full suite**

Run: `cd backend && RELOPASS_DISABLE_RATE_LIMITS=1 pytest tests/test_specialist_review_router.py -v && python -c "from backend.app.main import create_app; create_app()"`
Expected: tests pass; app builds with the router mounted (no import error).

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/specialist_review.py backend/app/main.py backend/tests/test_specialist_review_router.py
git commit -m "feat(P1-02d): specialist-review submit endpoint (AIQ-634)"
```

---

## Validation Criteria (from Notion) → where satisfied

| Criterion | Task |
|-----------|------|
| RLS scopes events to admin; INSERT+SELECT round-trip; UPDATE/DELETE denied (AIQ-631) | Task 1 Steps 1–3 |
| Reason-code dropdown matches enum exactly; renders empty + pre-filled (AIQ-632) | Task 2 Steps 2–5 |
| Specialist reviews France→Norway roadmap end-to-end; rows land in `specialist_review_events` (AIQ-633) | Task 3 + Task 4 |
| Bad reason_code → 422; full approval → `released_to_user=true`; rejection → regeneration (AIQ-634) | Task 4 Steps 1, 3 |
| Specialist can approve a roadmap in <10 min; corrections stored with reason codes (AIQ-196) | All tasks |

## Post-implementation (Notion bookkeeping)

After all four tasks ship + CI/canary clean:
- Set AIQ-631 / 632 / 633 / 634 → `Done`.
- Set AIQ-196 → **Archive** (NOT "Done" — its Execution Notes mandate archive-once-children-ship).
- Per project memory, the Notion MCP may not reach the AI Work Queue; if status updates fail, emit Execution Notes for manual paste instead.

## Self-review notes

- **Spec coverage**: every AIQ-631/632/633/634 expected-output bullet maps to a task above; the `released_to_user`/regeneration gap (absent in the schema) is closed by the `roadmap_review_status` table.
- **Type consistency**: `AiStep`/`StepReviewValue`/`ReasonCode`/`ReviewDecision` are defined once (Task 2) and imported by Task 3; `ReviewItem`/`SubmitBody` field names match between the frontend `submit()` payload and the backend Pydantic models.
- **Open dependency**: the GET data source assumes P1-01's AI step output; if P1-01 lands a different persistence shape, only Task 4 Step 3's `get_roadmap` body changes.
