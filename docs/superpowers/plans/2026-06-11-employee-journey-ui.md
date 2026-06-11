# Employee Journey UI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved "E / ReloPass Native" employee-journey redesign as real React/antigravity code, starting with a tested, shippable foundation-component library and the first live screen (the Intake wizard step-rail), then rolling out the remaining screens.

**Architecture:** Add a small set of reusable presentational components to the antigravity design system (the building blocks every redesigned screen shares), each built test-first in isolation. Then wire them into live screens one at a time. Pure presentational components take data + callbacks as props; data fetching stays in the existing `employeeAPI`/`cases` wrappers. No backend changes in this plan (two backend fixes are tracked separately as [ROADMAP-DYN] and [ASK-ONCE]).

**Tech Stack:** React 18, TypeScript (strict), Tailwind 3 (navy/accent scales already registered), Vite + Vitest + @testing-library/react (jsdom), React Router 6. New dependency: `flag-icons` (CSS flag library).

**Design source of truth:** `docs/design/employee-journey-ui-brief.md` + the HTML mockups in `~/.gstack/projects/rlecomte1929-rolec/designs/intake-wizard-20260611/`.

---

## Conventions (read before starting)

- **antigravity components are NAMED exports** via the barrel `frontend/src/components/antigravity/index.ts`. New components go in `frontend/src/components/antigravity/<Name>.tsx` and get added to the barrel.
- **Tests** live next to the component as `<Name>.test.tsx`, run with `npm --prefix frontend run test` (`vitest run`, jsdom, `globals: true`). No setup file exists — each test imports matchers itself: `import '@testing-library/jest-dom/vitest'`. No custom render wrapper; use `render()` from `@testing-library/react` directly.
- **Palette:** use Tailwind tokens `navy-800` (`#0b2b43`, primary), `accent-500` (`#1f8e8b`, teal), `navy-50` (`#f0f5fa`), borders `#e2e8f0`. NO purple/coral/cream.
- **Type-check gate:** `cd frontend && npx tsc --noEmit` must pass before every commit (strict mode, `noUnusedLocals`, `noUnusedParameters`).
- **Commit cadence:** commit after each task (Romain's preference: small, revertible steps).
- **Branch:** create `feat/employee-journey-ui-foundation` off `main` before Task 1.

---

## File Structure (whole journey, per-PR)

**PR 1 — Foundation components** (this plan, Phase 1):
- Create `frontend/src/components/antigravity/CountryFlag.tsx` — flag + accessible country name.
- Create `frontend/src/lib/countryFlagCode.ts` — country-name/demonym → ISO 3166-1 alpha-2.
- Create `frontend/src/components/antigravity/StatusPill.tsx` — journey status pill (done/in-progress/upcoming/blocked/action/ready/submitted/in-review).
- Create `frontend/src/components/antigravity/PhaseContextBar.tsx` — the 3-phase "where am I" bar.
- Create `frontend/src/components/antigravity/StepRail.tsx` — horizontal wizard step rail.
- Create `frontend/src/components/antigravity/SegmentedOptionCards.tsx` — selectable option cards.
- Create `frontend/src/components/antigravity/AutosaveChip.tsx` — "Draft saved" status chip.
- Create `frontend/src/components/antigravity/ConfirmFromIntake.tsx` — "From your intake — confirm" card (ask-once pattern).
- Modify `frontend/src/components/antigravity/index.ts` — barrel exports for all of the above.
- Modify `frontend/package.json` — add `flag-icons`.
- Modify `frontend/src/index.css` — import `flag-icons` CSS.
- Tests: one `*.test.tsx` per component + `countryFlagCode.test.ts`.

**PR 2 — Intake wizard step-rail** (this plan, Phase 2):
- Create `frontend/src/features/employee-journey/WizardStepRail.tsx` — adapts the wizard's `stepCompletion` to `StepRail`.
- Modify `frontend/src/pages/employee/CaseWizardPage.tsx` — swap the vertical `WizardSidebar` for the horizontal `WizardStepRail`; add `AutosaveChip`.
- Test: `frontend/src/features/employee-journey/WizardStepRail.test.tsx`.

**PR 3+ — Screen rollout** (separate plans, see "Roadmap" at the end): Dashboard journey-home, Services & Policy (+ empty), Roadmap (+ empty/light), Dossier & Forms, Form Editor, Immigration checklist + confirm, Rich Profile.

---

## Phase 1 — Foundation components

### Task 1: CountryFlag + countryFlagCode util

**Files:**
- Create: `frontend/src/lib/countryFlagCode.ts`
- Create: `frontend/src/lib/countryFlagCode.test.ts`
- Create: `frontend/src/components/antigravity/CountryFlag.tsx`
- Create: `frontend/src/components/antigravity/CountryFlag.test.tsx`
- Modify: `frontend/package.json` (add `flag-icons`), `frontend/src/index.css`, `frontend/src/components/antigravity/index.ts`

- [ ] **Step 1: Add the flag-icons dependency**

Run: `npm --prefix frontend install flag-icons@7`
Then add to `frontend/src/index.css` directly under the existing `@import url('...Inter...')` line:

```css
@import 'flag-icons/css/flag-icons.min.css';
```

- [ ] **Step 2: Write the failing test for countryFlagCode**

Create `frontend/src/lib/countryFlagCode.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { countryFlagCode } from './countryFlagCode';

describe('countryFlagCode', () => {
  it('maps country names to ISO alpha-2 (lowercase)', () => {
    expect(countryFlagCode('Germany')).toBe('de');
    expect(countryFlagCode('France')).toBe('fr');
    expect(countryFlagCode('India')).toBe('in');
  });
  it('maps demonyms (nationalities) to ISO alpha-2', () => {
    expect(countryFlagCode('German')).toBe('de');
    expect(countryFlagCode('Indian')).toBe('in');
    expect(countryFlagCode('Polish')).toBe('pl');
  });
  it('accepts an existing ISO alpha-2 code', () => {
    expect(countryFlagCode('DE')).toBe('de');
  });
  it('is case- and whitespace-insensitive', () => {
    expect(countryFlagCode('  french ')).toBe('fr');
  });
  it('returns null for unknown input', () => {
    expect(countryFlagCode('Atlantis')).toBeNull();
    expect(countryFlagCode('')).toBeNull();
  });
});
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `npm --prefix frontend run test -- countryFlagCode`
Expected: FAIL — "Cannot find module './countryFlagCode'".

- [ ] **Step 4: Implement countryFlagCode**

Create `frontend/src/lib/countryFlagCode.ts`:

```typescript
// Country name / demonym (nationality) -> ISO 3166-1 alpha-2 (lowercase, for flag-icons).
// Extend as new corridors are supported. Unknown input returns null (render no flag).
const MAP: Record<string, string> = {
  germany: 'de', german: 'de',
  france: 'fr', french: 'fr',
  india: 'in', indian: 'in',
  poland: 'pl', polish: 'pl',
  spain: 'es', spanish: 'es',
  italy: 'it', italian: 'it',
  netherlands: 'nl', dutch: 'nl',
  'united states': 'us', usa: 'us', american: 'us',
  'united kingdom': 'gb', uk: 'gb', british: 'gb',
  japan: 'jp', japanese: 'jp',
  norway: 'no', norwegian: 'no',
  switzerland: 'ch', swiss: 'ch',
  'united arab emirates': 'ae', uae: 'ae', emirati: 'ae',
  singapore: 'sg', singaporean: 'sg',
  brazil: 'br', brazilian: 'br',
  canada: 'ca', canadian: 'ca',
  ireland: 'ie', irish: 'ie',
  portugal: 'pt', portuguese: 'pt',
  sweden: 'se', swedish: 'se',
};

const ISO2 = new Set(Object.values(MAP));

export function countryFlagCode(input: string | null | undefined): string | null {
  if (!input) return null;
  const key = input.trim().toLowerCase();
  if (!key) return null;
  if (key.length === 2 && ISO2.has(key)) return key;
  return MAP[key] ?? null;
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `npm --prefix frontend run test -- countryFlagCode`
Expected: PASS (5 tests).

- [ ] **Step 6: Write the failing test for CountryFlag**

Create `frontend/src/components/antigravity/CountryFlag.test.tsx`:

```typescript
import '@testing-library/jest-dom/vitest';
import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { CountryFlag } from './CountryFlag';

afterEach(cleanup);

describe('CountryFlag', () => {
  it('renders the flag glyph plus the visible country label', () => {
    const { container } = render(<CountryFlag country="Indian" />);
    expect(screen.getByText('Indian')).toBeInTheDocument();
    expect(container.querySelector('.fi.fi-in')).toBeTruthy();
  });
  it('marks the flag glyph as decorative (aria-hidden)', () => {
    const { container } = render(<CountryFlag country="Germany" />);
    expect(container.querySelector('.fi.fi-de')?.getAttribute('aria-hidden')).toBe('true');
  });
  it('renders just the label when the country is unknown', () => {
    const { container } = render(<CountryFlag country="Atlantis" />);
    expect(screen.getByText('Atlantis')).toBeInTheDocument();
    expect(container.querySelector('.fi')).toBeNull();
  });
});
```

- [ ] **Step 7: Run the test to verify it fails**

Run: `npm --prefix frontend run test -- CountryFlag`
Expected: FAIL — "Cannot find module './CountryFlag'".

- [ ] **Step 8: Implement CountryFlag**

Create `frontend/src/components/antigravity/CountryFlag.tsx`:

```typescript
import React from 'react';
import { countryFlagCode } from '../../lib/countryFlagCode';

interface CountryFlagProps {
  /** Country name or demonym, e.g. "Germany" or "German". Doubles as the accessible label. */
  country: string;
  /** Override the resolved label (e.g. show "Germany" while the flag came from "German"). */
  label?: string;
  className?: string;
}

/** Flag glyph (decorative) + the country name as the accessible label. */
export const CountryFlag: React.FC<CountryFlagProps> = ({ country, label, className = '' }) => {
  const code = countryFlagCode(country);
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      {code && <span className={`fi fi-${code} rounded-sm`} aria-hidden="true" />}
      <span>{label ?? country}</span>
    </span>
  );
};
```

- [ ] **Step 9: Run the test to verify it passes**

Run: `npm --prefix frontend run test -- CountryFlag`
Expected: PASS (3 tests).

- [ ] **Step 10: Export from the barrel and type-check**

Add to `frontend/src/components/antigravity/index.ts`:

```typescript
export { CountryFlag } from './CountryFlag';
```

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 11: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/index.css \
  frontend/src/lib/countryFlagCode.ts frontend/src/lib/countryFlagCode.test.ts \
  frontend/src/components/antigravity/CountryFlag.tsx frontend/src/components/antigravity/CountryFlag.test.tsx \
  frontend/src/components/antigravity/index.ts
git commit -m "feat(antigravity): CountryFlag + countryFlagCode (flag-icons)"
```

---

### Task 2: StatusPill

**Files:**
- Create: `frontend/src/components/antigravity/StatusPill.tsx`
- Create: `frontend/src/components/antigravity/StatusPill.test.tsx`
- Modify: `frontend/src/components/antigravity/index.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/antigravity/StatusPill.test.tsx`:

```typescript
import '@testing-library/jest-dom/vitest';
import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { StatusPill } from './StatusPill';

afterEach(cleanup);

describe('StatusPill', () => {
  it('renders the provided label', () => {
    render(<StatusPill status="in-progress">In progress</StatusPill>);
    expect(screen.getByText('In progress')).toBeInTheDocument();
  });
  it('applies the teal treatment for in-progress', () => {
    render(<StatusPill status="in-progress">In progress</StatusPill>);
    expect(screen.getByText('In progress').className).toContain('text-accent-600');
  });
  it('applies the amber treatment for action', () => {
    render(<StatusPill status="action">Action needed</StatusPill>);
    expect(screen.getByText('Action needed').className).toContain('#7a5e2a');
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm --prefix frontend run test -- StatusPill`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement StatusPill**

Create `frontend/src/components/antigravity/StatusPill.tsx`:

```typescript
import React from 'react';

export type JourneyStatus =
  | 'done' | 'in-progress' | 'upcoming' | 'blocked'
  | 'action' | 'ready' | 'submitted' | 'in-review';

const STYLES: Record<JourneyStatus, string> = {
  done:          'bg-navy-50 text-navy-800',
  'in-progress': 'bg-accent-50 text-accent-600',
  upcoming:      'bg-[#f3f4f6] text-[#6b7280]',
  blocked:       'bg-[#f4efe5] text-[#7a5e2a]',
  action:        'bg-[#f4efe5] text-[#7a5e2a]',
  ready:         'bg-accent-50 text-accent-600',
  submitted:     'bg-navy-50 text-navy-800',
  'in-review':   'bg-[#f3f4f6] text-[#374151]',
};

interface StatusPillProps {
  status: JourneyStatus;
  children: React.ReactNode;
  className?: string;
}

export const StatusPill: React.FC<StatusPillProps> = ({ status, children, className = '' }) => (
  <span
    className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11.5px] font-semibold ${STYLES[status]} ${className}`}
  >
    {children}
  </span>
);
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm --prefix frontend run test -- StatusPill`
Expected: PASS (3 tests).

- [ ] **Step 5: Export + type-check + commit**

Add `export { StatusPill } from './StatusPill';` and `export type { JourneyStatus } from './StatusPill';` to the barrel.
Run: `cd frontend && npx tsc --noEmit` (expect clean), then:

```bash
git add frontend/src/components/antigravity/StatusPill.tsx frontend/src/components/antigravity/StatusPill.test.tsx frontend/src/components/antigravity/index.ts
git commit -m "feat(antigravity): StatusPill for journey statuses"
```

---

### Task 3: PhaseContextBar (the 3-phase "where am I")

**Files:**
- Create: `frontend/src/components/antigravity/PhaseContextBar.tsx`
- Create: `frontend/src/components/antigravity/PhaseContextBar.test.tsx`
- Modify: `frontend/src/components/antigravity/index.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/antigravity/PhaseContextBar.test.tsx`:

```typescript
import '@testing-library/jest-dom/vitest';
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { PhaseContextBar } from './PhaseContextBar';

afterEach(cleanup);

const PHASES = [
  { key: 'intake', label: 'Intake', status: 'done' as const },
  { key: 'services', label: 'Services & policy', status: 'current' as const },
  { key: 'roadmap', label: 'Roadmap', status: 'upcoming' as const },
];

describe('PhaseContextBar', () => {
  it('renders all phase labels', () => {
    render(<PhaseContextBar phases={PHASES} />);
    expect(screen.getByText('Intake')).toBeInTheDocument();
    expect(screen.getByText('Services & policy')).toBeInTheDocument();
    expect(screen.getByText('Roadmap')).toBeInTheDocument();
  });
  it('marks the current phase with aria-current', () => {
    render(<PhaseContextBar phases={PHASES} />);
    expect(screen.getByText('Services & policy').closest('[aria-current="step"]')).toBeTruthy();
  });
  it('calls onSelect with the phase key when a done phase is clicked', () => {
    const onSelect = vi.fn();
    render(<PhaseContextBar phases={PHASES} onSelect={onSelect} />);
    fireEvent.click(screen.getByText('Intake'));
    expect(onSelect).toHaveBeenCalledWith('intake');
  });
  it('does NOT call onSelect for an upcoming phase', () => {
    const onSelect = vi.fn();
    render(<PhaseContextBar phases={PHASES} onSelect={onSelect} />);
    fireEvent.click(screen.getByText('Roadmap'));
    expect(onSelect).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm --prefix frontend run test -- PhaseContextBar`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement PhaseContextBar**

Create `frontend/src/components/antigravity/PhaseContextBar.tsx`:

```typescript
import React from 'react';

export type PhaseStatus = 'done' | 'current' | 'upcoming';
export interface Phase {
  key: string;
  label: string;
  status: PhaseStatus;
}

interface PhaseContextBarProps {
  phases: Phase[];
  /** Fired when a navigable (done) phase is selected. Upcoming phases are not clickable. */
  onSelect?: (key: string) => void;
  className?: string;
}

export const PhaseContextBar: React.FC<PhaseContextBarProps> = ({ phases, onSelect, className = '' }) => (
  <nav
    aria-label="Relocation phases"
    className={`flex items-center gap-3 rounded-xl border border-[#e2e8f0] bg-white px-5 py-3 shadow-sm ${className}`}
  >
    {phases.map((p, i) => {
      const navigable = p.status === 'done' && Boolean(onSelect);
      const dotClass =
        p.status === 'done' ? 'bg-navy-800 text-white'
        : p.status === 'current' ? 'ring-2 ring-accent-500 text-accent-600 bg-white'
        : 'border border-[#e2e8f0] text-[#9aa6b2] bg-white';
      return (
        <React.Fragment key={p.key}>
          {i > 0 && <span className="h-px w-6 flex-none bg-[#e2e8f0]" aria-hidden="true" />}
          <button
            type="button"
            disabled={!navigable}
            aria-current={p.status === 'current' ? 'step' : undefined}
            onClick={() => navigable && onSelect?.(p.key)}
            className={`inline-flex items-center gap-2 rounded-lg px-2 py-1 text-[13px] font-semibold ${navigable ? 'hover:bg-navy-50 cursor-pointer' : 'cursor-default'} ${p.status === 'upcoming' ? 'text-[#9aa6b2]' : 'text-navy-800'}`}
          >
            <span className={`flex h-6 w-6 items-center justify-center rounded-full text-[11px] ${dotClass}`}>
              {p.status === 'done' ? '✓' : i + 1}
            </span>
            {p.label}
          </button>
        </React.Fragment>
      );
    })}
  </nav>
);
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm --prefix frontend run test -- PhaseContextBar`
Expected: PASS (4 tests).

- [ ] **Step 5: Export + type-check + commit**

Add `export { PhaseContextBar } from './PhaseContextBar';` and `export type { Phase, PhaseStatus } from './PhaseContextBar';` to the barrel.
Run `cd frontend && npx tsc --noEmit` (expect clean), then:

```bash
git add frontend/src/components/antigravity/PhaseContextBar.tsx frontend/src/components/antigravity/PhaseContextBar.test.tsx frontend/src/components/antigravity/index.ts
git commit -m "feat(antigravity): PhaseContextBar (3-phase journey nav)"
```

---

### Task 4: StepRail (horizontal wizard steps)

**Files:**
- Create: `frontend/src/components/antigravity/StepRail.tsx`
- Create: `frontend/src/components/antigravity/StepRail.test.tsx`
- Modify: `frontend/src/components/antigravity/index.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/antigravity/StepRail.test.tsx`:

```typescript
import '@testing-library/jest-dom/vitest';
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { StepRail } from './StepRail';

afterEach(cleanup);

const STEPS = [
  { label: 'Your move', status: 'done' as const },
  { label: 'Your household', status: 'current' as const },
  { label: 'Services', status: 'upcoming' as const },
];

describe('StepRail', () => {
  it('renders all step labels and the step counter', () => {
    render(<StepRail steps={STEPS} />);
    expect(screen.getByText('Your move')).toBeInTheDocument();
    expect(screen.getByText('Your household')).toBeInTheDocument();
    expect(screen.getByText(/Step 2 of 3/i)).toBeInTheDocument();
  });
  it('invokes onSelect with the index for a done step', () => {
    const onSelect = vi.fn();
    render(<StepRail steps={STEPS} onSelect={onSelect} />);
    fireEvent.click(screen.getByText('Your move'));
    expect(onSelect).toHaveBeenCalledWith(0);
  });
  it('does not invoke onSelect for an upcoming step', () => {
    const onSelect = vi.fn();
    render(<StepRail steps={STEPS} onSelect={onSelect} />);
    fireEvent.click(screen.getByText('Services'));
    expect(onSelect).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm --prefix frontend run test -- StepRail`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement StepRail**

Create `frontend/src/components/antigravity/StepRail.tsx`:

```typescript
import React from 'react';

export type StepStatus = 'done' | 'current' | 'upcoming';
export interface RailStep {
  label: string;
  status: StepStatus;
  icon?: React.ReactNode;
}

interface StepRailProps {
  steps: RailStep[];
  /** Fired when a done step is clicked (navigation back). Current/upcoming are not navigable. */
  onSelect?: (index: number) => void;
  className?: string;
}

export const StepRail: React.FC<StepRailProps> = ({ steps, onSelect, className = '' }) => {
  const currentIndex = steps.findIndex((s) => s.status === 'current');
  return (
    <section className={`rounded-xl border border-[#e2e8f0] bg-white px-7 py-5 shadow-sm ${className}`}>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-[13px] font-semibold uppercase tracking-wider text-[#6b7280]">Your relocation plan</h2>
        <span className="text-[13px] font-medium text-[#6b7280]">
          Step <span className="font-semibold text-navy-800">{currentIndex + 1}</span> of {steps.length}
        </span>
      </div>
      <ol className="grid" style={{ gridTemplateColumns: `repeat(${steps.length}, minmax(0, 1fr))` }}>
        {steps.map((s, i) => {
          const navigable = s.status === 'done' && Boolean(onSelect);
          const dot =
            s.status === 'done' ? 'bg-navy-800 text-white'
            : s.status === 'current' ? 'ring-4 ring-accent-500 text-accent-600 bg-white'
            : 'border-2 border-[#e2e8f0] text-[#9aa6b2] bg-white';
          return (
            <li key={s.label} className="flex flex-col items-center text-center">
              <button
                type="button"
                disabled={!navigable}
                aria-current={s.status === 'current' ? 'step' : undefined}
                onClick={() => navigable && onSelect?.(i)}
                className={`flex flex-col items-center gap-2 ${navigable ? 'cursor-pointer' : 'cursor-default'}`}
              >
                <span className={`flex h-10 w-10 items-center justify-center rounded-full text-[13px] ${dot}`}>
                  {s.status === 'done' ? '✓' : s.icon ?? i + 1}
                </span>
                <span className={`text-[13px] font-semibold ${s.status === 'upcoming' ? 'text-[#6b7280]' : 'text-navy-800'}`}>
                  {s.label}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </section>
  );
};
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm --prefix frontend run test -- StepRail`
Expected: PASS (3 tests).

- [ ] **Step 5: Export + type-check + commit**

Add `export { StepRail } from './StepRail';` and `export type { RailStep, StepStatus } from './StepRail';` to the barrel.
Run `cd frontend && npx tsc --noEmit` (expect clean), then:

```bash
git add frontend/src/components/antigravity/StepRail.tsx frontend/src/components/antigravity/StepRail.test.tsx frontend/src/components/antigravity/index.ts
git commit -m "feat(antigravity): StepRail (horizontal wizard steps)"
```

---

### Task 5: SegmentedOptionCards

**Files:**
- Create: `frontend/src/components/antigravity/SegmentedOptionCards.tsx`
- Create: `frontend/src/components/antigravity/SegmentedOptionCards.test.tsx`
- Modify: `frontend/src/components/antigravity/index.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/antigravity/SegmentedOptionCards.test.tsx`:

```typescript
import '@testing-library/jest-dom/vitest';
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { SegmentedOptionCards } from './SegmentedOptionCards';

afterEach(cleanup);

const OPTIONS = [
  { value: 'solo', label: 'Just me' },
  { value: 'partner', label: 'My partner' },
  { value: 'family', label: 'Partner & children' },
];

describe('SegmentedOptionCards', () => {
  it('renders every option label', () => {
    render(<SegmentedOptionCards options={OPTIONS} value="family" onChange={() => {}} />);
    OPTIONS.forEach((o) => expect(screen.getByText(o.label)).toBeInTheDocument());
  });
  it('marks the selected option with aria-pressed', () => {
    render(<SegmentedOptionCards options={OPTIONS} value="family" onChange={() => {}} />);
    expect(screen.getByRole('button', { name: /Partner & children/ }).getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByRole('button', { name: /Just me/ }).getAttribute('aria-pressed')).toBe('false');
  });
  it('calls onChange with the value when an option is clicked', () => {
    const onChange = vi.fn();
    render(<SegmentedOptionCards options={OPTIONS} value="family" onChange={onChange} />);
    fireEvent.click(screen.getByRole('button', { name: /My partner/ }));
    expect(onChange).toHaveBeenCalledWith('partner');
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm --prefix frontend run test -- SegmentedOptionCards`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement SegmentedOptionCards**

Create `frontend/src/components/antigravity/SegmentedOptionCards.tsx`:

```typescript
import React from 'react';

export interface SegmentedOption {
  value: string;
  label: string;
  description?: string;
  icon?: React.ReactNode;
}

interface SegmentedOptionCardsProps {
  options: SegmentedOption[];
  value: string;
  onChange: (value: string) => void;
  className?: string;
}

export const SegmentedOptionCards: React.FC<SegmentedOptionCardsProps> = ({ options, value, onChange, className = '' }) => (
  <div
    className={`grid gap-3 ${className}`}
    style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }}
  >
    {options.map((o) => {
      const selected = o.value === value;
      return (
        <button
          key={o.value}
          type="button"
          aria-pressed={selected}
          onClick={() => onChange(o.value)}
          className={`relative flex flex-col items-start rounded-xl px-4 py-4 text-left transition ${
            selected
              ? 'border-2 border-navy-800 bg-navy-50 shadow-sm'
              : 'border border-[#e2e8f0] bg-white hover:border-navy-600 hover:bg-navy-50'
          }`}
        >
          {selected && (
            <span className="absolute right-3 top-3 flex h-6 w-6 items-center justify-center rounded-full bg-accent-500 text-white" aria-hidden="true">✓</span>
          )}
          {o.icon && <span className="mb-2 text-navy-700">{o.icon}</span>}
          <span className="text-[14px] font-semibold text-navy-800">{o.label}</span>
          {o.description && <span className="mt-0.5 text-[12px] text-[#6b7280]">{o.description}</span>}
        </button>
      );
    })}
  </div>
);
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm --prefix frontend run test -- SegmentedOptionCards`
Expected: PASS (3 tests).

- [ ] **Step 5: Export + type-check + commit**

Add `export { SegmentedOptionCards } from './SegmentedOptionCards';` and `export type { SegmentedOption } from './SegmentedOptionCards';` to the barrel.
Run `cd frontend && npx tsc --noEmit` (expect clean), then:

```bash
git add frontend/src/components/antigravity/SegmentedOptionCards.tsx frontend/src/components/antigravity/SegmentedOptionCards.test.tsx frontend/src/components/antigravity/index.ts
git commit -m "feat(antigravity): SegmentedOptionCards"
```

---

### Task 6: AutosaveChip

**Files:**
- Create: `frontend/src/components/antigravity/AutosaveChip.tsx`
- Create: `frontend/src/components/antigravity/AutosaveChip.test.tsx`
- Modify: `frontend/src/components/antigravity/index.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/antigravity/AutosaveChip.test.tsx`:

```typescript
import '@testing-library/jest-dom/vitest';
import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { AutosaveChip } from './AutosaveChip';

afterEach(cleanup);

describe('AutosaveChip', () => {
  it('shows "Draft saved" when saved', () => {
    render(<AutosaveChip state="saved" />);
    expect(screen.getByText('Draft saved')).toBeInTheDocument();
  });
  it('shows "Saving…" when saving', () => {
    render(<AutosaveChip state="saving" />);
    expect(screen.getByText(/Saving/)).toBeInTheDocument();
  });
  it('shows an error message when state is error', () => {
    render(<AutosaveChip state="error" />);
    expect(screen.getByText(/Couldn.t save/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm --prefix frontend run test -- AutosaveChip`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement AutosaveChip**

Create `frontend/src/components/antigravity/AutosaveChip.tsx`:

```typescript
import React from 'react';

interface AutosaveChipProps {
  state: 'saved' | 'saving' | 'error';
  className?: string;
}

const CONTENT: Record<AutosaveChipProps['state'], { text: string; cls: string }> = {
  saved:  { text: 'Draft saved', cls: 'border-accent-500/25 bg-accent-50 text-accent-600' },
  saving: { text: 'Saving…',     cls: 'border-[#e2e8f0] bg-[#f3f4f6] text-[#6b7280]' },
  error:  { text: "Couldn't save — retrying", cls: 'border-[#e6c9c9] bg-[#f7eeee] text-[#7a2a2a]' },
};

export const AutosaveChip: React.FC<AutosaveChipProps> = ({ state, className = '' }) => {
  const { text, cls } = CONTENT[state];
  return (
    <span
      role="status"
      aria-live="polite"
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[13px] font-semibold ${cls} ${className}`}
    >
      {state === 'saved' && <span aria-hidden="true">✓</span>}
      {text}
    </span>
  );
};
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm --prefix frontend run test -- AutosaveChip`
Expected: PASS (3 tests).

- [ ] **Step 5: Export + type-check + commit**

Add `export { AutosaveChip } from './AutosaveChip';` to the barrel.
Run `cd frontend && npx tsc --noEmit` (expect clean), then:

```bash
git add frontend/src/components/antigravity/AutosaveChip.tsx frontend/src/components/antigravity/AutosaveChip.test.tsx frontend/src/components/antigravity/index.ts
git commit -m "feat(antigravity): AutosaveChip"
```

---

### Task 7: ConfirmFromIntake (ask-once pattern)

**Files:**
- Create: `frontend/src/components/antigravity/ConfirmFromIntake.tsx`
- Create: `frontend/src/components/antigravity/ConfirmFromIntake.test.tsx`
- Modify: `frontend/src/components/antigravity/index.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/antigravity/ConfirmFromIntake.test.tsx`:

```typescript
import '@testing-library/jest-dom/vitest';
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { ConfirmFromIntake } from './ConfirmFromIntake';

afterEach(cleanup);

const ROWS = [
  { label: 'Legal name', value: 'Priya Nair' },
  { label: 'Nationality', value: 'Indian', flag: 'Indian' },
];

describe('ConfirmFromIntake', () => {
  it('renders each carried-over field as a read-only value (no inputs)', () => {
    const { container } = render(<ConfirmFromIntake title="From your intake" rows={ROWS} onConfirmAll={() => {}} />);
    expect(screen.getByText('Priya Nair')).toBeInTheDocument();
    expect(screen.getByText('Indian')).toBeInTheDocument();
    expect(container.querySelector('input')).toBeNull(); // ask-once: never a blank input
  });
  it('renders a flag when a row provides one', () => {
    const { container } = render(<ConfirmFromIntake title="From your intake" rows={ROWS} onConfirmAll={() => {}} />);
    expect(container.querySelector('.fi.fi-in')).toBeTruthy();
  });
  it('fires onConfirmAll when the confirm button is clicked', () => {
    const onConfirmAll = vi.fn();
    render(<ConfirmFromIntake title="From your intake" rows={ROWS} onConfirmAll={onConfirmAll} />);
    fireEvent.click(screen.getByRole('button', { name: /Confirm all/i }));
    expect(onConfirmAll).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm --prefix frontend run test -- ConfirmFromIntake`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement ConfirmFromIntake**

Create `frontend/src/components/antigravity/ConfirmFromIntake.tsx`:

```typescript
import React from 'react';
import { CountryFlag } from './CountryFlag';
import { Button } from './Button';

export interface ConfirmRow {
  label: string;
  value: string;
  /** If set, render a flag next to the value (country name/demonym). */
  flag?: string;
}

interface ConfirmFromIntakeProps {
  title: string;
  subtitle?: string;
  rows: ConfirmRow[];
  onConfirmAll: () => void;
  onEdit?: () => void;
  className?: string;
}

/** Ask-once: shows already-known fields as read-only confirmable values, never blank inputs. */
export const ConfirmFromIntake: React.FC<ConfirmFromIntakeProps> = ({ title, subtitle, rows, onConfirmAll, onEdit, className = '' }) => (
  <section className={`overflow-hidden rounded-xl border border-[#e2e8f0] bg-white shadow-sm ${className}`}>
    <div className="flex items-start justify-between gap-3 border-b border-[#e2e8f0] bg-accent-50/60 px-6 py-4">
      <div>
        <h3 className="text-[15px] font-bold text-navy-800">{title}</h3>
        {subtitle && <p className="mt-0.5 text-[13px] text-[#6b7280]">{subtitle}</p>}
      </div>
      <span className="inline-flex items-center gap-1.5 rounded-full bg-accent-500/10 px-2.5 py-1 text-[11.5px] font-semibold text-accent-600" aria-hidden="true">Already on file</span>
    </div>
    <dl>
      {rows.map((r) => (
        <div key={r.label} className="flex items-center justify-between gap-4 border-b border-[#e2e8f0] px-6 py-4 last:border-b-0">
          <div>
            <dt className="text-[12px] font-semibold uppercase tracking-wide text-[#9aa6b2]">{r.label}</dt>
            <dd className="mt-1 text-[15px] font-semibold text-navy-800">
              {r.flag ? <CountryFlag country={r.flag} label={r.value} /> : r.value}
            </dd>
          </div>
          <span className="inline-flex items-center gap-1 rounded-full bg-accent-500/10 px-2.5 py-1 text-[11.5px] font-semibold text-accent-600">✓ On file</span>
        </div>
      ))}
    </dl>
    <div className="flex items-center justify-between gap-3 px-6 py-4">
      <p className="text-[12px] text-[#6b7280]">We never ask for the same thing twice — edit once and it updates everywhere.</p>
      <div className="flex items-center gap-3">
        {onEdit && <Button variant="ghost" size="sm" onClick={onEdit}>Edit a detail</Button>}
        <Button variant="primary" size="sm" onClick={onConfirmAll}>Confirm all — these are correct</Button>
      </div>
    </div>
  </section>
);
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm --prefix frontend run test -- ConfirmFromIntake`
Expected: PASS (3 tests).

- [ ] **Step 5: Export + type-check + full suite + commit**

Add `export { ConfirmFromIntake } from './ConfirmFromIntake';` and `export type { ConfirmRow } from './ConfirmFromIntake';` to the barrel.
Run `cd frontend && npx tsc --noEmit` (expect clean) and `npm --prefix frontend run test` (whole suite green), then:

```bash
git add frontend/src/components/antigravity/ConfirmFromIntake.tsx frontend/src/components/antigravity/ConfirmFromIntake.test.tsx frontend/src/components/antigravity/index.ts
git commit -m "feat(antigravity): ConfirmFromIntake (ask-once pattern)"
```

- [ ] **Step 6: Open the PR for Phase 1**

```bash
git push -u origin feat/employee-journey-ui-foundation
gh pr create --title "feat(antigravity): employee-journey foundation components" --body "Adds CountryFlag, StatusPill, PhaseContextBar, StepRail, SegmentedOptionCards, AutosaveChip, ConfirmFromIntake (all tested) for the employee-journey redesign. Spec: docs/design/employee-journey-ui-brief.md"
```

---

## Phase 2 — Intake wizard step-rail (first live screen)

### Task 8: WizardStepRail adapter

**Files:**
- Create: `frontend/src/features/employee-journey/WizardStepRail.tsx`
- Create: `frontend/src/features/employee-journey/WizardStepRail.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/features/employee-journey/WizardStepRail.test.tsx`:

```typescript
import '@testing-library/jest-dom/vitest';
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { WizardStepRail } from './WizardStepRail';

afterEach(cleanup);

describe('WizardStepRail', () => {
  it('maps current + completed steps onto the rail', () => {
    render(<WizardStepRail currentStep={2} completedSteps={[1]} maxUnlocked={2} onSelect={() => {}} />);
    expect(screen.getByText('Relocation basics')).toBeInTheDocument();
    expect(screen.getByText('Your household')).toBeInTheDocument();
    expect(screen.getByText(/Step 2 of 5/i)).toBeInTheDocument();
  });
  it('selects a completed, unlocked step', () => {
    const onSelect = vi.fn();
    render(<WizardStepRail currentStep={2} completedSteps={[1]} maxUnlocked={2} onSelect={onSelect} />);
    fireEvent.click(screen.getByText('Relocation basics'));
    expect(onSelect).toHaveBeenCalledWith(1);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm --prefix frontend run test -- WizardStepRail`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement WizardStepRail**

Create `frontend/src/features/employee-journey/WizardStepRail.tsx`:

```typescript
import React from 'react';
import { StepRail, type RailStep } from '../../components/antigravity';

// Real v2 wizard steps (CaseWizardPage Step1..Step5).
const LABELS = ['Relocation basics', 'Your details', 'Your household', 'Assignment', 'Review'];

interface WizardStepRailProps {
  currentStep: number;        // 1-based
  completedSteps: number[];   // 1-based completed step numbers
  maxUnlocked: number;        // highest navigable step (1-based)
  onSelect: (stepNumber: number) => void; // 1-based
}

export const WizardStepRail: React.FC<WizardStepRailProps> = ({ currentStep, completedSteps, maxUnlocked, onSelect }) => {
  const steps: RailStep[] = LABELS.map((label, i) => {
    const n = i + 1;
    const status: RailStep['status'] =
      n === currentStep ? 'current' : completedSteps.includes(n) ? 'done' : 'upcoming';
    return { label, status };
  });
  return (
    <StepRail
      steps={steps}
      onSelect={(index) => {
        const n = index + 1;
        if (n <= maxUnlocked) onSelect(n);
      }}
    />
  );
};
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm --prefix frontend run test -- WizardStepRail`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/employee-journey/WizardStepRail.tsx frontend/src/features/employee-journey/WizardStepRail.test.tsx
git commit -m "feat(employee-journey): WizardStepRail adapter"
```

### Task 9: Swap the wizard sidebar for the horizontal rail

**Files:**
- Modify: `frontend/src/pages/employee/CaseWizardPage.tsx` (the `WizardSidebar` block, ~lines 667-679)

- [ ] **Step 1: Read the current layout block**

Run: `sed -n '660,700p' frontend/src/pages/employee/CaseWizardPage.tsx` (confirm the `grid grid-cols-1 lg:grid-cols-[260px,1fr]` + `<WizardSidebar .../>` block matches the snippet below before editing).

- [ ] **Step 2: Replace the two-column sidebar with the horizontal rail**

In `CaseWizardPage.tsx`, change the layout wrapper so the rail sits on top in a single column. Replace:

```tsx
<div className="grid grid-cols-1 lg:grid-cols-[260px,1fr] gap-6">
  <div className="space-y-6">
    <WizardSidebar
      currentStep={currentStep}
      completedSteps={completedSteps}
      onSelect={(stepNumber) => {
        if (stepNumber > stepCompletion.maxUnlocked) {
          setError('Complete the previous steps first.');
          return;
        }
        navigate(`/employee/case/${assignmentId}/wizard/${stepNumber}`);
      }}
    />
```

with:

```tsx
<div className="space-y-6">
  <WizardStepRail
    currentStep={currentStep}
    completedSteps={completedSteps}
    maxUnlocked={stepCompletion.maxUnlocked}
    onSelect={(stepNumber) => {
      if (stepNumber > stepCompletion.maxUnlocked) {
        setError('Complete the previous steps first.');
        return;
      }
      navigate(`/employee/case/${assignmentId}/wizard/${stepNumber}`);
    }}
  />
```

Then close the surrounding `grid` wrapper correctly: the original closed the `<div className="space-y-6">` and the grid `</div>` around the step content. Adjust the closing tags so the step content (`stepNode`) renders below the rail in the same single column. Remove the now-unused `WizardSidebar` import if nothing else uses it. Add the import: `import { WizardStepRail } from '../../features/employee-journey/WizardStepRail';`

- [ ] **Step 3: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors (fix any unused-import errors from removing `WizardSidebar`).

- [ ] **Step 4: Visual verification in the running app**

Run: `npm --prefix frontend run dev` and open `http://localhost:3000`. Log in as the demo employee (`employee@testingapril.com` / `EmpPass!1`), open a case wizard route (`/employee/case/<id>/wizard/2`). Confirm: the horizontal step rail renders on top, the current step shows the teal ring + "Step 2 of 5", completed steps are clickable and navigate, upcoming steps are not. Take a screenshot for the PR.

- [ ] **Step 5: Build + commit**

Run: `npm --prefix frontend run build` (must pass — the pre-push hook runs this).

```bash
git add frontend/src/pages/employee/CaseWizardPage.tsx
git commit -m "feat(employee-journey): horizontal step rail in the intake wizard"
```

- [ ] **Step 6: Push + PR**

```bash
git push origin feat/employee-journey-ui-foundation
gh pr create --title "feat(employee-journey): intake wizard horizontal step rail" --body "Swaps the vertical WizardSidebar for the new horizontal StepRail (PhaseContextBar/StepRail foundation). Visual-verified against the demo employee. Spec: docs/design/employee-journey-ui-brief.md"
```

---

## Roadmap — remaining screens (each its own plan + PR)

Detail each of these in its own `writing-plans` pass when reached. Order favors live-data screens first, then empty-first screens, then sub-surfaces. All reuse the Phase 1 components.

1. **Dashboard journey-home** — `frontend/src/pages/EmployeeJourney.tsx`. Replace the 5-pill `flowSteps` with `PhaseContextBar` + 3 phase cards; "What needs you" aggregator (Forms + Tasks + Immigration sources, source-tagged); claim/empty state from `employeeAPI.getAssignmentsOverview`. Mock: `dashboard-E.html` / `dashboard-claim-E.html`.
2. **Services & Policy (+ empty)** — new route + page; service picker (`SegmentedOptionCards`/multi-select from `/api/hr/service-categories`), live caps from `/api/employee/policy/caps`, honest empty state, Policy Assistant panel. Mocks: `services-policy-E.html`, `services-policy-empty-E.html`.
3. **Roadmap (+ empty/light)** — `frontend/src/pages/employee/EmployeeCaseRoadmapPage.tsx`. Track timelines + `StatusPill`; first-class empty "being built" state; the light/heavy variation becomes real once [ROADMAP-DYN] lands. Mocks: `roadmap-E.html`, `roadmap-empty-E.html`, `roadmap-light-E.html`.
4. **Dossier & Forms** — `frontend/src/pages/employee/EmployeeDossierPage.tsx`. Status-tabbed form cards (`StatusPill`), completion strip, "Indicative — confirm with authority" banner. Mock: `dossier-E.html`.
5. **Form Editor** — `frontend/src/pages/employee/FormEditorPage.tsx`. AI-prefill "Pre-filled" tags + confirm states, sticky submit. Mock: `form-editor-E.html`.
6. **Immigration checklist + confirm** — `ImmigrationChecklistPage.tsx` + the intake confirm screen using `ConfirmFromIntake`. The confirm screen is the front-end half of the [ASK-ONCE] backend task. Mocks: `immigration-checklist-E.html`, `immigration-confirm-E.html`.
7. **Rich Profile (dedup)** — `EmployeeRichProfilePage.tsx`. Household roster read-only from intake (`ConfirmFromIntake`-style), enrichments only. Mock: `rich-profile-E.html`.

---

## Self-review notes

- **Spec coverage:** Phase 1 covers every shared primitive the brief's principles need (flags, status pills, phase/step nav, segmented cards, autosave, ask-once card). Phase 2 delivers the first live screen. The Roadmap section maps every remaining mock to a target file. Two backend behaviors (dynamic roadmap, ask-once dedup) are out of scope here and tracked as [ROADMAP-DYN]/[ASK-ONCE].
- **Type consistency:** component prop/type names are reused verbatim across tasks (`RailStep`, `Phase`, `SegmentedOption`, `ConfirmRow`, `JourneyStatus`). `WizardStepRail` consumes `StepRail` + `RailStep` as defined in Task 4.
- **Known adaptation:** Task 9 edits a real file (`CaseWizardPage.tsx`); the executor must confirm the exact closing-tag structure around the grid before committing (Step 1 re-reads it). The wizard step labels in `WizardStepRail` are the real v2 sequence.
