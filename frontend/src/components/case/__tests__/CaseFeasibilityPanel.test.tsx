import '@testing-library/jest-dom/vitest';
import React from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchCaseOverview } from '../../../api/cases';
import { CaseFeasibilityPanel } from '../CaseFeasibilityPanel';
import type { CaseFeasibility, CaseOverview } from '../../../api/cases';

vi.mock('../../../api/cases', () => ({ fetchCaseOverview: vi.fn() }));

const mocked = <T,>(fn: T) => fn as T & ReturnType<typeof vi.fn>;

function overviewWith(feasibility: CaseFeasibility | null): CaseOverview {
  return {
    case_id: 'case-1',
    employee: { employee_id: 'emp-1', display_name: 'Test Employee' },
    status: 'in_progress',
    family_members: [],
    feasibility,
  };
}

const CRITICAL: CaseFeasibility = {
  verdict: 'critical',
  required_days: 104,
  available_days: 30,
  derivation: '104 days of steps must complete before “Travel to Ireland”; 30 days remain until the target start date — 74 days short.',
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('CaseFeasibilityPanel', () => {
  it('renders a critical warning with both day counts', async () => {
    mocked(fetchCaseOverview).mockResolvedValue(overviewWith(CRITICAL));
    render(<CaseFeasibilityPanel caseId="case-1" />);

    await waitFor(() =>
      expect(screen.getByText(/unlikely to be achievable/i)).toBeInTheDocument(),
    );
    expect(screen.getByText('104 days')).toBeInTheDocument();
    expect(screen.getByText('30 days')).toBeInTheDocument();
    // The server's derivation is shown verbatim — never recomputed client-side.
    expect(screen.getByText(CRITICAL.derivation)).toBeInTheDocument();
  });

  it('renders a softer warning for a tight timeline', async () => {
    mocked(fetchCaseOverview).mockResolvedValue(
      overviewWith({ ...CRITICAL, verdict: 'tight', available_days: 110, derivation: 'tight' }),
    );
    render(<CaseFeasibilityPanel caseId="case-1" />);

    await waitFor(() =>
      expect(screen.getByText(/no room for delay/i)).toBeInTheDocument(),
    );
    expect(screen.queryByText(/unlikely to be achievable/i)).not.toBeInTheDocument();
  });

  it('renders nothing for an ok verdict', async () => {
    mocked(fetchCaseOverview).mockResolvedValue(
      overviewWith({ ...CRITICAL, verdict: 'ok', available_days: 300 }),
    );
    const { container } = render(<CaseFeasibilityPanel caseId="case-1" />);

    await waitFor(() => expect(fetchCaseOverview).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing when feasibility is null — absence is not reassurance', async () => {
    mocked(fetchCaseOverview).mockResolvedValue(overviewWith(null));
    const { container } = render(<CaseFeasibilityPanel caseId="case-1" />);

    await waitFor(() => expect(fetchCaseOverview).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing and makes no request when caseId is absent', () => {
    // detail.caseId is Optional on the command-center response; a case with no
    // relocation_cases row must not trigger a doomed request.
    const { container } = render(<CaseFeasibilityPanel caseId={null} />);
    expect(fetchCaseOverview).not.toHaveBeenCalled();
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing when the request fails (fetch returns null)', async () => {
    mocked(fetchCaseOverview).mockResolvedValue(null);
    const { container } = render(<CaseFeasibilityPanel caseId="case-1" />);

    await waitFor(() => expect(fetchCaseOverview).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it('reports a start date already in the past', async () => {
    mocked(fetchCaseOverview).mockResolvedValue(
      overviewWith({ ...CRITICAL, available_days: -10 }),
    );
    render(<CaseFeasibilityPanel caseId="case-1" />);

    await waitFor(() =>
      expect(screen.getByText(/already passed/i)).toBeInTheDocument(),
    );
  });
});
