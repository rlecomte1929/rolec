import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../api/payment', () => ({ getPaymentStatus: vi.fn() }));

import { getPaymentStatus } from '../api/payment';
import { fetchRoadmapUnlocked } from './paymentStatus';

describe('fetchRoadmapUnlocked (server-backed roadmap gate)', () => {
  beforeEach(() => vi.clearAllMocks());

  it('FAILS CLOSED (false) without a caseId — err toward the paywall, no server call', async () => {
    expect(await fetchRoadmapUnlocked('')).toBe(false);
    expect(getPaymentStatus).not.toHaveBeenCalled();
  });

  it('reflects the server roadmap_unlocked=false (locked)', async () => {
    vi.mocked(getPaymentStatus).mockResolvedValue({
      case_id: 'c1', access_tier: 'free', payment_status: 'unpaid', roadmap_unlocked: false,
    });
    expect(await fetchRoadmapUnlocked('c1')).toBe(false);
  });

  it('reflects the server roadmap_unlocked=true (paid / flag off)', async () => {
    vi.mocked(getPaymentStatus).mockResolvedValue({
      case_id: 'c1', access_tier: 'roadmap', payment_status: 'roadmap_paid', roadmap_unlocked: true,
    });
    expect(await fetchRoadmapUnlocked('c1')).toBe(true);
  });

  it('FAILS CLOSED (false) when the status call throws — a free €800 roadmap is worse than a recoverable false lock', async () => {
    vi.mocked(getPaymentStatus).mockRejectedValue(new Error('network'));
    expect(await fetchRoadmapUnlocked('c1')).toBe(false);
  });

  it('FAILS CLOSED (false) on a 404 — the direct-load assignment_id path must not bypass the paywall', async () => {
    vi.mocked(getPaymentStatus).mockRejectedValue({ response: { status: 404 } });
    expect(await fetchRoadmapUnlocked('assignment-id')).toBe(false);
  });
});
