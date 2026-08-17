/**
 * [AIQ-1902] The `onLoaded` seam that lets the HR cockpit's Path tile agree with the list
 * mounted underneath it.
 *
 * The contract that matters is the failure direction. This callback is what stops the
 * tile saying "No permit mapping for this destination yet." — so if a failed fetch
 * reported a stale or optimistic value, the tile would start making claims the section
 * itself carefully refuses to make. `null` means "no answer", and loading and failure
 * both mean `null`.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import type { CaseRequirementsDTO } from '../../../../types';

const getRequirements = vi.fn();
vi.mock('../../../../api/cases', () => ({ getRequirements: (id: string) => getRequirements(id) }));
vi.mock('../../../../components/requirements/Citations', () => ({ Citations: () => null }));
vi.mock('../../../../components/requirements/ImmigrationDisclaimer', () => ({
  ImmigrationDisclaimer: () => null,
}));

import { DestinationRequirements } from '../DestinationRequirements';

const item = (id: string) => ({
  id,
  pillar: 'RESIDENCE',
  title: `IE requirement ${id}`,
  description: '…',
  severity: 'WARN',
  owner: 'EMPLOYEE',
  requiredFields: [],
  statusForCase: 'MISSING' as const,
  citations: [],
});

const irelandDto = (count: number): CaseRequirementsDTO => ({
  caseId: '6ecadafe-0fdb-43c5-b8dc-0284e323cf51',
  destCountry: 'IRELAND',
  purpose: 'employment',
  computedAt: '2026-08-17T00:00:00Z',
  requirements: Array.from({ length: count }, (_, i) => item(String(i))),
  sources: [],
  covered: true,
});

// mockClear, not mockReset — see the note in DestinationRequirements.hr.test.tsx.
beforeEach(() => getRequirements.mockClear());

describe('onLoaded', () => {
  it('reports null while loading, then the loaded dossier', async () => {
    getRequirements.mockResolvedValue(irelandDto(14));
    const onLoaded = vi.fn();

    render(<DestinationRequirements caseId="c1" audience="hr" onLoaded={onLoaded} />);

    // First call is synchronous with the fetch starting: "no answer yet", so the host
    // page cannot keep showing a count from a previously selected case.
    expect(onLoaded.mock.calls[0][0]).toBeNull();

    await waitFor(() => expect(onLoaded).toHaveBeenCalledTimes(2));
    expect(onLoaded.mock.calls.at(-1)![0].requirements).toHaveLength(14);
  });

  // The failure direction lives in DestinationRequirements.onLoaded.failure.test.tsx —
  // own file, for the harness reason documented in DestinationRequirements.hr.failure.
  it('does not refetch when the caller passes a fresh arrow each render', async () => {
    getRequirements.mockResolvedValue(irelandDto(1));
    const { rerender } = render(
      <DestinationRequirements caseId="c1" audience="hr" onLoaded={() => {}} />,
    );
    await waitFor(() => expect(getRequirements).toHaveBeenCalledTimes(1));

    rerender(<DestinationRequirements caseId="c1" audience="hr" onLoaded={() => {}} />);
    rerender(<DestinationRequirements caseId="c1" audience="hr" onLoaded={() => {}} />);

    expect(getRequirements).toHaveBeenCalledTimes(1);
  });

  it('is optional — the two dossier pages that do not pass it still render', async () => {
    getRequirements.mockResolvedValue(irelandDto(2));
    expect(() => render(<DestinationRequirements caseId="c1" />)).not.toThrow();
    await waitFor(() => expect(getRequirements).toHaveBeenCalled());
  });
});
