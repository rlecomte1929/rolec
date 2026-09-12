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

/** Consecutive heading levels must not jump by more than 1 (WCAG 1.3.1). */
function headingLevels(container: HTMLElement): number[] {
  return Array.from(container.querySelectorAll('h1,h2,h3,h4,h5,h6')).map((h) =>
    Number(h.tagName[1]),
  );
}

function expectNoSkippedHeadingLevel(container: HTMLElement) {
  const levels = headingLevels(container);
  expect(levels[0], 'page must open with its h1').toBe(1);
  for (let i = 1; i < levels.length; i += 1) {
    expect(
      levels[i]! - levels[i - 1]!,
      `heading ${i} (h${levels[i]}) skips a level after h${levels[i - 1]}: ${levels.join(' -> ')}`,
    ).toBeLessThanOrEqual(1);
  }
}

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
    fireEvent.click(screen.getByRole('button', { name: /create your first case/i }));
    // The ?new=1 deep link AIQ-1568 added — the form is local state, so this is the seam.
    expect(mockNavigate).toHaveBeenCalledWith('/hr/dashboard?new=1');
  });

  it('keeps the setup steps — demoted, not removed', () => {
    // A tester who wants the full HR experience must still have every step.
    signedInAs('hr-a1b2@probe.test');
    renderPage();
    expect(screen.getByText(/configure your company/i)).toBeInTheDocument();
    expect(screen.getByText(/build your relocation policy/i)).toBeInTheDocument();
    expect(screen.getByText(/curate your service providers/i)).toBeInTheDocument();
    expect(screen.getByText(/optional — the full hr setup/i)).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: /get started/i })[2]).toHaveAttribute(
      'href',
      '/hr/service-providers?tab=vendor',
    );
  });

  it('nests setup cards as h3 under the optional-setup h2', () => {
    signedInAs('hr-a1b2@probe.test');
    const { container } = renderPage();
    expect(screen.getByRole('heading', { level: 1, name: /open your first relocation case/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2, name: /optional — the full hr setup/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 3, name: /configure your company/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 3, name: /build your relocation policy/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 3, name: /curate your service providers/i })).toBeInTheDocument();
    expectNoSkippedHeadingLevel(container);
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
    expect(screen.queryByRole('button', { name: /create your first case/i })).toBeNull();
    expect(screen.getByRole('button', { name: /open the mobility command center/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^open cases$/i })).toBeInTheDocument();
  });

  it('shows a pending state within the click of an exit', () => {
    signedInAs('marie.dupont@acme-corp.com');
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: /open the mobility command center/i }));
    expect(screen.getByRole('progressbar', { name: /opening page/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /opening/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /^open cases$/i })).toBeDisabled();
  });

  it('sends step 3 to Service Providers vendor curation, not the legacy grid', () => {
    signedInAs('marie.dupont@acme-corp.com');
    renderPage();
    const links = screen.getAllByRole('link');
    expect(links[2]).toHaveAttribute('href', '/hr/service-providers?tab=vendor');
    expect(links[2]).toHaveAccessibleName(/service providers/i);
  });

  it('gives each setup link a unique name that matches the destination H1', () => {
    signedInAs('marie.dupont@acme-corp.com');
    renderPage();
    expect(screen.getByRole('link', { name: 'Open company profile →' })).toHaveAttribute(
      'href',
      '/hr/company-profile',
    );
    expect(screen.getByRole('link', { name: 'Open policy →' })).toHaveAttribute('href', '/hr/policy');
    expect(screen.getByRole('link', { name: 'Open service providers →' })).toHaveAttribute(
      'href',
      '/hr/service-providers?tab=vendor',
    );
    expect(screen.queryAllByRole('link', { name: /get started/i })).toHaveLength(0);
  });

  it('places the first-case CTA beside the steps from 960px up', () => {
    signedInAs('marie.dupont@acme-corp.com');
    renderPage();
    const layout = screen.getByTestId('hr-welcome-layout');
    expect(layout.className).toContain('grid-cols-1');
    expect(layout.className).toContain('min-[960px]:grid-cols-');
    expect(layout.querySelector('aside')).not.toBeNull();
    expect(screen.getByRole('heading', { name: /ready to open your first case/i })).toBeInTheDocument();
  });

  it('emphasizes the Start here card beyond the chip', () => {
    signedInAs('marie.dupont@acme-corp.com');
    const { container } = renderPage();
    expect(container.querySelector('.ring-accent-500')).not.toBeNull();
    expect(screen.getByRole('link', { name: 'Open company profile →' }).className).toContain('bg-navy-800');
    expect(screen.getByRole('link', { name: 'Open policy →' }).className).not.toContain('bg-navy-800');
  });

  it('puts an h2 above the setup cards so h3 titles do not skip a level', () => {
    signedInAs('marie.dupont@acme-corp.com');
    const { container } = renderPage();
    expect(screen.getByRole('heading', { level: 1, name: /set up your company workspace/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2, name: /how it works/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 3, name: /configure your company/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 3, name: /build your relocation policy/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 3, name: /curate your service providers/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2, name: /ready to open your first case/i })).toBeInTheDocument();
    expectNoSkippedHeadingLevel(container);
  });

  it('no email (unknown session) falls back to the real-HR landing', () => {
    signedInAs('');
    renderPage();
    expect(screen.getByRole('heading', { name: /set up your company workspace/i })).toBeInTheDocument();
  });
});
