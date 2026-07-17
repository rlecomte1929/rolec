import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// Mock the network client (also keeps the test off client.ts's supabase import chain).
vi.mock('../../api/testDrive', () => ({
  provisionTestDrive: vi.fn(),
  recordTestDriveEvent: vi.fn(),
  completeTestDrive: vi.fn(),
}));
// The marketing barrel transitively imports api/supabase, whose createClient throws
// in jsdom when VITE_SUPABASE_* are unset — neutralise it (known vitest trap).
vi.mock('../../api/supabase', () => ({ supabase: { functions: { invoke: vi.fn() } } }));
// AIQ-1569: the signed-in guard calls the canonical sign-out.
const mockLogout = vi.fn().mockResolvedValue(undefined);
vi.mock('../../api/client', () => ({ authAPI: { logout: () => mockLogout() } }));
// Passthrough layout — avoids pulling PublicHeader/Footer providers into the unit test.
vi.mock('../../components/public', () => ({
  PublicLayout: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

import { provisionTestDrive, completeTestDrive, recordTestDriveEvent } from '../../api/testDrive';
import { TestDrivePage } from './TestDrivePage';

// jsdom has no matchMedia; the marketing FadeIn reads it on mount.
if (!window.matchMedia) {
  window.matchMedia = (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  });
}

// AIQ-1569: this jsdom setup has NO window.localStorage — a bare getItem throws, which is
// how the signed-in guard first crashed the whole credentials block here. Shim a
// Map-backed one (same spirit as the matchMedia shim above) so the session can be staged.
// The product code guards its own reads regardless: private-browsing modes throw for real.
if (!window.localStorage) {
  const store = new Map<string, string>();
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: {
      getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
      setItem: (k: string, v: string) => void store.set(k, String(v)),
      removeItem: (k: string) => void store.delete(k),
      clear: () => store.clear(),
      key: (i: number) => [...store.keys()][i] ?? null,
      get length() { return store.size; },
    },
  });
}

const mockProvision = provisionTestDrive as unknown as ReturnType<typeof vi.fn>;
const mockComplete = completeTestDrive as unknown as ReturnType<typeof vi.fn>;
const mockRecordEvent = recordTestDriveEvent as unknown as ReturnType<typeof vi.fn>;

const OK_RESULT = {
  ok: true as const, sessionId: 's-qa', corridorId: 'FR_NO', campaign: 'qa-posthog',
  hr: { username: 'HR-qa', email: 'hr-qa@probe.test', password: 'p', role: 'HR' as const },
  employee: { username: 'EMP-qa', email: 'emp-qa@probe.test', password: 'p', role: 'EMPLOYEE' as const },
};

function renderAt(search: string) {
  return render(
    <MemoryRouter initialEntries={[`/test-drive${search}`]}>
      <TestDrivePage />
    </MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  vi.clearAllMocks();
});

