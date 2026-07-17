import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', () => ({ useNavigate: () => mockNavigate }));

const mockGetAuthItem = vi.fn();
vi.mock('../utils/demo', () => ({ getAuthItem: (k: string) => mockGetAuthItem(k) as string | null }));

const mockHasSeen = vi.fn();
vi.mock('../utils/welcomeSeen', () => ({ hasSeenWelcome: (id: string) => mockHasSeen(id) as boolean }));

import { useWelcomeRedirect } from './useWelcomeRedirect';

describe('useWelcomeRedirect', () => {
  beforeEach(() => {
    mockNavigate.mockReset();
    mockGetAuthItem.mockReset();
    mockHasSeen.mockReset();
  });

  it('redirects a user who has not seen the welcome', () => {
    mockGetAuthItem.mockReturnValue('user-1');
    mockHasSeen.mockReturnValue(false);
    renderHook(() => useWelcomeRedirect('/hr/welcome'));
    expect(mockNavigate).toHaveBeenCalledWith('/hr/welcome', { replace: true });
  });

  it('does not redirect when the welcome was already seen', () => {
    mockGetAuthItem.mockReturnValue('user-1');
    mockHasSeen.mockReturnValue(true);
    renderHook(() => useWelcomeRedirect('/hr/welcome'));
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('does not redirect when there is no signed-in user id', () => {
    mockGetAuthItem.mockReturnValue('');
    mockHasSeen.mockReturnValue(false);
    renderHook(() => useWelcomeRedirect('/employee/welcome'));
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  // AIQ-1568 (TD-BUG-1): a first-run welcome must greet someone who just logged in — it
  // must never hijack a deliberate destination. The command-center "Add your first
  // relocation" CTA routes here with ?new=1; if this redirect still fired, a fresh
  // test-drive HR would be bounced to onboarding and the CTA would look broken all over
  // again — the same loop, one layer down.
  it('skips the redirect when the user arrived with an explicit intent', () => {
    mockGetAuthItem.mockReturnValue('user-1');
    mockHasSeen.mockReturnValue(false);   // brand-new HR — would normally redirect
    renderHook(() => useWelcomeRedirect('/hr/welcome', { skip: true }));
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('still redirects a fresh user when skip is false', () => {
    mockGetAuthItem.mockReturnValue('user-1');
    mockHasSeen.mockReturnValue(false);
    renderHook(() => useWelcomeRedirect('/hr/welcome', { skip: false }));
    expect(mockNavigate).toHaveBeenCalledWith('/hr/welcome', { replace: true });
  });
});
