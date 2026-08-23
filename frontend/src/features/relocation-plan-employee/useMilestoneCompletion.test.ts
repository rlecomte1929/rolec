/**
 * [AIQ-2057] Ticking a step off the employee's relocation plan.
 *
 * The write endpoint and its API wrapper already existed; nothing could reach them, so
 * Andrea's 16 milestones were a document she could read and not a plan she could work
 * through. This hook is the half that has to be right under failure: an optimistic tick
 * that survives the refetch, and a rejected request that puts the row back rather than
 * leaving a lie on screen.
 */
import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const mockUpdateMilestone = vi.fn();

// api/client loads the Supabase singleton at module scope, which throws with no env.
vi.mock('../../api/supabase', () => ({ supabase: {} }));
vi.mock('../../api/supabaseAuth', () => ({ signOutSupabase: vi.fn() }));
vi.mock('../../api/client', () => ({
  timelineAPI: { updateMilestone: (...a: unknown[]) => mockUpdateMilestone(...a) },
}));

import { useMilestoneCompletion } from './useMilestoneCompletion';

const CASE_ID = 'case-abc';
const TASK = 'milestone-1';

beforeEach(() => {
  mockUpdateMilestone.mockReset();
});

describe('the optimistic tick', () => {
  it('sends the milestone id and the done status through the existing wrapper', async () => {
    mockUpdateMilestone.mockResolvedValue({ id: TASK, status: 'done' });
    const { result } = renderHook(() => useMilestoneCompletion(CASE_ID, vi.fn()));

    await act(async () => {
      await result.current.toggle(TASK, 'not_started');
    });

    expect(mockUpdateMilestone).toHaveBeenCalledWith(CASE_ID, TASK, { status: 'done' });
  });

  it('un-ticks a completed step back to pending', async () => {
    mockUpdateMilestone.mockResolvedValue({ id: TASK, status: 'pending' });
    const { result } = renderHook(() => useMilestoneCompletion(CASE_ID, vi.fn()));

    await act(async () => {
      await result.current.toggle(TASK, 'completed');
    });

    expect(mockUpdateMilestone).toHaveBeenCalledWith(CASE_ID, TASK, { status: 'pending' });
  });

  it('shows the new status immediately, before the server answers', async () => {
    let release: (v: unknown) => void = () => {};
    mockUpdateMilestone.mockReturnValue(new Promise((res) => { release = res; }));
    const { result } = renderHook(() => useMilestoneCompletion(CASE_ID, vi.fn()));

    act(() => { void result.current.toggle(TASK, 'not_started'); });

    await waitFor(() => expect(result.current.statusOverrides[TASK]).toBe('completed'));
    expect(result.current.savingTaskIds.has(TASK)).toBe(true);

    await act(async () => { release({ id: TASK, status: 'done' }); });
  });

  it('keeps the override after success so the refetch does not flash the old status back', async () => {
    mockUpdateMilestone.mockResolvedValue({ id: TASK, status: 'done' });
    const refetch = vi.fn();
    const { result } = renderHook(() => useMilestoneCompletion(CASE_ID, refetch));

    await act(async () => { await result.current.toggle(TASK, 'not_started'); });

    expect(result.current.statusOverrides[TASK]).toBe('completed');
    expect(refetch).toHaveBeenCalledTimes(1);
    expect(result.current.savingTaskIds.has(TASK)).toBe(false);
  });
});

describe('when the write is rejected', () => {
  it('restores the previous status instead of leaving the tick on screen', async () => {
    mockUpdateMilestone.mockRejectedValue(new Error('409'));
    const { result } = renderHook(() => useMilestoneCompletion(CASE_ID, vi.fn()));

    await act(async () => { await result.current.toggle(TASK, 'not_started'); });

    expect(result.current.statusOverrides[TASK]).toBeUndefined();
    expect(result.current.savingTaskIds.has(TASK)).toBe(false);
  });

  it('surfaces an error the page can render — a silent failure is the worst outcome', async () => {
    mockUpdateMilestone.mockRejectedValue(new Error('boom'));
    const { result } = renderHook(() => useMilestoneCompletion(CASE_ID, vi.fn()));

    await act(async () => { await result.current.toggle(TASK, 'not_started'); });

    expect(result.current.error).toMatch(/couldn|could not|try again/i);
  });

  it('does not refetch on failure — there is nothing new to fetch', async () => {
    mockUpdateMilestone.mockRejectedValue(new Error('boom'));
    const refetch = vi.fn();
    const { result } = renderHook(() => useMilestoneCompletion(CASE_ID, refetch));

    await act(async () => { await result.current.toggle(TASK, 'not_started'); });

    expect(refetch).not.toHaveBeenCalled();
  });

  it('a later success clears the earlier error', async () => {
    mockUpdateMilestone.mockRejectedValueOnce(new Error('boom'));
    const { result } = renderHook(() => useMilestoneCompletion(CASE_ID, vi.fn()));
    await act(async () => { await result.current.toggle(TASK, 'not_started'); });
    expect(result.current.error).toBeTruthy();

    mockUpdateMilestone.mockResolvedValue({ id: TASK, status: 'done' });
    await act(async () => { await result.current.toggle(TASK, 'not_started'); });
    expect(result.current.error).toBeNull();
  });
});

describe('guards', () => {
  it('does nothing without a case id — never fire a write at an undefined URL', async () => {
    const { result } = renderHook(() => useMilestoneCompletion(undefined, vi.fn()));
    await act(async () => { await result.current.toggle(TASK, 'not_started'); });
    expect(mockUpdateMilestone).not.toHaveBeenCalled();
  });

  it('ignores a second click while the first is still in flight', async () => {
    let release: (v: unknown) => void = () => {};
    mockUpdateMilestone.mockReturnValue(new Promise((res) => { release = res; }));
    const { result } = renderHook(() => useMilestoneCompletion(CASE_ID, vi.fn()));

    act(() => { void result.current.toggle(TASK, 'not_started'); });
    await waitFor(() => expect(result.current.savingTaskIds.has(TASK)).toBe(true));
    act(() => { void result.current.toggle(TASK, 'not_started'); });

    expect(mockUpdateMilestone).toHaveBeenCalledTimes(1);
    await act(async () => { release({ id: TASK, status: 'done' }); });
  });
});
