import { afterEach, describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor, cleanup } from '@testing-library/react';
import { usePolicyPublished } from '../usePolicyPublished';
import { createWrapper } from './queryTestUtils';
import { policyConfigMatrixAPI } from '../../api/client';

vi.mock('../../api/client', () => ({
  hrAPI: { listAssignments: vi.fn() },
  policyConfigMatrixAPI: { hrPublished: vi.fn() },
}));

const mockPublished = policyConfigMatrixAPI.hrPublished as unknown as ReturnType<typeof vi.fn>;

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('usePolicyPublished', () => {
  it('starts null (unknown) then resolves true when a version is published', async () => {
    mockPublished.mockResolvedValueOnce({ version_number: 3, published_at: '2026-06-01' });

    const { result } = renderHook(() => usePolicyPublished(), { wrapper: createWrapper() });

    expect(result.current).toBeNull();
    await waitFor(() => expect(result.current).toBe(true));
  });

  it('resolves false when nothing is published', async () => {
    mockPublished.mockResolvedValueOnce({ version_number: 0, published_at: null });

    const { result } = renderHook(() => usePolicyPublished(), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current).toBe(false));
  });

  it('stays null (never false) when the check fails', async () => {
    mockPublished.mockRejectedValueOnce(new Error('nope'));

    const { result } = renderHook(() => usePolicyPublished(), { wrapper: createWrapper() });

    await waitFor(() => expect(mockPublished).toHaveBeenCalled());
    // Give the rejected query a chance to settle; it must remain unknown, not flip to false.
    await new Promise((r) => setTimeout(r, 20));
    expect(result.current).toBeNull();
  });
});
