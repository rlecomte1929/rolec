import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock the transport so we can count network calls without pulling api/supabase.
const apiGet = vi.fn();
vi.mock('./client', () => ({ apiGet: (...a: unknown[]) => apiGet(...a) }));

import { fetchRelocationPlanView } from './relocationPlanView';

describe('fetchRelocationPlanView — in-flight dedup', () => {
  beforeEach(() => apiGet.mockReset());

  it('collapses concurrent identical requests into a single network call', async () => {
    let resolveFn: (v: unknown) => void = () => {};
    apiGet.mockReturnValueOnce(new Promise((res) => { resolveFn = res; }));

    // 7 consumers mount and fetch on the same tick (the roadmap scenario).
    const ps = Array.from({ length: 7 }, () =>
      fetchRelocationPlanView('case-1', { role: 'employee' }),
    );
    resolveFn({ ok: true });
    const results = await Promise.all(ps);

    expect(apiGet).toHaveBeenCalledTimes(1);
    // All sharers resolve to the same object.
    expect(new Set(results).size).toBe(1);
  });

  it('re-fetches fresh once the in-flight request has settled', async () => {
    apiGet.mockResolvedValue({ ok: true });
    await fetchRelocationPlanView('case-2', { role: 'employee' });
    await fetchRelocationPlanView('case-2', { role: 'employee' }); // sequential → not deduped
    expect(apiGet).toHaveBeenCalledTimes(2);
  });

  it('does not dedup across different case/role keys', async () => {
    apiGet.mockResolvedValue({ ok: true });
    const a = fetchRelocationPlanView('case-3', { role: 'employee' });
    const b = fetchRelocationPlanView('case-3', { role: 'hr' });
    const c = fetchRelocationPlanView('case-4', { role: 'employee' });
    // Different request paths → each fires (the dedup decision is synchronous).
    expect(apiGet).toHaveBeenCalledTimes(3);
    await Promise.all([a, b, c]);
  });
});
