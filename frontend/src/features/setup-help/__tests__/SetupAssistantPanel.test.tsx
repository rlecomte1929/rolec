/**
 * Tests for SetupAssistantPanel.
 *
 * api/setupAssistant is mocked to avoid the jsdom supabase-import trap
 * (per existing patterns: see hrPolicyAssistantPanel.test.tsx which mocks
 * api/client; here we mock api/setupAssistant directly).
 *
 * react-router-dom is mocked so useNavigate works in jsdom.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom/vitest';
import { SetupAssistantPanel } from '../SetupAssistantPanel';
import { SetupAssistantDrawer } from '../SetupAssistantDrawer';
import type { SetupStatus, SetupAssistantAnswer } from '../../../api/setupAssistant';

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockNavigate = vi.fn();

vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}));

const mockGetSetupStatus = vi.fn<[], Promise<SetupStatus>>();
const mockAskSetupAssistant = vi.fn<[string], Promise<SetupAssistantAnswer>>();

vi.mock('../../../api/setupAssistant', () => ({
  getSetupStatus: (...args: unknown[]) => mockGetSetupStatus(...(args as [])),
  askSetupAssistant: (...args: unknown[]) =>
    mockAskSetupAssistant(...(args as [string])),
}));

// ── Fixtures ─────────────────────────────────────────────────────────────────

function baseStatus(overrides: Partial<SetupStatus> = {}): SetupStatus {
  return {
    company_profile_complete: true,
    policy_published: false,
    cases_count: 0,
    // employees_invited is a count (int), not a boolean — the panel treats
    // > 0 as done. Use 0 for pending, a positive number for done.
    employees_invited: 0,
    first_case_id: null,
    next_step: { label: 'Publish your first policy', route: '/hr/policy' },
    ...overrides,
  };
}

function baseAnswer(overrides: Partial<SetupAssistantAnswer> = {}): SetupAssistantAnswer {
  return {
    answer: 'Go to HR > Policy to publish your first policy.',
    next_step: { label: 'Go to Policy Builder', route: '/hr/policy' },
    cited_topics: ['policy'],
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('SetupAssistantPanel', () => {
  it('renders setup-progress summary from getSetupStatus', async () => {
    mockGetSetupStatus.mockResolvedValue(
      baseStatus({
        company_profile_complete: true,
        policy_published: false,
        cases_count: 0,
        employees_invited: 0,
      })
    );
    mockAskSetupAssistant.mockResolvedValue(baseAnswer());

    render(<SetupAssistantPanel />);

    // Checklist items appear
    await waitFor(() => {
      expect(screen.getByText('Company profile')).toBeInTheDocument();
    });
    expect(screen.getByText('Policy published')).toBeInTheDocument();
    expect(screen.getByText('First relocation case')).toBeInTheDocument();
    expect(screen.getByText('Employee invited')).toBeInTheDocument();

    // "Pending" badge for unpublished policy
    const pendingItems = screen.getAllByText('Pending');
    expect(pendingItems.length).toBeGreaterThan(0);

    // Next step hint
    expect(screen.getByText(/publish your first policy/i)).toBeInTheDocument();
  });

  it('submits a question, renders answer and next-step button, clicking navigates', async () => {
    mockGetSetupStatus.mockResolvedValue(baseStatus());
    mockAskSetupAssistant.mockResolvedValue(
      baseAnswer({
        answer: 'Go to HR > Policy to publish.',
        next_step: { label: 'Go to Policy Builder', route: '/hr/policy' },
      })
    );

    const user = userEvent.setup();
    render(<SetupAssistantPanel />);

    // Wait for status to load so we don't hit a stale state
    await waitFor(() => expect(screen.getByText('Policy published')).toBeInTheDocument());

    await user.type(
      screen.getByPlaceholderText(/how do i publish/i),
      'How do I publish a policy?'
    );
    await user.click(screen.getByRole('button', { name: /^ask$/i }));

    // askSetupAssistant called with the question
    await waitFor(() =>
      expect(mockAskSetupAssistant).toHaveBeenCalledWith('How do I publish a policy?')
    );

    // Answer text rendered
    expect(await screen.findByText(/go to hr > policy to publish/i)).toBeInTheDocument();

    // Next-step button rendered
    const nextBtn = await screen.findByTestId('setup-next-step-btn');
    expect(nextBtn).toBeInTheDocument();
    expect(nextBtn).toHaveTextContent('Go to Policy Builder');

    // Clicking calls navigate with the route
    await user.click(nextBtn);
    expect(mockNavigate).toHaveBeenCalledWith('/hr/policy');
  });

  it('hides next-step button when route is null', async () => {
    mockGetSetupStatus.mockResolvedValue(baseStatus());
    mockAskSetupAssistant.mockResolvedValue(
      baseAnswer({
        answer: 'You are all set!',
        next_step: { label: '', route: null },
      })
    );

    const user = userEvent.setup();
    render(<SetupAssistantPanel />);

    await waitFor(() => expect(screen.getByText('Policy published')).toBeInTheDocument());

    await user.type(screen.getByPlaceholderText(/how do i publish/i), 'Am I done?');
    await user.click(screen.getByRole('button', { name: /^ask$/i }));

    await screen.findByText(/you are all set/i);
    expect(screen.queryByTestId('setup-next-step-btn')).not.toBeInTheDocument();
  });

  it('treats employees_invited > 0 (int) as done and 0 as pending', async () => {
    // employees_invited is an int count from the backend; the panel maps > 0 → done.
    mockGetSetupStatus.mockResolvedValue(
      baseStatus({
        company_profile_complete: true,
        policy_published: true,
        cases_count: 1,
        employees_invited: 2,
      })
    );
    mockAskSetupAssistant.mockResolvedValue(baseAnswer());

    render(<SetupAssistantPanel />);

    // All steps done — no "Pending" badge at all
    await waitFor(() => expect(screen.getByText('Employee invited')).toBeInTheDocument());
    expect(screen.queryByText('Pending')).not.toBeInTheDocument();

    cleanup();
    vi.clearAllMocks();

    // Re-render with 0 employees invited → still pending
    mockGetSetupStatus.mockResolvedValue(
      baseStatus({ employees_invited: 0 })
    );
    render(<SetupAssistantPanel />);
    await waitFor(() => expect(screen.getByText('Employee invited')).toBeInTheDocument());
    // At least one "Pending" badge expected
    expect(screen.getAllByText('Pending').length).toBeGreaterThan(0);
  });

  it('shows an error message when askSetupAssistant rejects', async () => {
    mockGetSetupStatus.mockResolvedValue(baseStatus());
    mockAskSetupAssistant.mockRejectedValue(
      new Error('Network error')
    );

    const user = userEvent.setup();
    render(<SetupAssistantPanel />);

    await waitFor(() => expect(screen.getByText('Policy published')).toBeInTheDocument());

    await user.type(screen.getByPlaceholderText(/how do i publish/i), 'Help!');
    await user.click(screen.getByRole('button', { name: /^ask$/i }));

    // Error message shown (Alert renders with role="alert")
    const errorEl = await screen.findByRole('alert');
    expect(errorEl).toBeInTheDocument();
    expect(errorEl).toHaveTextContent('Network error');
  });
});

describe('SetupAssistantDrawer', () => {
  it('renders nothing when closed', () => {
    mockGetSetupStatus.mockResolvedValue(baseStatus());
    render(
      <SetupAssistantDrawer open={false} onOpenChange={vi.fn()} />
    );
    expect(screen.queryByTestId('setup-assistant-drawer')).not.toBeInTheDocument();
  });

  it('renders a fixed-position dialog panel when open', async () => {
    mockGetSetupStatus.mockResolvedValue(baseStatus());

    render(
      <SetupAssistantDrawer open onOpenChange={vi.fn()} />
    );

    const panel = screen.getByTestId('setup-assistant-drawer');
    expect(panel).toBeInTheDocument();

    // The panel must have `fixed` in its className so it overlays content
    // on all breakpoints (not in-flow like the docked column).
    expect(panel.className).toContain('fixed');

    // z-50 ensures it renders above other content
    expect(panel.className).toContain('z-50');

    // It must be a dialog with an accessible label
    expect(panel).toHaveAttribute('role', 'dialog');
    expect(panel).toHaveAttribute('aria-modal', 'true');
    expect(panel).toHaveAttribute('aria-labelledby', 'setup-assistant-drawer-title');
  });

  it('calls onOpenChange(false) when the Close button is clicked', async () => {
    mockGetSetupStatus.mockResolvedValue(baseStatus());
    const onOpenChange = vi.fn();

    const user = userEvent.setup();
    render(<SetupAssistantDrawer open onOpenChange={onOpenChange} />);

    // "Close" is the exact aria-label on the X button; "Close panel" is the backdrop.
    await user.click(screen.getByRole('button', { name: /^close$/i }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
