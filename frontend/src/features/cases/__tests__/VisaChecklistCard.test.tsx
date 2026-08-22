/**
 * Visa Checklist card — the three empty states and the tick round trip.
 *
 * The states matter more than they look: "no catalogue for this destination" and "we checked
 * and nothing applies" are different answers, and rendering the same sentence for both is the
 * AIQ-1473c failure where an empty list reads as "nothing is required".
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const mocks = vi.hoisted(() => ({
  getCaseChecklist: vi.fn(),
  setCaseChecklistItem: vi.fn(),
}));

vi.mock('../../../api/cases', () => ({
  getCaseChecklist: mocks.getCaseChecklist,
  setCaseChecklistItem: mocks.setCaseChecklistItem,
}));

import { VisaChecklistCard } from '../VisaChecklistCard';

const view = (over: Record<string, unknown> = {}) => ({
  caseId: 'case-1',
  destCountry: 'IRELAND',
  purpose: 'employment',
  covered: true,
  items: [
    {
      id: 'req-csep',
      title: 'Critical Skills Employment Permit',
      pillar: 'RESIDENCE',
      description: 'Employer-led application to DETE.',
      severity: 'WARN',
      owner: 'EMPLOYEE',
      nonObvious: true,
      timing: 'before travel',
      completed: false,
      completedAt: null,
    },
    {
      id: 'req-irp',
      title: 'Stamp 1 / IRP registration',
      pillar: 'RESIDENCE',
      description: '',
      severity: 'WARN',
      owner: 'EMPLOYEE',
      nonObvious: null,
      timing: null,
      completed: false,
      completedAt: null,
    },
  ],
  completedCount: 0,
  totalCount: 2,
  percentComplete: 0,
  ...over,
});

function renderCard(caseId: string | null = 'case-1') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <VisaChecklistCard caseId={caseId} />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('VisaChecklistCard', () => {
  it('renders the requirements with progress', async () => {
    mocks.getCaseChecklist.mockResolvedValue(view());
    renderCard();
    expect(await screen.findByText('Critical Skills Employment Permit')).toBeInTheDocument();
    expect(screen.getByText('Stamp 1 / IRP registration')).toBeInTheDocument();
    expect(screen.getByText('0 of 2 complete')).toBeInTheDocument();
  });

  it('flags a non-obvious item and shows its timing', async () => {
    mocks.getCaseChecklist.mockResolvedValue(view());
    renderCard();
    expect(await screen.findByText('Easy to miss')).toBeInTheDocument();
    expect(screen.getByText('before travel')).toBeInTheDocument();
  });

  it('does NOT flag an item whose nonObvious is null', async () => {
    // null means "not modeled", which is not the same as false and must not render the flag.
    mocks.getCaseChecklist.mockResolvedValue(
      view({ items: [{ ...view().items[1] }] }),
    );
    renderCard();
    await screen.findByText('Stamp 1 / IRP registration');
    expect(screen.queryByText('Easy to miss')).not.toBeInTheDocument();
  });

  it('ticking posts and adopts the server-returned view', async () => {
    mocks.getCaseChecklist.mockResolvedValue(view());
    mocks.setCaseChecklistItem.mockResolvedValue(
      view({
        items: [
          { ...view().items[0], completed: true, completedAt: '2026-08-17T10:00:00Z' },
          view().items[1],
        ],
        completedCount: 1,
        percentComplete: 50,
      }),
    );
    renderCard();
    const boxes = await screen.findAllByRole('checkbox');
    fireEvent.click(boxes[0]);

    await waitFor(() => expect(mocks.setCaseChecklistItem).toHaveBeenCalledWith('case-1', 'req-csep', true));
    // The counter comes from the server's response, not a local guess.
    expect(await screen.findByText('1 of 2 complete')).toBeInTheDocument();
  });

  it('distinguishes "no catalogue" from "nothing applies"', async () => {
    mocks.getCaseChecklist.mockResolvedValue(view({ covered: false, items: [], totalCount: 0 }));
    const { unmount } = renderCard();
    expect(await screen.findByText(/No requirements catalogue for IRELAND/)).toBeInTheDocument();
    unmount();
    cleanup();

    mocks.getCaseChecklist.mockResolvedValue(view({ covered: true, items: [], totalCount: 0 }));
    renderCard();
    expect(await screen.findByText('No requirements apply to this case.')).toBeInTheDocument();
  });

  it('says so plainly when the checklist cannot be loaded', async () => {
    mocks.getCaseChecklist.mockRejectedValue(new Error('boom'));
    renderCard();
    expect(
      await screen.findByText(/Unable to load the checklist/),
    ).toBeInTheDocument();
  });

  it('renders nothing without a case id', () => {
    const { container } = renderCard(null);
    expect(container).toBeEmptyDOMElement();
    expect(mocks.getCaseChecklist).not.toHaveBeenCalled();
  });
});
