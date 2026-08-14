/**
 * AIQ-1697 — getCaseAiSummary wrapper.
 * Proves it calls the HR-scoped ai-summary endpoint (assignment id encoded) and
 * returns the parsed 4-section payload. The apiGet module boundary is mocked, so no
 * network and no supabase import.
 */
import { describe, expect, it, vi, beforeEach, type Mock } from 'vitest';

vi.mock('../client', () => ({ apiGet: vi.fn() }));

import { apiGet } from '../client';
import { getCaseAiSummary } from '../caseSummary';

const apiGetMock = apiGet as unknown as Mock;

beforeEach(() => apiGetMock.mockReset());

describe('getCaseAiSummary', () => {
  it('calls the HR ai-summary endpoint and returns the summary', async () => {
    const payload = {
      assignment_id: 'assign-1',
      company_id: 'co-A',
      summary: { status: 'Active.', blockers: [], next_actions: ['file permit'], cost_variance: 'Under budget.' },
      generated_at: '2026-07-25T00:00:00Z',
    };
    apiGetMock.mockResolvedValue(payload);

    const res = await getCaseAiSummary('assign-1');

    expect(apiGetMock).toHaveBeenCalledTimes(1);
    expect(apiGetMock.mock.calls[0][0]).toBe('/api/hr/cases/assign-1/ai-summary');
    expect(res.summary.status).toBe('Active.');
    expect(res.summary.next_actions).toEqual(['file permit']);
  });

  it('encodes the assignment id', async () => {
    apiGetMock.mockResolvedValue({});
    await getCaseAiSummary('a/b');
    expect(apiGetMock.mock.calls[0][0]).toBe('/api/hr/cases/a%2Fb/ai-summary');
  });
});
