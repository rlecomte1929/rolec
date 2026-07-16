import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act, fireEvent, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { TestDriveFrictionPrompt, stageFromPath } from './TestDriveFrictionPrompt';

const mockGetSession = vi.fn();
const mockEmitFriction = vi.fn();
vi.mock('../api/testDrive', () => ({
  getTestDriveSession: () => mockGetSession(),
  emitTestDriveFriction: (...a: unknown[]) => mockEmitFriction(...a),
}));

function renderAt(path: string, idleMs = 1000) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <TestDriveFrictionPrompt idleMs={idleMs} />
    </MemoryRouter>,
  );
}

describe('TestDriveFrictionPrompt', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockGetSession.mockReset();
    mockEmitFriction.mockReset();
  });
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it('stageFromPath maps journey routes to coarse stages', () => {
    expect(stageFromPath('/employee/case/abc/intake')).toBe('intake');
    expect(stageFromPath('/employee/case/abc/roadmap')).toBe('roadmap');
    expect(stageFromPath('/hr/dashboard')).toBe('hr');
  });

  it('is a complete no-op for real users (no test-drive session)', () => {
    mockGetSession.mockReturnValue(null);
    renderAt('/employee/case/abc/intake');
    void act(() => vi.advanceTimersByTime(5000));
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(mockEmitFriction).not.toHaveBeenCalled();
  });

  it('fires after idle-on-stage and records the reason + stage on send', () => {
    mockGetSession.mockReturnValue({ session_id: 's1', campaign: 'qa', corridor_id: 'FR_NO' });
    renderAt('/employee/case/abc/intake', 1000);
    // Active tester never trips it; here we simulate a stall by advancing past the idle window.
    void act(() => vi.advanceTimersByTime(1100));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Confusing' }));
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));
    expect(mockEmitFriction).toHaveBeenCalledTimes(1);
    expect(mockEmitFriction).toHaveBeenCalledWith('intake', 'confusing', '');
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('does not fire twice for the same stage after it was answered', () => {
    mockGetSession.mockReturnValue({ session_id: 's1' });
    renderAt('/employee/case/abc/intake', 1000);
    void act(() => vi.advanceTimersByTime(1100));
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));
    expect(mockEmitFriction).toHaveBeenCalledTimes(1);
    // Idle again on the same stage → must not re-prompt.
    void act(() => vi.advanceTimersByTime(3000));
    expect(screen.queryByRole('dialog')).toBeNull();
  });
});
