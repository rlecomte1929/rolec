import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react';

vi.mock('../../api/adminTestDrive', () => ({
  getTestDriveOverview: vi.fn(),
  testDriveContactsCsvUrl: vi.fn(() => '/api/admin/test-drive/contacts.csv'),
}));
// utils/demo → client → supabase chain guard (known vitest trap).
vi.mock('../../api/supabase', () => ({ supabase: {} }));

import { getTestDriveOverview } from '../../api/adminTestDrive';
import { TestDriveTab } from './TestDriveTab';

const mockOverview = getTestDriveOverview as unknown as ReturnType<typeof vi.fn>;

const OVERVIEW = {
  funnel: { invited: 10, clicked: 8, provisioned: 5, completed: 3, surveyed: 3, pilot: 2, intro: 1 },
  scorecard: {
    avg_overall: 4.2,
    problem_fit: { yes: 2, somewhat: 1, no: 0 },
    totals: { invited: 10, clicked: 8, provisioned: 5, completed: 3, surveyed: 3, pilot: 2, intro: 1 },
  },
  pilot_leads: [{
    tester_name: 'Alex', tester_email: 'a@x.test', tester_company_role: 'Head of Mobility',
    tester_sector: 'energy', pilot_interest: 'yes', pilot_note: '', corridor_id: 'GB_US',
    tester_segment: 'prospect', created_at: '2026-07-05',
  }],
  completions: [
    {
      tester_name: 'Alex', tester_email: 'a@x.test', tester_company_role: 'Head of Mobility',
      tester_sector: 'energy', q1_overall: 5, pilot_interest: 'yes', corridor_id: 'GB_US',
      tester_segment: 'prospect', created_at: '2026-07-05',
    },
    {
      tester_name: 'Priya', tester_email: 'priya@y.test', tester_company_role: 'HRBP',
      tester_sector: 'pharma', q1_overall: 4, pilot_interest: 'no', corridor_id: 'GB_US',
      tester_segment: 'prospect', created_at: '2026-07-04',
    },
  ],
  testimonials: [{
    testimonial: 'Coordinates the handoffs that usually break.', tester_name: 'Alex',
    tester_company_role: 'Head of Mobility', corridor_id: 'GB_US', created_at: '2026-07-05',
  }],
  corridor: null, segment: null, generated_at: '2026-07-05',
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('TestDriveTab', () => {
  it('renders scorecard, funnel, pilot leads and consented testimonials', async () => {
    mockOverview.mockResolvedValue(OVERVIEW);
    render(<TestDriveTab />);

    expect(await screen.findByText(/Coordinates the handoffs/)).toBeInTheDocument();
    expect(screen.getAllByText('Provisioned').length).toBeGreaterThan(0); // scorecard + funnel
    expect(screen.getByText(/4\.2/)).toBeInTheDocument();
    expect(screen.getAllByText(/Head of Mobility/).length).toBeGreaterThan(0); // pilot + testimonial
    expect(screen.getByText(/Pilot leads \(1\)/)).toBeInTheDocument();
    expect(screen.getByText(/Testimonials \(1\)/)).toBeInTheDocument();
  });

  it('lists every completer with a per-row thank-you mailto', async () => {
    mockOverview.mockResolvedValue(OVERVIEW);
    render(<TestDriveTab />);

    expect(await screen.findByText(/Survey responses \(2\)/)).toBeInTheDocument();
    // Priya completed but is NOT a pilot lead — she only appears via Survey responses.
    expect(screen.getByText('Priya')).toBeInTheDocument();
    // Every completer with an email gets a thank-you mailto (pilot leads + completions).
    const links = screen.getAllByRole('link', { name: /Send thank-you/ });
    expect(links.length).toBeGreaterThanOrEqual(2);
    expect(links.some((a) => a.getAttribute('href')?.startsWith('mailto:priya@y.test'))).toBe(true);
  });

  it('re-fetches when a corridor slice is selected', async () => {
    mockOverview.mockResolvedValue(OVERVIEW);
    render(<TestDriveTab />);
    await screen.findByText(/Coordinates the handoffs/);
    expect(mockOverview).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole('button', { name: 'London → New York' }));

    await waitFor(() => expect(mockOverview).toHaveBeenCalledTimes(2));
    expect(mockOverview).toHaveBeenLastCalledWith({ corridor: 'GB_US', segment: undefined });
  });
});
