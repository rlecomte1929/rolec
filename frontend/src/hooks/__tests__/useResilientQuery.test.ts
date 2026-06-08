import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor, cleanup } from '@testing-library/react';
import { useResilientQuery } from '../useResilientQuery';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('useResilientQuery (AIQ-655)', () => {
  it('resolves: sets data and clears loading', async () => {
    const { result } = renderHook(() =>
      useResilientQuery(async () => 'value', []),
    );
    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toBe('value');
    expect(result.current.error).toBeNull();
  });

  it('surfaces a rejection as an Error', async () => {
    const { result } = renderHook(() =>
      useResilientQuery(async () => {
        throw new Error('boom');
      }, []),
    );
    await waitFor(() => expect(result.current.error).not.toBeNull());
    expect(result.current.error?.message).toBe('boom');
    expect(result.current.data).toBeNull();
  });

  it('retry() re-runs the fetcher', async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce('first')
      .mockResolvedValueOnce('second');
    const { result } = renderHook(() => useResilientQuery(fetcher, []));
    await waitFor(() => expect(result.current.data).toBe('first'));

    act(() => result.current.retry());
    await waitFor(() => expect(result.current.data).toBe('second'));
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it('ignores a stale (aborted) run that resolves after a retry', async () => {
    // First run hangs until we release it; the retry resolves immediately.
    let releaseFirst: (v: string) => void = () => {};
    const fetcher = vi
      .fn()
      .mockImplementationOnce(
        () => new Promise<string>((res) => { releaseFirst = res; }),
      )
      .mockResolvedValueOnce('fresh');

    const { result } = renderHook(() => useResilientQuery(fetcher, []));
    act(() => result.current.retry()); // aborts run #1, starts run #2
    await waitFor(() => expect(result.current.data).toBe('fresh'));

    // Run #1 resolves late — its result must NOT overwrite the fresh data.
    act(() => releaseFirst('stale'));
    await Promise.resolve();
    expect(result.current.data).toBe('fresh');
  });

  it('tracks offline/online via window events', async () => {
    const { result } = renderHook(() => useResilientQuery(async () => 'x', []));
    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => {
      window.dispatchEvent(new Event('offline'));
    });
    expect(result.current.isOffline).toBe(true);
    act(() => {
      window.dispatchEvent(new Event('online'));
    });
    expect(result.current.isOffline).toBe(false);
  });
});
