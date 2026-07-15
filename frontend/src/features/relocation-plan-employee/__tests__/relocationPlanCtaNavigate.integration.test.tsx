/**
 * [AIQ-1547] Integration coverage for the roadmap task-CTA navigation path.
 *
 * The resolver is unit-tested in
 * `relocation-plan/task-card/__tests__/relocationTaskCtaMap.test.ts`, but nothing
 * exercised the *button → hook → navigate* wiring that the employee roadmap actually
 * uses (EmployeeCaseRoadmapPage builds `runCta` from `useRelocationPlanCtaHandler` and
 * hands it to RoadmapTemplate's action buttons). This test renders that real hook inside
 * a router and clicks a button, asserting where the user lands.
 *
 * Regression guard for BUG-260715-A317: the form/requirement CTAs must land on
 * Dossier & Forms, never back on the intake wizard.
 */
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { useRelocationPlanCtaHandler } from '../relocationPlanCtaNavigate';
import type { RelocationPlanCtaDTO } from '../../../types/relocationPlanView';

const CASE_ID = 'case-abc';

function LocationProbe() {
  const loc = useLocation();
  return <div data-testid="loc">{loc.pathname + loc.search}</div>;
}

function Harness({ cta, formHint }: { cta: RelocationPlanCtaDTO; formHint?: string }) {
  const runCta = useRelocationPlanCtaHandler(CASE_ID);
  return (
    <button type="button" onClick={() => runCta(cta, formHint)}>
      go
    </button>
  );
}

function clickCta(cta: RelocationPlanCtaDTO, formHint?: string): string {
  // Allow multiple calls within a single test (auto-cleanup only runs between tests).
  cleanup();
  render(
    <MemoryRouter initialEntries={[`/employee/case/${CASE_ID}/roadmap`]}>
      <Harness cta={cta} formHint={formHint} />
      <LocationProbe />
    </MemoryRouter>,
  );
  fireEvent.click(screen.getByRole('button', { name: 'go' }));
  return screen.getByTestId('loc').textContent ?? '';
}

describe('[AIQ-1547] roadmap CTA button → navigation target', () => {
  it('form task (complete_wizard_step) lands on Dossier & Forms, not the intake wizard', () => {
    expect(clickCta({ type: 'complete_wizard_step', label: 'Continue' })).toBe(
      `/employee/case/${CASE_ID}/dossier`,
    );
  });

  it('requirements task (view_details/View requirements) lands on Dossier & Forms', () => {
    expect(clickCta({ type: 'view_details', label: 'View requirements' })).toBe(
      `/employee/case/${CASE_ID}/dossier`,
    );
  });

  it('a formHint deep-links ?form=<key> on Dossier & Forms', () => {
    expect(
      clickCta({ type: 'complete_wizard_step', label: 'Continue' }, 'confirm_family_details'),
    ).toBe(`/employee/case/${CASE_ID}/dossier?form=confirm_family_details`);
  });

  it('no button ever routes back to the intake wizard', () => {
    for (const cta of [
      { type: 'complete_wizard_step', label: 'Continue' } as const,
      { type: 'view_details', label: 'View requirements' } as const,
    ]) {
      expect(clickCta(cta)).not.toContain('/intake');
    }
  });

  it('regression: upload_document still routes to the documents surface', () => {
    expect(clickCta({ type: 'upload_document', label: 'Upload' }, 'passport_copy')).toBe(
      `/employee/case/${CASE_ID}/documents?doc=passport_copy`,
    );
  });
});
