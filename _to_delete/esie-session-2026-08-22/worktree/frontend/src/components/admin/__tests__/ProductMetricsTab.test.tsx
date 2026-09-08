import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { ProductMetricsTab } from '../ProductMetricsTab';

// Mock the API wrapper (it imports api/client → api/supabase, the jsdom trap).
vi.mock('../../../api/adminProductMetrics', () => ({
  getProductMetrics: vi.fn().mockResolvedValue({
    period_days: 30,
    since: '2026-06-18T00:00:00Z',
    events: {
      case_created: 8,
      case_assigned: 6,
      policy_published: 3,
      wizard_step_completed: 20,
      wizard_completed: 5,
      estimate_review_opened: 10,
      exception_request_submitted: 4,
      exception_request_decided: 2,
    },
    rates: { wizard_completion_pct: 25, exception_request_pct: 40, exception_decided_pct: 50 },
    daily: [{ date: '2026-07-01', case_created: 3, policy_published: 1, wizard_completed: 2, estimate_review_opened: 4, exception_request_submitted: 1 }],
  }),
}));

describe('ProductMetricsTab', () => {
  it('renders headline counts, a funnel rate, and the daily breakdown', async () => {
    render(<ProductMetricsTab />);

    // headline tile value
    expect(await screen.findByText('Cases created')).toBeInTheDocument();
    expect(screen.getByText('8')).toBeInTheDocument();

    // a funnel rate is surfaced
    await waitFor(() => expect(screen.getByText(/25% of steps/)).toBeInTheDocument());

    // daily breakdown row rendered
    expect(screen.getByText('2026-07-01')).toBeInTheDocument();

    // deep-link out to PostHog
    const link = screen.getByRole('link', { name: /Open PostHog/i });
    expect(link).toHaveAttribute('href', expect.stringContaining('posthog.com'));
  });
});
