/**
 * AIQ-1856 — the batch recommendations call must outlast the work it triggers.
 *
 * Production (BUG-260817-8F10): POST /api/recommendations/batch returned 200 OK after
 * 11,963 ms. The axios instance's default timeout is 12,000 ms, so the client aborted
 * 77 ms before the response arrived and logged it as a status-0 failed request — the
 * employee was told the server was unreachable for work that had already succeeded.
 *
 * This endpoint fans out one engine run per selected service, so multi-second responses
 * are its normal cost, not a fault. It must therefore carry an explicit timeout well
 * clear of the 12s default (which exists to surface a genuinely dead API quickly).
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';

const post = vi.fn();

vi.mock('../../../api/client', () => ({
  default: { post, get: vi.fn() },
}));

const DEFAULT_AXIOS_TIMEOUT_MS = 12_000;

describe('recommendationsEngineAPI.recommendBatch', () => {
  beforeEach(() => {
    post.mockReset();
    post.mockResolvedValue({ data: { results: {} } });
  });

  it('overrides the 12s default timeout so a slow-but-successful batch is not aborted', async () => {
    const { recommendationsEngineAPI } = await import('../api');
    await recommendationsEngineAPI.recommendBatch('asg-1', ['movers', 'schools']);

    expect(post).toHaveBeenCalledTimes(1);
    const [url, body, config] = post.mock.calls[0];
    expect(url).toBe('/api/recommendations/batch');
    expect(body).toMatchObject({ assignment_id: 'asg-1', selected_services: ['movers', 'schools'] });
    expect(config?.timeout).toBeGreaterThan(DEFAULT_AXIOS_TIMEOUT_MS);
  });

  it('still sends shortlisted area ids only when there are some', async () => {
    const { recommendationsEngineAPI } = await import('../api');

    await recommendationsEngineAPI.recommendBatch('asg-1', ['housing'], ['area-1']);
    expect(post.mock.calls[0][1]).toMatchObject({ shortlisted_area_ids: ['area-1'] });

    post.mockClear();
    await recommendationsEngineAPI.recommendBatch('asg-1', ['housing'], []);
    expect(post.mock.calls[0][1].shortlisted_area_ids).toBeUndefined();
  });
});
