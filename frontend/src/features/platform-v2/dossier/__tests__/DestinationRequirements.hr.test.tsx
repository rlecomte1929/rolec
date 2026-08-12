/**
 * The HR audience of the destination-requirements section.
 *
 * HR was the one persona that could not see any of this: /hr/requirements reads a
 * different table, the roadmap overlay carries copy for a couple of titles, and the same
 * content was meanwhile public on the unauthenticated corridor endpoint. Rendering the
 * employee component as-is would have told an HR user "what YOUR destination requires"
 * about somebody else's move, so the strings are keyed on `audience`.
 *
 * What these pin:
 *   - the copy is third-person for HR and unchanged for the employee default;
 *   - a fetch failure still refuses to imply that nothing is required — under BOTH
 *     audiences, because that is the whole reason the four states exist;
 *   - the unknown-nationality caveat appears only for HR, and only when the engine
 *     could not classify.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import type { CaseRequirementsDTO } from '../../../../types';

const getRequirements = vi.fn();
vi.mock('../../../../api/cases', () => ({ getRequirements: (id: string) => getRequirements(id) }));
vi.mock('../../../../components/requirements/Citations', () => ({ Citations: () => null }));
vi.mock('../../../../components/requirements/ImmigrationDisclaimer', () => ({
  ImmigrationDisclaimer: () => null,
}));

import { DestinationRequirements } from '../DestinationRequirements';

const dto = (over: Partial<CaseRequirementsDTO> = {}): CaseRequirementsDTO => ({
  caseId: 'c1',
  destCountry: 'NORWAY',
  purpose: 'employment',
  computedAt: '2026-08-12T00:00:00Z',
  requirements: [],
  sources: [],
  covered: true,
  ...over,
});

const item = (over = {}) => ({
  id: '1',
  pillar: 'EMPLOYMENT',
  title: 'Tax deduction card (skattekort) before first salary',
  description: 'Without a tax deduction card, the employer must deduct 50 percent tax.',
  severity: 'BLOCKER',
  owner: 'EMPLOYEE',
  requiredFields: [],
  statusForCase: 'MISSING' as const,
  citations: [],
  ...over,
});

// mockClear, not mockReset — mockReset strips the implementation, leaving a rejection
// unconsumed and surfacing it as an unhandled error instead of exercising the catch.
beforeEach(() => getRequirements.mockClear());

describe('the copy addresses the right person', () => {
  it('HR reads about the employee, never to them', async () => {
    getRequirements.mockResolvedValue(dto({ requirements: [item()] }));
    render(<DestinationRequirements caseId="c1" audience="hr" />);

    await waitFor(() => expect(screen.getByText(/What this destination requires/i)).toBeTruthy());
    expect(screen.queryByText(/What your destination requires/i)).toBeNull();
  });

  it('the employee default is untouched', async () => {
    getRequirements.mockResolvedValue(dto({ requirements: [item()] }));
    render(<DestinationRequirements caseId="c1" />);

    await waitFor(() => expect(screen.getByText(/What your destination requires/i)).toBeTruthy());
  });

  it('the waived-nationality explainer is third-person for HR', async () => {
    getRequirements.mockResolvedValue(
      dto({
        nationalityClass: 'EU_EEA',
        nationalityWaived: ['Valid passport (6+ months)'],
        requirements: [item()],
      }),
    );
    render(<DestinationRequirements caseId="c1" audience="hr" />);

    await waitFor(() => expect(screen.getByTestId('nationality-waived')).toBeTruthy());
    expect(screen.getByText(/this employee’s nationality/i)).toBeTruthy();
    expect(screen.getByText(/Because this employee has EU\/EEA freedom of movement/i)).toBeTruthy();
  });
});

// The HR failure state lives in DestinationRequirements.hr.failure.test.tsx — a rejected
// mock alongside waitFor polling in a shared module surfaces as an unhandled error before
// the component's catch runs. Same reason the employee failure test has its own file.

describe('the unknown-nationality caveat', () => {
  it('warns HR when the engine could not classify — the list is the fullest one', async () => {
    // No nationalityClass: rules_engine fell back to THIRD_COUNTRY and deliberately
    // published no waived list, so the reader cannot otherwise account for the list.
    getRequirements.mockResolvedValue(dto({ requirements: [item()] }));
    render(<DestinationRequirements caseId="c1" audience="hr" />);

    await waitFor(() => expect(screen.getByTestId('nationality-unknown')).toBeTruthy());
  });

  it('stays quiet once the nationality IS known', async () => {
    getRequirements.mockResolvedValue(
      dto({ nationalityClass: 'EU_EEA', requirements: [item()] }),
    );
    render(<DestinationRequirements caseId="c1" audience="hr" />);

    await waitFor(() => expect(screen.getByText(/What this destination requires/i)).toBeTruthy());
    expect(screen.queryByTestId('nationality-unknown')).toBeNull();
  });

  it('is not shown to the employee — they cannot fix the missing field', async () => {
    getRequirements.mockResolvedValue(dto({ requirements: [item()] }));
    render(<DestinationRequirements caseId="c1" />);

    await waitFor(() => expect(screen.getByText(/What your destination requires/i)).toBeTruthy());
    expect(screen.queryByTestId('nationality-unknown')).toBeNull();
  });

  it('does not fire on a catalog gap, where the empty list has its own explanation', async () => {
    getRequirements.mockResolvedValue(dto({ covered: false, requirements: [] }));
    render(<DestinationRequirements caseId="c1" audience="hr" />);

    await waitFor(() => expect(screen.getByText(/What this destination requires/i)).toBeTruthy());
    expect(screen.queryByTestId('nationality-unknown')).toBeNull();
  });
});
