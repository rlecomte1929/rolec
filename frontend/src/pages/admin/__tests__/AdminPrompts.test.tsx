/**
 * AdminPrompts — Parker Step D.
 *
 * Renders the prompt registry table from a mocked API and verifies that
 * clicking "Promote" calls promptsAPI.promote with the right version id.
 */
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { render, screen, waitFor, fireEvent, cleanup } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// AdminLayout pulls in nav chrome we don't need for these assertions.
vi.mock('../AdminLayout', () => ({
  AdminLayout: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock('../../../api/client', () => ({
  promptsAPI: {
    list: vi.fn(),
    promote: vi.fn().mockResolvedValue({ status: 'prod' }),
    setCanaryShare: vi.fn().mockResolvedValue({ canary_share: 0.1 }),
    winRates: vi.fn().mockResolvedValue({}),
  },
}));

import { AdminPrompts } from '../AdminPrompts';
import { promptsAPI } from '../../../api/client';

const ROWS = [
  {
    id: 'v1-id',
    task_key: 'policy_extraction',
    version: 1,
    system_prompt: 'SYS',
    user_template: null,
    model_name: 'claude-sonnet-4-6',
    temperature: 0,
    max_tokens: 4096,
    status: 'prod',
  },
  {
    id: 'v2-id',
    task_key: 'policy_extraction',
    version: 2,
    system_prompt: 'SYS2',
    user_template: null,
    model_name: 'claude-sonnet-4-6',
    temperature: 0,
    max_tokens: 4096,
    status: 'draft',
  },
];

describe('AdminPrompts', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (promptsAPI.list as ReturnType<typeof vi.fn>).mockResolvedValue(ROWS);
    (promptsAPI.promote as ReturnType<typeof vi.fn>).mockResolvedValue({ status: 'prod' });
    (promptsAPI.winRates as ReturnType<typeof vi.fn>).mockResolvedValue({
      'v1-id': {
        version_id: 'v1-id',
        approvals: 8,
        total: 10,
        win_rate: 0.8,
        ci_low: 0.49,
        ci_high: 0.94,
      },
    });
  });

  afterEach(() => cleanup());

  it('renders the task table from the API', async () => {
    render(<AdminPrompts />);
    await waitFor(() => expect(promptsAPI.list).toHaveBeenCalled());
    expect(await screen.findByText('policy_extraction')).toBeInTheDocument();
    expect(screen.getByText('v1')).toBeInTheDocument();
    expect(screen.getByText('v2')).toBeInTheDocument();
  });

  it('renders per-version win rates from the API', async () => {
    render(<AdminPrompts />);
    await waitFor(() => expect(promptsAPI.winRates).toHaveBeenCalledWith('policy_extraction'));
    expect(await screen.findByText('80% (8/10)')).toBeInTheDocument();
  });

  it('promotes a non-prod version to prod on click', async () => {
    render(<AdminPrompts />);
    const promoteBtn = await screen.findByRole('button', { name: 'Promote' });
    fireEvent.click(promoteBtn);
    await waitFor(() =>
      expect(promptsAPI.promote).toHaveBeenCalledWith('v2-id', 'prod')
    );
  });
});
