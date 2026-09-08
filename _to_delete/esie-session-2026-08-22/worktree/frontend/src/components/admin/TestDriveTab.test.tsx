import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react';

vi.mock('../../api/adminTestDrive', () => ({
  getTestDriveOverview: vi.fn(),
  testDriveContactsCsvUrl: vi.fn(() => '/api/admin/test-drive/contacts.csv'),
  recordInvitesSent: vi.fn(),
}));
// utils/demo → client → supabase chain guard (known vitest trap).
vi.mock('../../api/supabase', () => ({ supabase: {} }));

import { getTestDriveOverview, recordInvitesSent } from '../../api/adminTestDrive';
// Type-only: erased at compile time, so it is unaffected by the vi.mock factory above.
import type { TestDriveOverview } from '../../api/adminTestDrive';
import { TestDriveTab } from './TestDriveTab';

const mockOverview = getTestDriveOverview as unknown as ReturnType<typeof vi.fn>;
const mockRecord = recordInvitesSent as unknown as ReturnType<typeof vi.fn>;

const FUNNEL = {
  invited: 10, clicked: 8, provisioned: 5,
  hr_handoff: 5, intake_start: 4, intake_completed: 4, roadmap_reached: 3, vendor_selected: 3,
  completed: 3, surveyed: 3, pilot: 2, intro: 1,
};

// Typed against the real contract on purpose: `mockOverview` is `vi.fn()` (i.e. `any`),
// so an untyped fixture silently drifts from TestDriveOverview and tsc stays green while
// the component crashes at render. That is exactly how this fixture fell behind the
// TD-M3/M4/M5 fields below. Keep the annotation — it makes the next drift a type error.
const OVERVIEW: TestDriveOverview = {
  funnel: FUNNEL,
  scorecard: {
    avg_overall: 4.2,
    problem_fit: { yes: 2, somewhat: 1, no: 0 },
    // TD-M4 (AIQ-1559)
    trust_intent: { yes: 2, maybe: 1, no: 0 },
    totals: FUNNEL,
  },
  // TD-M3 (AIQ-1558) + TD-M5 (AIQ-1561). Empty renders each section's empty-state, which
  // keeps these pre-existing assertions untouched. The populated paths
  // (stage_timing.map / follow_up.map) still have no unit coverage — see review note.
  stage_timing: [],
  follow_up: [],
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
  corridor: null, segment: null, campaign: null, generated_at: '2026-07-05',
};

// TD-M6 (AIQ-1562): with no segment filter, one load fans out to three fetches —
// overall + prospect + internal — so the default view shows the split side by side
// instead of a blended number. Call-count assertions below are in units of loads.
const FETCHES_PER_LOAD = 3;

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
    // TD-M6: the average now renders once per segment column (overall/prospect/internal).
    expect(screen.getAllByText(/4\.2/).length).toBeGreaterThan(0);
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

  it('shows a computed click-through % from invited/clicked (TD-FIX-3)', async () => {
    mockOverview.mockResolvedValue(OVERVIEW); // invited 10, clicked 8 → 80%
    render(<TestDriveTab />);
    expect(await screen.findByText(/Click-through:/)).toBeInTheDocument();
    expect(screen.getByText('80%')).toBeInTheDocument();
  });

  it('records invites sent and re-fetches the dashboard (TD-FIX-3)', async () => {
    mockOverview.mockResolvedValue(OVERVIEW);
    mockRecord.mockResolvedValue({ ok: true, recorded: 25 });
    render(<TestDriveTab />);
    await screen.findByText(/Coordinates the handoffs/);
    expect(mockOverview).toHaveBeenCalledTimes(FETCHES_PER_LOAD);

    fireEvent.change(screen.getByLabelText('Invites sent'), { target: { value: '25' } });
    fireEvent.click(screen.getByRole('button', { name: /Record invites sent/i }));

    await waitFor(() => expect(mockRecord).toHaveBeenCalledWith({ count: 25, channel: 'whatsapp' }));
    expect(await screen.findByText(/Recorded 25 invites\./)).toBeInTheDocument();
    // onRecorded reloads the overview (a second full load).
    await waitFor(() => expect(mockOverview).toHaveBeenCalledTimes(FETCHES_PER_LOAD * 2));
  });

  it('re-fetches when a corridor slice is selected', async () => {
    mockOverview.mockResolvedValue(OVERVIEW);
    render(<TestDriveTab />);
    await screen.findByText(/Coordinates the handoffs/);
    expect(mockOverview).toHaveBeenCalledTimes(FETCHES_PER_LOAD);

    fireEvent.click(screen.getByRole('button', { name: 'London → New York' }));

    await waitFor(() => expect(mockOverview).toHaveBeenCalledTimes(FETCHES_PER_LOAD * 2));
    // AIQ-1537: the slice now carries the (default) campaign alongside corridor/segment.
    // toHaveBeenCalledWith, not LastCalledWith: TD-M6's fan-out means the overall slice is
    // the FIRST of the three, and the last call is the 'internal' one.
    expect(mockOverview).toHaveBeenCalledWith({ corridor: 'GB_US', segment: undefined, campaign: 'insead-2026' });
  });
});
