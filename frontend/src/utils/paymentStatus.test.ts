import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../api/payment', () => ({ getPaymentStatus: vi.fn() }));

import { getPaymentStatus } from '../api/payment';
import { fetchRoadmapUnlocked } from './paymentStatus';

describe('fetchRoadmapUnlocked (server-backed roadmap gate)', () => {
  beforeEach(() => vi.clearAllMocks());

  it('returns true without a caseId — nothing to gate, no server call', async () => {
    expect(await fetchRoadmapUnlocked('')).toBe(true);
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

  it('FAILS OPEN (true) when the status call throws — never wrongly paywall on a transient error', async () => {
    vi.mocked(getPaymentStatus).mockRejectedValue(new Error('network'));
    expect(await fetchRoadmapUnlocked('c1')).toBe(true);
  });
});
