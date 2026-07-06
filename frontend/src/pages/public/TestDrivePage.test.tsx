import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// Mock the network client (also keeps the test off client.ts's supabase import chain).
vi.mock('../../api/testDrive', () => ({ provisionTestDrive: vi.fn(), recordTestDriveEvent: vi.fn() }));
// The marketing barrel transitively imports api/supabase, whose createClient throws
// in jsdom when VITE_SUPABASE_* are unset — neutralise it (known vitest trap).
vi.mock('../../api/supabase', () => ({ supabase: { functions: { invoke: vi.fn() } } }));
// Passthrough layout — avoids pulling PublicHeader/Footer providers into the unit test.
vi.mock('../../components/public', () => ({
  PublicLayout: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

import { provisionTestDrive } from '../../api/testDrive';
import { TestDrivePage } from './TestDrivePage';

// jsdom has no matchMedia; the marketing FadeIn reads it on mount.
if (!window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}

const mockProvision = provisionTestDrive as unknown as ReturnType<typeof vi.fn>;

function renderAt(search: string) {
  return render(
    <MemoryRouter initialEntries={[`/test-drive${search}`]}>
      <TestDrivePage />
    </MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('TestDrivePage', () => {
  it('renders the hero + corridor label for a Tier-A corridor, no early-coverage note', () => {
    renderAt('?corridor=FR_NO&token=t');
    expect(
      screen.getByRole('heading', { name: /Run one relocation, end to end/i }),
    ).toBeInTheDocument();
    expect(screen.getAllByText(/Paris → Oslo/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/early coverage/i)).not.toBeInTheDocument();
  });

  it('shows the Tier-B early-coverage note only for a Tier-B corridor', () => {
    renderAt('?corridor=GB_US&token=t');
    expect(screen.getAllByText(/London → New York/).length).toBeGreaterThan(0);
    expect(screen.getByText(/early coverage/i)).toBeInTheDocument();
  });

  it('falls back to the default corridor for an unknown token', () => {
    renderAt('?corridor=ZZ_ZZ&token=t');
    expect(screen.getAllByText(/Paris → Oslo/).length).toBeGreaterThan(0);
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
    fireEvent.click(screen.getByRole('button', { name: /start the test/i }));

    await waitFor(() => expect(mockProvision).toHaveBeenCalledTimes(1));
    expect(mockProvision).toHaveBeenCalledWith({
      first_name: 'Alex',
      corridor_id: 'GB_US',
      tester_segment: 'prospect',
      invite_token: 'invite-xyz',
    });
    // The card shows the login email (login accepts email or username).
    expect(await screen.findByText('hr-alex@probe.test')).toBeInTheDocument();
    expect(screen.getByText('emp-alex@probe.test')).toBeInTheDocument();
  });

  it('surfaces the API error and does not show credentials', async () => {
    mockProvision.mockResolvedValue({ ok: false, error: 'This invite link is invalid or has expired.' });
    renderAt('?corridor=FR_NO');

    fireEvent.change(screen.getByLabelText(/first name/i), { target: { value: 'Sam' } });
    fireEvent.click(screen.getByRole('button', { name: /start the test/i }));

    expect(await screen.findByText(/invite link is invalid/i)).toBeInTheDocument();
    expect(screen.queryByText(/Your two test logins/i)).not.toBeInTheDocument();
  });
});
