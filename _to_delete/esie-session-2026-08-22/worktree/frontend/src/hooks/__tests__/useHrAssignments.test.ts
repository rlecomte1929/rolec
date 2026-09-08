import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor, act, cleanup } from '@testing-library/react';
import { useHrAssignments } from '../useHrAssignments';
import { createWrapper } from './queryTestUtils';
import { hrAPI } from '../../api/client';

vi.mock('../../api/client', () => ({
  hrAPI: { listAssignments: vi.fn() },
  policyConfigMatrixAPI: { hrPublished: vi.fn() },
}));
vi.mock('../../perf/authPerf', () => ({ trackAuthPerf: vi.fn() }));
vi.mock('../../perf/pagePerf', () => ({
  trackFirstMeaningfulContent: vi.fn(),
  trackRouteEntry: vi.fn(),
  trackShellRender: vi.fn(),
}));
vi.mock('../../navigation/safeNavigate', () => ({ safeNavigate: vi.fn() }));

const mockList = hrAPI.listAssignments as unknown as ReturnType<typeof vi.fn>;

const page = (n: number, start = 0): Array<{ id: string }> =>
  Array.from({ length: n }, (_, i) => ({ id: `a${start + i}` }));

const filters = { search: '', status: 'all', destination: '' };

beforeEach(() => {
  // jsdom in this project doesn't expose localStorage; provide an in-memory stub.
  const store = new Map<string, string>();
  vi.stubGlobal('localStorage', {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => {
      store.set(k, v);
    },
    removeItem: (k: string) => {
      store.delete(k);
    },
    clear: () => store.clear(),
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe('useHrAssignments', () => {
  it('loads the first page, exposes total/hasMore, and writes the last-assignment id', async () => {
    mockList.mockResolvedValueOnce({ assignments: page(25), total: 40 });
    const ref = { current: 123 as number | null };

    const { result } = renderHook(() => useHrAssignments(filters, ref), { wrapper: createWrapper() });

    expect(result.current.isLoading).toBe(true);
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.assignments).toHaveLength(25);
    expect(result.current.total).toBe(40);
    expect(result.current.hasMore).toBe(true);
    expect(localStorage.getItem('relopass_last_assignment_id')).toBe('a0');
    expect(mockList.mock.calls[0][0]).toMatchObject({ offset: 0, limit: 25 });
  });

  it('appends the next page via loadMore and stops once total is reached', async () => {
    mockList
      .mockResolvedValueOnce({ assignments: page(25, 0), total: 40 })
      .mockResolvedValueOnce({ assignments: page(15, 25), total: 40 });
    const ref = { current: null as number | null };

    const { result } = renderHook(() => useHrAssignments(filters, ref), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.assignments).toHaveLength(25));

    act(() => result.current.loadMore());
    await waitFor(() => expect(result.current.assignments).toHaveLength(40));

    expect(result.current.hasMore).toBe(false);
    expect(mockList.mock.calls[1][0]).toMatchObject({ offset: 25, limit: 25 });
  });

  it('surfaces a fetch failure via isError without crashing', async () => {
    mockList.mockRejectedValueOnce(new Error('boom'));
    const ref = { current: null as number | null };

    const { result } = renderHook(() => useHrAssignments(filters, ref), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.assignments).toHaveLength(0);
    expect(result.current.total).toBe(0);
  });
});
