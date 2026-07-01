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
    employees_invited: false,
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
        employees_invited: false,
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
