import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RoadmapPaywallGate } from '../RoadmapPaywallGate';

const trackPaywallImpression = vi.fn();
const trackPaymentInitiated = vi.fn();
vi.mock('../../../analyticsEvents', () => ({
  trackPaywallImpression: (...a: unknown[]) => trackPaywallImpression(...a),
  trackPaymentInitiated: (...a: unknown[]) => trackPaymentInitiated(...a),
}));

vi.mock('../../../api/client', () => ({
  default: { post: vi.fn().mockResolvedValue({ data: { checkoutUrl: 'https://checkout.example/s' } }) },
}));
vi.mock('../../../utils/demo', () => ({ getAuthItem: () => null }));
vi.mock('../../../utils/testAccount', () => ({ looksLikeTestEmail: () => false }));

describe('RoadmapPaywallGate analytics', () => {
  beforeEach(() => {
    trackPaywallImpression.mockReset();
    trackPaymentInitiated.mockReset();
  });

  it('fires paywall_impression on mount without PII', () => {
    render(<RoadmapPaywallGate assignmentId="asgn-1" destCity="Madrid" destCountry="Spain" />);
    expect(trackPaywallImpression).toHaveBeenCalledTimes(1);
    const props = trackPaywallImpression.mock.calls[0][0] as Record<string, unknown>;
    expect(props).toEqual({ assignment_id: 'asgn-1' });
    expect(JSON.stringify(props)).not.toMatch(/email|@|Madrid|Spain/i);
  });

  it('fires payment_initiated on Unlock click', async () => {
    const user = userEvent.setup();
    render(<RoadmapPaywallGate assignmentId="asgn-1" />);
    await user.click(screen.getByRole('button', { name: /unlock full roadmap/i }));
    expect(trackPaymentInitiated).toHaveBeenCalledWith({ assignment_id: 'asgn-1' });
    const props = trackPaymentInitiated.mock.calls[0][0] as Record<string, unknown>;
    expect(JSON.stringify(props)).not.toMatch(/email|@|name/i);
  });
});