describe('TestDrivePage', () => {
  it('[AIQ-1563] forwards ?campaign= to provision and the funnel click event', async () => {
    mockProvision.mockResolvedValue(OK_RESULT);
    renderAt('?campaign=qa-posthog');
    // the click event fires on mount, tagged with the campaign
    await waitFor(() => expect(mockRecordEvent).toHaveBeenCalled());
    expect(mockRecordEvent).toHaveBeenCalledWith(
      expect.objectContaining({ event_type: 'click', campaign: 'qa-posthog' }),
    );
    // and provision carries it
    fireEvent.change(screen.getByLabelText(/first name/i), { target: { value: 'QA' } });
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'qa@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: /start the test/i }));
    await waitFor(() => expect(mockProvision).toHaveBeenCalledTimes(1));
    expect(mockProvision).toHaveBeenCalledWith(expect.objectContaining({ campaign: 'qa-posthog' }));
  });

  it('[AIQ-1563] omits campaign when ?campaign= is absent (plain cohort link unchanged)', async () => {
    mockProvision.mockResolvedValue({ ...OK_RESULT, campaign: 'insead-2026' });
    renderAt('');
    fireEvent.change(screen.getByLabelText(/first name/i), { target: { value: 'Plain' } });
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'plain@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: /start the test/i }));
    await waitFor(() => expect(mockProvision).toHaveBeenCalledTimes(1));
    expect('campaign' in mockProvision.mock.calls[0][0]).toBe(false);
  });

  it('renders the hero + corridor label for a Tier-A corridor, no early-coverage note', () => {
    renderAt('?corridor=FR_NO&token=t');
    expect(
      screen.getByRole('heading', { name: /Run one relocation, end to end/i }),
    ).toBeInTheDocument();
    expect(screen.getAllByText(/Paris → Oslo/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/early coverage/i)).not.toBeInTheDocument();
    // TD-FIX-5 + TD-FIX-7: the HR step still names the assigned route, but as a statement
    // of fact — the corridor is now pinned on the case server-side, and the tester has no
    // route field to set.
    expect(
      screen.getByText(/Your route is already set: Paris → Oslo\./i),
    ).toBeInTheDocument();
  });

  it('shows the Tier-B early-coverage note only for a Tier-B corridor', () => {
    renderAt('?corridor=GB_US&token=t');
    expect(screen.getAllByText(/London → New York/).length).toBeGreaterThan(0);
    expect(screen.getByText(/early coverage/i)).toBeInTheDocument();
  });

  it('hides corridor label when ?corridor= is unknown (shown only after server assigns)', () => {
    renderAt('?corridor=ZZ_ZZ&token=t');
    // Unknown corridor → assignedCorridorId null until provision → no corridor section
    expect(screen.queryByText(/Paris → Oslo/)).not.toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: /Run one relocation, end to end/i }),
    ).toBeInTheDocument();
  });

  it('provisions with the corridor + invite token from the URL and shows both credential sets', async () => {
    mockProvision.mockResolvedValue({
      ok: true,
      sessionId: 's1',
      corridorId: 'GB_US',
      campaign: 'insead-2026',
      hr: { username: 'HR-alex-1a2b', email: 'hr-alex@probe.test', password: 'pw-hr', role: 'HR' },
      employee: {
        username: 'EMP-alex-1a2b',
        email: 'emp-alex@probe.test',
        password: 'pw-emp',
        role: 'EMPLOYEE',
      },
    });
    renderAt('?corridor=GB_US&token=invite-xyz');

    fireEvent.change(screen.getByLabelText(/first name/i), { target: { value: 'Alex' } });
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'tester@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: /start the test/i }));

    await waitFor(() => expect(mockProvision).toHaveBeenCalledTimes(1));
    // TD-FIX-2 (AIQ-1503): no ?segment= on the single link → segment left undefined
    // at provision (resolved later by the survey one-tap), never silently 'prospect'.
    expect(mockProvision).toHaveBeenCalledWith({
      first_name: 'Alex',
      tester_email: 'tester@example.com',
      corridor_id: 'GB_US',
      tester_segment: undefined,
      invite_token: 'invite-xyz',
    });
    // The card shows the login email (login accepts email or username).
    expect(await screen.findByText('hr-alex@probe.test')).toBeInTheDocument();
    expect(screen.getByText('emp-alex@probe.test')).toBeInTheDocument();
    // TD-FIX-7 (AIQ-1510): the credentials block restates the assigned route at the
    // moment the tester picks up their logins — and it follows THIS session's corridor
    // (GB_US), not a hardcoded default. Plain text: no emphasis on any word.
    const corridorNote = screen.getByText(
      /Your test: London → New York — already set for you\./i,
    );
    expect(corridorNote).toBeInTheDocument();
    expect(corridorNote.querySelector('strong, b, em')).toBeNull();
  });

  it('provisions from a bare /test-drive URL (no token) with invite_token undefined', async () => {
    mockProvision.mockResolvedValue({
      ok: true,
      sessionId: 's2',
      corridorId: 'FR_NO',
      campaign: 'insead-2026',
      hr: { username: 'HR-r-1a2b', email: 'hr-r@probe.test', password: 'pw-hr', role: 'HR' },
      employee: { username: 'EMP-r-1a2b', email: 'emp-r@probe.test', password: 'pw-emp', role: 'EMPLOYEE' },
    });
    renderAt('');

    fireEvent.change(screen.getByLabelText(/first name/i), { target: { value: 'Romain' } });
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'tester@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: /start the test/i }));

    await waitFor(() => expect(mockProvision).toHaveBeenCalledTimes(1));
    expect(mockProvision).toHaveBeenCalledWith({
      first_name: 'Romain',
      tester_email: 'tester@example.com',
      tester_segment: undefined,
      invite_token: undefined,
    });
  });

  it('provisions with NO email — declining contact is a valid choice (AIQ-1556)', async () => {
    // The relocation data is synthetic, so nothing here may force real PII. A tester who
    // does not consent to a follow-up must still get the full test: no error, no block,
    // and tester_email simply omitted from the payload (stored NULL server-side).
    mockProvision.mockResolvedValue({
      ok: true,
      sessionId: 's3',
      corridorId: 'FR_NO',
      campaign: 'insead-2026',
      hr: { username: 'HR-r-1a2b', email: 'hr-r@probe.test', password: 'pw-hr', role: 'HR' },
      employee: { username: 'EMP-r-1a2b', email: 'emp-r@probe.test', password: 'pw-emp', role: 'EMPLOYEE' },
    });
    renderAt('');

    fireEvent.change(screen.getByLabelText(/first name/i), { target: { value: 'Romain' } });
    // Email deliberately left untouched.
    fireEvent.click(screen.getByRole('button', { name: /start the test/i }));

    await waitFor(() => expect(mockProvision).toHaveBeenCalledTimes(1));
    expect(mockProvision).toHaveBeenCalledWith({
      first_name: 'Romain',
      tester_segment: undefined,
      invite_token: undefined,
    });
    // The tester still gets their logins on screen — nothing is gated behind the email.
    expect(await screen.findByText('hr-r@probe.test')).toBeInTheDocument();
    expect(screen.getByText('emp-r@probe.test')).toBeInTheDocument();
  });

  it('still rejects a malformed email that was actually typed (AIQ-1556)', async () => {
    // Optional does not mean unvalidated: if they opt in, the address must be usable.
    renderAt('');
    fireEvent.change(screen.getByLabelText(/first name/i), { target: { value: 'Romain' } });
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'notanemail' } });
    fireEvent.click(screen.getByRole('button', { name: /start the test/i }));

    expect(await screen.findByText(/valid email address/i)).toBeInTheDocument();
    expect(mockProvision).not.toHaveBeenCalled();
  });

  it('honours an explicit ?segment=internal at provision (TD-FIX-2)', async () => {
    mockProvision.mockResolvedValue({
      ok: true,
      sessionId: 's3',
      corridorId: 'FR_NO',
      campaign: 'insead-2026',
      hr: { username: 'HR-d-1a2b', email: 'hr-d@probe.test', password: 'pw-hr', role: 'HR' },
      employee: { username: 'EMP-d-1a2b', email: 'emp-d@probe.test', password: 'pw-emp', role: 'EMPLOYEE' },
    });
    renderAt('?corridor=FR_NO&token=t&segment=internal');

    fireEvent.change(screen.getByLabelText(/first name/i), { target: { value: 'Dana' } });
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'tester@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: /start the test/i }));

    await waitFor(() => expect(mockProvision).toHaveBeenCalledTimes(1));
    expect(mockProvision).toHaveBeenCalledWith({
      first_name: 'Dana',
      tester_email: 'tester@example.com',
      corridor_id: 'FR_NO',
      tester_segment: 'internal',
      invite_token: 't',
    });
  });

  it("records completion via POST /complete when 'I've completed my test' is clicked (TD-FIX-1)", async () => {
    mockProvision.mockResolvedValue({
      ok: true,
      sessionId: 'sess-42',
      corridorId: 'GB_US',
      campaign: 'insead-2026',
      hr: { username: 'HR-alex-1a2b', email: 'hr-alex@probe.test', password: 'pw-hr', role: 'HR' },
      employee: { username: 'EMP-alex-1a2b', email: 'emp-alex@probe.test', password: 'pw-emp', role: 'EMPLOYEE' },
    });
    mockComplete.mockResolvedValue(undefined);
    renderAt('?corridor=GB_US&token=invite-xyz');

    fireEvent.change(screen.getByLabelText(/first name/i), { target: { value: 'Alex' } });
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'tester@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: /start the test/i }));

    const cta = await screen.findByRole('button', { name: /i've completed my test/i });
    fireEvent.click(cta);

    // The session is marked complete before the tester is routed to the survey.
    await waitFor(() => expect(mockComplete).toHaveBeenCalledWith('sess-42'));
  });

  it('surfaces the API error and does not show credentials', async () => {
    mockProvision.mockResolvedValue({ ok: false, error: 'This invite link is invalid or has expired.' });
    renderAt('?corridor=FR_NO');

    fireEvent.change(screen.getByLabelText(/first name/i), { target: { value: 'Sam' } });
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'tester@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: /start the test/i }));

    expect(await screen.findByText(/invite link is invalid/i)).toBeInTheDocument();
    expect(screen.queryByText(/Your two test logins/i)).not.toBeInTheDocument();
  });

  // ── AIQ-1569 (TD-BUG-2) ──────────────────────────────────────────────────────
  // The page assumed a logged-out visitor. Anyone with a live ReloPass session —
  // Romain demoing to an investor, or a tester who already has an account — clicked
  // "Sign in →" and landed in their OWN account, not the test HR login.

  it('logged out: the Sign in link is unchanged', async () => {
    mockProvision.mockResolvedValue(OK_RESULT);
    renderAt('');
    fireEvent.change(screen.getByLabelText(/first name/i), { target: { value: 'Plain' } });
    fireEvent.click(screen.getByRole('button', { name: /start the test/i }));
    await screen.findByText('hr-qa@probe.test');
    expect(screen.getByRole('link', { name: /sign in/i })).toBeInTheDocument();
    expect(screen.queryByTestId('td-signed-in-guard')).toBeNull();
  });

  it('already signed in: names the account and offers sign-out instead of a silent login', async () => {
    window.localStorage.setItem('relopass_token', 'tok-123');
    window.localStorage.setItem('relopass_email', 'admin@relopass.com');
    mockProvision.mockResolvedValue(OK_RESULT);
    renderAt('');
    fireEvent.change(screen.getByLabelText(/first name/i), { target: { value: 'Romain' } });
    fireEvent.click(screen.getByRole('button', { name: /start the test/i }));

    expect(await screen.findByTestId('td-signed-in-guard')).toHaveTextContent('admin@relopass.com');
    // The bare link is what dropped the user into their own account — it must be gone.
    expect(screen.queryByRole('link', { name: /^Sign in/i })).toBeNull();
  });

  it('the sign-out button calls the canonical logout', async () => {
    window.localStorage.setItem('relopass_token', 'tok-123');
    window.localStorage.setItem('relopass_email', 'admin@relopass.com');
    mockProvision.mockResolvedValue(OK_RESULT);
    renderAt('');
    fireEvent.change(screen.getByLabelText(/first name/i), { target: { value: 'Romain' } });
    fireEvent.click(screen.getByRole('button', { name: /start the test/i }));

    fireEvent.click(await screen.findByTestId('td-sign-out'));
    await waitFor(() => expect(mockLogout).toHaveBeenCalled());
  });

  it('storage throwing (private mode) degrades to the plain link, never a crash', async () => {
    const spy = vi.spyOn(window.localStorage, 'getItem').mockImplementation(() => {
      throw new Error('SecurityError: storage disabled');
    });
    mockProvision.mockResolvedValue(OK_RESULT);
    renderAt('');
    fireEvent.change(screen.getByLabelText(/first name/i), { target: { value: 'Priv' } });
    fireEvent.click(screen.getByRole('button', { name: /start the test/i }));
    // The credentials block must still render — the tester's logins are the whole point.
    expect(await screen.findByText('hr-qa@probe.test')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /sign in/i })).toBeInTheDocument();
    spy.mockRestore();
  });
});
