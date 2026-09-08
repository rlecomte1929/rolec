import '@testing-library/jest-dom/vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';

// api/client pulls in api/supabase, which breaks the jsdom test env — mock it.
vi.mock('../../api/client', () => ({ authAPI: { logout: vi.fn() } }));

const acceptMock = vi.fn();
const stashMock = vi.fn();
const clearMock = vi.fn();
vi.mock('../../api/companyInvites', () => ({
  companyInvitesAPI: { accept: (t: string) => acceptMock(t) },
  stashPendingInvite: (t: string) => stashMock(t),
  clearPendingInvite: () => clearMock(),
  readPendingInvite: vi.fn(() => null),
}));

// Control auth state per test without touching real storage.
let authToken: string | null = null;
vi.mock('../../utils/demo', () => ({
  getAuthItem: (k: string) =>
    k === 'relopass_token' ? authToken : k === 'relopass_role' ? 'HR' : null,
  clearAuthItems: vi.fn(),
}));

const navigateMock = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => navigateMock };
});

import { InviteAccept } from '../InviteAccept';

// jsdom in this project ships no localStorage; safeNavigate() uses it directly. Shim it.
const _store = new Map<string, string>();
Object.defineProperty(window, 'localStorage', {
  configurable: true,
  writable: true,
  value: {
    getItem: (k: string) => (_store.has(k) ? _store.get(k)! : null),
    setItem: (k: string, v: string) => void _store.set(k, String(v)),
    removeItem: (k: string) => void _store.delete(k),
    clear: () => _store.clear(),
    key: (i: number) => Array.from(_store.keys())[i] ?? null,
    get length() {
      return _store.size;
    },
  },
});

const TOKEN = 'raw-accept-token-abc123';

function renderAt(token = TOKEN) {
  return render(
    <MemoryRouter initialEntries={[`/invite/${token}`]}>
      <Routes>
        <Route path="/invite/:token" element={<InviteAccept />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('InviteAccept', () => {
  beforeEach(() => {
    authToken = null;
    acceptMock.mockReset();
    stashMock.mockReset();
    clearMock.mockReset();
    navigateMock.mockReset();
  });

  it('signposts "create an account first" when logged out, and never redeems', async () => {
    authToken = null;
    renderAt();
    expect(await screen.findByRole('button', { name: /create your account/i })).toBeInTheDocument();
    // the token is carried across the register/login round trip, and no redeem is attempted
    expect(stashMock).toHaveBeenCalledWith(TOKEN);
    expect(acceptMock).not.toHaveBeenCalled();
  });

  it('redeems automatically when logged in as the invited person, then leaves for the app', async () => {
    authToken = 'session';
    acceptMock.mockResolvedValue({ id: 'inv-1', status: 'accepted', company_id: 'c1' });
    renderAt();
    await waitFor(() => expect(acceptMock).toHaveBeenCalledWith(TOKEN));
    await waitFor(() => expect(clearMock).toHaveBeenCalled()); // stash cleared on success
    await waitFor(() => expect(navigateMock).toHaveBeenCalled()); // routed into the app
  });

  it('shows a readable message (not a raw error) when logged in as a different person (403)', async () => {
    authToken = 'session';
    acceptMock.mockRejectedValue({ status: 403 });
    renderAt();
    expect(await screen.findByText(/different email address/i)).toBeInTheDocument();
    // keeps the token so re-auth as the invited email can finish the round trip
    expect(stashMock).toHaveBeenCalledWith(TOKEN);
  });

  it('renders a readable expiry message on 410', async () => {
    authToken = 'session';
    acceptMock.mockRejectedValue({ status: 410 });
    renderAt();
    expect(await screen.findByText(/expired/i)).toBeInTheDocument();
  });

  it('never writes the raw token to the console', async () => {
    const spies = [
      vi.spyOn(console, 'log').mockImplementation(() => {}),
      vi.spyOn(console, 'warn').mockImplementation(() => {}),
      vi.spyOn(console, 'error').mockImplementation(() => {}),
    ];
    authToken = 'session';
    acceptMock.mockResolvedValue({ id: 'inv-1', status: 'accepted', company_id: 'c1' });
    renderAt();
    await waitFor(() => expect(acceptMock).toHaveBeenCalled());
    for (const spy of spies) {
      for (const call of spy.mock.calls) {
        expect(JSON.stringify(call)).not.toContain(TOKEN);
      }
      spy.mockRestore();
    }
  });
});
