/**
 * AIQ-1571 (TD-BUG-4) — the HR welcome must not bury the case behind company setup for a
 * test-drive session.
 *
 * The campaign asks testers to "run the HR side — configure the case and hand it to the
 * employee". This page answered with "Set up your company workspace": a 12-field
 * company-profile form badged "Start here", with the case CTA below a divider at the
 * bottom. Testers did sysadmin work before reaching the point of the test.
 *
 * The fix inverts the emphasis for test accounts ONLY. A real HR genuinely should
 * configure their company first — it pre-fills every case they open — so these tests pin
 * both paths, not just the new one.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

expect.extend(matchers);

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => ({
  ...(await vi.importActual<Record<string, unknown>>('react-router-dom')),
  useNavigate: () => mockNavigate,
}));

const mockGetAuthItem = vi.fn();
vi.mock('../../utils/demo', () => ({ getAuthItem: (k: string) => mockGetAuthItem(k) as string | null }));
vi.mock('../../utils/welcomeSeen', () => ({ markWelcomeSeen: vi.fn() }));
// WelcomeShell reaches api/supabase via the client chain; createClient throws in jsdom
// with VITE_SUPABASE_* unset (the known vitest trap). Stub the shell — this test is about
// which landing renders, not the chrome around it.
vi.mock('../../components/WelcomeShell', () => ({
  WelcomeShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

import { HrWelcomePage } from './HrWelcomePage';

/** WelcomeStepCard renders a react-router <Link>, so a Router must be in context. */
const renderPage = () => render(<MemoryRouter><HrWelcomePage /></MemoryRouter>);

/** Stub the auth store: `email` decides which landing renders. */
function signedInAs(email: string) {
  mockGetAuthItem.mockImplementation((k: string) =>
    k === 'relopass_email' ? email : k === 'relopass_user_id' ? 'u-1' : null,
  );
}

beforeEach(() => {
  mockNavigate.mockReset();
  mockGetAuthItem.mockReset();
});
afterEach(cleanup);

describe('HrWelcomePage — test-drive HR', () => {
  it('leads with the case, not the company-setup wizard', () => {
    signedInAs('hr-a1b2@probe.test');
    renderPage();
    expect(screen.getByRole('heading', { name: /open your first relocation case/i })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /set up your company workspace/i })).toBeNull();
  });

  it('the case CTA goes straight to the one real case form', () => {
    signedInAs('hr-a1b2@probe.test');
    renderPage();
    fireEvent.click(screen.getByTestId('hr-welcome-create-case'));
    // The ?new=1 deep link AIQ-1568 added — the form is local state, so this is the seam.
    expect(mockNavigate).toHaveBeenCalledWith('/hr/dashboard?new=1');
  });

  it('keeps the setup steps — demoted, not removed', () => {
    // A tester who wants the full HR experience must still have every step.
    signedInAs('hr-a1b2@probe.test');
    renderPage();
    expect(screen.getByText(/configure your company/i)).toBeInTheDocument();
    expect(screen.getByText(/build your relocation policy/i)).toBeInTheDocument();
    expect(screen.getByText(/curate your provider list/i)).toBeInTheDocument();
    expect(screen.getByText(/optional — the full hr setup/i)).toBeInTheDocument();
  });

  it('treats the e2e runner domain as a test account too', () => {
    signedInAs('hr_run_1784@testco.com');
    renderPage();
    expect(screen.getByRole('heading', { name: /open your first relocation case/i })).toBeInTheDocument();
  });
});

describe('HrWelcomePage — real HR', () => {
  it('is unchanged: company setup still leads', () => {
    // The guard is narrow on purpose. A real HR SHOULD configure their company first.
    signedInAs('marie.dupont@acme-corp.com');
    renderPage();
    expect(screen.getByRole('heading', { name: /set up your company workspace/i })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /open your first relocation case/i })).toBeNull();
    expect(screen.queryByTestId('hr-welcome-create-case')).toBeNull();
  });

  it('no email (unknown session) falls back to the real-HR landing', () => {
    signedInAs('');
    renderPage();
    expect(screen.getByRole('heading', { name: /set up your company workspace/i })).toBeInTheDocument();
  });
});
