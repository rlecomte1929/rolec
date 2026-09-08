import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock the transport so we can count network calls without pulling api/supabase.
const apiGet = vi.fn();
vi.mock('./client', () => ({ apiGet: (...a: unknown[]) => apiGet(...a) }));

import { fetchRelocationPlanView } from './relocationPlanView';

describe('fetchRelocationPlanView — short-window dedup', () => {
  beforeEach(() => {
    apiGet.mockReset();
    vi.useFakeTimers();
    vi.setSystemTime(0);
  });
  afterEach(() => vi.useRealTimers());

  it('collapses a mount/poll burst (concurrent + within-window) into one call', async () => {
    apiGet.mockResolvedValue({ ok: 1 });
    const a = fetchRelocationPlanView('c', { role: 'employee' }); // t=0
    vi.setSystemTime(900);
    const b = fetchRelocationPlanView('c', { role: 'employee' }); // +0.9s — within window
    vi.setSystemTime(2000);
    const c = fetchRelocationPlanView('c', { role: 'employee' }); // +2.0s — still < 2.5s
    await Promise.all([a, b, c]);
    expect(apiGet).toHaveBeenCalledTimes(1);
  });

  it('re-fetches fresh once the window has elapsed (e.g. the ~6s poll)', async () => {
    apiGet.mockResolvedValue({ ok: 1 });
    await fetchRelocationPlanView('c2', { role: 'employee' }); // t=0
    vi.setSystemTime(3000); // past the 2.5s window
    await fetchRelocationPlanView('c2', { role: 'employee' });
    expect(apiGet).toHaveBeenCalledTimes(2);
  });

  it('forceFresh bypasses the window (post-seed refetch reads new data)', async () => {
    apiGet.mockResolvedValue({ ok: 1 });
    await fetchRelocationPlanView('c3', { role: 'employee' }); // t=0
    vi.setSystemTime(500);
    await fetchRelocationPlanView('c3', { role: 'employee', forceFresh: true }); // within window, forced fresh
    expect(apiGet).toHaveBeenCalledTimes(2);
  });

  it('evicts on error so a retry re-fetches (errors never cache)', async () => {
    apiGet.mockRejectedValueOnce(new Error('boom')).mockResolvedValueOnce({ ok: 1 });
    await expect(fetchRelocationPlanView('c4', { role: 'employee' })).rejects.toThrow();
    vi.setSystemTime(500); // within window, but the errored entry was evicted
    await fetchRelocationPlanView('c4', { role: 'employee' });
    expect(apiGet).toHaveBeenCalledTimes(2);
  });

  it('does not dedup across different case/role keys', async () => {
    apiGet.mockResolvedValue({ ok: 1 });
    const a = fetchRelocationPlanView('c5', { role: 'employee' });
    const b = fetchRelocationPlanView('c5', { role: 'hr' });
    const c = fetchRelocationPlanView('c6', { role: 'employee' });
    expect(apiGet).toHaveBeenCalledTimes(3);
    await Promise.all([a, b, c]);
  });
});
