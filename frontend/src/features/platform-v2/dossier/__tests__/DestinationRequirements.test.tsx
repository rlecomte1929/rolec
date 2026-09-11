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
  destCountry: 'FRANCE',
  purpose: 'employment',
  computedAt: '2026-07-14T00:00:00Z',
  requirements: [],
  sources: [],
  covered: true,
  ...over,
});

const item = (over = {}) => ({
  id: '1',
  pillar: 'RESIDENCE',
  title: 'Long-stay work visa',
  description: 'Apply for the VLS-TS.',
  severity: 'BLOCKER',
  owner: 'EMPLOYEE',
  requiredFields: [],
  statusForCase: 'MISSING' as const,
  citations: [],
  ...over,
});

// mockClear, not mockReset: mockReset strips the implementation, which left the
// rejection un-consumed and surfaced it as an unhandled error instead of exercising
// the component's catch.
beforeEach(() => getRequirements.mockClear());

describe('an empty section must never claim "nothing is required"', () => {
  it('a CATALOG GAP (covered=false) renders the honest notice, not a claim', async () => {
    getRequirements.mockResolvedValue(dto({ covered: false, requirements: [] }));
    render(<DestinationRequirements caseId="c1" />);

    await waitFor(() => expect(screen.getByText(/Requirements not available yet/i)).toBeTruthy());
    expect(screen.queryByText(/no destination requirements apply/i)).toBeNull();
  });
});

describe('the nationality-waived explainer is NOT symmetric', () => {
  it('shows it for an EU national — their list genuinely got shorter', async () => {
    getRequirements.mockResolvedValue(
      dto({
        nationalityClass: 'EU_EEA',
        nationalityWaived: ['Long-stay work visa'],
        requirements: [item({ outcomeType: 'nothing_to_do', reason: 'Freedom of movement applies.' })],
      }),
    );
    render(<DestinationRequirements caseId="c1" />);
    await waitFor(() => expect(screen.getByTestId('nationality-waived')).toBeTruthy());
  });

  it('HIDES it for a third-country national — the array holds the EU items, and showing it would say "Justificatif de domicile doesn\'t apply to you"', async () => {
    getRequirements.mockResolvedValue(
      dto({
        nationalityClass: 'THIRD_COUNTRY',
        nationalityWaived: ['Justificatif de domicile (proof of French address)'],
        requirements: [item()],
      }),
    );
    render(<DestinationRequirements caseId="c1" />);

    await waitFor(() => expect(screen.getByText('Long-stay work visa')).toBeTruthy());
    expect(screen.queryByTestId('nationality-waived')).toBeNull();
    expect(screen.queryByText(/Justificatif/i)).toBeNull();
  });
});

describe('a nothing_to_do item is a stated answer', () => {
  it('renders its reason and offers no affordances', async () => {
    getRequirements.mockResolvedValue(
      dto({
        requirements: [
          item({
            id: '2',
            title: 'No visa or residence permit required',
            statusForCase: 'CONFIRMED',
            outcomeType: 'nothing_to_do',
            reason: 'You are a national of France. You have the right of entry and residence.',
          }),
        ],
      }),
    );
    render(<DestinationRequirements caseId="c1" />);

    await waitFor(() => expect(screen.getByTestId('requirement-confirmation')).toBeTruthy());
    expect(screen.getByText(/right of entry and residence/i)).toBeTruthy();
    expect(screen.queryByText('Upload')).toBeNull();
    expect(screen.queryByText('Mark Reviewed')).toBeNull();
  });
});

describe('the happy path', () => {
  it('groups requirements by pillar', async () => {
    getRequirements.mockResolvedValue(
      dto({
        requirements: [
          item({ id: '1', pillar: 'IDENTITY', title: 'Valid passport' }),
          item({ id: '2', pillar: 'RESIDENCE', title: 'Long-stay work visa' }),
        ],
      }),
    );
    render(<DestinationRequirements caseId="c1" />);

    await waitFor(() => expect(screen.getByText('Valid passport')).toBeTruthy());
    expect(screen.getByText('IDENTITY')).toBeTruthy();
    expect(screen.getByText('RESIDENCE')).toBeTruthy();
  });

  it('renders SOCIAL_SECURITY under a friendly section label', async () => {
    getRequirements.mockResolvedValue(
      dto({
        requirements: [
          item({
            id: 'a1',
            pillar: 'SOCIAL_SECURITY',
            title: 'A1 / Portable Document for posted workers',
            owner: 'EMPLOYER',
          }),
        ],
      }),
    );
    render(<DestinationRequirements caseId="c1" />);
    await waitFor(() => expect(screen.getByText('A1 / Portable Document for posted workers')).toBeTruthy());
    expect(screen.getByText('Social security & pension')).toBeTruthy();
    expect(screen.queryByText('SOCIAL_SECURITY')).toBeNull();
  });

  it('uses the same social-security label for the HR audience', async () => {
    getRequirements.mockResolvedValue(
      dto({
        requirements: [
          item({
            id: 'a1',
            pillar: 'SOCIAL_SECURITY',
            title: 'A1 / Portable Document for posted workers',
          }),
        ],
      }),
    );
    render(<DestinationRequirements caseId="c1" audience="hr" />);
    await waitFor(() => expect(screen.getByText('Social security & pension')).toBeTruthy());
  });

  it('shows that the corridor is not ready when the catalog fails sufficiency', async () => {
    getRequirements.mockResolvedValue(
      dto({
        catalogReady: false,
        catalogNotReadyReason: 'This corridor is not ready. We have no approved, cited requirements to serve.',
      }),
    );
    render(<DestinationRequirements caseId="c1" />);
    await waitFor(() => expect(screen.getByTestId('catalog-not-ready')).toBeTruthy());
  });
});
