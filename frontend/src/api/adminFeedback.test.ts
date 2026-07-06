import { describe, it, expect, vi, beforeEach } from 'vitest';

const apiGet = vi.fn();
vi.mock('./client', () => ({
  apiGet: (...args: unknown[]) => apiGet(...args),
  apiPost: vi.fn(),
  apiPatch: vi.fn(),
}));

import { listFeedback } from './adminFeedback';

describe('listFeedback', () => {
  beforeEach(() => apiGet.mockReset());

  it('coerces the backend has_screenshot 0/1 to a real boolean', async () => {
    apiGet.mockResolvedValue({
      items: [
        { id: 'a', has_screenshot: 0 },
        { id: 'b', has_screenshot: 1 },
      ],
    });
    const rows = await listFeedback();
    // 0 must become false (not the number 0) so JSX `{row.has_screenshot && …}`
    // renders nothing instead of a stray "0".
    expect(rows[0].has_screenshot).toBe(false);
    expect(rows[1].has_screenshot).toBe(true);
  });
});
